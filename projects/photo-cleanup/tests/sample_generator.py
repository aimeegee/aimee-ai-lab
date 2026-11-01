"""生成带标注的验收样本集（全部是代码合成的图片/视频，不需要 Aimee 提供真实照片）。

覆盖 requirements.md 的 AC-4 ~ AC-11 对样本集数量和种类的要求。
用法: python sample_generator.py <输出目录>
生成后会在输出目录旁写一份 manifest.json，记录每个样本的"标准答案"，
test_acceptance.py 用这份 manifest 逐条核对 AC。
"""

from __future__ import annotations

import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter
from PIL.ExifTags import Base

# 注意：cv2 故意不在模块顶层导入。在这台开发机上，opencv 和 pillow_heif 在同一进程里
# 只要 `import cv2` 发生在"用 pillow_heif 编码/保存 HEIC"之前，HEIC 编码就会 segfault
# （已验证：只是 import，不调用 VideoWriter 也会触发；读取已有 HEIC 文件不受影响）。
# 生产代码 photo_cleanup 从不编码 HEIC（只读取），不受影响；这里把 cv2 的 import
# 延迟到 write_video() 内部，并保证 generate() 里所有 HEIC 编码都在第一次调用
# write_video() 之前完成，绕开这个环境里的库冲突。见 README「已知问题」。

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

CAMERA_RESOLUTIONS = [(3024, 4032), (4032, 3024), (4000, 3000)]
# 几个真实存在、且彼此不同的 iPhone 截图分辨率(对应 config.py 里的表)
SCREENSHOT_RESOLUTIONS = [(1170, 2532), (828, 1792), (1125, 2436), (1179, 2556)]


def make_scene(seed: int, w: int, h: int) -> Image.Image:
    """生成一张"看起来像照片"的合成图：大片中等亮度背景 + 若干色块 + 高斯模糊。
    中等亮度背景 + 模糊是为了让 phash 对缩放/重新压缩稳健（见团队验证记录），
    同时避免背景过亮/过暗，不触发截图去边条逻辑的误剪。
    """
    rng = random.Random(seed)
    bg = (rng.randint(90, 200), rng.randint(90, 200), rng.randint(90, 200))
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    for _ in range(10):
        x0, y0 = rng.randint(0, w), rng.randint(0, h)
        x1, y1 = x0 + rng.randint(int(w * 0.05), int(w * 0.3)), y0 + rng.randint(int(h * 0.05), int(h * 0.3))
        color = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        if rng.random() < 0.5:
            draw.ellipse([x0, y0, x1, y1], fill=color)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=color)
    return img.filter(ImageFilter.GaussianBlur(8))


def with_camera_exif(img: Image.Image, make: str = "Apple", model: str = "iPhone 13") -> "Image.Exif":
    exif = img.getexif()
    exif[Base.Make] = make
    exif[Base.Model] = model
    return exif


def save_jpg(img: Image.Image, path: str, quality: int = 90, exif=None) -> None:
    kwargs = {"quality": quality}
    if exif is not None:
        kwargs["exif"] = exif
    img.save(path, **kwargs)


def save_heic(img: Image.Image, path: str, quality: int = 90, exif=None) -> None:
    kwargs = {"quality": quality}
    if exif is not None:
        kwargs["exif"] = exif
    img.save(path, **kwargs)


def make_screenshot_of(photo: Image.Image, screen_w: int, screen_h: int) -> Image.Image:
    """模拟"对着自己拍的照片截屏"：Photos 等 App 常见的按比例适配(fit)展示方式，
    上下留出状态栏/手势条的系统 UI（见团队对 phash 去边条做法的验证）。
    """
    canvas = Image.new("RGB", (screen_w, screen_h), (8, 8, 8))
    pw, ph = photo.size
    avail_h = int(screen_h * 0.90)
    scale = min(screen_w / pw, avail_h / ph)
    nw, nh = int(pw * scale), int(ph * scale)
    resized = photo.resize((nw, nh))
    ox, oy = (screen_w - nw) // 2, (screen_h - nh) // 2
    canvas.paste(resized, (ox, oy))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, screen_w, int(screen_h * 0.035)], fill=(235, 235, 235))
    draw.rectangle([0, screen_h - int(screen_h * 0.015), screen_w, screen_h], fill=(0, 0, 0))
    return canvas


