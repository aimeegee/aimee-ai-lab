"""命令行入口。

M1 只实现 preview 模式；--mode execute 会直接报错退出，提示这是 M2 的工作，
这样 agent 按 --help 读参数时不会被"看起来支持但其实没做"的参数误导。
"""

from __future__ import annotations

import argparse
import sys
import time

from .classify import classify
from .config import Config
from .report import build_report, default_report_paths, write_json, write_markdown
from .walker import scan_directory


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="photo-cleanup",
        description="本地照片清理工具（M1 预览版）：扫描一个照片目录，识别完全重复/相似图片/误拍短视频/截图，生成报告。只读，不改动任何文件。",
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
        choices=["preview", "execute"],
        default="preview",
        help="preview=只读生成报告（M1，已实现）；execute=真正删除/移动（M2，尚未实现）",
    )
    p.add_argument("--report-dir", dest="report_dir", default=None, help="报告输出目录；默认在输入目录同级的 photo-cleanup-reports/ 下")
    p.add_argument("--review-dir", dest="review_dir", default=None, help="「待复查」文件夹路径（M2 执行模式用，M1 不生效）")
    p.add_argument("--json-only", action="store_true", help="只写 JSON 报告，不写 Markdown")
    p.add_argument("--quiet", action="store_true", help="不在终端打印摘要，只生成报告文件")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.mode == "execute":
        print(
            "错误: --mode execute（执行模式）还没实现，这是 M2 的范围。"
            "当前只支持 --mode preview（默认），只读生成报告，不会改动任何文件。",
            file=sys.stderr,
        )
        return 2

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
    report = build_report(result)
    elapsed = time.time() - t0
    report["运行耗时秒数"] = round(elapsed, 2)

    json_path, md_path = default_report_paths(config.input_dir, config.report_dir)
    write_json(report, json_path)
    if not args.json_only:
        write_markdown(report, md_path)

    if not args.quiet:
        print(f"扫描完成，耗时 {elapsed:.1f} 秒。")
        print(f"文件总数: {report['文件总数']}（图片 {report['其中图片']}, 视频 {report['其中视频']}）")
        for cat, count in report["汇总"].items():
            print(f"  {cat}: {count}")
        print(f"JSON 报告: {json_path}")
        if not args.json_only:
            print(f"Markdown 报告: {md_path}")
        if errors:
            print(f"运行中有 {len(errors)} 条警告/错误，详见报告末尾。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
