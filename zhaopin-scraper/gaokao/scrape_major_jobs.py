#!/usr/bin/env python3
"""用 Playwright 批量抓取高考专业对应的就业市场薪资数据。"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from scraper.parser import parse_html_job_list
from gaokao.config import MAJOR_TO_JOBS, DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("major_jobs")


def scrape_all_major_jobs(max_pages: int = 2) -> dict[str, list[dict]]:
    """为每个专业的每个关键词抓取职位数据。"""
    # 收集所有需要搜索的关键词（去重）
    kw_to_majors: dict[str, list[str]] = {}
    for major, kws in MAJOR_TO_JOBS.items():
        for kw in kws:
            kw_to_majors.setdefault(kw, []).append(major)

    all_keywords = sorted(kw_to_majors.keys())
    logger.info("总计 %d 个关键词, 覆盖 %d 个专业", len(all_keywords), len(MAJOR_TO_JOBS))

    results: dict[str, list[dict]] = {}
    batch_size = 15

    for batch_start in range(0, len(all_keywords), batch_size):
        batch = all_keywords[batch_start:batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (len(all_keywords) + batch_size - 1) // batch_size

        logger.info("批次 %d/%d (%d 个关键词)", batch_num, total_batches, len(batch))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = context.new_page()

            for kw in batch:
                all_items = []
                for pg in range(1, max_pages + 1):
                    try:
                        page.goto(f"https://sou.zhaopin.com/?kw={kw}&p={pg}", timeout=15000)
                        page.wait_for_selector(".joblist-box__item", timeout=8000)
                        time.sleep(1)
                        items = parse_html_job_list(page.content())
                        all_items.extend(items)
                        if len(items) < 15:
                            break
                        time.sleep(random.uniform(1, 2))
                    except Exception:
                        break

                results[kw] = [j.to_dict() for j in all_items]
                count = len(all_items)
                with_sal = sum(1 for j in all_items if j.salary_min and j.salary_min > 0)
                logger.info("  %s: %d 条 (%d 有薪资)", kw, count, with_sal)
                time.sleep(random.uniform(0.5, 1.5))

            context.close()
            browser.close()

        # 每批次保存进度
        _save_progress(results)
        time.sleep(2)

    return results


def _save_progress(results: dict[str, list[dict]]):
    path = DATA_DIR / "major_jobs_progress.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


def aggregate_by_major(results: dict[str, list[dict]]) -> dict[str, dict]:
    """将关键词级数据聚合到专业级别。"""
    import pandas as pd

    major_stats = {}
    for major, kws in MAJOR_TO_JOBS.items():
        all_jobs = []
        for kw in kws:
            if kw in results:
                all_jobs.extend(results[kw])

        if not all_jobs:
            major_stats[major] = {
                "job_count": 0, "salary_median": 0, "salary_avg": 0,
                "salary_min": 0, "salary_max": 0, "top_companies": [], "top_cities": [],
            }
            continue

        df = pd.DataFrame(all_jobs)
        df["sal_avg"] = df.apply(
            lambda r: (r["salary_min"] + r["salary_max"]) / 2
            if r.get("salary_min") and r["salary_min"] > 0 else None, axis=1)

        valid = df[df["sal_avg"].notna()]
        top_companies = df["company_name"].value_counts().head(5).index.tolist() if "company_name" in df else []
        top_cities = df["city"].value_counts().head(5).index.tolist() if "city" in df else []

        major_stats[major] = {
            "job_count": len(df),
            "salary_median": int(valid["sal_avg"].median()) if len(valid) > 0 else 0,
            "salary_avg": int(valid["sal_avg"].mean()) if len(valid) > 0 else 0,
            "salary_min": int(valid["sal_avg"].quantile(0.25)) if len(valid) > 0 else 0,
            "salary_max": int(valid["sal_avg"].quantile(0.75)) if len(valid) > 0 else 0,
            "top_companies": top_companies,
            "top_cities": top_cities,
        }

    return major_stats


def main():
    logger.info("开始抓取专业对应就业数据 (Playwright)")

    results = scrape_all_major_jobs(max_pages=2)

    # 汇总
    flat_jobs = []
    for kw, jobs in results.items():
        for j in jobs:
            j["search_keyword"] = kw
            flat_jobs.append(j)

    # 保存原始数据
    with open(DATA_DIR / "major_jobs_all.json", "w", encoding="utf-8") as f:
        json.dump(flat_jobs, f, ensure_ascii=False, indent=2)

    # 聚合到专业
    major_stats = aggregate_by_major(results)
    with open(DATA_DIR / "major_job_stats.json", "w", encoding="utf-8") as f:
        json.dump(major_stats, f, ensure_ascii=False, indent=2)

    # 统计
    total_jobs = sum(len(v) for v in results.values())
    with_data = sum(1 for v in major_stats.values() if v["job_count"] > 0)
    logger.info("=" * 60)
    logger.info("完成:")
    logger.info("  关键词: %d", len(results))
    logger.info("  总职位: %d", total_jobs)
    logger.info("  有数据的专业: %d / %d", with_data, len(MAJOR_TO_JOBS))
    logger.info("=" * 60)

    # 打印专业薪资排名
    ranked = sorted(major_stats.items(), key=lambda x: x[1]["salary_median"], reverse=True)
    print("\n专业就业薪资排名 (中位月薪):")
    for i, (major, stats) in enumerate(ranked[:30], 1):
        if stats["salary_median"] > 0:
            print(f"  {i:2d}. {major:20s} | {stats['salary_median']:>8,}元 | {stats['job_count']:>3d}个岗位")


if __name__ == "__main__":
    main()
