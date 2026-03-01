#!/usr/bin/env python3
"""国企招聘数据爬虫 — Playwright + DrissionPage 驱动

数据源:
1. 智联招聘 — 公司类型筛选"国企" (Playwright 反爬)
2. 国聘网 iguopin.com — 国资委官方招聘平台
3. 各央企官网招聘页 (DrissionPage)
"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("soe")

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class SOEJob:
    """国企岗位数据"""
    job_name: str = ""
    salary_raw: str = ""
    salary_min: int = 0
    salary_max: int = 0
    company_name: str = ""
    company_type: str = "国企"
    industry: str = ""
    city: str = ""
    experience: str = ""
    education: str = ""
    job_url: str = ""
    source: str = ""           # 数据来源: zhaopin/iguopin/official
    soe_category: str = ""     # 央企/地方国企/国有银行 等
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 薪资解析 ──────────────────────────────────────────────

_SALARY_PAT = re.compile(r"(?P<low>[\d.]+)\s*(?P<low_unit>[kK千万]?)\s*[-~至]\s*(?P<high>[\d.]+)\s*(?P<high_unit>[kK千万]?)")
_SALARY_YUAN = re.compile(r"(?P<low>\d+)\s*[-~至]\s*(?P<high>\d+)\s*元")
_MONTHS_PAT = re.compile(r"(\d+)\s*薪")

def _unit_mul(u: str) -> int:
    if u in ("k", "K", "千"): return 1000
    if u == "万": return 10000
    return 1

def parse_salary(raw: str) -> tuple[int, int]:
    if not raw or "面议" in raw:
        return 0, 0
    m = _SALARY_YUAN.search(raw)
    if m:
        return int(m.group("low")), int(m.group("high"))
    m = _SALARY_PAT.search(raw)
    if not m:
        return 0, 0
    low = float(m.group("low")) * _unit_mul(m.group("low_unit") or m.group("high_unit"))
    high = float(m.group("high")) * _unit_mul(m.group("high_unit") or m.group("low_unit"))
    return int(low), int(high)


# ── 1. 智联招聘 国企筛选 (Playwright) ─────────────────────

def scrape_zhaopin_soe(cities: Optional[dict[str, str]] = None, max_pages: int = 5) -> list[SOEJob]:
    """用 Playwright 抓取智联招聘公司类型=国企的职位。"""
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    default_cities = {
        "530": "北京", "538": "上海", "763": "广州", "765": "深圳",
        "653": "杭州", "551": "成都", "749": "武汉", "599": "西安",
    }
    cities = cities or default_cities
    all_jobs: list[SOEJob] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for city_code, city_name in cities.items():
            logger.info("智联国企 — %s", city_name)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            # 反检测
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = context.new_page()

            for pg in range(1, max_pages + 1):
                # companyType=1 = 国企
                url = f"https://sou.zhaopin.com/?jl={city_code}&ct=1&p={pg}"
                try:
                    page.goto(url, timeout=20000)
                    page.wait_for_selector(".joblist-box__item", timeout=10000)
                    time.sleep(1.5)
                except Exception:
                    if pg == 1:
                        logger.warning("  %s p1 加载失败", city_name)
                    break

                html = page.content()
                jobs = _parse_zhaopin_html(html, city_name)
                if not jobs:
                    break
                all_jobs.extend(jobs)
                logger.info("  %s p%d: %d 条", city_name, pg, len(jobs))

                if len(jobs) < 15:
                    break
                time.sleep(random.uniform(1.5, 3))

            context.close()
            time.sleep(1)

        browser.close()

    logger.info("智联国企 完成: %d 条", len(all_jobs))
    return all_jobs


def _parse_zhaopin_html(html: str, fallback_city: str) -> list[SOEJob]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    items: list[SOEJob] = []

    for card in soup.select(".joblist-box__item"):
        name_el = card.select_one(".jobinfo__name")
        salary_el = card.select_one(".jobinfo__salary")
        info_items = card.select(".jobinfo__other-info-item")
        company_el = card.select_one(".companyinfo__name")
        company_tags = [t.get_text(strip=True) for t in card.select(".companyinfo__tag .joblist-box__item-tag")]
        skill_tags = [t.get_text(strip=True) for t in card.select(".jobinfo__tag .joblist-box__item-tag")]

        job_name = name_el.get_text(strip=True) if name_el else ""
        salary_raw = salary_el.get_text(strip=True) if salary_el else ""
        sal_min, sal_max = parse_salary(salary_raw)

        city = fallback_city
        experience = ""
        education = ""
        for idx, el in enumerate(info_items):
            t = el.get_text(strip=True)
            if idx == 0:
                city = t.split("·")[0]
            elif idx == 1:
                experience = t
            elif idx == 2:
                education = t

        job_url = ""
        if name_el and name_el.get("href"):
            job_url = name_el["href"]

        # 判断国企类别
        soe_cat = "国企"
        cn = (company_el.get_text(strip=True) if company_el else "").lower()
        if any(k in cn for k in ["银行", "bank"]):
            soe_cat = "国有银行"
        elif any(k in cn for k in ["中国", "国家", "中石", "中海", "中铁", "中建", "中航", "国电", "华能", "中车"]):
            soe_cat = "央企"
        elif any(k in cn for k in ["省", "市", "区"]):
            soe_cat = "地方国企"

        items.append(SOEJob(
            job_name=job_name,
            salary_raw=salary_raw,
            salary_min=sal_min,
            salary_max=sal_max,
            company_name=company_el.get_text(strip=True) if company_el else "",
            company_type=company_tags[0] if company_tags else "国企",
            industry=company_tags[2] if len(company_tags) > 2 else "",
            city=city,
            experience=experience,
            education=education,
            job_url=job_url,
            source="zhaopin",
            soe_category=soe_cat,
            tags=skill_tags,
        ))
    return items


# ── 2. 国聘网 (Playwright) ───────────────────────────────

def scrape_iguopin(max_pages: int = 10) -> list[SOEJob]:
    """抓取国聘网 iguopin.com 央企/国企招聘信息。"""
    from playwright.sync_api import sync_playwright
    from bs4 import BeautifulSoup

    all_jobs: list[SOEJob] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        for pg in range(1, max_pages + 1):
            url = f"https://www.iguopin.com/position/list?page={pg}"
            try:
                page.goto(url, timeout=20000)
                page.wait_for_selector(".position-item, .job-item, .list-item", timeout=10000)
                time.sleep(2)
            except Exception:
                logger.warning("国聘网 p%d 加载失败, 尝试备选选择器", pg)
                try:
                    page.wait_for_selector("body", timeout=5000)
                    time.sleep(2)
                except Exception:
                    break

            html = page.content()
            jobs = _parse_iguopin_html(html)
            if jobs:
                all_jobs.extend(jobs)
                logger.info("国聘网 p%d: %d 条", pg, len(jobs))
            else:
                # 尝试从页面文本提取
                text = page.inner_text("body")
                if "暂无" in text or len(text) < 200:
                    break
                logger.info("国聘网 p%d: 未解析到结构化数据, body长度=%d", pg, len(text))

            if len(jobs) < 10:
                break
            time.sleep(random.uniform(2, 4))

        context.close()
        browser.close()

    logger.info("国聘网 完成: %d 条", len(all_jobs))
    return all_jobs


def _parse_iguopin_html(html: str) -> list[SOEJob]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    items: list[SOEJob] = []

    for card in soup.select(".position-item, .job-item, .list-item, [class*='job'], [class*='position']"):
        title_el = card.select_one("a[class*='title'], h3, .job-name, .position-name, [class*='name']")
        company_el = card.select_one("[class*='company'], [class*='corp']")
        salary_el = card.select_one("[class*='salary'], [class*='money'], [class*='pay']")
        city_el = card.select_one("[class*='city'], [class*='location'], [class*='area']")

        title = title_el.get_text(strip=True) if title_el else ""
        if not title or len(title) < 2:
            continue

        salary_raw = salary_el.get_text(strip=True) if salary_el else ""
        sal_min, sal_max = parse_salary(salary_raw)

        url = ""
        if title_el and title_el.name == "a" and title_el.get("href"):
            href = title_el["href"]
            url = href if href.startswith("http") else f"https://www.iguopin.com{href}"

        items.append(SOEJob(
            job_name=title,
            salary_raw=salary_raw,
            salary_min=sal_min,
            salary_max=sal_max,
            company_name=company_el.get_text(strip=True) if company_el else "",
            company_type="国企",
            city=city_el.get_text(strip=True) if city_el else "",
            job_url=url,
            source="iguopin",
            soe_category="央企",
        ))
    return items


# ── 3. 央企集团官网招聘 (DrissionPage) ───────────────────

SOE_CAREER_SITES = {
    "中国石油": "https://zhaopin.cnpc.com.cn",
    "中国石化": "https://job.sinopec.com",
    "国家电网": "https://zhaopin.sgcc.com.cn",
    "中国移动": "https://hr.10086.cn",
    "中国电信": "https://hr.chinatelecom.com.cn",
    "中国联通": "https://hr.chinaunicom.com",
    "中国建筑": "https://job.cscec.com",
    "中国中铁": "https://job.crec.cn",
    "中国铁建": "https://job.crcc.cn",
    "中国交建": "https://hr.ccccltd.cn",
    "中国航空工业": "https://campus.avic.com",
    "中国船舶": "https://job.cssc.net.cn",
    "中国兵器工业": "https://job.norincogroup.com.cn",
    "中国航天科技": "https://zhaopin.casc.ac.cn",
    "中国华能": "https://job.chng.com.cn",
    "国家能源集团": "https://job.ceic.com",
    "中国工商银行": "https://job.icbc.com.cn",
    "中国建设银行": "https://job.ccb.com",
    "中国农业银行": "https://job.abchina.com",
    "中国银行": "https://campus.chinahr.com/boc",
}


def scrape_soe_officials() -> list[SOEJob]:
    """尝试从央企官网提取招聘信息。"""
    try:
        from DrissionPage import ChromiumPage, ChromiumOptions
    except ImportError:
        logger.warning("DrissionPage 未安装，跳过官网爬取")
        return []

    all_jobs: list[SOEJob] = []

    co = ChromiumOptions()
    co.headless()
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-dev-shm-usage")

    for company, url in SOE_CAREER_SITES.items():
        logger.info("央企官网: %s → %s", company, url)
        try:
            page = ChromiumPage(co)
            page.get(url, timeout=15)
            time.sleep(3)

            # 尝试提取职位信息
            text = page.html
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(text, "lxml")

            # 通用选择器
            job_links = soup.select("a[href*='job'], a[href*='position'], a[href*='recruit'], a[href*='zhaopin']")
            for link in job_links[:20]:
                title = link.get_text(strip=True)
                if title and len(title) > 2 and len(title) < 50:
                    all_jobs.append(SOEJob(
                        job_name=title,
                        company_name=company,
                        company_type="国企",
                        job_url=link.get("href", ""),
                        source="official",
                        soe_category="央企",
                    ))

            page.quit()
            logger.info("  %s: %d 条链接", company, min(len(job_links), 20))
        except Exception as e:
            logger.warning("  %s 失败: %s", company, str(e)[:80])
            try:
                page.quit()
            except Exception:
                pass
        time.sleep(2)

    logger.info("央企官网 完成: %d 条", len(all_jobs))
    return all_jobs


# ── 主入口 ────────────────────────────────────────────────

def main():
    all_data: list[SOEJob] = []

    # 1. 智联招聘国企数据 (主要数据源，有薪资)
    logger.info("=" * 60)
    logger.info("阶段1: 智联招聘 — 国企筛选")
    logger.info("=" * 60)
    zhaopin_jobs = scrape_zhaopin_soe(max_pages=5)
    all_data.extend(zhaopin_jobs)

    # 保存中间结果
    _save(all_data, "soe_zhaopin")

    # 2. 国聘网
    logger.info("=" * 60)
    logger.info("阶段2: 国聘网")
    logger.info("=" * 60)
    iguopin_jobs = scrape_iguopin(max_pages=10)
    all_data.extend(iguopin_jobs)

    # 3. 央企官网
    logger.info("=" * 60)
    logger.info("阶段3: 央企官网")
    logger.info("=" * 60)
    official_jobs = scrape_soe_officials()
    all_data.extend(official_jobs)

    # 保存全量
    _save(all_data, "soe_all")

    # 统计
    logger.info("=" * 60)
    logger.info("国企招聘数据爬取完成:")
    logger.info("  智联国企: %d 条", len(zhaopin_jobs))
    logger.info("  国聘网: %d 条", len(iguopin_jobs))
    logger.info("  央企官网: %d 条", len(official_jobs))
    logger.info("  总计: %d 条", len(all_data))
    with_salary = sum(1 for j in all_data if j.salary_min > 0)
    logger.info("  有薪资: %d 条", with_salary)
    logger.info("=" * 60)


def _save(jobs: list[SOEJob], name: str):
    data = [j.to_dict() for j in jobs]
    json_path = DATA_DIR / f"{name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    import pandas as pd
    csv_path = DATA_DIR / f"{name}.csv"
    pd.DataFrame(data).to_csv(csv_path, index=False, encoding="utf-8-sig")
    logger.info("保存: %s (%d 条)", json_path.name, len(data))


if __name__ == "__main__":
    main()
