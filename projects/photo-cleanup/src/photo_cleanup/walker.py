"""扫描目录，为每个文件建立 FileRecord，并完成：
- 字节哈希
- 图片：分辨率、EXIF、感知哈希（完整/去边条两种）
- 视频：时长
- Live Photo 配对（图片 <-> 同名 .MOV）

这一层只负责「收集事实」，不做任何分类判断（完全重复/相似/短视频/截图的判断逻辑在 classify.py）。
"""

from __future__ import annotations

import os

from PIL import Image, UnidentifiedImageError

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:  # pragma: no cover - pillow_heif 是必需依赖，正常不会走到这里
    pass

from .config import Config
from .exif_meta import read_camera_exif
from .hashing import compute_phash_variants, sha256_file
from .models import FileKind, FileRecord
from .video_meta import read_duration_seconds


def _iter_files(root: str, follow_symlinks: bool):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
        # 跳过「待复查」文件夹本身（防止它恰好在 input_dir 内部时被重复处理）
        dirnames[:] = [d for d in dirnames if d != "待复查"]
        for name in filenames:
            if name.startswith("."):
                # 跳过隐藏文件（如 .DS_Store），不是本工具的处理对象
                continue
            yield os.path.join(dirpath, name)


def scan_directory(config: Config) -> tuple[list[FileRecord], list[str]]:
    """返回 (file_records, errors)。"""
    input_dir = os.path.abspath(config.input_dir)
    image_exts = config.image_extensions()
    video_exts = config.video_extensions()

    records: dict[str, FileRecord] = {}
    errors: list[str] = []

    for path in _iter_files(input_dir, config.follow_symlinks):
        ext = os.path.splitext(path)[1].lower()
        try:
            stat = os.stat(path)
        except OSError as e:
            errors.append(f"无法读取文件信息 {path}: {e}")
            continue

        rel_path = os.path.relpath(path, input_dir)

        if ext in image_exts:
            kind = FileKind.IMAGE
        elif ext in video_exts:
            kind = FileKind.VIDEO
        else:
            kind = FileKind.OTHER

        record = FileRecord(
            path=path,
            rel_path=rel_path,
            size=stat.st_size,
            mtime=stat.st_mtime,
            kind=kind,
            ext=ext,
        )

        if kind in (FileKind.IMAGE, FileKind.VIDEO):
            try:
                record.sha256 = sha256_file(path)
            except OSError as e:
                errors.append(f"无法读取文件内容 {path}: {e}")
                continue

        if kind == FileKind.IMAGE:
            try:
                with Image.open(path) as img:
                    img.load()
                    record.width, record.height = img.size
                    has_exif, make, model = read_camera_exif(img)
                    record.has_camera_exif = has_exif
                    record.exif_make = make
                    record.exif_model = model
                    phash_full, phash_trim = compute_phash_variants(img, hash_size=config.phash_size)
                    record.phash_full = phash_full
                    record.phash_trimmed = phash_trim
            except (UnidentifiedImageError, OSError) as e:
                errors.append(f"无法解析图片 {path}: {e}")

        elif kind == FileKind.VIDEO:
            duration, err = read_duration_seconds(path)
            record.duration_seconds = duration
            record.video_meta_error = err
            if err:
                errors.append(f"视频时长读取失败 {path}: {err}")

        records[path] = record

    _link_live_photos(records, image_exts)

    return list(records.values()), errors


def _link_live_photos(records: dict[str, FileRecord], image_exts: set[str]) -> None:
    """同目录、同文件名（不含扩展名，大小写不敏感）的图片 + .MOV 视为 Live Photo。"""
    by_dir_stem: dict[tuple[str, str], list[FileRecord]] = {}
    for rec in records.values():
        d = os.path.dirname(rec.path)
        stem = os.path.splitext(os.path.basename(rec.path))[0].lower()
        by_dir_stem.setdefault((d, stem), []).append(rec)

    for (_, _stem), group in by_dir_stem.items():
        images = [r for r in group if r.kind == FileKind.IMAGE]
        movs = [r for r in group if r.kind == FileKind.VIDEO and r.ext == ".mov"]
        if not images or not movs:
            continue
        # 常见情况是一张图片配一个 .MOV；若出现多张同名不同格式的图片（如 HEIC+JPG 都存在），
        # 全部与该 .MOV 建立关联，报告里都能看到配对关系（已知限制：见 README）。
        for mov in movs:
            mov.is_live_photo_companion = True
            mov.live_photo_owner = images[0].path
            for img in images:
                img.live_photo_companion = mov.path
