"""定时任务调度 — 周期性抓取薪资数据"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import schedule

import config

logger = logging.getLogger(__name__)


def _run_full_pipeline() -> None:
    """执行一次完整的抓取 + 清洗 + 分析流程。"""
    logger.info("定时任务触发: %s", datetime.now().isoformat())

    try:
        from scraper.zhaopin import ZhaopinScraper
        from scraper.proxy import ProxyPool
        from analysis.clean import load_raw_data, clean_dataframe, save_clean_data
        from analysis.analyze import generate_full_report
        from analysis.visualize import generate_all_charts

        proxy_pool = ProxyPool(config.PROXY_LIST)
        scraper = ZhaopinScraper(proxy_pool=proxy_pool)
        scraper.scrape_all()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        scraper.save_json(config.DATA_DIR / f"zhaopin_jobs_{timestamp}.json")
        scraper.save_csv(config.DATA_DIR / f"zhaopin_jobs_{timestamp}.csv")
        scraper.save_json()
        scraper.save_csv()

        df = load_raw_data()
        df = clean_dataframe(df)
        save_clean_data(df)

        generate_full_report(df)
        generate_all_charts(df)

        logger.info("定时任务完成: %d 条数据", len(scraper.all_jobs))
    except Exception:
        logger.exception("定时任务执行失败")


def run_scheduler() -> None:
    """启动调度器，按配置间隔周期执行。"""
    interval = config.SCHEDULE_INTERVAL_DAYS
    logger.info("定时调度已启动: 每 %d 天执行一次", interval)

    schedule.every(interval).days.at("02:00").do(_run_full_pipeline)

    # 首次立即执行
    logger.info("首次执行...")
    _run_full_pipeline()

    logger.info("等待下次调度...")
    while True:
        schedule.run_pending()
        time.sleep(60)
