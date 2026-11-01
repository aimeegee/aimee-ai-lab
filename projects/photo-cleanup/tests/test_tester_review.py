"""独立 Tester 复核：Engineer 的 tests/test_acceptance.py 全部通过，
但样本/断言本身可能有漏洞或遗漏边界——这个文件专门补这些洞，不依赖
test_acceptance.py 的 sample_world（故意用独立/隔离的样本，避免重复同样的confound）。

发现记录见 Tester 回报，这里只放可重复运行的复现代码。
"""

from __future__ import annotations

import hashlib
import os
import random
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from photo_cleanup import naming  # noqa: E402
from photo_cleanup.classify import classify  # noqa: E402
from photo_cleanup.config import Config  # noqa: E402
from photo_cleanup.models import Category  # noqa: E402
from photo_cleanup.walker import scan_directory  # noqa: E402

PROJECT_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
SAMPLE_GENERATOR = os.path.join(os.path.dirname(__file__), "sample_generator.py")


# ---------- AC-1: 动态验证——真跑一次 preview，期间拦截 socket.socket，确认零网络调用 ----------
# （Engineer 原测试只做了源码里搜字符串的静态检查，没有真正跑起来验证；这里补一个动态验证）


def test_ac1_dynamic_no_socket_calls_during_real_run(tmp_path):
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    # 跑在子进程里，这样可以安全地给 socket.socket 打补丁而不影响 pytest 自身
    script = f"""
import socket, sys
socket.socket = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("NETWORK CALL ATTEMPTED"))
sys.path.insert(0, {PROJECT_SRC!r})
sys.argv = ["photo-cleanup", "--dir", {str(photos_dir)!r}, "--mode", "preview", "--quiet",
            "--report-dir", {str(tmp_path / "reports")!r}]
from photo_cleanup.cli import main
sys.exit(main(sys.argv[1:]))
"""
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 0, f"打了 socket 补丁后跑 preview 失败（可能真的发起了网络调用）:\n{proc.stdout}\n{proc.stderr}"


# ---------- AC-4: 已知缺口——macOS 的「空格+数字2」副本后缀不被识别，且会导致保留错误的文件 ----------
# 这不算 AC-4 字面要求之外的 FAIL（AC-4 原文举例只提 "(1)"/"-1"），但 STATUS.md 已经记录了这个缺口，
# 这里把它变成一个可重复运行的断言，防止以后被静默"修复"或者被静默"更坏"而没人注意到。


def test_ac4_known_gap_macos_space_2_suffix_not_recognized():
    # 不被识别为副本后缀
    assert naming.has_copy_suffix("IMG_1713 2.HEIC") is False
    # 后果：两个文件名都被当成"不带后缀"，min() 按字符串排序——空格(0x20) < 点(0x2E)，
    # 导致带" 2"的文件名反而被当成"优先保留"，这是 STATUS.md 里说的"选择有点随意"的具体表现。
    picked = naming.pick_preferred_by_name(["IMG_1713.HEIC", "IMG_1713 2.HEIC"])
    assert picked == "IMG_1713 2.HEIC", (
        "如果这个断言失败，说明这个已知缺口被修复了（或者行为变了）——去更新 STATUS.md / README 的"
        "「已知局限」，不要只删这个测试。"
    )


# ---------- AC-9: Engineer 的样本有 confound——12 个 Live Photo 伴生 .MOV 互相字节完全相同 ----------
# （sample_generator.write_video 的帧内容只依赖循环下标，不依赖任何per-file种子，相同时长的视频
#  天然字节相同）。导致这 12 个 .MOV 全部被分进同一个"完全重复"组，final_category 自然不是"短视频"，
#  但这并没有真正验证"Live Photo 伴生文件应免于短视频判断"这条规则本身，只是被更高优先级的
#  "完全重复"规则意外掩盖了。这里用内容互不相同的视频单独验证真正要测的行为。


