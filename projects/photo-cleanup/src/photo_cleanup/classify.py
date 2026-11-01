"""把 walker.scan_directory() 收集到的事实，套用四条规则并按优先级仲裁。

优先级（AC-11）：完全重复 > 相似 > 短视频 > 截图标记。
每个文件最终只有一个 category/action，但 hits 列表里保留了全部命中的规则
（含当时的具体数值），方便以后做反馈调参（M4）。
"""

from __future__ import annotations

import os
from collections import defaultdict

from . import naming
from .config import Config
from .hashing import UnionFind, cluster_similar, phash_distance
from .models import (
    CATEGORY_PRIORITY,
    Action,
    Category,
    DuplicateGroup,
    FileKind,
    FileRecord,
    Hit,
    ScanResult,
)
from .screenshot_rules import is_screenshot


def classify(config: Config, files: list[FileRecord], errors: list[str]) -> ScanResult:
    media_files = [f for f in files if f.kind in (FileKind.IMAGE, FileKind.VIDEO)]
    records_by_path = {f.path: f for f in media_files}

    exact_groups = _build_exact_duplicate_groups(media_files)
    _apply_exact_duplicate_hits(exact_groups, records_by_path)

    image_files = [f for f in media_files if f.kind == FileKind.IMAGE]

    # 截图是一个独立判断，不管最终展示的类别是什么，都要先算出来，
    # 因为相似组的保留规则需要知道"组里谁是截图"。
    screenshot_flags: dict[str, tuple[bool, str]] = {}
    for f in image_files:
        flag, reason = is_screenshot(f.width, f.height, f.has_camera_exif)
        screenshot_flags[f.path] = (flag, reason)

    similar_groups = _build_similar_groups(config, image_files, screenshot_flags)
    _apply_similar_hits(similar_groups, records_by_path)

    _apply_short_video_hits(config, media_files)
    _apply_screenshot_hits(image_files, screenshot_flags)

    exact_by_id = {g.group_id: g for g in exact_groups}
    similar_by_id = {g.group_id: g for g in similar_groups}
    for f in media_files:
        _resolve_priority(f, exact_by_id, similar_by_id)

    _propagate_to_live_photo_companions(media_files)

    return ScanResult(
        config=config,
        files=files,
        exact_groups=exact_groups,
        similar_groups=similar_groups,
        errors=errors,
    )


def _build_exact_duplicate_groups(media_files: list[FileRecord]) -> list[DuplicateGroup]:
    by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    for f in media_files:
        if f.sha256:
            by_hash[f.sha256].append(f)

    groups: list[DuplicateGroup] = []
    idx = 0
    for members in by_hash.values():
        if len(members) < 2:
            continue
        idx += 1
        group_id = f"dup-{idx:04d}"
        names = [os.path.basename(m.path) for m in members]
        keep_name = naming.pick_preferred_by_name(names)
        keep_path = next(m.path for m in members if os.path.basename(m.path) == keep_name)
        groups.append(
            DuplicateGroup(
                group_id=group_id,
                kind="exact",
                member_paths=sorted(m.path for m in members),
                keep_path=keep_path,
                reason_for_keep="文件名不带副本后缀（如空格+括号数字、短横线+数字、"
                "macOS 常见的空格+数字如' 2'）优先；都带或都不带副本后缀时取文件名排序第一个",
            )
        )
    groups.sort(key=lambda g: g.group_id)
    return groups


def _apply_exact_duplicate_hits(groups: list[DuplicateGroup], records_by_path: dict[str, FileRecord]) -> None:
    for g in groups:
        for path in g.member_paths:
            rec = records_by_path.get(path)
            if rec is None:
                continue
            reason = (
                f"与组内其余 {len(g.member_paths) - 1} 个文件字节完全相同（组 {g.group_id}），"
                f"组内保留 {os.path.basename(g.keep_path)}"
            )
            rec.hits.append(
                Hit(
                    category=Category.EXACT_DUPLICATE,
                    reason=reason,
                    group_id=g.group_id,
                    numeric_evidence={"group_size": len(g.member_paths)},
                )
            )


