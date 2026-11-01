"""测试专用小工具。

execute 模式会把"完全重复"的多余文件挪进真实的系统废纸篓（macOS 的 ~/.Trash，
见 src/photo_cleanup/trash.py）——这是生产行为本身要求的（AC-13），测试没法绕过去
不碰真实回收站，不然就测不到真实行为。但测试结束后应该把自己丢进去的测试样本清掉，
不给 Aimee 的真实废纸篓留垃圾。
"""

from __future__ import annotations

import os


def cleanup_trashed(op_log: dict) -> None:
    """删掉 op_log 里记录为"删除(废纸篓)"的那些文件（它们已经被 execute 移进了系统回收站）。"""
    for op in op_log.get("操作", []):
        if op.get("动作") == "删除(废纸篓)":
            dest = op.get("去向")
            if dest and os.path.exists(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
