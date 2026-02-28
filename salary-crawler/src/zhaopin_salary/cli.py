from __future__ import annotations

import argparse
from pathlib import Path

from zhaopin_salary.scheduler import monthly_cron_line


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zhaopin salary crawler pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser("crawl", help="crawl raw jobs")
    crawl_parser.add_argument("--targets", required=True, help="targets config path")
    crawl_parser.add_argument("--output", required=True, help="raw jsonl output path")
    crawl_parser.add_argument("--max-pages", type=int, default=3, help="max pages per city-industry")
    crawl_parser.add_argument("--download-delay", type=float, default=1.5, help="base request delay seconds")
    crawl_parser.add_argument("--use-selenium", action="store_true", help="use selenium fallback on empty list pages")
    crawl_parser.set_defaults(func=run_crawl)

    clean_parser = subparsers.add_parser("clean", help="clean raw dataset")
    clean_parser.add_argument("--input", required=True, help="raw jsonl input path")
    clean_parser.add_argument("--csv", required=True, help="clean csv output path")
    clean_parser.add_argument("--json", required=True, help="clean json output path")
    clean_parser.set_defaults(func=run_clean)

    report_parser = subparsers.add_parser("report", help="build charts and summary report")
    report_parser.add_argument("--input", required=True, help="clean csv input path")
    report_parser.add_argument("--figure-dir", required=True, help="figure output directory")
    report_parser.add_argument("--summary", required=True, help="summary markdown path")
    report_parser.set_defaults(func=run_report)

    all_parser = subparsers.add_parser("all", help="run crawl + clean + report")
    all_parser.add_argument("--targets", required=True, help="targets config path")
    all_parser.add_argument("--raw", required=True, help="raw jsonl output path")
    all_parser.add_argument("--csv", required=True, help="clean csv output path")
    all_parser.add_argument("--json", required=True, help="clean json output path")
    all_parser.add_argument("--figure-dir", required=True, help="figure output directory")
    all_parser.add_argument("--summary", required=True, help="summary markdown path")
    all_parser.add_argument("--max-pages", type=int, default=3, help="max pages per city-industry")
    all_parser.add_argument("--download-delay", type=float, default=1.5, help="base request delay seconds")
    all_parser.add_argument("--use-selenium", action="store_true", help="use selenium fallback on empty list pages")
    all_parser.set_defaults(func=run_all)

    schedule_parser = subparsers.add_parser("schedule", help="print monthly cron example")
    schedule_parser.add_argument(
        "--project-root",
        default=str(Path.cwd()),
        help="project root for cron command (default: current directory)",
    )
    schedule_parser.set_defaults(func=run_schedule)

    discover_parser = subparsers.add_parser("discover", help="discover industries/cities from homepage")
    discover_parser.add_argument("--homepage", default="https://www.zhaopin.com/", help="homepage url to discover targets")
    discover_parser.add_argument("--output", required=True, help="output targets json path")
    discover_parser.set_defaults(func=run_discover)
    return parser


def run_crawl(args: argparse.Namespace) -> None:
    try:
        from scrapy.crawler import CrawlerProcess
    except ImportError as exc:
        raise RuntimeError("缺少 Scrapy，请先执行 pip install -r requirements.txt") from exc

    from zhaopin_salary.spiders.zhaopin_spider import ZhaopinSpider

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {
        "LOG_LEVEL": "INFO",
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": args.download_delay,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "RETRY_ENABLED": True,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [408, 429, 500, 502, 503, 504, 522, 524],
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": args.download_delay,
        "AUTOTHROTTLE_MAX_DELAY": 10.0,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
        "COOKIES_ENABLED": False,
        "ITEM_PIPELINES": {"zhaopin_salary.pipelines.JsonlPipeline": 300},
    }
    process = CrawlerProcess(settings=settings)
    process.crawl(
        ZhaopinSpider,
        targets_path=args.targets,
        output_path=str(output_path),
        max_pages=args.max_pages,
        use_selenium=args.use_selenium,
    )
    process.start()
    print(f"[crawl] done -> {output_path}")


def run_clean(args: argparse.Namespace) -> None:
    from zhaopin_salary.cleaning import clean_dataset

    stats = clean_dataset(args.input, args.csv, args.json)
    print(f"[clean] raw_rows={stats['raw_rows']} clean_rows={stats['clean_rows']} dropped={stats['dropped_duplicates']}")
    print(f"[clean] csv={args.csv}")
    print(f"[clean] json={args.json}")


def run_report(args: argparse.Namespace) -> None:
    from zhaopin_salary.analysis import generate_report

    stats = generate_report(args.input, args.figure_dir, args.summary)
    print(f"[report] rows={stats['rows']} figures={stats['figures']}")
    print(f"[report] figure_dir={args.figure_dir}")
    print(f"[report] summary={args.summary}")


def run_all(args: argparse.Namespace) -> None:
    crawl_args = argparse.Namespace(
        targets=args.targets,
        output=args.raw,
        max_pages=args.max_pages,
        download_delay=args.download_delay,
        use_selenium=args.use_selenium,
    )
    run_crawl(crawl_args)
    clean_args = argparse.Namespace(input=args.raw, csv=args.csv, json=args.json)
    run_clean(clean_args)
    report_args = argparse.Namespace(input=args.csv, figure_dir=args.figure_dir, summary=args.summary)
    run_report(report_args)


def run_schedule(args: argparse.Namespace) -> None:
    cron = monthly_cron_line(args.project_root)
    print(cron)


def run_discover(args: argparse.Namespace) -> None:
    from zhaopin_salary.discovery import discover_targets

    payload = discover_targets(homepage_url=args.homepage, output_path=args.output)
    print(f"[discover] cities={len(payload.get('cities', []))} industries={len(payload.get('industries', []))}")
    print(f"[discover] output={args.output}")


if __name__ == "__main__":
    main()

