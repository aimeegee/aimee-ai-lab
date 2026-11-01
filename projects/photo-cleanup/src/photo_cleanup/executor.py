"""执行模式（M2）：把 classify() 的分类结果真正落地，并生成可还原的操作记录。

设计上刻意不碰分类逻辑（那是 classify.py 的职责），这里只读每个 FileRecord 的
final_action 按动作分发：

- DELETE_TO_TRASH -> trash.move_to_trash()（移入系统回收站，不是永久删除，AC-13）
- MOVE_TO_REVIEW  -> 移到「待复查/<类别>/[<组号>/]」下（AC-14/AC-15）
- 其它（KEEP_IN_GROUP / MARK_ONLY / NO_ACTION）-> 原样不动（AC-14 的保留文件、AC-16 的截图）

Live Photo 伴生 .MOV 不需要在这里特殊处理：classify.py 已经把它们的
final_category/final_action/group_id 设成跟配对图片一致（见
classify._propagate_to_live_photo_companions），这里按普通命中文件各自单独处理、
各自单独写一条操作记录——这样他们自然会和配对图片同生共死、落到同一个目标文件夹，
revert 时也能各自还原（AC-15/AC-18）。

幂等性（AC-19）：这里没有做任何"记住上次执行过"的状态。之所以"对同一目录再跑一次
执行模式不会产生新的删除/移动"，是因为每次执行前都会重新 scan_directory + classify：
执行一次之后，完全重复组/相似组里的多余文件已经不在原目录了，组内只剩 1 个文件，
达不到"组"的最低人数（>=2），自然不会再被分类命中；短视频和它的 Live Photo 伴生文件
同理。非图片/视频文件永远不会有 final_action != NO_ACTION（见 classify.py 只处理
FileKind.IMAGE/VIDEO），所以这里永远不会碰它们。
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime

from .fsutil import unique_dest_path
from .models import Action, Category, FileRecord, ScanResult
from .report import numeric_evidence_for
from .trash import move_to_trash

# 「待复查」下按类别分的子文件夹名（完全重复不会走到这里，落在回收站里）
_CATEGORY_DIR_NAMES = {
    Category.SIMILAR: "相似",
    Category.SHORT_VIDEO: "短视频",
}


def default_review_dir(input_dir: str, review_dir: str | None) -> str:
    """默认「待复查」目录：输入目录同级、以输入目录名命名，保证一定在输入目录之外
    （需求「待复查文件夹位于输入目录之外」），且不同输入目录的「待复查」互不覆盖
    （与 report.default_report_paths 同一思路）。
    """
    if review_dir:
        return os.path.abspath(review_dir)
    input_dir = os.path.abspath(input_dir)
    base_name = os.path.basename(input_dir.rstrip(os.sep)) or "root"
    return os.path.join(os.path.dirname(input_dir), f"{base_name}-待复查")


def _dest_dir_for(review_root: str, rec: FileRecord) -> str:
    sub = _CATEGORY_DIR_NAMES.get(rec.final_category, rec.final_category.value)
    dest = os.path.join(review_root, sub)
    if rec.final_category == Category.SIMILAR and rec.group_id:
        dest = os.path.join(dest, rec.group_id)
    return dest


def execute(config, result: ScanResult) -> dict:
    """真正执行删除/移动，返回操作记录（dict，可直接 json.dump 或传给 write_operation_log）。"""
    review_root = default_review_dir(config.input_dir, config.review_dir)
    operations: list[dict] = []

    targets = [f for f in result.files if f.final_action in (Action.DELETE_TO_TRASH, Action.MOVE_TO_REVIEW)]
    targets.sort(key=lambda f: f.path)  # 操作记录顺序稳定、可复现，方便 diff/排查

    for rec in targets:
        if not os.path.exists(rec.path):
            # 防御性跳过：理论上不会发生（scan 和 execute 在同一次运行里，中间没有其它改动）。
            continue

        if rec.final_action == Action.DELETE_TO_TRASH:
            dest = move_to_trash(rec.path)
        else:  # MOVE_TO_REVIEW
            dest_dir = _dest_dir_for(review_root, rec)
            os.makedirs(dest_dir, exist_ok=True)
            dest = unique_dest_path(dest_dir, os.path.basename(rec.path))
            shutil.move(rec.path, dest)

        operations.append(
            {
                "原路径": rec.path,
                "去向": dest,
                "类别": rec.final_category.value,
                "动作": rec.final_action.value,
                "组号": rec.group_id,
                "命中原因": rec.final_reason,
                "数值证据": numeric_evidence_for(rec),
            }
        )

    return {
        "生成时间": datetime.now().isoformat(timespec="seconds"),
        "输入目录": os.path.abspath(config.input_dir),
        "待复查目录": review_root,
        "操作数": len(operations),
        "操作": operations,
    }


def write_operation_log(log: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def default_operation_log_path(input_dir: str, report_dir: str | None) -> str:
    """跟 report.default_report_paths 同一套命名规则，文件名带输入目录名 + 时间戳。"""
    input_dir = os.path.abspath(input_dir)
    base_dir_name = os.path.basename(input_dir.rstrip(os.sep)) or "root"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = report_dir or os.path.join(os.path.dirname(input_dir), "photo-cleanup-reports")
    return os.path.join(out_dir, f"{base_dir_name}_{timestamp}_operations.json")


def find_latest_operation_log(input_dir: str, report_dir: str | None) -> str | None:
    """revert 模式没传 --operation-log 时，自动找该目录最近一次 execute 生成的操作记录。"""
    input_dir = os.path.abspath(input_dir)
    base_dir_name = os.path.basename(input_dir.rstrip(os.sep)) or "root"
    out_dir = report_dir or os.path.join(os.path.dirname(input_dir), "photo-cleanup-reports")
    if not os.path.isdir(out_dir):
        return None
    candidates = [
        os.path.join(out_dir, name)
        for name in os.listdir(out_dir)
        if name.startswith(f"{base_dir_name}_") and name.endswith("_operations.json")
    ]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)


def revert(operation_log_path: str) -> list[str]:
    """按操作记录，把「待复查」里被移动的文件放回原路径。

    只还原「移至待复查」的文件；「删除(废纸篓)」的文件留在回收站里不还原——AC-18 要求
    "还原后原目录与执行前相比只差被删除的完全重复副本"，也就是说回收站里的文件本来就
    不该被这个函数拿回来。

    返回被还原的原路径列表。
    """
    with open(operation_log_path, encoding="utf-8") as f:
        log = json.load(f)

    restored: list[str] = []
    for op in log.get("操作", []):
        if op["动作"] != Action.MOVE_TO_REVIEW.value:
            continue
        src, dst = op["去向"], op["原路径"]
        if not os.path.exists(src):
            # 用户可能已经自己处理过（手动删掉/挪走了），不是这个函数的职责，跳过不报错。
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        restored.append(dst)
    return restored
