"""核心数据模型。

设计上刻意把「文件记录」「分组」「命中结果」拆成独立的 dataclass，
而不是在 classify.py 里用一堆散装 dict ——
这样 M2（执行模式：真正删除/移动）可以直接复用这些结构，
只需要在上面补一层「执行器」，不需要改分类逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FileKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    OTHER = "other"


class Category(str, Enum):
    EXACT_DUPLICATE = "完全重复"
    SIMILAR = "相似"
    SHORT_VIDEO = "短视频"
    SCREENSHOT = "截图"
    NONE = "无命中"


class Action(str, Enum):
    KEEP_IN_GROUP = "保留(本组)"
    DELETE_TO_TRASH = "删除(废纸篓)"
    MOVE_TO_REVIEW = "移至待复查"
    MARK_ONLY = "仅标记"
    NO_ACTION = "无动作"


# 类别优先级，数字越小优先级越高。用于 AC-11 的冲突仲裁。
CATEGORY_PRIORITY = {
    Category.EXACT_DUPLICATE: 0,
    Category.SIMILAR: 1,
    Category.SHORT_VIDEO: 2,
    Category.SCREENSHOT: 3,
    Category.NONE: 99,
}


@dataclass
class FileRecord:
    """目录扫描后，每个文件对应一条记录。"""

    path: str  # 绝对路径
    rel_path: str  # 相对 input_dir 的路径，报告里更易读
    size: int
    mtime: float
    kind: FileKind
    ext: str

    sha256: str | None = None

    # 图片专属
    width: int | None = None
    height: int | None = None
    phash_full: object | None = None  # imagehash.ImageHash，完整画面
    phash_trimmed: object | None = None  # 去掉四周近纯色边条（截图状态栏/黑边）后的画面
    has_camera_exif: bool = False
    exif_make: str | None = None
    exif_model: str | None = None

    # 视频专属
    duration_seconds: float | None = None
    video_meta_error: str | None = None

    # Live Photo：该文件自身是图片时，对应的 .MOV 伴生文件路径（若有）
    live_photo_companion: str | None = None
    # 该文件自身是 .MOV 时，是否是某张图片的 Live Photo 伴生文件
    is_live_photo_companion: bool = False
    live_photo_owner: str | None = None  # 对应图片的 path

    # 分类结果（由 classify.py 填充）
    hits: list["Hit"] = field(default_factory=list)
    final_category: Category = Category.NONE
    final_action: Action = Action.NO_ACTION
    final_reason: str = ""
    group_id: str | None = None  # 命中的组号（完全重复组或相似组）


@dataclass
class Hit:
    """一次规则命中（可能同一文件命中多条规则，由 classify.py 做优先级仲裁）。"""

    category: Category
    reason: str
    group_id: str | None = None
    numeric_evidence: dict = field(default_factory=dict)
    """记录判断用的具体数值，供以后做反馈调参（M4）。
    例如相似组: {"phash_distance": 3}；短视频: {"duration_seconds": 1.8}
    """


@dataclass
class DuplicateGroup:
    group_id: str
    kind: str  # "exact" | "similar"
    member_paths: list[str]
    keep_path: str
    reason_for_keep: str
    max_pairwise_distance: int | None = None  # 仅相似组：组内最大感知哈希距离


@dataclass
class ScanResult:
    config: object
    files: list[FileRecord]
    exact_groups: list[DuplicateGroup]
    similar_groups: list[DuplicateGroup]
    skipped_paths: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
