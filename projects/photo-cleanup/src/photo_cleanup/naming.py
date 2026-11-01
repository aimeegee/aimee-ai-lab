"""文件名规则：副本后缀判定、编辑/裁剪版配对（如 IMG_1234 / IMG_E1234）。

这些规则只看文件名字符串，不碰文件内容，所以单独放一个模块方便测试和复用。
"""

from __future__ import annotations

import os
import re

# "xxx (1)"、"xxx-1" 这类系统自动加的副本后缀。
# 不匹配下划线+数字（比如 IMG_0001 本身就是这种格式，不是副本后缀）。
_COPY_SUFFIX_RE = re.compile(r"(\s\(\d+\)|-\d+)$")

# iOS 编辑版文件名：在前缀（通常是 "IMG_"）之后插入一个 "E"。
# 例: IMG_1234.JPG 的编辑版是 IMG_E1234.JPG
_EDITED_RE = re.compile(r"^(?P<prefix>[A-Za-z]+_)E(?P<num>\d+)$")
_ORIGINAL_RE = re.compile(r"^(?P<prefix>[A-Za-z]+_)(?P<num>\d+)$")


def stem(filename: str) -> str:
    return os.path.splitext(filename)[0]


def has_copy_suffix(filename: str) -> bool:
    return bool(_COPY_SUFFIX_RE.search(stem(filename)))


def pick_preferred_by_name(filenames: list[str]) -> str:
    """AC-4 的保留规则：不带副本后缀的优先；都带或都不带时取文件名排序第一个。"""
    no_suffix = [f for f in filenames if not has_copy_suffix(f)]
    pool = no_suffix if no_suffix else filenames
    return min(pool, key=lambda f: f)


def edited_counterpart_stem(filename: str) -> str | None:
    """如果 filename 是编辑版（如 IMG_E1234），返回对应原图的 stem（如 IMG_1234）；否则 None。"""
    m = _EDITED_RE.match(stem(filename))
    if not m:
        return None
    return f"{m.group('prefix')}{m.group('num')}"


def is_edited_version(filename: str) -> bool:
    return edited_counterpart_stem(filename) is not None


def is_plain_numbered_name(filename: str) -> bool:
    return bool(_ORIGINAL_RE.match(stem(filename)))
