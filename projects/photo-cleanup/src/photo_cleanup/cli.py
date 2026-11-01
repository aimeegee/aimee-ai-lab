"""命令行入口。

三种模式：
- preview：只读，生成报告（M1）
- execute：真正删除/移动（M2）——完全重复副本进系统回收站，相似组多余项/短视频
  移到「待复查」，并生成一份操作记录
- revert：按某次 execute 生成的操作记录，把「待复查」里的文件放回原路径（M2）
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from .classify import classify
from .config import Config
from .executor import (
    default_operation_log_path,
    execute,
    find_latest_operation_log,
    revert,
    write_operation_log,
)
from .report import build_report, default_report_paths, write_json, write_markdown
from .walker import scan_directory


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="photo-cleanup",
        description=(
            "本地照片清理工具：扫描一个照片目录，识别完全重复/相似图片/误拍短视频/截图。"
            "preview 模式只读生成报告；execute 模式真正清理（完全重复副本进系统回收站，"
            "可疑项移到「待复查」）并生成操作记录；revert 模式按操作记录把「待复查」里的文件放回原路径。"
        ),
    )
    p.add_argument("--dir", "-d", required=True, dest="input_dir", help="要扫描的照片目录（含子目录）")
    p.add_argument(
        "--video-threshold-seconds",
        "--short-video-threshold",
        type=float,
        default=3.0,
        dest="video_threshold_seconds",
        help="短视频时长阈值，单位秒，低于此值标记为短视频（默认 3）",
    )
    p.add_argument(
        "--similarity-threshold",
        "--similarity-leniency",
        type=int,
        default=10,
        dest="similarity_threshold",
        help="相似判定的感知哈希汉明距离阈值，数值越大越宽松，越容易把不同照片归并到一组（默认 10，偏严）",
    )
    p.add_argument(
        "--phash-size",
        type=int,
        default=16,
        dest="phash_size",
        help="感知哈希的 hash_size（越大越精细，默认 16，一般不需要改）",
    )
    p.add_argument(
        "--mode",
        choices=["preview", "execute", "revert"],
        default="preview",
        help="preview=只读生成报告；execute=真正删除/移动并生成操作记录；"
        "revert=按操作记录把「待复查」里的文件放回原路径",
    )
    p.add_argument("--report-dir", dest="report_dir", default=None, help="报告（及 execute 的操作记录）输出目录；默认在输入目录同级的 photo-cleanup-reports/ 下")
    p.add_argument(
        "--review-dir",
        dest="review_dir",
        default=None,
        help="「待复查」文件夹路径（execute 模式用）；默认在输入目录同级的 <目录名>-待复查/ 下",
    )
    p.add_argument(
        "--operation-log",
        dest="operation_log",
        default=None,
        help="revert 模式用：要还原的操作记录 JSON 路径；不填则自动找该目录最近一次 execute 生成的操作记录",
    )
    p.add_argument("--json-only", action="store_true", help="只写 JSON 报告，不写 Markdown")
    p.add_argument("--quiet", action="store_true", help="不在终端打印摘要，只生成报告文件")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.mode == "revert":
        log_path = args.operation_log or find_latest_operation_log(args.input_dir, args.report_dir)
        if not log_path or not os.path.exists(log_path):
            print(
                "错误: 找不到可用的操作记录，请用 --operation-log 指定要还原的 JSON 文件路径。",
                file=sys.stderr,
            )
            return 2
        restored = revert(log_path)
        if not args.quiet:
            print(f"还原完成，共 {len(restored)} 个文件从「待复查」放回原路径。使用的操作记录: {log_path}")
        return 0

    config = Config(
        input_dir=args.input_dir,
        video_threshold_seconds=args.video_threshold_seconds,
        similarity_threshold=args.similarity_threshold,
        phash_size=args.phash_size,
        review_dir=args.review_dir,
        report_dir=args.report_dir,
        mode=args.mode,
    )

    t0 = time.time()
    files, errors = scan_directory(config)
    result = classify(config, files, errors)

    op_log = None
    if args.mode == "execute":
        op_log = execute(config, result)

    report = build_report(result)
    elapsed = time.time() - t0
    report["运行耗时秒数"] = round(elapsed, 2)

    json_path, md_path = default_report_paths(config.input_dir, config.report_dir)
    write_json(report, json_path)
    if not args.json_only:
        write_markdown(report, md_path)

    op_log_path = None
    if op_log is not None:
        op_log_path = default_operation_log_path(config.input_dir, config.report_dir)
        write_operation_log(op_log, op_log_path)

    if not args.quiet:
        print(f"扫描完成，耗时 {elapsed:.1f} 秒。")
        print(f"文件总数: {report['文件总数']}（图片 {report['其中图片']}, 视频 {report['其中视频']}）")
        for cat, count in report["汇总"].items():
            print(f"  {cat}: {count}")
        print(f"JSON 报告: {json_path}")
        if not args.json_only:
            print(f"Markdown 报告: {md_path}")
        if op_log_path:
            print(f"操作记录: {op_log_path}（本次操作数 {op_log['操作数']}）")
        if errors:
            print(f"运行中有 {len(errors)} 条警告/错误，详见报告末尾。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
