from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from scrapy.exceptions import DropItem
except ImportError:
    class DropItem(Exception):
        """Fallback exception used when Scrapy is unavailable."""


def build_dedup_key(item: dict[str, Any]) -> str:
    url = _norm(item.get("job_url"))
    company = _norm(item.get("company_name"))
    title = _norm(item.get("job_title"))
    return "|".join((url, company, title))


class JsonlPipeline:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._fp = None

    def open_spider(self, spider) -> None:  # type: ignore[no-untyped-def]
        output_path = getattr(spider, "output_path", "data/raw/jobs_raw.jsonl")
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = path.open("w", encoding="utf-8")

    def close_spider(self, spider) -> None:  # type: ignore[no-untyped-def]
        if self._fp:
            self._fp.close()
            self._fp = None

    def process_item(self, item, spider):  # type: ignore[no-untyped-def]
        normalized = dict(item)
        key = build_dedup_key(normalized)
        if key in self._seen:
            raise DropItem(f"duplicate job record: {key}")
        self._seen.add(key)

        if not self._fp:
            raise DropItem("pipeline output file is not initialized")
        self._fp.write(json.dumps(normalized, ensure_ascii=False) + "\n")
        return item


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())

