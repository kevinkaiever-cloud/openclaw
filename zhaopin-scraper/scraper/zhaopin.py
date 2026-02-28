"""智联招聘数据抓取器 — 基于 Selenium 的全量职位抓取"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from tqdm import tqdm

import config
from scraper.parser import JobItem, parse_html_job_list

logger = logging.getLogger(__name__)


def _make_driver(proxy: Optional[str] = None) -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")

    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)
    # webdriver 属性伪装
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


class ZhaopinScraper:
    """智联招聘全量职位薪资数据抓取器（Selenium 驱动）。"""

    def __init__(self, proxy: Optional[str] = None) -> None:
        self.proxy = proxy
        self.all_jobs: list[JobItem] = []
        self._page_count = 0

    def scrape_all(
        self,
        cities: Optional[dict[str, str]] = None,
        industries: Optional[dict[str, str]] = None,
        keywords: Optional[list[str]] = None,
        max_pages: int = 0,
    ) -> list[JobItem]:
        """按城市 × 关键词组合全量抓取。

        Args:
            cities: {城市代码: 城市名}, 默认用 config.CITIES
            industries: 未使用（行业信息从页面提取），保留接口兼容
            keywords: 搜索关键词列表，默认 [""]（全部职位）
            max_pages: 每组合最大翻页数，0 表示用 config 值
        """
        cities = cities or config.CITIES
        keywords = keywords or [""]
        max_pages = max_pages or config.MAX_PAGES_PER_QUERY

        total_combos = len(cities) * len(keywords)
        logger.info("开始抓取: %d 城市 × %d 关键词 = %d 组合", len(cities), len(keywords), total_combos)

        with tqdm(total=total_combos, desc="抓取进度", unit="组") as pbar:
            for city_code, city_name in cities.items():
                # 每个城市新建浏览器实例，避免长时间运行后被反爬拦截
                driver = None
                try:
                    driver = _make_driver(self.proxy)
                    for kw in keywords:
                        desc = f"{city_name}"
                        if kw:
                            desc += f"/{kw}"
                        pbar.set_postfix_str(desc)

                        jobs = self._scrape_search(driver, city_code, city_name, kw, max_pages)
                        self.all_jobs.extend(jobs)
                        pbar.update(1)
                except Exception as exc:
                    logger.warning("城市 %s 抓取异常: %s", city_name, exc)
                    pbar.update(1)
                finally:
                    if driver:
                        try:
                            driver.quit()
                        except Exception:
                            pass
                    time.sleep(1)  # 浏览器释放缓冲

        logger.info("抓取完成, 共 %d 条职位数据, %d 页", len(self.all_jobs), self._page_count)
        return self.all_jobs

    def _scrape_search(
        self,
        driver: webdriver.Chrome,
        city_code: str,
        city_name: str,
        keyword: str,
        max_pages: int,
    ) -> list[JobItem]:
        """抓取单个搜索条件的所有分页。"""
        all_items: list[JobItem] = []

        for page in range(1, max_pages + 1):
            url = f"https://sou.zhaopin.com/?jl={city_code}&kw={keyword}&p={page}"

            try:
                driver.get(url)
                # 等待职位卡片加载
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".joblist-box__item"))
                )
                time.sleep(1)  # JS 渲染缓冲
            except Exception:
                if page == 1:
                    logger.warning("首页加载失败: %s kw=%s", city_name, keyword)
                break

            html = driver.page_source
            items = parse_html_job_list(html)
            self._page_count += 1

            if not items:
                break

            # 补充城市信息
            for j in items:
                if not j.city:
                    j.city = city_name

            all_items.extend(items)
            logger.debug("  %s p%d: %d 条", city_name, page, len(items))

            # 检测是否还有下一页
            if not self._has_next_page(driver):
                break

            # 少于一整页说明到末尾
            if len(items) < 15:
                break

            self._polite_delay()

        return all_items

    def _has_next_page(self, driver: webdriver.Chrome) -> bool:
        """检测分页控件中是否还有下一页。"""
        try:
            # "下一页" 按钮：.soupager__btn 但不含 --disable，文本为"下一页"
            btns = driver.find_elements(By.CSS_SELECTOR, ".soupager__btn:not(.soupager__btn--disable)")
            for btn in btns:
                if "下一页" in btn.text:
                    return True
            return False
        except Exception:
            return False

    def _polite_delay(self) -> None:
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
        logger.info("JSON 已保存: %s (%d 条)", path, len(data))
        return path

    def save_csv(self, path: Optional[Path] = None) -> Path:
        import pandas as pd

        path = path or config.DATA_DIR / "zhaopin_jobs.csv"
        df = pd.DataFrame([j.to_dict() for j in self.all_jobs])
        df.to_csv(path, index=False, encoding=config.CSV_ENCODING)
        logger.info("CSV 已保存: %s (%d 条)", path, len(df))
        return path

    @property
    def stats(self) -> dict:
        return {
            "total_jobs": len(self.all_jobs),
            "total_pages": self._page_count,
            "with_salary": sum(1 for j in self.all_jobs if j.salary_min is not None),
            "unique_companies": len({j.company_name for j in self.all_jobs if j.company_name}),
            "unique_cities": len({j.city for j in self.all_jobs if j.city}),
        }