def test_ac9_live_photo_exemption_in_isolation_without_exact_dup_confound(tmp_path):
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw
    from PIL.ExifTags import Base

    root = tmp_path / "lp_isolated"
    root.mkdir()

    rng = random.Random(1)
    img = Image.new("RGB", (1600, 1200), (120, 140, 160))
    draw = ImageDraw.Draw(img)
    for _ in range(8):
        x0, y0 = rng.randint(0, 1600), rng.randint(0, 1200)
        draw.rectangle([x0, y0, x0 + 80, y0 + 80], fill=(rng.randint(0, 255), 0, 0))
    exif = img.getexif()
    exif[Base.Make] = "Apple"
    exif[Base.Model] = "iPhone 13"
    img.save(root / "IMG_0099.JPG", quality=90, exif=exif)

    mov_path = str(root / "IMG_0099.MOV")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(mov_path, fourcc, 30.0, (320, 240))
    r = random.Random(777)
    for i in range(45):  # 1.5s @ 30fps，低于默认短视频阈值 3 秒
        frame = np.random.RandomState(r.randint(0, 10**6) + i).randint(0, 255, (240, 320, 3), dtype=np.uint8)
        vw.write(frame)
    vw.release()

    config = Config(input_dir=str(root), video_threshold_seconds=3.0, similarity_threshold=10)
    files, errors = scan_directory(config)
    assert not errors
    result = classify(config, files, errors)
    by_name = {os.path.basename(f.path): f for f in result.files}

    mov_rec = by_name["IMG_0099.MOV"]
    assert mov_rec.is_live_photo_companion is True
    assert mov_rec.final_category == Category.NONE, (
        "隔离测试（无完全重复干扰）下，Live Photo 伴生 .MOV 应该完全不命中任何规则，"
        "不只是'不命中短视频规则'"
    )
    assert Category.SHORT_VIDEO not in {h.category for h in mov_rec.hits}


# ---------- AC-11: 补一个样本集里没有的组合——两个字节相同的短视频，验证"完全重复 > 短视频"仍然成立 ----------
# Engineer 的冲突样本只测了"截图 + 完全重复"这一种组合；"短视频 + 完全重复"这个组合完全没有样本覆盖。


def test_ac11_priority_exact_duplicate_beats_short_video(tmp_path):
    import cv2
    import numpy as np

    root = tmp_path / "video_conflict"
    root.mkdir()
    path1 = str(root / "clip_a.mp4")
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(path1, fourcc, 30.0, (320, 240))
    for i in range(30):  # 1 秒，低于默认阈值
        frame = np.full((240, 320, 3), (i * 5) % 255, dtype=np.uint8)
        vw.write(frame)
    vw.release()

    path2 = str(root / "clip_a (1).mp4")
    with open(path1, "rb") as f:
        raw = f.read()
    with open(path2, "wb") as f:
        f.write(raw)

    config = Config(input_dir=str(root), video_threshold_seconds=3.0, similarity_threshold=10)
    files, errors = scan_directory(config)
    result = classify(config, files, errors)
    by_name = {os.path.basename(f.path): f for f in result.files}

    for name in ("clip_a.mp4", "clip_a (1).mp4"):
        rec = by_name[name]
        assert rec.final_category == Category.EXACT_DUPLICATE, (
            f"{name} 同时命中完全重复(两个文件字节相同)和短视频(1秒<3秒阈值)规则，"
            f"按 AC-11 优先级应归为完全重复，实际 = {rec.final_category}"
        )
        hit_categories = {h.category for h in rec.hits}
        assert Category.SHORT_VIDEO in hit_categories, "没有真正命中短视频规则，这个冲突测试没意义"
        assert Category.EXACT_DUPLICATE in hit_categories


# ---------- AC-6/AC-5 安全边际检查：确认聚类不是"刚好卡线"而是有余量（反脆弱性证据，不是新 AC） ----------


def test_distinct_photos_cluster_margin_is_not_marginal(tmp_path):
    """这不是独立的 AC，只是确认 AC-6 的 55 张互不相同样本不是"刚好低于阈值才没误判"——
    如果余量很小，以后随手改个参数就可能让 AC-6 变得脆弱。用真实样本生成器的产物测。
    """
    tmp_root = str(tmp_path / "samples")
    proc = subprocess.run([sys.executable, SAMPLE_GENERATOR, tmp_root], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr

    from photo_cleanup.hashing import phash_distance
    import itertools

    config = Config(input_dir=tmp_root, similarity_threshold=10)
    files, errors = scan_directory(config)
    distinct = [f for f in files if f"{os.sep}distinct{os.sep}" in f.path]
    assert len(distinct) >= 50
    min_dist = min(
        phash_distance((a.phash_full, a.phash_trimmed), (b.phash_full, b.phash_trimmed))
        for a, b in itertools.combinations(distinct, 2)
        if a.phash_full is not None and b.phash_full is not None
    )
    assert min_dist > 30, (
        f"互不相同照片之间的最小感知哈希距离只有 {min_dist}（阈值 10），余量比预期小，"
        "AC-6 可能比看起来更容易因为样本/参数微调而变脆弱"
    )
