from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from zhaopin_salary.models import now_iso

SALARY_TEXT_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*[-~至]\s*\d+(?:\.\d+)?\s*[kK千万元]?\s*(?:/|每)?\s*(?:月|年|天|小时)?"
)
EXPERIENCE_PATTERN = re.compile(
    r"(应届生|经验不限|\d+\s*[-~至]\s*\d+\s*年|\d+\s*年以上|\d+\s*年以下)"
)
EDUCATION_PATTERN = re.compile(r"(学历不限|中专|大专|本科|硕士|博士)")

LIST_CARD_SELECTORS = [
    "div[data-job-id]",
    "li[data-job-id]",
    "div[class*='joblist-item']",
    "li[class*='joblist-item']",
    "div[class*='position-item']",
    "li[class*='position-item']",
]

TITLE_SELECTORS = [
    "h1",
    "h2",
    "[class*='job-title']",
    "[class*='position-name']",
    "[class*='jobName']",
]

COMPANY_SELECTORS = [
    "[class*='company-name']",
    "[class*='companyName']",
    "a[href*='company']",
]

SALARY_SELECTORS = [
    "[class*='salary']",
    "[class*='job-salary']",
    "[class*='position-salary']",
]

CITY_SELECTORS = [
    "[class*='job-address']",
    "[class*='work-city']",
    "[class*='city']",
]

DETAIL_META_SELECTORS = [
    "[class*='job-require']",
    "[class*='job-info']",
    "[class*='summary']",
    "[class*='requirements']",
]


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(value.split())
    return collapsed.strip() or None


