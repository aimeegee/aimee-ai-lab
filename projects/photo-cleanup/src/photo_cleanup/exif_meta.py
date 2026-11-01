"""EXIF 读取：只关心「有没有相机信息」，不做任何内容解读。"""

from __future__ import annotations

from PIL import Image
from PIL.ExifTags import Base


def read_camera_exif(img: "Image.Image") -> tuple[bool, str | None, str | None]:
    """返回 (has_camera_exif, make, model)。

    has_camera_exif = 是否存在 Make / Model / GPSInfo 三者之一。
    截图识别规则要求「无相机 EXIF（无 Make / Model / GPS）」，
    所以只要三者之一存在，就认为「有相机 EXIF」，不算截图候选。
    """
    try:
        exif = img.getexif()
    except Exception:
        return False, None, None

    if not exif:
        return False, None, None

    make = exif.get(Base.Make)
    model = exif.get(Base.Model)
    gps = exif.get(Base.GPSInfo)

    make = make.strip() if isinstance(make, str) else make
    model = model.strip() if isinstance(model, str) else model

    has_camera_exif = bool(make) or bool(model) or bool(gps)
    return has_camera_exif, make, model