def _build_similar_groups(
    config: Config,
    image_files: list[FileRecord],
    screenshot_flags: dict[str, tuple[bool, str]],
) -> list[DuplicateGroup]:
    if not image_files:
        return []

    hash_variants = [(f.phash_full, f.phash_trimmed) for f in image_files]
    valid_idx = [i for i, hv in enumerate(hash_variants) if hv[0] is not None and hv[1] is not None]
    # 有图片解析失败、没拿到 phash 的，不参与相似聚类（失败原因已记录在 errors 里）

    sub_variants = [hash_variants[i] for i in valid_idx]
    phash_groups = cluster_similar(sub_variants, config.similarity_threshold)
    local_to_global = {local: valid_idx[local] for local in range(len(valid_idx))}

    n = len(image_files)
    uf = UnionFind(n)
    for g in phash_groups:
        g_global = [local_to_global[i] for i in g]
        first = g_global[0]
        for other in g_global[1:]:
            uf.union(first, other)

    # 文件名配对的编辑/裁剪版（如 IMG_1234 / IMG_E1234）：无论 phash 距离多少，强制并入同一组
    stem_to_index: dict[tuple[str, str], int] = {}
    for i, f in enumerate(image_files):
        key = (os.path.dirname(f.path), naming.stem(os.path.basename(f.path)).lower())
        stem_to_index[key] = i

    for i, f in enumerate(image_files):
        counterpart_stem = naming.edited_counterpart_stem(os.path.basename(f.path))
        if counterpart_stem is None:
            continue
        key = (os.path.dirname(f.path), counterpart_stem.lower())
        j = stem_to_index.get(key)
        if j is not None and j != i:
            uf.union(i, j)

    raw_groups = uf.groups()
    index_groups = [sorted(members) for members in raw_groups.values() if len(members) >= 2]

    groups: list[DuplicateGroup] = []
    for idx, members_idx in enumerate(sorted(index_groups, key=lambda g: g[0]), start=1):
        members = [image_files[i] for i in members_idx]
        group_id = f"sim-{idx:04d}"
        keep, reason = _pick_similar_keep(members, screenshot_flags)
        max_dist = _max_group_distance(members, hash_variants, image_files)
        groups.append(
            DuplicateGroup(
                group_id=group_id,
                kind="similar",
                member_paths=[m.path for m in members],
                keep_path=keep.path,
                reason_for_keep=reason,
                max_pairwise_distance=max_dist,
            )
        )
    return groups


def _max_group_distance(
    members: list[FileRecord],
    hash_variants: list[tuple],
    image_files: list[FileRecord],
) -> int | None:
    dists = []
    for a_i in range(len(members)):
        for b_i in range(a_i + 1, len(members)):
            a, b = members[a_i], members[b_i]
            if a.phash_full is None or b.phash_full is None:
                continue
            dists.append(phash_distance((a.phash_full, a.phash_trimmed), (b.phash_full, b.phash_trimmed)))
    return max(dists) if dists else None


def _pick_similar_keep(
    members: list[FileRecord], screenshot_flags: dict[str, tuple[bool, str]]
) -> tuple[FileRecord, str]:
    edited_candidates = [m for m in members if naming.is_edited_version(os.path.basename(m.path))]
    if edited_candidates:
        keep = max(edited_candidates, key=lambda r: ((r.width or 0) * (r.height or 0), r.size))
        return keep, "组内存在文件名配对的编辑/裁剪版（如 IMG_E1234），按规则保留编辑版"

    non_screenshots = [m for m in members if not screenshot_flags.get(m.path, (False, ""))[0]]
    if non_screenshots:
        keep = max(non_screenshots, key=lambda r: ((r.width or 0) * (r.height or 0), r.size))
        return keep, "组内无编辑版，但有非截图版本，按规则保留非截图版本（像素数最多，相同则文件更大）"

    keep = max(members, key=lambda r: ((r.width or 0) * (r.height or 0), r.size))
    return keep, "组内无编辑版、全部是截图，按规则保留像素数最多（相同则文件更大）的一张"


