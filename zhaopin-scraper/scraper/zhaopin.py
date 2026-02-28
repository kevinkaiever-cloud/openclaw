"""智联招聘数据抓取器 — 核心抓取逻辑"""

from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path
from typing import Optional

import requests
from fake_useragent import UserAgent
from tqdm import tqdm

import config
from scraper.parser import JobItem, parse_api_results, parse_html_job_list, parse_salary
from scraper.proxy import ProxyPool
from scraper.browser import BrowserAutomation

logger = logging.getLogger(__name__)

ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")


class ZhaopinScraper:
    """智联招聘全量职位薪资数据抓取器。

    两种抓取策略:
    1. **API 模式**（默认）: 直接调用前端搜索 API，速度快、数据结构化。
    2. **HTML 模式**（降级）: 当 API 被封或返回异常时，用 Selenium 渲染页面后解析 HTML。
    """

    def __init__(
        self,
        proxy_pool: Optional[ProxyPool] = None,
        use_selenium: bool = False,
    ) -> None:
        self.session = requests.Session()
        self.proxy_pool = proxy_pool or ProxyPool(config.PROXY_LIST)
        self.use_selenium = use_selenium
        self.all_jobs: list[JobItem] = []
        self._request_count = 0

    # ── 公开方法 ──────────────────────────────────────────

    def scrape_all(
        self,
        cities: Optional[dict[str, str]] = None,
        industries: Optional[dict[str, str]] = None,
        keywords: Optional[list[str]] = None,
    ) -> list[JobItem]:
        """按城市 × 行业（或关键词）组合全量抓取。"""
        cities = cities or config.CITIES
        industries = industries or config.INDUSTRIES
        keywords = keywords or [""]

        total_combos = len(cities) * len(industries) * len(keywords)
        logger.info(
            "开始全量抓取: %d 城市 × %d 行业 × %d 关键词 = %d 组合",
            len(cities), len(industries), len(keywords), total_combos,
        )

        with tqdm(total=total_combos, desc="抓取进度", unit="组") as pbar:
            for city_code, city_name in cities.items():
                for ind_code, ind_name in industries.items():
                    for kw in keywords:
                        desc = f"{city_name}/{ind_name}"
                        if kw:
                            desc += f"/{kw}"
                        pbar.set_postfix_str(desc)

                        jobs = self._scrape_combination(
                            city_code=city_code,
                            industry_code=ind_code,
                            keyword=kw,
                        )
                        # 补充元数据
                        for j in jobs:
                            if not j.city:
                                j.city = city_name
                            if not j.industry:
                                j.industry = ind_name
                        self.all_jobs.extend(jobs)
                        pbar.update(1)

        logger.info("抓取完成, 共 %d 条职位数据", len(self.all_jobs))
        return self.all_jobs

    def scrape_by_keyword(self, keyword: str, city_code: str = "") -> list[JobItem]:
        """按关键词搜索抓取。"""
        return self._scrape_combination(city_code=city_code, keyword=keyword)

    # ── 内部方法 ──────────────────────────────────────────

    def _scrape_combination(
        self,
        city_code: str = "",
        industry_code: str = "",
        keyword: str = "",
    ) -> list[JobItem]:
        """抓取单个 城市+行业+关键词 组合的所有分页数据。"""
        all_items: list[JobItem] = []

        for page in range(1, config.MAX_PAGES_PER_QUERY + 1):
            if self.use_selenium:
                items = self._fetch_page_selenium(city_code, industry_code, keyword, page)
            else:
                items = self._fetch_page_api(city_code, industry_code, keyword, page)

            if not items:
                break

            all_items.extend(items)
            logger.debug("  第 %d 页: %d 条", page, len(items))

            # 如果返回数量少于一页，说明没有更多数据
            if len(items) < config.PAGE_SIZE:
                break

            self._polite_delay()

        return all_items

    def _fetch_page_api(
        self,
        city_code: str,
        industry_code: str,
        keyword: str,
        page: int,
    ) -> list[JobItem]:
        """通过搜索 API 抓取一页数据。"""
        params = {
            "pageSize": str(config.PAGE_SIZE),
            "cityId": city_code,
            "industryCode": industry_code,
            "kw": keyword,
            "start": str((page - 1) * config.PAGE_SIZE),
            "ct": "0",
        }

        headers = {**config.HEADERS, "User-Agent": ua.random}
        proxies = self.proxy_pool.get() if self.proxy_pool.available else None

        for attempt in range(config.MAX_RETRIES):
            try:
                resp = self.session.get(
                    config.SEARCH_API,
                    params=params,
                    headers=headers,
                    proxies=proxies,
                    timeout=15,
                )
                self._request_count += 1

                if resp.status_code == 403:
                    logger.warning("API 返回 403, 可能触发反爬（尝试 %d/%d）", attempt + 1, config.MAX_RETRIES)
                    if self.proxy_pool.available:
                        proxies = self.proxy_pool.get_random()
                    time.sleep(config.RETRY_BACKOFF ** (attempt + 1))
                    continue

                resp.raise_for_status()
                data = resp.json()
                return parse_api_results(data)

            except requests.RequestException as exc:
                logger.warning("请求失败（尝试 %d/%d）: %s", attempt + 1, config.MAX_RETRIES, exc)
                time.sleep(config.RETRY_BACKOFF ** (attempt + 1))

        return []

    def _fetch_page_selenium(
        self,
        city_code: str,
        industry_code: str,
        keyword: str,
        page: int,
    ) -> list[JobItem]:
        """使用 Selenium 渲染搜索页面并解析 HTML。"""
        url = (
            f"https://sou.zhaopin.com/?jl={city_code}"
            f"&in={industry_code}"
            f"&kw={keyword}"
            f"&p={page}"
        )

        proxy_str = None
        if self.proxy_pool.available:
            pd = self.proxy_pool.get()
            if pd:
                proxy_str = pd.get("http")

        try:
            with BrowserAutomation(
                headless=config.SELENIUM_HEADLESS,
                proxy=proxy_str,
            ) as browser:
                html = browser.get_page_source(url, wait_selector=".joblist-box__item")
                browser.scroll_to_bottom()
                html = browser.driver.page_source
                return parse_html_job_list(html)
        except Exception:
            logger.exception("Selenium 抓取失败: %s", url)
            return []

    def _polite_delay(self) -> None:
        """礼貌延时，避免请求过快被封。"""
        delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
        time.sleep(delay)

    # ── 数据导出 ──────────────────────────────────────────

    def save_json(self, path: Optional[Path] = None) -> Path:
        path = path or config.DATA_DIR / "zhaopin_jobs.json"
        data = [j.to_dict() for j in self.all_jobs]
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=config.JSON_INDENT),
            encoding="utf-8",
        )
        logger.info("数据已保存为 JSON: %s (%d 条)", path, len(data))
        return path

    def save_csv(self, path: Optional[Path] = None) -> Path:
        import pandas as pd

        path = path or config.DATA_DIR / "zhaopin_jobs.csv"
        df = pd.DataFrame([j.to_dict() for j in self.all_jobs])
        df.to_csv(path, index=False, encoding=config.CSV_ENCODING)
        logger.info("数据已保存为 CSV: %s (%d 条)", path, len(df))
        return path

    @property
    def stats(self) -> dict:
        return {
            "total_jobs": len(self.all_jobs),
            "total_requests": self._request_count,
            "with_salary": sum(1 for j in self.all_jobs if j.salary_min is not None),
            "unique_companies": len({j.company_name for j in self.all_jobs if j.company_name}),
            "unique_cities": len({j.city for j in self.all_jobs if j.city}),
        }
