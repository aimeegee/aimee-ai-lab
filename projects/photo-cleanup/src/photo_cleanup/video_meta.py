"""视频元数据：只读取时长，不解读画面内容。

用 OpenCV（本地库，不联网）读取帧数和帧率算时长，不依赖 ffprobe/ffmpeg 命令行。
"""

from __future__ import annotations

import cv2


def read_duration_seconds(path: str) -> tuple[float | None, str | None]:
    """返回 (duration_seconds, error)。读取失败时 duration 为 None，error 有说明。"""
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return None, "无法打开视频文件（编解码器不支持或文件损坏）"

        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        fps = cap.get(cv2.CAP_PROP_FPS)

        if fps and fps > 0 and frame_count and frame_count > 0:
            return frame_count / fps, None

        # 回退方案：有些容器不提供可靠的 FRAME_COUNT/FPS，逐帧计数（较慢，仅在必要时用）。
        if fps and fps > 0:
            count = 0
            while True:
                ok, _ = cap.read()
                if not ok:
                    break
                count += 1
            if count > 0:
                return count / fps, None

        return None, "无法从视频元数据读取有效的帧率或帧数"
    finally:
        cap.release()
