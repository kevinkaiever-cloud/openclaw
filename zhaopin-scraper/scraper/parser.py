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


# ── 智联招聘额外薪资格式（"8000-15000元"） ────────────────
_SALARY_YUAN_PAT = re.compile(r"(?P<low>\d+)\s*[-~至]\s*(?P<high>\d+)\s*元")


# ── HTML 页面解析（适配实际页面结构） ─────────────────────

def parse_html_job_list(html: str) -> list[JobItem]:
    """从智联招聘搜索结果页 HTML 提取职位列表。

    适配 2024-2026 页面结构：
    - .joblist-box__item  职位卡片
    - .jobinfo__name      职位名称 (a 标签，含链接)
    - .jobinfo__salary    薪资
    - .jobinfo__other-info-item  城市 / 经验 / 学历
    - .companyinfo__name  公司名称
    - .companyinfo__tag .joblist-box__item-tag  公司类型 / 规模 / 行业
    - .jobinfo__tag .joblist-box__item-tag  技能标签
    """
    soup = BeautifulSoup(html, "lxml")
    items: list[JobItem] = []

    cards = soup.select(".joblist-box__item")
    for card in cards:
        # 职位名称 + 链接
        name_el = card.select_one(".jobinfo__name")
        job_name = name_el.get_text(strip=True) if name_el else ""
        job_url = ""
        if name_el and name_el.get("href"):
            job_url = name_el["href"]

        # 薪资
        salary_el = card.select_one(".jobinfo__salary")
        salary_raw = salary_el.get_text(strip=True) if salary_el else ""
        sal_min, sal_max, months = parse_salary(salary_raw)

        # "8000-15000元" 特殊处理
        if sal_min is None and salary_raw:
            m_yuan = _SALARY_YUAN_PAT.search(salary_raw)
            if m_yuan:
                sal_min = int(m_yuan.group("low"))
                sal_max = int(m_yuan.group("high"))
                months = 12

        # 城市 / 经验 / 学历 (jobinfo__other-info-item)
        info_items = card.select(".jobinfo__other-info-item")
        city = ""
        district = ""
        experience = ""
        education = ""
        for idx, el in enumerate(info_items):
            text = el.get_text(strip=True)
            if idx == 0:
                # 第一项是城市，可能包含 "北京·海淀·羊坊店"
                parts = text.split("·")
                city = parts[0] if parts else text
                district = "·".join(parts[1:]) if len(parts) > 1 else ""
            elif idx == 1:
                experience = text
            elif idx == 2:
                education = text

        # 公司名称
        company_el = card.select_one(".companyinfo__name")
        company_name = company_el.get_text(strip=True) if company_el else ""

        # 公司标签: 类型 / 规模 / 行业
        company_tags = [t.get_text(strip=True) for t in card.select(".companyinfo__tag .joblist-box__item-tag")]
        company_type = company_tags[0] if len(company_tags) > 0 else ""
        company_size = company_tags[1] if len(company_tags) > 1 else ""
        industry = company_tags[2] if len(company_tags) > 2 else ""

        # 技能标签
        skill_tags = [t.get_text(strip=True) for t in card.select(".jobinfo__tag .joblist-box__item-tag")]

        items.append(JobItem(
            job_name=job_name,
            salary_raw=salary_raw,
            salary_min=sal_min,
            salary_max=sal_max,
            salary_months=months,
            company_name=company_name,
            company_size=company_size,
            company_type=company_type,
            industry=industry,
            city=city,
            district=district,
            experience=experience,
            education=education,
            job_url=job_url,
            tags=skill_tags,
        ))

    return items
