"""逐条核对 requirements.md 的 AC-13 ~ AC-19（M2 执行模式范围）。

风格上跟 test_acceptance.py / test_tester_review.py 保持一致：用 sample_generator.py
生成的合成样本集做断言。区别是这里的测试会真正删除/移动文件（execute 模式本身的职责），
所以不能像 test_acceptance.py 那样所有测试共用同一个 session 级样本目录——每个要跑
execute 的测试都先把样本集拷贝到自己独立的临时目录，互不干扰，且方便每个测试单独断言
"执行前/执行后"的文件系统状态。

另外：execute 模式会把"完全重复"的多余文件真正移进系统回收站（macOS 的 ~/.Trash，
这是 AC-13 的字面要求，没法用别的方式假装测到），测试跑完会用 trash_test_support.cleanup_trashed
清掉自己丢进回收站的东西，不给 Aimee 的真实废纸篓留垃圾。
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trash_test_support import cleanup_trashed  # noqa: E402

from photo_cleanup.classify import classify  # noqa: E402
from photo_cleanup.config import Config  # noqa: E402
from photo_cleanup.executor import execute, revert, write_operation_log  # noqa: E402
from photo_cleanup.models import Category  # noqa: E402
from photo_cleanup.report import build_report  # noqa: E402
from photo_cleanup.walker import scan_directory  # noqa: E402

PROJECT_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
SAMPLE_GENERATOR = os.path.join(os.path.dirname(__file__), "sample_generator.py")


@pytest.fixture(scope="session")
def sample_source():
    """只生成一次（慢：要编码一堆 JPEG/HEIC/视频），后面每个测试各自拷贝一份再改动。"""
    tmp_root = tempfile.mkdtemp(prefix="photo_cleanup_m2_src_")
    photos_dir = os.path.join(tmp_root, "photos")
    proc = subprocess.run(
        [sys.executable, SAMPLE_GENERATOR, photos_dir],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"样本生成失败:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    manifest_path = os.path.join(tmp_root, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    return {"dir": photos_dir, "manifest": manifest}


def _remap(obj, old_prefix: str, new_prefix: str):
    """manifest 里记的是 sample_source 原始目录下的路径，拷贝到新目录后要整体替换前缀。"""
    if isinstance(obj, str):
        return new_prefix + obj[len(old_prefix):] if obj.startswith(old_prefix) else obj
    if isinstance(obj, list):
        return [_remap(x, old_prefix, new_prefix) for x in obj]
    if isinstance(obj, dict):
        return {k: _remap(v, old_prefix, new_prefix) for k, v in obj.items()}
    return obj


def _fresh_copy(sample_source, tmp_path):
    src_dir = sample_source["dir"]
    dst_dir = str(tmp_path / "photos")
    shutil.copytree(src_dir, dst_dir)
    manifest = _remap(sample_source["manifest"], src_dir, dst_dir)
    return dst_dir, manifest


def _run_execute(photos_dir: str, review_dir: str, **config_kwargs):
    config = Config(input_dir=photos_dir, review_dir=review_dir, **config_kwargs)
    files, errors = scan_directory(config)
    result = classify(config, files, errors)
    op_log = execute(config, result)
    return config, result, op_log


@pytest.fixture(autouse=True)
def _cleanup_trash(request):
    """每个测试把自己执行产生的操作记录注册进来，测试结束后统一清理回收站残留。"""
    logs: list[dict] = []
    request.node._op_logs = logs
    yield
    for log in logs:
        cleanup_trashed(log)


def _run_execute_tracked(request_logs, photos_dir, review_dir, **config_kwargs):
    config, result, op_log = _run_execute(photos_dir, review_dir, **config_kwargs)
    request_logs.append(op_log)
    return config, result, op_log


# ---------- AC-13: 完全重复组的多余副本（及其 Live Photo 伴生文件）进系统回收站，保留文件原地不动 ----------


def test_ac13_exact_duplicates_moved_to_trash(sample_source, tmp_path, request):
    photos_dir, manifest = _fresh_copy(sample_source, tmp_path)
    review_dir = str(tmp_path / "待复查")
    _config, _result, op_log = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)

    trashed_paths = {op["原路径"] for op in op_log["操作"] if op["动作"] == "删除(废纸篓)"}

    for group in manifest["exact_duplicate_groups"]:
        keep = group["expected_keep"]
        for p in group["files"]:
            if p == keep:
                assert os.path.exists(p), f"保留文件 {p} 应该还在原位"
            else:
                assert not os.path.exists(p), f"重复副本 {p} 应该已经从原位置移走"
                assert p in trashed_paths, f"{p} 应该出现在操作记录的「删除(废纸篓)」条目里"

    # 1 字节差异的那一对不是完全重复，不应该被当成完全重复删除/进回收站
    # （这一对的像素内容几乎一样，phash 距离很近，可能被正当地归入相似组再移到待复查——
    #  那不是这里测的内容，test_acceptance.py 的 AC-4 已经测过"不是完全重复"这一点；
    #  这里只确认它们没有被错误地送进回收站）
    p1, p2 = manifest["byte_diff_pair"]
    assert p1 not in trashed_paths
    assert p2 not in trashed_paths


# ---------- AC-14: 相似组保留文件原地不动，多余项移到「待复查/相似/<组号>/」 ----------


def test_ac14_similar_group_extras_moved_to_review_subfolder(sample_source, tmp_path, request):
    photos_dir, manifest = _fresh_copy(sample_source, tmp_path)
    review_dir = str(tmp_path / "待复查")
    _config, result, op_log = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)

    by_path = {f.path: f for f in result.files}

    for group in manifest["similar_groups"]:
        keep = group["expected_keep"]
        assert os.path.exists(keep), f"相似组保留文件 {keep} 应该还在原位"
        group_id = by_path[keep].group_id
        assert group_id, f"保留文件 {keep} 应该有 group_id"
        group_folder = os.path.join(review_dir, "相似", group_id)

        for p in group["files"]:
            if p == keep:
                continue
            assert not os.path.exists(p), f"{p} 应该已经从原位置移走"
            dest = os.path.join(group_folder, os.path.basename(p))
            assert os.path.exists(dest), f"{p} 应该出现在 {group_folder} 下"

    # 报告能对应到该组的保留文件（组号 -> 保留文件）
    report = build_report(result)
    group_rows = {row["组号"]: row["保留文件"] for row in report["相似组"]}
    for group in manifest["similar_groups"]:
        keep = group["expected_keep"]
        group_id = by_path[keep].group_id
        assert group_rows[group_id] == keep


def test_ac14_default_review_dir_is_outside_input_dir():
    """需求原文："待复查"文件夹位于输入目录之外；没传 --review-dir 时也要满足这一点。"""
    from photo_cleanup.executor import default_review_dir

    input_dir = "/tmp/some-photos-2025"
    review_dir = default_review_dir(input_dir, None)
    assert os.path.commonpath([review_dir, input_dir]) != os.path.abspath(input_dir), (
        f"默认「待复查」目录 {review_dir} 不应该嵌套在输入目录 {input_dir} 内部"
    )
    assert review_dir != input_dir


# ---------- AC-15: 短视频移到「待复查/短视频/」；相似组多余项的 Live Photo 伴生 .MOV 跟图片去同一个文件夹 ----------


def test_ac15_short_videos_moved_to_review_subfolder(sample_source, tmp_path, request):
    photos_dir, manifest = _fresh_copy(sample_source, tmp_path)
    review_dir = str(tmp_path / "待复查")
    _config, _result, op_log = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)

    short_video_folder = os.path.join(review_dir, "短视频")
    for item in manifest["short_videos"]:
        p = item["file"]
        if item["expect_marked"]:
            assert not os.path.exists(p), f"{p} 应该已经从原位置移走"
            dest = os.path.join(short_video_folder, os.path.basename(p))
            assert os.path.exists(dest), f"{p} 应该出现在 {short_video_folder} 下"
        else:
            assert os.path.exists(p), f"{p} 时长不低于阈值，不应该被移动"


def _write_random_video(path: str, duration_seconds: float, seed: int, fps: float = 30.0, size=(320, 240)) -> None:
    import cv2
    import numpy as np

    rng = np.random.RandomState(seed)
    n_frames = round(duration_seconds * fps)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(path, fourcc, fps, size)
    for _ in range(n_frames):
        frame = rng.randint(0, 255, (size[1], size[0], 3), dtype=np.uint8)
        vw.write(frame)
    vw.release()


def test_ac15_similar_group_extra_live_photo_companion_follows_image(tmp_path, request):
    """样本生成器里的 Live Photo 样本本身都没命中任何规则（不是本测试想测的场景），
    所以这里专门构造一个"相似组多余项带 Live Photo 伴生 .MOV"的最小场景，验证需求原文
    "相似组多余项若有 Live Photo 伴生 .MOV，伴生文件和图片移到同一个文件夹"。
    """
    from PIL import Image, ImageDraw
    from PIL.ExifTags import Base

    root = tmp_path / "lp_similar"
    root.mkdir()

    def exif_for(img):
        exif = img.getexif()
        exif[Base.Make] = "Apple"
        exif[Base.Model] = "iPhone 13"
        return exif

    rng = random.Random(42)
    base = Image.new("RGB", (1600, 1200), (120, 140, 160))
    draw = ImageDraw.Draw(base)
    for _ in range(8):
        x0, y0 = rng.randint(0, 1600), rng.randint(0, 1200)
        draw.rectangle([x0, y0, x0 + 80, y0 + 80], fill=(rng.randint(0, 255), 0, 0))

    orig_path = root / "IMG_0200.JPG"
    base.save(orig_path, quality=92, exif=exif_for(base))

    # 相似组的"多余项"：对同一张照片重新压缩（内容几乎相同，字节不同，不算完全重复），
    # 带一个 Live Photo 伴生 .MOV
    extra_path = root / "IMG_0201.JPG"
    base.save(extra_path, quality=40, exif=exif_for(base))
    mov_path = root / "IMG_0201.MOV"
    _write_random_video(str(mov_path), duration_seconds=1.5, seed=99)

    review_dir = str(tmp_path / "待复查")
    config = Config(input_dir=str(root), review_dir=review_dir, similarity_threshold=10)
    files, errors = scan_directory(config)
    assert not errors
    result = classify(config, files, errors)

    by_name = {os.path.basename(f.path): f for f in result.files}
    extra_rec = by_name["IMG_0201.JPG"]
    mov_rec = by_name["IMG_0201.MOV"]
    assert extra_rec.final_category == Category.SIMILAR, "测试前提：IMG_0201.JPG 应该被归入相似组"
    assert extra_rec.final_action.value == "移至待复查"
    assert mov_rec.group_id == extra_rec.group_id, "测试前提：伴生 .MOV 应该跟图片同组"

    op_log = execute(config, result)
    request.node._op_logs.append(op_log)

    group_folder = os.path.join(review_dir, "相似", extra_rec.group_id)
    assert os.path.exists(os.path.join(group_folder, "IMG_0201.JPG"))
    assert os.path.exists(os.path.join(group_folder, "IMG_0201.MOV")), (
        "Live Photo 伴生 .MOV 应该跟着配对图片一起移到同一个待复查子文件夹，不能变成孤儿"
    )
    assert not os.path.exists(extra_path)
    assert not os.path.exists(mov_path)
    assert os.path.exists(orig_path), "保留文件 IMG_0200.JPG 应该原地不动"


# ---------- AC-16: 只命中截图规则（没有同时命中完全重复/相似）的文件全部原地不动，内容和修改时间不变 ----------


def test_ac16_screenshot_only_files_untouched(sample_source, tmp_path, request):
    photos_dir, manifest = _fresh_copy(sample_source, tmp_path)
    review_dir = str(tmp_path / "待复查")

    def snapshot(paths):
        out = {}
        for p in paths:
            st = os.stat(p)
            with open(p, "rb") as f:
                h = hashlib.sha256(f.read()).hexdigest()
            out[p] = (st.st_size, st.st_mtime, h)
        return out

    before = snapshot(manifest["screenshots"])

    config, result, op_log = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)
    by_path = {f.path: f for f in result.files}

    mark_only = [p for p in manifest["screenshots"] if by_path[p].final_action.value == "仅标记"]
    assert mark_only, "样本集里应该存在只命中截图规则的文件（没有同时命中完全重复/相似）"

    after = snapshot(mark_only)
    for p in mark_only:
        assert before[p] == after[p], f"{p} 只应该被标记为截图，内容/修改时间不应该变化"
        assert os.path.exists(p)
        assert by_path[p].final_category == Category.SCREENSHOT


# ---------- AC-17: 文件数对账；被删除的文件全部能在报告的「完全重复」类别里找到 ----------


def test_ac17_file_count_conservation(sample_source, tmp_path, request):
    photos_dir, manifest = _fresh_copy(sample_source, tmp_path)
    review_dir = str(tmp_path / "待复查")

    def count_files(root):
        if not os.path.isdir(root):
            return 0
        return sum(len(filenames) for _, _, filenames in os.walk(root))

    before_count = count_files(photos_dir)

    config, result, op_log = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)

    after_input_count = count_files(photos_dir)
    after_review_count = count_files(review_dir)
    deleted_count = sum(1 for op in op_log["操作"] if op["动作"] == "删除(废纸篓)")

    assert after_input_count + after_review_count == before_count - deleted_count

    report = build_report(result)
    exact_dup_paths = {
        row["原路径"] for row in report["命中文件明细"] if row["类别"] == Category.EXACT_DUPLICATE.value
    }
    deleted_paths = {op["原路径"] for op in op_log["操作"] if op["动作"] == "删除(废纸篓)"}
    assert deleted_paths, "样本集里应该有被删除的完全重复副本"
    assert deleted_paths <= exact_dup_paths


# ---------- AC-18: 操作记录带具体数值；运行还原后「待复查」清空，原目录只差被删除的完全重复副本 ----------


def test_ac18_operation_log_numeric_evidence_and_revert(sample_source, tmp_path, request):
    photos_dir, manifest = _fresh_copy(sample_source, tmp_path)
    review_dir = str(tmp_path / "待复查")

    def snapshot(root):
        out = {}
        for dirpath, _dirs, filenames in os.walk(root):
            for name in filenames:
                p = os.path.join(dirpath, name)
                with open(p, "rb") as f:
                    h = hashlib.sha256(f.read()).hexdigest()
                out[os.path.relpath(p, root)] = (os.path.getsize(p), h)
        return out

    before = snapshot(photos_dir)

    config, result, op_log = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)

    similar_ops = [op for op in op_log["操作"] if op["类别"] == Category.SIMILAR.value]
    assert similar_ops, "样本集里应该有相似组的操作记录"
    assert all("phash_distance" in op["数值证据"] for op in similar_ops), (
        "相似组的操作记录应该带感知哈希距离"
    )

    short_video_ops = [op for op in op_log["操作"] if op["类别"] == Category.SHORT_VIDEO.value]
    assert short_video_ops, "样本集里应该有短视频的操作记录"
    assert all("duration_seconds" in op["数值证据"] for op in short_video_ops), (
        "短视频的操作记录应该带视频秒数"
    )
    for op in op_log["操作"]:
        assert op["原路径"] and op["去向"], "每条操作记录都应该有原路径和去向"

    op_log_path = str(tmp_path / "ops.json")
    write_operation_log(op_log, op_log_path)

    expected_restore_count = sum(1 for op in op_log["操作"] if op["动作"] == "移至待复查")
    restored = revert(op_log_path)
    assert len(restored) == expected_restore_count

    after = snapshot(photos_dir)
    deleted_rel = {
        os.path.relpath(op["原路径"], photos_dir)
        for op in op_log["操作"]
        if op["动作"] == "删除(废纸篓)"
    }
    expected = {k: v for k, v in before.items() if k not in deleted_rel}
    assert after == expected, "还原后原目录应该跟执行前一样，只差被删除的完全重复副本"

    for op in op_log["操作"]:
        if op["动作"] == "移至待复查":
            assert not os.path.exists(op["去向"]), "还原后「待复查」里不应该还残留被还原走的文件"


# ---------- AC-19: 对同一目录再跑一次执行模式不产生新的删除/移动；非图片/视频文件不受影响 ----------


def test_ac19_second_execute_run_is_noop_and_non_media_files_untouched(sample_source, tmp_path, request):
    photos_dir, manifest = _fresh_copy(sample_source, tmp_path)
    review_dir = str(tmp_path / "待复查")

    txt_path = os.path.join(photos_dir, "notes.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("hello aimee")
    aae_path = os.path.join(photos_dir, "IMG_9999.AAE")
    with open(aae_path, "w", encoding="utf-8") as f:
        f.write("<aae/>")

    _config1, _result1, op_log1 = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)
    assert op_log1["操作数"] > 0, "第一次执行应该产生删除/移动"
    assert os.path.exists(txt_path)
    assert os.path.exists(aae_path)

    _config2, _result2, op_log2 = _run_execute_tracked(request.node._op_logs, photos_dir, review_dir)
    assert op_log2["操作数"] == 0, "对同一目录再跑一次执行模式，不应该产生新的删除或移动"

    assert os.path.exists(txt_path), ".txt 文件不应该被删除或移动"
    assert os.path.exists(aae_path), ".AAE 文件不应该被删除或移动"
    with open(txt_path, encoding="utf-8") as f:
        assert f.read() == "hello aimee"
    with open(aae_path, encoding="utf-8") as f:
        assert f.read() == "<aae/>"
