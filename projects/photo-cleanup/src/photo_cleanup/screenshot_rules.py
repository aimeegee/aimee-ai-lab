"""截图识别规则：分辨率匹配已知设备屏幕 + 无相机 EXIF。

不做内容识别（不 OCR、不判断是广告还是收据），这是需求里明确排除的范围。
"""

from __future__ import annotations

from .config import KNOWN_IPHONE_SCREEN_RESOLUTIONS


def is_screenshot(width: int | None, height: int | None, has_camera_exif: bool) -> tuple[bool, str]:
    if has_camera_exif:
        return False, "存在相机 EXIF（Make/Model/GPS 之一），不是截图"
    if width is None or height is None:
        return False, "缺少分辨率信息，无法判定"
    if (width, height) in KNOWN_IPHONE_SCREEN_RESOLUTIONS:
        return True, f"分辨率 {width}x{height} 匹配已知 iPhone 屏幕像素，且无相机 EXIF"
    return False, f"分辨率 {width}x{height} 不在已知设备屏幕分辨率表中"
