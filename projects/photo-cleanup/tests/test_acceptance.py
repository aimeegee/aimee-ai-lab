"""逐条核对 requirements.md 的 AC-1 ~ AC-12（M1 范围）。

用法: cd projects/photo-cleanup && python3 -m pytest tests/test_acceptance.py -v

样本集由 sample_generator.py 在每次测试会话开始时生成到临时目录（纯代码合成，
不需要 Aimee 提供真实照片），数量和种类覆盖 AC-4/5/6/8/9/10 的最低要求。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trash_test_support import cleanup_trashed  # noqa: E402

from photo_cleanup.classify import classify  # noqa: E402
from photo_cleanup.config import Config  # noqa: E402
from photo_cleanup.models import Category  # noqa: E402
from photo_cleanup.report import build_report  # noqa: E402
from photo_cleanup.walker import scan_directory  # noqa: E402

PROJECT_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
SAMPLE_GENERATOR = os.path.join(os.path.dirname(__file__), "sample_generator.py")


@pytest.fixture(scope="session")
def sample_world():
    tmp_root = tempfile.mkdtemp(prefix="photo_cleanup_samples_")
    photos_dir = os.path.join(tmp_root, "photos")
    # 用独立子进程生成样本：sample_generator.py 既要用 pillow_heif 编码 HEIC，
    # 又要用 cv2 写测试视频；这台开发机上两者在同一进程里顺序不对会 segfault
    # （生产代码 photo_cleanup 只读取 HEIC、不编码，不受影响，见 sample_generator.py 头部注释）。
    # 当前进程这时已经因为上面 import photo_cleanup.walker 而加载了 cv2，
    # 所以样本生成必须放到全新的子进程里跑，而不是直接在本进程调用 generate()。
    proc = subprocess.run(
        [sys.executable, SAMPLE_GENERATOR, photos_dir],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"样本生成失败:\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    manifest_path = os.path.join(tmp_root, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    config = Config(input_dir=photos_dir, video_threshold_seconds=3.0, similarity_threshold=10)
    files, errors = scan_directory(config)
    result = classify(config, files, errors)
    report = build_report(result)

    by_path = {f.path: f for f in result.files}
    return {
        "dir": photos_dir,
        "manifest": manifest,
        "config": config,
        "result": result,
        "report": report,
        "by_path": by_path,
    }


# ---------- AC-1: 断网也能跑；运行期间没有任何对外网络请求（静态检查） ----------


def test_ac1_no_network_calls_in_source():
    forbidden_tokens = ["requests.", "urllib.request", "http.client", "socket.socket", "urlopen("]
    offenders = []
    for dirpath, _dirs, filenames in os.walk(PROJECT_SRC):
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            for token in forbidden_tokens:
                if token in content:
                    offenders.append((path, token))
    assert not offenders, f"源码里出现了可疑的网络调用: {offenders}"


def test_ac1_preview_and_execute_modes_runnable(sample_world, tmp_path):
    # preview 模式已跑通（sample_world fixture 本身就是一次完整 preview 运行）
    assert sample_world["report"]["模式"] == "preview"

    # execute 模式(M2)现在已经实现了；在一份独立拷贝上跑一次，确认命令行入口能跑完、不报错。
    # 真正的删除/移动/还原行为由 tests/test_execute_acceptance.py 的 AC-13~19 覆盖，这里只确认
    # "preview 和 execute 两种模式都能跑完"这条 AC-1 本身的字面要求。
    exec_dir = str(tmp_path / "exec_copy")
    shutil.copytree(sample_world["dir"], exec_dir)
    reports_dir = str(tmp_path / "reports")
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "photo_cleanup.cli",
            "--dir",
            exec_dir,
            "--mode",
            "execute",
            "--quiet",
            "--review-dir",
            str(tmp_path / "待复查"),
            "--report-dir",
            reports_dir,
        ],
        cwd=PROJECT_SRC,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"execute 模式运行失败:\n{proc.stdout}\n{proc.stderr}"

    op_log_files = [n for n in os.listdir(reports_dir) if n.endswith("_operations.json")]
    assert op_log_files, "execute 模式应该生成一份操作记录"
    with open(os.path.join(reports_dir, op_log_files[0]), encoding="utf-8") as f:
        op_log = json.load(f)
    try:
        assert op_log["操作数"] > 0
    finally:
        cleanup_trashed(op_log)


# ---------- AC-2: 报告字段完整，汇总数与明细行数一致 ----------


def test_ac2_report_fields_and_summary_consistency(sample_world):
    report = sample_world["report"]
    assert report["汇总数与明细行数一致"] is True
    assert sum(report["汇总"].values()) == len(report["命中文件明细"])

    for row in report["命中文件明细"]:
        assert row["原路径"]
        assert row["类别"] in [c.value for c in Category if c != Category.NONE]
        assert row["命中原因"]
        assert row["动作"]

    for g in report["完全重复组"] + report["相似组"]:
        assert g["保留文件"] in g["组内文件"]


# ---------- AC-3: 预览模式前后原目录文件完全不变，且不创建"待复查" ----------


def test_ac3_preview_mode_is_read_only(sample_world):
    photos_dir = sample_world["dir"]

    def snapshot():
        out = {}
        for dirpath, _dirs, filenames in os.walk(photos_dir):
            for name in filenames:
                p = os.path.join(dirpath, name)
                st = os.stat(p)
                with open(p, "rb") as f:
                    h = hashlib.sha256(f.read()).hexdigest()
                out[p] = (st.st_size, st.st_mtime, h)
        return out

    before = snapshot()
    config = Config(input_dir=photos_dir)
    files, errors = scan_directory(config)
    classify(config, files, errors)
    after = snapshot()

    assert before == after
    assert not os.path.isdir(os.path.join(os.path.dirname(photos_dir), "待复查"))
    assert not os.path.isdir(os.path.join(photos_dir, "待复查"))


# ---------- AC-4: >=10 组完全重复，保留规则正确；1 字节差异不算完全重复 ----------


def test_ac4_exact_duplicates(sample_world):
    by_path = sample_world["by_path"]
    manifest = sample_world["manifest"]

    assert len(manifest["exact_duplicate_groups"]) >= 10

    for group in manifest["exact_duplicate_groups"]:
        files = group["files"]
        group_ids = {by_path[p].group_id for p in files}
        categories = {by_path[p].final_category for p in files}
        assert len(group_ids) == 1, f"组内文件没有被归到同一个完全重复组: {files}"
        assert categories == {Category.EXACT_DUPLICATE}

        keep_candidates = [p for p in files if by_path[p].final_action.value == "保留(本组)"]
        assert keep_candidates == [group["expected_keep"]], (
            f"组 {files} 期望保留 {group['expected_keep']}，实际保留 {keep_candidates}"
        )

    p1, p2 = manifest["byte_diff_pair"]
    assert by_path[p1].final_category != Category.EXACT_DUPLICATE
    assert by_path[p2].final_category != Category.EXACT_DUPLICATE
    assert by_path[p1].sha256 != by_path[p2].sha256


# ---------- AC-5 / AC-7: 相似组数量、两种配对场景、保留规则 ----------


def test_ac5_and_ac7_similar_groups(sample_world):
    by_path = sample_world["by_path"]
    manifest = sample_world["manifest"]

    groups = manifest["similar_groups"]
    assert len(groups) >= 20

    kind_counts = {"edited": 0, "screenshot": 0, "plain": 0}
    for group in groups:
        kind_counts[group["kind"]] += 1
        files = group["files"]
        group_ids = {by_path[p].group_id for p in files}
        assert len(group_ids) == 1, f"相似组成员没有被归入同一组: {files} -> {[by_path[p].group_id for p in files]}"
        assert None not in group_ids

        keep_candidates = [p for p in files if by_path[p].final_action.value == "保留(本组)"]
        assert keep_candidates == [group["expected_keep"]], (
            f"组 {files} 期望保留 {group['expected_keep']}，实际保留 {keep_candidates}"
        )

    assert kind_counts["edited"] >= 5
    assert kind_counts["screenshot"] >= 5


# ---------- AC-6: 50 张互不相同的照片，0 张被误归入相似组 ----------


def test_ac6_no_false_merge_among_distinct_photos(sample_world):
    by_path = sample_world["by_path"]
    manifest = sample_world["manifest"]
    distinct = manifest["distinct_photos"]
    assert len(distinct) >= 50

    false_merges = []
    for i, p in enumerate(distinct):
        gi = by_path[p].group_id
        if gi is None:
            continue
        for q in distinct[i + 1 :]:
            if by_path[q].group_id == gi:
                false_merges.append((p, q, gi))
    assert not false_merges, f"以下互不相同的照片被误归入同一相似组: {false_merges}"


# ---------- AC-8: 短视频阈值 ----------


def test_ac8_short_video_threshold(sample_world):
    by_path = sample_world["by_path"]
    for item in sample_world["manifest"]["short_videos"]:
        rec = by_path[item["file"]]
        is_marked = rec.final_category == Category.SHORT_VIDEO
        assert is_marked == item["expect_marked"], (
            f"{item['file']} 时长 {item['duration_seconds']}s，期望标记={item['expect_marked']}，实际={is_marked}"
        )
        if is_marked:
            evidence = None
            for h in rec.hits:
                if h.category == Category.SHORT_VIDEO:
                    evidence = h.numeric_evidence
            assert evidence and "duration_seconds" in evidence


# ---------- AC-9: Live Photo 伴生 .MOV 不被标记为短视频 ----------


def test_ac9_live_photo_companions_not_marked_short_video(sample_world):
    by_path = sample_world["by_path"]
    manifest = sample_world["manifest"]
    assert len(manifest["live_photos"]) >= 10

    for pair in manifest["live_photos"]:
        mov_rec = by_path[pair["mov"]]
        assert mov_rec.is_live_photo_companion is True
        assert mov_rec.final_category != Category.SHORT_VIDEO


# ---------- AC-10: 截图 / 相机照片识别 ----------


def test_ac10_screenshot_detection(sample_world):
    by_path = sample_world["by_path"]
    manifest = sample_world["manifest"]
    screenshots = manifest["screenshots"]
    camera_photos = manifest["camera_photos"]

    assert len(screenshots) >= 20
    assert len(camera_photos) >= 30
    resolutions = {(by_path[p].width, by_path[p].height) for p in screenshots}
    assert len(resolutions) >= 3

    detected = sum(1 for p in screenshots if by_path[p].final_category == Category.SCREENSHOT)
    # 阈值按样本实际数量等比例设置（AC-10 原文"至少20张截图...至少19张被识别"隐含识别率 >= 95%），
    # 不写死 19：如果以后样本集规模变了，断言也跟着变严/变松，不会变相放宽标准
    # （Tester 发现的问题，见 STATUS.md「已完成」commit c6cb811 之后的部分）。
    min_detected = math.ceil(len(screenshots) * 19 / 20)
    assert detected >= min_detected, (
        f"只有 {detected}/{len(screenshots)} 张截图被识别，要求 >= {min_detected}（即识别率 >= 95%）"
    )

    false_positive = [p for p in camera_photos if by_path[p].final_category == Category.SCREENSHOT]
    assert not false_positive, f"以下相机照片被误判为截图: {false_positive}"


# ---------- AC-11: 完全重复 > 相似 > 短视频 > 截图标记 的冲突仲裁 ----------


def test_ac11_priority_conflict(sample_world):
    by_path = sample_world["by_path"]
    manifest = sample_world["manifest"]
    files = manifest["conflict_test"]["files"]

    for p in files:
        rec = by_path[p]
        assert rec.final_category == Category.EXACT_DUPLICATE
        # 同一文件在报告里只应出现一次 —— 用我们的数据模型，天然只有一条 final_category，
        # 这里再确认 hits 里确实同时命中了"截图"规则，证明不是因为没触发截图规则才通过
        hit_categories = {h.category for h in rec.hits}
        assert Category.SCREENSHOT in hit_categories
        assert Category.EXACT_DUPLICATE in hit_categories

    report = sample_world["report"]
    matching_rows = [r for r in report["命中文件明细"] if r["原路径"] in files]
    assert len(matching_rows) == len(files)
    for row in matching_rows:
        assert row["类别"] == Category.EXACT_DUPLICATE.value


# ---------- AC-12: 性能（缩小规模验证趋势，5000 文件规模见"自测"说明里的已知局限） ----------


def test_ac12_perf_smoke(sample_world):
    photos_dir = sample_world["dir"]
    t0 = time.time()
    config = Config(input_dir=photos_dir)
    files, errors = scan_directory(config)
    classify(config, files, errors)
    elapsed = time.time() - t0
    n = len(files)
    # 缩小规模的烟雾测试：确保没有明显的 O(n^2) 级卡顿（每文件均摊耗时在合理范围）。
    # 真实 5000 文件 30 分钟内跑完，没有在 Aimee 的机器上实测，见自测报告里的遗留问题。
    assert n > 0
    per_file = elapsed / n
    assert per_file < 2.0, f"每文件均摊耗时 {per_file:.3f}s 过高，共 {n} 文件耗时 {elapsed:.1f}s"
