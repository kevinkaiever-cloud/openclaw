from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import scrapy

from zhaopin_salary.models import JobRecord
from zhaopin_salary.parsers import parse_detail_page, parse_listing_page
from zhaopin_salary.salary import parse_salary
from zhaopin_salary.selenium_fetcher import render_dynamic_page


class ZhaopinSpider(scrapy.Spider):
    name = "zhaopin_salary"
    allowed_domains = ["sou.zhaopin.com", "jobs.zhaopin.com", "zhaopin.com"]

    def __init__(
        self,
        targets_path: str,
        output_path: str = "data/raw/jobs_raw.jsonl",
        max_pages: int = 3,
        use_selenium: bool = False,
        selenium_wait_seconds: float = 2.5,
        selenium_scroll_rounds: int = 2,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.targets_path = targets_path
        self.output_path = output_path
        self.max_pages = max(1, int(max_pages))
        self.use_selenium = bool(use_selenium)
        self.selenium_wait_seconds = float(selenium_wait_seconds)
        self.selenium_scroll_rounds = int(selenium_scroll_rounds)
        self.targets = self._load_targets(Path(targets_path))

    def start_requests(self):  # type: ignore[override]
        cities: list[dict[str, str]] = self.targets.get("cities", [])
        industries: list[dict[str, str]] = self.targets.get("industries", [])
        for city in cities:
            for industry in industries:
                for page in range(1, self.max_pages + 1):
                    query = urlencode(
                        {
                            "jl": city["code"],
                            "in": industry["code"],
                            "p": page,
                        }
                    )
                    url = f"https://sou.zhaopin.com/?{query}"
                    yield scrapy.Request(
                        url=url,
                        callback=self.parse_listing,
                        errback=self.on_error,
                        meta={
                            "city_name": city["name"],
                            "industry_name": industry["name"],
                            "page": page,
                        },
                    )

    def parse_listing(self, response: scrapy.http.Response):  # type: ignore[override]
        city_name = response.meta.get("city_name")
        industry_name = response.meta.get("industry_name")
        records = parse_listing_page(
            html=response.text,
            source_url=response.url,
            industry=industry_name,
            city=city_name,
        )

        if not records and self.use_selenium:
            self.logger.info("Selenium fallback for listing page: %s", response.url)
            dynamic_html = render_dynamic_page(
                url=response.url,
                wait_seconds=self.selenium_wait_seconds,
                scroll_rounds=self.selenium_scroll_rounds,
            )
            records = parse_listing_page(
                html=dynamic_html,
                source_url=response.url,
                industry=industry_name,
                city=city_name,
            )

        for record in records:
            job_url = record.get("job_url")
            if not job_url:
                continue
            yield response.follow(
                job_url,
                callback=self.parse_detail,
                errback=self.on_error,
                meta={"seed_item": record},
            )

    def parse_detail(self, response: scrapy.http.Response):  # type: ignore[override]
        seed_item = response.meta.get("seed_item") or {}
        detail_item = parse_detail_page(response.text, seed_item)
        salary_result = parse_salary(detail_item.get("salary_raw"))
        detail_item["salary_min"] = salary_result.salary_min
        detail_item["salary_max"] = salary_result.salary_max
        detail_item["salary_period"] = salary_result.salary_period
        detail_item["salary_months"] = salary_result.salary_months
        detail_item["salary_parsed"] = salary_result.salary_parsed

        record = JobRecord.from_partial(detail_item)
        yield record.to_dict()

    def on_error(self, failure):  # type: ignore[no-untyped-def]
        request = getattr(failure, "request", None)
        if request is not None:
            self.logger.warning("Request failed: %s (%s)", request.url, failure.value)
        else:
            self.logger.warning("Request failed: %s", failure.value)

    @staticmethod
    def _load_targets(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"targets file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("targets file must be a JSON object")
        if "cities" not in data or "industries" not in data:
            raise ValueError("targets file must include both 'cities' and 'industries'")
        return data

