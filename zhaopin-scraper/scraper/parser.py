"""数据解析工具 — 从原始 HTML / JSON 提取结构化职位数据"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class JobItem:
    """单条职位数据"""

    job_name: str = ""
    salary_raw: str = ""                # 原始薪资文本, 如 "8K-15K·13薪"
    salary_min: Optional[int] = None    # 解析后最低月薪 (元)
    salary_max: Optional[int] = None    # 解析后最高月薪 (元)
    salary_months: int = 12             # 年薪月数
    company_name: str = ""
    company_size: str = ""
    company_type: str = ""
    industry: str = ""
    city: str = ""
    district: str = ""
    experience: str = ""
    education: str = ""
    job_type: str = ""                  # 全职/兼职
    job_url: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ── 薪资解析 ──────────────────────────────────────────────

# 支持格式:
#   "8K-15K"  "8k-15k/月"  "8千-1.5万/月"  "20万-30万/年"
#   "8K-15K·13薪"  "面议"
_SALARY_PAT = re.compile(
    r"(?P<low>[\d.]+)\s*(?P<low_unit>[kK千万]?)\s*[-~至]\s*"
    r"(?P<high>[\d.]+)\s*(?P<high_unit>[kK千万]?)",
)
_MONTHS_PAT = re.compile(r"(\d+)\s*薪")
_YEARLY_PAT = re.compile(r"/\s*年")


def _unit_multiplier(unit: str) -> int:
    if unit in ("k", "K", "千"):
        return 1_000
    if unit == "万":
        return 10_000
    return 1


def parse_salary(raw: str) -> tuple[Optional[int], Optional[int], int]:
    """解析薪资字符串 → (min_monthly, max_monthly, months)

    返回的 min/max 均为 **月薪**（元），months 为年薪月数。
    无法解析时返回 (None, None, 12)。
    """
    if not raw or "面议" in raw:
        return None, None, 12

    m = _SALARY_PAT.search(raw)
    if not m:
        return None, None, 12

    low = float(m.group("low"))
    high = float(m.group("high"))
    low *= _unit_multiplier(m.group("low_unit") or m.group("high_unit"))
    high *= _unit_multiplier(m.group("high_unit") or m.group("low_unit"))

    months = 12
    mm = _MONTHS_PAT.search(raw)
    if mm:
        months = int(mm.group(1))

    # "XX万/年" 需换算为月薪
    if _YEARLY_PAT.search(raw):
        low = low / 12
        high = high / 12

    return int(low), int(high), months


# ── JSON API 响应解析 ─────────────────────────────────────

def parse_api_results(data: dict) -> list[JobItem]:
    """解析智联招聘搜索 API 返回的 JSON，提取职位列表。"""
    items: list[JobItem] = []
    results = data.get("data", {}).get("results", [])
    if not results:
        results = data.get("data", {}).get("list", [])

    for r in results:
        salary_raw = r.get("salary", "") or r.get("salaryReal", "")
        sal_min, sal_max, months = parse_salary(salary_raw)

        city_info = r.get("city", {})
        city_name = ""
        district = ""
        if isinstance(city_info, dict):
            items_list = city_info.get("items", [])
            if items_list:
                city_name = items_list[0].get("name", "")
                if len(items_list) > 1:
                    district = items_list[1].get("name", "")
        elif isinstance(city_info, str):
            city_name = city_info

        company = r.get("company", {}) or {}

        welfare = r.get("welfare", []) or []
        if isinstance(welfare, str):
            welfare = [welfare]

        item = JobItem(
            job_name=r.get("jobName", "") or r.get("name", ""),
            salary_raw=salary_raw,
            salary_min=sal_min,
            salary_max=sal_max,
            salary_months=months,
            company_name=company.get("name", "") if isinstance(company, dict) else str(company),
            company_size=company.get("size", {}).get("name", "") if isinstance(company, dict) else "",
            company_type=company.get("type", {}).get("name", "") if isinstance(company, dict) else "",
            industry=_extract_industry(company) if isinstance(company, dict) else "",
            city=city_name,
            district=district,
            experience=_safe_name(r.get("workingExp", {})),
            education=_safe_name(r.get("eduLevel", {})),
            job_type=_safe_name(r.get("jobType", {})),
            job_url=r.get("positionURL", "") or r.get("url", ""),
            tags=welfare,
        )
        items.append(item)

    return items


def _safe_name(obj) -> str:
    if isinstance(obj, dict):
        return obj.get("name", "")
    return str(obj) if obj else ""


def _extract_industry(company: dict) -> str:
    ind = company.get("industry", {})
    if isinstance(ind, dict):
        return ind.get("name", "")
    if isinstance(ind, str):
        return ind
    return ""


# ── HTML 页面解析（备用方案） ─────────────────────────────

def parse_html_job_list(html: str) -> list[JobItem]:
    """从搜索结果 HTML 页面提取职位列表（当 API 不可用时的备用方案）。"""
    soup = BeautifulSoup(html, "lxml")
    items: list[JobItem] = []

    # 智联招聘搜索结果页通常使用 .joblist-box__item 或 .positionlist 类名
    cards = soup.select(".joblist-box__item, .contentpile__content__wrapper, .positionlist .positionlist-cell")
    for card in cards:
        link = card.select_one("a[href*='jobs']")
        title_el = card.select_one(".iteminfo__line1__jobname, .contentpile__content__wrapper__cpt span, .cell__title")
        salary_el = card.select_one(".iteminfo__line1__jobname__salary, .contentpile__content__wrapper__cpt__money, .cell__salary")
        company_el = card.select_one(".iteminfo__line1__companyname a, .contentpile__content__wrapper__cname, .cell__company")
        city_el = card.select_one(".iteminfo__line2__jobdesc span:first-child, .contentpile__content__wrapper__unit span:first-child")
        exp_el = card.select_one(".iteminfo__line2__jobdesc span:nth-child(2)")
        edu_el = card.select_one(".iteminfo__line2__jobdesc span:nth-child(3)")

        title = title_el.get_text(strip=True) if title_el else ""
        salary_raw = salary_el.get_text(strip=True) if salary_el else ""
        sal_min, sal_max, months = parse_salary(salary_raw)

        items.append(JobItem(
            job_name=title,
            salary_raw=salary_raw,
            salary_min=sal_min,
            salary_max=sal_max,
            salary_months=months,
            company_name=company_el.get_text(strip=True) if company_el else "",
            city=city_el.get_text(strip=True) if city_el else "",
            experience=exp_el.get_text(strip=True) if exp_el else "",
            education=edu_el.get_text(strip=True) if edu_el else "",
            job_url=link["href"] if link and link.get("href") else "",
        ))

    return items