def _apply_similar_hits(groups: list[DuplicateGroup], records_by_path: dict[str, FileRecord]) -> None:
    for g in groups:
        keep_rec = records_by_path.get(g.keep_path)
        for path in g.member_paths:
            rec = records_by_path.get(path)
            if rec is None:
                continue
            dist = None
            if rec is not keep_rec and keep_rec is not None and rec.phash_full is not None and keep_rec.phash_full is not None:
                dist = phash_distance(
                    (rec.phash_full, rec.phash_trimmed), (keep_rec.phash_full, keep_rec.phash_trimmed)
                )
            reason = f"相似组 {g.group_id}（{len(g.member_paths)} 个文件），组内保留 {os.path.basename(g.keep_path)}"
            if dist is not None:
                reason += f"，与组内保留文件的感知哈希距离 = {dist}"
            rec.hits.append(
                Hit(
                    category=Category.SIMILAR,
                    reason=reason,
                    group_id=g.group_id,
                    numeric_evidence={"phash_distance": dist} if dist is not None else {},
                )
            )


def _apply_short_video_hits(config: Config, media_files: list[FileRecord]) -> None:
    for f in media_files:
        if f.kind != FileKind.VIDEO:
            continue
        if f.is_live_photo_companion:
            continue  # Live Photo 伴生文件不参与短视频判断（AC-9）
        if f.duration_seconds is None:
            continue
        if f.duration_seconds < config.video_threshold_seconds:
            f.hits.append(
                Hit(
                    category=Category.SHORT_VIDEO,
                    reason=f"视频时长 {f.duration_seconds:.2f} 秒 < 阈值 {config.video_threshold_seconds} 秒",
                    numeric_evidence={
                        "duration_seconds": round(f.duration_seconds, 3),
                        "threshold_seconds": config.video_threshold_seconds,
                    },
                )
            )


def _apply_screenshot_hits(image_files: list[FileRecord], screenshot_flags: dict[str, tuple[bool, str]]) -> None:
    for f in image_files:
        flag, reason = screenshot_flags.get(f.path, (False, ""))
        if flag:
            f.hits.append(Hit(category=Category.SCREENSHOT, reason=reason))


def _resolve_priority(
    f: FileRecord,
    exact_by_id: dict[str, DuplicateGroup],
    similar_by_id: dict[str, DuplicateGroup],
) -> None:
    if not f.hits:
        f.final_category = Category.NONE
        f.final_action = Action.NO_ACTION
        f.final_reason = ""
        return

    best_hit = min(f.hits, key=lambda h: CATEGORY_PRIORITY[h.category])
    f.final_category = best_hit.category
    f.final_reason = best_hit.reason
    f.group_id = best_hit.group_id

    if best_hit.category == Category.EXACT_DUPLICATE:
        g = exact_by_id.get(best_hit.group_id)
        is_keep = bool(g and g.keep_path == f.path)
        f.final_action = Action.KEEP_IN_GROUP if is_keep else Action.DELETE_TO_TRASH
    elif best_hit.category == Category.SIMILAR:
        g = similar_by_id.get(best_hit.group_id)
        is_keep = bool(g and g.keep_path == f.path)
        f.final_action = Action.KEEP_IN_GROUP if is_keep else Action.MOVE_TO_REVIEW
    elif best_hit.category == Category.SHORT_VIDEO:
        f.final_action = Action.MOVE_TO_REVIEW
    elif best_hit.category == Category.SCREENSHOT:
        f.final_action = Action.MARK_ONLY
    else:
        f.final_action = Action.NO_ACTION


def _propagate_to_live_photo_companions(media_files: list[FileRecord]) -> None:
    """图片命中规则时，同名 .MOV 伴生文件在报告里跟着展示同样的分类/动作，
    方便 M2 执行时知道要把伴生文件一起处理（需求「Live Photo 支持」）。
    """
    by_path = {f.path: f for f in media_files}
    for f in media_files:
        if f.kind != FileKind.IMAGE or not f.live_photo_companion:
            continue
        companion = by_path.get(f.live_photo_companion)
        if companion is None or f.final_category == Category.NONE:
            continue
        if companion.hits:
            continue  # 伴生文件自己已经有命中（极少见），不覆盖
        companion.final_category = f.final_category
        companion.final_action = f.final_action
        companion.final_reason = f"Live Photo 伴生文件，随图片 {os.path.basename(f.path)} 一起处理：{f.final_reason}"
        companion.group_id = f.group_id
