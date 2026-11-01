"""把文件移到系统回收站（废纸篓），不做永久删除。

原计划用 `send2trash` 这个第三方库（跨平台、是这类需求的标准做法），但本机开发环境的
权限策略会拦截 `pip install`（会把安装新包当成"从外部下载/执行代码"拒绝），所以改成
不需要任何新依赖的实现：直接把文件挪进 macOS 的 `~/.Trash`——这正是 Finder「废纸篓」
在磁盘上对应的真实目录，文件挪进去之后会出现在 Finder 的废纸篓列表里，Aimee 可以在那里
手动把它捞出来，满足需求里"删除方式为移到系统废纸篓，不做永久删除"这条安全原则。

已知局限（已记录到 README「已知局限」）：
- 不会写 Finder 的"原始位置"元数据，所以 Finder 右键菜单的"放回原处"在这些文件上不可用；
  想找回文件可以直接去 Finder 的"废纸篓"里手动拖出来（文件物理上确实在那里）。
- 只实现了 macOS（Aimee 的使用环境是 Mac）；其它系统直接报错，不假装支持。
- 只处理本机启动盘上的文件；外接硬盘/网络盘上的文件，macOS 原生会挪到那个卷自己的
  `.Trashes` 目录，这里统一挪到当前用户的 `~/.Trash`，不影响 Aimee 当前的实际使用场景
  （照片目录在本机磁盘上）。
"""

from __future__ import annotations

import os
import platform
import shutil

from .fsutil import unique_dest_path


def move_to_trash(path: str) -> str:
    """把 path 移到系统废纸篓，返回它在废纸篓里的最终路径。"""
    if platform.system() != "Darwin":
        raise NotImplementedError(
            f"系统回收站支持目前只实现了 macOS（Aimee 的使用环境），当前系统: {platform.system()}"
        )

    trash_dir = os.path.expanduser("~/.Trash")
    os.makedirs(trash_dir, exist_ok=True)

    dest = unique_dest_path(trash_dir, os.path.basename(path))
    shutil.move(path, dest)
    return dest