def parse_listing_page(html: str, source_url: str, industry: str | None, city: str | None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    records = _extract_from_json_ld(soup, source_url, industry, city)
    if records:
        return records

    cards = _extract_cards(soup)
    parsed: list[dict[str, Any]] = []
    for card in cards:
        link_tag = card.select_one("a[href]")
        job_url = None
        if isinstance(link_tag, Tag):
            href = link_tag.get("href")
            if href:
                job_url = urljoin(source_url, href)

        title = _first_text(card, ["a[title]", "[class*='job-name']", "[class*='position-name']", "h3"])
        if not title and isinstance(link_tag, Tag):
            title = normalize_text(link_tag.get_text(" ", strip=True))

        salary_raw = _first_text(card, SALARY_SELECTORS)
        if not salary_raw:
            salary_raw = _extract_salary_from_text(card.get_text(" ", strip=True))

        company_name = _first_text(card, COMPANY_SELECTORS)
        exp_req = _extract_by_pattern(card.get_text(" ", strip=True), EXPERIENCE_PATTERN)
        edu_req = _extract_by_pattern(card.get_text(" ", strip=True), EDUCATION_PATTERN)

        if job_url and title:
            parsed.append(
                {
                    "job_title": title,
                    "salary_raw": salary_raw,
                    "company_name": company_name,
                    "industry": industry,
                    "city": city,
                    "experience_req": exp_req,
                    "education_req": edu_req,
                    "job_url": job_url,
                    "crawl_time": now_iso(),
                }
            )
    return parsed


def parse_detail_page(html: str, fallback: dict[str, Any]) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    merged = dict(fallback)

    merged["job_title"] = normalize_text(merged.get("job_title")) or _first_text(soup, TITLE_SELECTORS)
    merged["company_name"] = normalize_text(merged.get("company_name")) or _first_text(soup, COMPANY_SELECTORS)

    salary_raw = normalize_text(merged.get("salary_raw")) or _first_text(soup, SALARY_SELECTORS)
    if not salary_raw:
        salary_raw = _extract_salary_from_text(soup.get_text(" ", strip=True))
    merged["salary_raw"] = salary_raw

    merged["city"] = normalize_text(merged.get("city")) or _first_text(soup, CITY_SELECTORS)

    detail_text = _collect_detail_text(soup)
    merged["experience_req"] = normalize_text(merged.get("experience_req")) or _extract_by_pattern(detail_text, EXPERIENCE_PATTERN)
    merged["education_req"] = normalize_text(merged.get("education_req")) or _extract_by_pattern(detail_text, EDUCATION_PATTERN)

    if not merged.get("industry"):
        merged["industry"] = _extract_industry_text(soup)

    merged["crawl_time"] = merged.get("crawl_time") or now_iso()
    return merged


def extract_industries_from_homepage(html: str, source_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, dict[str, str]] = {}
    for link in soup.select("a[href*='in=']"):
        href = link.get("href")
        if not href:
            continue
        query = parse_qs(urlparse(urljoin(source_url, href)).query)
        code = (query.get("in") or [None])[0]
        name = normalize_text(link.get_text(" ", strip=True))
        if code and name and code not in found:
            found[code] = {"code": code, "name": name}
    return list(found.values())


def extract_cities_from_homepage(html: str, source_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    found: dict[str, dict[str, str]] = {}
    for link in soup.select("a[href*='jl=']"):
        href = link.get("href")
        if not href:
            continue
        query = parse_qs(urlparse(urljoin(source_url, href)).query)
        code = (query.get("jl") or [None])[0]
        name = normalize_text(link.get_text(" ", strip=True))
        if code and name and code not in found:
            found[code] = {"code": code, "name": name}
    return list(found.values())


def _extract_cards(soup: BeautifulSoup) -> list[Tag]:
    for selector in LIST_CARD_SELECTORS:
        cards = soup.select(selector)
        if cards:
            return cards
    # Fallback: anchor-based pseudo cards.
    anchors = soup.select("a[href*='job']")
    return [anchor.parent if isinstance(anchor.parent, Tag) else anchor for anchor in anchors]


def _collect_detail_text(soup: BeautifulSoup) -> str:
    snippets: list[str] = []
    for selector in DETAIL_META_SELECTORS:
        for node in soup.select(selector):
            snippets.append(node.get_text(" ", strip=True))
    if not snippets:
        snippets.append(soup.get_text(" ", strip=True))
    return " ".join(snippets)


def _extract_salary_from_text(text: str) -> str | None:
    match = SALARY_TEXT_PATTERN.search(text)
    if not match:
        if "面议" in text:
            return "面议"
        return None
    return normalize_text(match.group(0))


def _extract_by_pattern(text: str, pattern: re.Pattern[str]) -> str | None:
    matched = pattern.search(text)
    if not matched:
        return None
    return normalize_text(matched.group(1))


def _extract_industry_text(soup: BeautifulSoup) -> str | None:
    candidates = [
        "[class*='industry']",
        "a[href*='industry']",
        "span[class*='trade']",
    ]
    return _first_text(soup, candidates)


def _first_text(container: Tag | BeautifulSoup, selectors: list[str]) -> str | None:
    for selector in selectors:
        node = container.select_one(selector)
        if node:
            value = normalize_text(node.get_text(" ", strip=True))
            if value:
                return value
    return None


def _extract_from_json_ld(
    soup: BeautifulSoup, source_url: str, industry: str | None, city: str | None
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for script in soup.select("script[type='application/ld+json']"):
        text = script.string or script.get_text()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        job_nodes = data if isinstance(data, list) else [data]
        for node in job_nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") != "JobPosting":
                continue
            job_url = node.get("url")
            if isinstance(job_url, str):
                job_url = urljoin(source_url, job_url)
            title = normalize_text(node.get("title")) if isinstance(node.get("title"), str) else None
            company = None
            hiring_org = node.get("hiringOrganization")
            if isinstance(hiring_org, dict):
                org_name = hiring_org.get("name")
                if isinstance(org_name, str):
                    company = normalize_text(org_name)

            loc = node.get("jobLocation")
            location_name = city
            if isinstance(loc, dict):
                address = loc.get("address")
                if isinstance(address, dict):
                    city_name = address.get("addressLocality")
                    if isinstance(city_name, str):
                        location_name = normalize_text(city_name)

            if job_url and title:
                records.append(
                    {
                        "job_title": title,
                        "salary_raw": None,
                        "company_name": company,
                        "industry": industry,
                        "city": location_name,
                        "experience_req": None,
                        "education_req": None,
                        "job_url": job_url,
                        "crawl_time": now_iso(),
                    }
                )
    return records