def write_video(
    path: str, duration_seconds: float, fps: float = 30.0, size=(320, 240), seed: int | None = None
) -> None:
    """写一个合成测试视频。

    M2 修复记录（Tester 发现的已知缺口，见 STATUS.md「已完成」commit c6cb811 之后的部分）：
    之前帧内容只由循环下标 i 决定、不带任何 per-file 随机性，导致两个时长相同的视频字节
    完全一致——Live Photo 样本里 12 个伴生 .MOV 时长都是 1.5 秒，于是全部互为"完全重复"，
    AC-9 的测试因此被"完全重复"规则意外掩盖，并没有真正测到"短视频豁免"逻辑本身
    （见 tests/test_tester_review.py 的独立复现）。这里加一个按 seed 派生的随机数生成器，
    让同时长的视频也有不同字节内容，AC-9 在 test_acceptance.py 里就能测到真实的豁免逻辑，
    不再依赖"完全重复"规则的意外掩盖。
    """
    import cv2  # 延迟导入，原因见文件头注释
    import numpy as np

    rng = np.random.RandomState(seed if seed is not None else random.randint(0, 2**31 - 1))
    n_frames = round(duration_seconds * fps)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    vw = cv2.VideoWriter(path, fourcc, fps, size)
    w, h = size
    for _ in range(n_frames):
        frame = rng.randint(0, 255, (h, w, 3), dtype=np.uint8)
        vw.write(frame)
    vw.release()


