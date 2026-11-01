"""生成报告（JSON + Markdown 两份）。

JSON 是给 agent/以后 M4 反馈调参用的机器可读版本；Markdown 是给 Aimee 看的人读版本。
两份内容来自同一份数据，保证不会出现"人读的和机器读的不一致"。

AC-2 要求"报告末尾的各类别汇总数与明细行数一致"：这里汇总数直接从同一份
明细列表（per_file_rows）里数出来，不是另算一遍，从结构上保证一致。
"""

from __future__ import annotations

import json
import os
from datetime import datetime

from .models import Category, FileKind, ScanResult


def _file_row(rec) -> dict:
    return {
        "原路径": rec.path,
        "相对路径": rec.rel_path,
        "类别": rec.final_category.value,
        "命中原因": rec.final_reason,
        "动作": rec.final_action.value,
        "组号": rec.group_id,
        "数值证据": numeric_evidence_for(rec),
    }


def numeric_evidence_for(rec) -> dict:
    """命中时的具体数值（相似组：感知哈希距离；短视频：时长秒数）。
    executor.py 的操作记录（M2）也用这个函数，保证报告和操作记录里的数值证据来自同一处逻辑。
    """
    for h in rec.hits:
        if h.category == rec.final_category:
            return h.numeric_evidence
    return {}


def build_report(result: ScanResult) -> dict:
    config = result.config
    hit_files = [f for f in result.files if f.final_category != Category.NONE]
    hit_files.sort(key=lambda f: f.rel_path)

    per_file_rows = [_file_row(f) for f in hit_files]

    summary = {cat.value: 0 for cat in Category if cat != Category.NONE}
    for f in hit_files:
        summary[f.final_category.value] += 1

    total_files = len(result.files)
    other_files = sum(1 for f in result.files if f.kind == FileKind.OTHER)
    image_files = sum(1 for f in result.files if f.kind == FileKind.IMAGE)
    video_files = sum(1 for f in result.files if f.kind == FileKind.VIDEO)
    live_photo_pairs = sum(1 for f in result.files if f.kind.value == "video" and f.is_live_photo_companion)

    report = {
        "生成时间": datetime.now().isoformat(timespec="seconds"),
        "输入目录": os.path.abspath(config.input_dir),
        "模式": config.mode,
        "参数": {
            "短视频阈值秒数": config.video_threshold_seconds,
            "相似度距离阈值": config.similarity_threshold,
            "phash_size": config.phash_size,
        },
        "文件总数": total_files,
        "其中图片": image_files,
        "其中视频": video_files,
        "其中Live_Photo伴生MOV": live_photo_pairs,
        "其中非图片非视频(不处理)": other_files,
        "汇总": summary,
        "汇总数与明细行数一致": sum(summary.values()) == len(per_file_rows),
        "完全重复组": [_group_row(g) for g in result.exact_groups],
        "相似组": [_group_row(g) for g in result.similar_groups],
        "命中文件明细": per_file_rows,
        "运行错误": result.errors,
    }
    return report


def _group_row(g) -> dict:
    row = {
        "组号": g.group_id,
        "组内文件数": len(g.member_paths),
        "组内文件": list(g.member_paths),
        "保留文件": g.keep_path,
        "保留理由": g.reason_for_keep,
    }
    if g.max_pairwise_distance is not None:
        row["组内最大感知哈希距离"] = g.max_pairwise_distance
    return row


def write_json(report: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def write_markdown(report: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines: list[str] = []
    lines.append(f"# 照片清理报告（{report['模式']} 模式）")
    lines.append("")
    lines.append(f"- 生成时间: {report['生成时间']}")
    lines.append(f"- 输入目录: {report['输入目录']}")
    lines.append(
        f"- 参数: 短视频阈值 {report['参数']['短视频阈值秒数']} 秒，"
        f"相似度距离阈值 {report['参数']['相似度距离阈值']}"
    )
    lines.append(
        f"- 文件总数 {report['文件总数']}（图片 {report['其中图片']}，视频 {report['其中视频']}，"
        f"其中 Live Photo 伴生 MOV {report['其中Live_Photo伴生MOV']}，"
        f"非图片/视频不处理 {report['其中非图片非视频(不处理)']}）"
    )
    lines.append("")
    lines.append("## 分类汇总")
    lines.append("")
    lines.append("| 类别 | 数量 |")
    lines.append("| --- | --- |")
    for cat, count in report["汇总"].items():
        lines.append(f"| {cat} | {count} |")
    lines.append("")
    lines.append(f"（汇总数与明细行数一致: {report['汇总数与明细行数一致']}）")
    lines.append("")

    if report["完全重复组"]:
        lines.append("## 完全重复组")
        lines.append("")
        for g in report["完全重复组"]:
            lines.append(f"### {g['组号']}（{g['组内文件数']} 个文件）")
            lines.append(f"- 保留: `{g['保留文件']}`")
            lines.append(f"- 理由: {g['保留理由']}")
            for p in g["组内文件"]:
                marker = "保留" if p == g["保留文件"] else "删除(废纸篓)"
                lines.append(f"  - `{p}` — {marker}")
            lines.append("")

    if report["相似组"]:
        lines.append("## 相似组")
        lines.append("")
        for g in report["相似组"]:
            extra = f"，组内最大感知哈希距离 {g['组内最大感知哈希距离']}" if "组内最大感知哈希距离" in g else ""
            lines.append(f"### {g['组号']}（{g['组内文件数']} 个文件{extra}）")
            lines.append(f"- 保留: `{g['保留文件']}`")
            lines.append(f"- 理由: {g['保留理由']}")
            for p in g["组内文件"]:
                marker = "保留" if p == g["保留文件"] else "移至待复查"
                lines.append(f"  - `{p}` — {marker}")
            lines.append("")

    lines.append("## 命中文件明细")
    lines.append("")
    lines.append("| 原路径 | 类别 | 命中原因 | 动作 | 组号 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in report["命中文件明细"]:
        lines.append(
            f"| {row['相对路径']} | {row['类别']} | {row['命中原因']} | {row['动作']} | {row['组号'] or ''} |"
        )
    lines.append("")

    if report["运行错误"]:
        lines.append("## 运行中的错误/警告")
        lines.append("")
        for e in report["运行错误"]:
            lines.append(f"- {e}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def default_report_paths(input_dir: str, report_dir: str | None) -> tuple[str, str]:
    """报告文件名里带输入目录名 + 时间戳，保证不同目录、不同次运行互不覆盖（AC-20）。"""
    input_dir = os.path.abspath(input_dir)
    base_dir_name = os.path.basename(input_dir.rstrip(os.sep)) or "root"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = report_dir or os.path.join(os.path.dirname(input_dir), "photo-cleanup-reports")
    stem = f"{base_dir_name}_{timestamp}"
    return (
        os.path.join(out_dir, f"{stem}.json"),
        os.path.join(out_dir, f"{stem}.md"),
    )
