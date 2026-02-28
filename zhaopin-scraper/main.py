#!/usr/bin/env python3
"""智联招聘薪资数据抓取 — 主入口

用法:
    # 全量抓取（所有城市 × 所有行业）
    python main.py scrape

    # 按关键词抓取
    python main.py scrape --keyword "Python开发" --city 530

    # 仅清洗已有数据
    python main.py clean

    # 仅分析 + 生成图表
    python main.py analyze

    # 全流程：抓取 → 清洗 → 分析 → 可视化
    python main.py all

    # 使用 Selenium（处理动态页面）
    python main.py scrape --selenium

    # 启动定时任务
    python main.py schedule
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from scraper.zhaopin import ZhaopinScraper
from analysis.clean import load_raw_data, clean_dataframe, save_clean_data
from analysis.analyze import generate_full_report
from analysis.visualize import generate_all_charts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("zhaopin-scraper")


def cmd_scrape(args: argparse.Namespace) -> None:
    """执行数据抓取。"""
    scraper = ZhaopinScraper()

    cities = config.CITIES
    if args.city:
        cities = {args.city: config.CITIES.get(args.city, args.city)}

    keywords = [args.keyword] if args.keyword else [""]
    max_pages = getattr(args, "max_pages", 0) or config.MAX_PAGES_PER_QUERY

    scraper.scrape_all(cities=cities, keywords=keywords, max_pages=max_pages)

    logger.info("抓取统计: %s", scraper.stats)

    # 保存原始数据
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scraper.save_json(config.DATA_DIR / f"zhaopin_jobs_{timestamp}.json")
    scraper.save_csv(config.DATA_DIR / f"zhaopin_jobs_{timestamp}.csv")
    # 同时覆盖最新文件（方便后续分析引用）
    scraper.save_json()
    scraper.save_csv()


def cmd_clean(args: argparse.Namespace) -> None:
    """执行数据清洗。"""
    df = load_raw_data()
    df = clean_dataframe(df)
    save_clean_data(df)
    logger.info("清洗完成")


def cmd_analyze(args: argparse.Namespace) -> None:
    """执行分析 + 可视化。"""
    # 优先使用清洗后数据
    clean_path = config.DATA_DIR / "zhaopin_clean.csv"
    if clean_path.exists():
        import pandas as pd
        df = pd.read_csv(clean_path, encoding=config.CSV_ENCODING)
    else:
        df = load_raw_data()
        df = clean_dataframe(df)
        save_clean_data(df)

    reports = generate_full_report(df)

    # 保存报告为 Excel（多 sheet）
    excel_path = config.OUTPUT_DIR / "salary_report.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for name, report_df in reports.items():
            report_df.to_excel(writer, sheet_name=name[:31], index=False)
    logger.info("分析报告已保存: %s", excel_path)

    # 打印概要
    for name, report_df in reports.items():
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")
        print(report_df.to_string(index=False))

    charts = generate_all_charts(df)
    logger.info("已生成 %d 张图表于 %s", len(charts), config.OUTPUT_DIR)


def cmd_all(args: argparse.Namespace) -> None:
    """全流程：抓取 → 清洗 → 分析。"""
    logger.info("开始全流程执行")
    cmd_scrape(args)
    cmd_clean(args)
    cmd_analyze(args)
    logger.info("全流程执行完毕")


def cmd_schedule(args: argparse.Namespace) -> None:
    """启动定时任务调度。"""
    from scheduler import run_scheduler
    run_scheduler()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="智联招聘薪资数据抓取与分析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # scrape
    p_scrape = sub.add_parser("scrape", help="抓取职位数据")
    p_scrape.add_argument("--keyword", "-k", default="", help="搜索关键词")
    p_scrape.add_argument("--city", "-c", default="", help="城市代码（如 530=北京）")
    p_scrape.add_argument("--max-pages", "-m", type=int, default=0, help="每组合最大翻页数")

    # clean
    sub.add_parser("clean", help="清洗已有数据")

    # analyze
    sub.add_parser("analyze", help="分析数据并生成图表")

    # all
    p_all = sub.add_parser("all", help="全流程：抓取 → 清洗 → 分析")
    p_all.add_argument("--keyword", "-k", default="", help="搜索关键词")
    p_all.add_argument("--city", "-c", default="", help="城市代码")
    p_all.add_argument("--max-pages", "-m", type=int, default=0, help="每组合最大翻页数")

    # schedule
    sub.add_parser("schedule", help="启动定时抓取调度")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "scrape": cmd_scrape,
        "clean": cmd_clean,
        "analyze": cmd_analyze,
        "all": cmd_all,
        "schedule": cmd_schedule,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