def generate(root: str) -> dict:
    os.makedirs(root, exist_ok=True)
    manifest: dict = {
        "exact_duplicate_groups": [],  # [{files:[...], expected_keep: str}]
        "byte_diff_pair": [],
        "similar_groups": [],  # [{files:[...], kind: "edited"|"screenshot"|"plain", expected_keep: str}]
        "distinct_photos": [],
        "short_videos": [],  # [{file, duration_seconds, expect_marked}]
        "live_photos": [],  # [{image, mov}]
        "screenshots": [],  # [file,...]
        "camera_photos": [],  # [file,...]
        "conflict_test": {},
    }

    # ---------- AC-4: >=10 组完全重复 ----------
    dup_dir = os.path.join(root, "exact_dup")
    os.makedirs(dup_dir, exist_ok=True)
    for i in range(12):
        img = make_scene(seed=1000 + i, w=1600, h=1200)
        exif = with_camera_exif(img)
        base_name = f"IMG_{4000 + i:04d}.JPG"
        base_path = os.path.join(dup_dir, base_name)
        save_jpg(img, base_path, quality=92, exif=exif)
        with open(base_path, "rb") as f:
            raw = f.read()

        if i % 3 == 0:
            # 一个带副本后缀、一个不带 -> 不带的赢
            dup_name = f"IMG_{4000 + i:04d} (1).JPG"
            expected_keep = base_name
        elif i % 3 == 1:
            # 两个都带副本后缀 -> 按文件名排序取第一个
            os.rename(base_path, os.path.join(dup_dir, f"IMG_{4000 + i:04d}-1.JPG"))
            base_name = f"IMG_{4000 + i:04d}-1.JPG"
            base_path = os.path.join(dup_dir, base_name)
            dup_name = f"IMG_{4000 + i:04d}-2.JPG"
            expected_keep = min(base_name, dup_name)
        else:
            # 两个都不带副本后缀 -> 按文件名排序取第一个
            os.rename(base_path, os.path.join(dup_dir, f"PHOTO_{4000 + i:04d}_A.JPG"))
            base_name = f"PHOTO_{4000 + i:04d}_A.JPG"
            base_path = os.path.join(dup_dir, base_name)
            dup_name = f"PHOTO_{4000 + i:04d}_B.JPG"
            expected_keep = min(base_name, dup_name)

        dup_path = os.path.join(dup_dir, dup_name)
        with open(dup_path, "wb") as f:
            f.write(raw)

        manifest["exact_duplicate_groups"].append(
            {"files": [base_path, dup_path], "expected_keep": os.path.join(dup_dir, expected_keep)}
        )

    # 1 对内容只差 1 字节，不应被判定为完全重复
    img = make_scene(seed=5000, w=1600, h=1200)
    p1 = os.path.join(dup_dir, "IMG_5000.JPG")
    save_jpg(img, p1, quality=92, exif=with_camera_exif(img))
    with open(p1, "rb") as f:
        raw = bytearray(f.read())
    raw[-50] ^= 0x01  # 翻转文件尾部一个字节（避开 JPEG 头部，防止文件损坏到无法解析）
    p2 = os.path.join(dup_dir, "IMG_5000 (1).JPG")
    with open(p2, "wb") as f:
        f.write(bytes(raw))
    manifest["byte_diff_pair"] = [p1, p2]

    # ---------- AC-5: >=20 组相似，其中 >=5 组 (a) 编辑版配对，>=5 组 (b) 截屏配对 ----------
    sim_dir = os.path.join(root, "similar")
    os.makedirs(sim_dir, exist_ok=True)

    # (a) 编辑/裁剪版文件名配对: IMG_xxxx / IMG_Exxxx
    for i in range(6):
        seed = 2000 + i
        base = make_scene(seed, 1600, 1200)
        num = 6000 + i
        orig_path = os.path.join(sim_dir, f"IMG_{num}.JPG")
        save_jpg(base, orig_path, quality=92, exif=with_camera_exif(base))

        w, h = base.size
        cropped = base.crop((int(w * 0.04), int(h * 0.04), int(w * 0.96), int(h * 0.96)))
        edited_path = os.path.join(sim_dir, f"IMG_E{num}.JPG")
        save_jpg(cropped, edited_path, quality=92, exif=with_camera_exif(base))

        resized_path = os.path.join(sim_dir, f"IMG_{num}_small.JPG")
        save_jpg(base.resize((w // 2, h // 2)), resized_path, quality=85, exif=with_camera_exif(base))

        files = [orig_path, edited_path, resized_path]
        manifest["similar_groups"].append({"files": files, "kind": "edited", "expected_keep": edited_path})

    # (b) 拍照后又截屏：原照片 + 该照片的截屏（含系统 UI 边条）
    for i in range(6):
        seed = 3000 + i
        base = make_scene(seed, 1600, 1200)
        num = 7000 + i
        orig_path = os.path.join(sim_dir, f"IMG_{num}.JPG")
        save_jpg(base, orig_path, quality=92, exif=with_camera_exif(base))

        w, h = base.size
        recompressed_path = os.path.join(sim_dir, f"IMG_{num}_q40.JPG")
        save_jpg(base, recompressed_path, quality=40, exif=with_camera_exif(base))

        screen_w, screen_h = SCREENSHOT_RESOLUTIONS[i % len(SCREENSHOT_RESOLUTIONS)]
        shot = make_screenshot_of(base, screen_w, screen_h)
        shot_path = os.path.join(sim_dir, f"Screenshot_{num}.PNG")
        shot.save(shot_path)  # PNG，不写 EXIF -> 无相机 EXIF

        files = [orig_path, recompressed_path, shot_path]
        manifest["similar_groups"].append({"files": files, "kind": "screenshot", "expected_keep": orig_path})

    # 其余 8 组：普通的缩放 / 重新压缩 / HEIC 格式变体（凑够 >=20 组）
    for i in range(8):
        seed = 4000 + i
        base = make_scene(seed, 1600, 1200)
        num = 8000 + i
        orig_path = os.path.join(sim_dir, f"IMG_{num}.JPG")
        save_jpg(base, orig_path, quality=92, exif=with_camera_exif(base))

        w, h = base.size
        resized_path = os.path.join(sim_dir, f"IMG_{num}_small.JPG")
        save_jpg(base.resize((int(w * 0.6), int(h * 0.6))), resized_path, quality=88, exif=with_camera_exif(base))

        heic_path = os.path.join(sim_dir, f"IMG_{num}.HEIC")
        save_heic(base, heic_path, quality=90, exif=with_camera_exif(base))

        files = [orig_path, resized_path, heic_path]
        # 普通组没有编辑版、没有截图成员 -> 保留像素数最多的一张（这里三者原始分辨率最大且相同，取文件更大的）
        sizes = {p: os.path.getsize(p) for p in files if os.path.exists(p)}
        # 用原图(未缩小)里文件更大的一个作为期望保留项: orig_path vs heic_path（分辨率相同）
        candidates = [orig_path, heic_path]
        expected_keep = max(candidates, key=lambda p: os.path.getsize(p))
        manifest["similar_groups"].append({"files": files, "kind": "plain", "expected_keep": expected_keep})

    # ---------- AC-6: >=50 场景互不相同的照片 ----------
    distinct_dir = os.path.join(root, "distinct")
    os.makedirs(distinct_dir, exist_ok=True)
    for i in range(55):
        img = make_scene(seed=9000 + i, w=1600, h=1200)
        path = os.path.join(distinct_dir, f"IMG_{9000 + i}.JPG")
        save_jpg(img, path, quality=90, exif=with_camera_exif(img))
        manifest["distinct_photos"].append(path)

    # ---------- AC-8: 短视频时长阈值 ----------
    video_dir = os.path.join(root, "short_video_test")
    os.makedirs(video_dir, exist_ok=True)
    for i, (name, dur, expect_marked) in enumerate(
        [
            ("clip_1s.mp4", 1.0, True),
            ("clip_2_9s.mp4", 2.9, True),
            ("clip_3_0s.mp4", 3.0, False),
            ("clip_10s.mp4", 10.0, False),
        ]
    ):
        path = os.path.join(video_dir, name)
        write_video(path, dur, seed=40000 + i)
        manifest["short_videos"].append({"file": path, "duration_seconds": dur, "expect_marked": expect_marked})

    # ---------- AC-9: >=10 组 Live Photo ----------
    live_dir = os.path.join(root, "live_photos")
    os.makedirs(live_dir, exist_ok=True)
    for i in range(12):
        num = 1 + i
        img = make_scene(seed=11000 + i, w=1600, h=1200)
        img_path = os.path.join(live_dir, f"IMG_{num:04d}.JPG")
        save_jpg(img, img_path, quality=90, exif=with_camera_exif(img))
        mov_path = os.path.join(live_dir, f"IMG_{num:04d}.MOV")
        # 低于短视频阈值，但是 Live Photo 伴生文件，不应被标记；每个伴生视频用不同 seed，
        # 避免同时长的视频字节完全相同、被"完全重复"规则意外掩盖（见 write_video 的修复记录）
        write_video(mov_path, 1.5, seed=50000 + i)
        manifest["live_photos"].append({"image": img_path, "mov": mov_path})

    # ---------- AC-10: 截图 / 相机照片 ----------
    shot_dir = os.path.join(root, "screenshots")
    os.makedirs(shot_dir, exist_ok=True)
    for i in range(24):
        w, h = SCREENSHOT_RESOLUTIONS[i % len(SCREENSHOT_RESOLUTIONS)]
        img = Image.new("RGB", (w, h), (230, 230, 230))
        draw = ImageDraw.Draw(img)
        rng = random.Random(20000 + i)
        for _ in range(6):
            x0, y0 = rng.randint(0, w), rng.randint(0, h)
            x1, y1 = x0 + rng.randint(50, 300), y0 + rng.randint(50, 300)
            draw.rectangle([x0, y0, x1, y1], fill=(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)))
        path = os.path.join(shot_dir, f"Screenshot_2025-01-{(i % 28) + 1:02d}-{i:02d}.PNG")
        img.save(path)  # 无 EXIF
        manifest["screenshots"].append(path)

    camera_dir = os.path.join(root, "camera_photos")
    os.makedirs(camera_dir, exist_ok=True)
    for i in range(32):
        if i % 3 == 0:
            w, h = CAMERA_RESOLUTIONS[0]  # 横
        elif i % 3 == 1:
            w, h = CAMERA_RESOLUTIONS[1]  # 竖
        else:
            # 裁剪过的相机照片：分辨率既不是整机分辨率，也不在截图分辨率表里
            w, h = 2200 + i, 2800 + i
        img = make_scene(seed=30000 + i, w=w, h=h)
        path = os.path.join(camera_dir, f"IMG_{9500 + i}.JPG")
        save_jpg(img, path, quality=90, exif=with_camera_exif(img))
        manifest["camera_photos"].append(path)

    # ---------- AC-11: 冲突测试 —— 同时是"截图"又有完全重复副本 ----------
    conflict_dir = os.path.join(root, "conflict_test")
    os.makedirs(conflict_dir, exist_ok=True)
    w, h = SCREENSHOT_RESOLUTIONS[0]
    img = Image.new("RGB", (w, h), (240, 240, 240))
    ImageDraw.Draw(img).rectangle([50, 50, w - 50, h - 50], fill=(10, 10, 10))
    p1 = os.path.join(conflict_dir, "Screenshot_conflict.PNG")
    img.save(p1)
    with open(p1, "rb") as f:
        raw = f.read()
    p2 = os.path.join(conflict_dir, "Screenshot_conflict (1).PNG")
    with open(p2, "wb") as f:
        f.write(raw)
    manifest["conflict_test"] = {"files": [p1, p2], "expected_keep": p1}

    with open(os.path.join(os.path.dirname(root.rstrip(os.sep)), "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return manifest


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "./samples/photos"
    m = generate(out)
    print(f"样本已生成到 {out}")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in m.items()}, ensure_ascii=False, indent=2))
