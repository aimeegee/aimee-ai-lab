"""可调参数与设备分辨率表。

设计原则（见 projects/photo-cleanup/decisions.md D-001 / D-002）：
- 相似判定默认偏严（similarity_threshold 小），可通过命令行调松
- 短视频默认阈值 3 秒，可通过命令行调整
"""

from __future__ import annotations

from dataclasses import dataclass, field

# 图片 / 视频 / Live Photo 伴生文件的扩展名（大小写不敏感）
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".heic", ".heif", ".png", ".tiff", ".tif", ".bmp", ".gif"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v"}

# 已知 iPhone 设备屏幕物理像素分辨率（宽, 高），两种朝向都收录。
# 用途：截图识别——截图分辨率必然等于设备屏幕物理像素。
# 来源：公开的 iOS 设备规格；此表只影响「截图」标记，不影响删除，
# 新机型分辨率不在表里时，截图可能漏判，不会误判相机照片。
KNOWN_IPHONE_SCREEN_RESOLUTIONS: set[tuple[int, int]] = set()


def _add_resolution(w: int, h: int) -> None:
    KNOWN_IPHONE_SCREEN_RESOLUTIONS.add((w, h))
    KNOWN_IPHONE_SCREEN_RESOLUTIONS.add((h, w))


for _w, _h in [
    (640, 960),    # iPhone 4/4s
    (640, 1136),   # iPhone 5/5s/5c/SE1
    (750, 1334),   # iPhone 6/7/8/SE2/SE3
    (1080, 1920),  # iPhone 6+/7+/8+
    (1125, 2001),  # iPhone XR 逻辑渲染（部分截图尺寸）
    (828, 1792),   # iPhone XR/11
    (1125, 2436),  # iPhone X/XS/11 Pro
    (1242, 2208),  # iPhone 6+/7+/8+ (放大渲染)
    (1242, 2688),  # iPhone XS Max/11 Pro Max
    (1170, 2532),  # iPhone 12/13/14
    (1284, 2778),  # iPhone 12/13 Pro Max, 14 Plus
    (1179, 2556),  # iPhone 14 Pro/15/16
    (1290, 2796),  # iPhone 14 Pro Max/15 Pro Max/16 Plus
    (1206, 2622),  # iPhone 15 Pro/16 Pro
    (1320, 2868),  # iPhone 15 Pro Max/16 Pro Max
]:
    _add_resolution(_w, _h)


@dataclass
class Config:
    """一次运行使用的全部可调参数。"""

    input_dir: str
    video_threshold_seconds: float = 3.0
    similarity_threshold: int = 10
    """两张图片的感知哈希汉明距离 <= 此值即视为相似（默认偏严，见 D-001）。"""
    phash_size: int = 16
    """phash 的 hash_size，16 => 256 bit 哈希，分辨力更高。"""
    review_dir: str | None = None
    """「待复查」文件夹路径；为空时默认放在 input_dir 的同级目录。M1 不使用，为 M2 预留。"""
    report_dir: str | None = None
    """报告输出目录；为空时默认放在 input_dir 的同级目录。"""
    mode: str = "preview"
    """preview | execute；M1 只实现 preview，execute 会报错提示未实现（M2 开发）。"""
    workers: int = 1
    """保留的并行度参数位，M1 未使用多进程，先占位方便 M2/M3 扩展。"""
    follow_symlinks: bool = False
    extra_image_extensions: tuple[str, ...] = field(default_factory=tuple)
    extra_video_extensions: tuple[str, ...] = field(default_factory=tuple)

    def image_extensions(self) -> set[str]:
        return IMAGE_EXTENSIONS | {e.lower() for e in self.extra_image_extensions}

    def video_extensions(self) -> set[str]:
        return VIDEO_EXTENSIONS | {e.lower() for e in self.extra_video_extensions}
