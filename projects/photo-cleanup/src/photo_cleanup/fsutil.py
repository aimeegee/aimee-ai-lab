"""进程内共享的小文件系统工具函数。

单独拆出来是因为 executor.py（移到「待复查」）和 trash.py（移到系统回收站）
都需要"目标目录下如果已经有同名文件，就不要覆盖"这段逻辑，放在这里避免两边互相 import。
"""

from __future__ import annotations

import os


def unique_dest_path(dest_dir: str, filename: str) -> str:
    """dest_dir 下如果已经存在同名文件，在文件名（不含扩展名）后加 __2/__3... 避免覆盖。"""
    candidate = os.path.join(dest_dir, filename)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(filename)
    i = 2
    while True:
        candidate = os.path.join(dest_dir, f"{stem}__{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1
