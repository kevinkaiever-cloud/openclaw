from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from zhaopin_salary.salary import parse_salary

EXPERIENCE_RANGE_PATTERN = re.compile(r"(?P<low>\d+)\s*[-~至]\s*(?P<high>\d+)\s*年")
EXPERIENCE_ABOVE_PATTERN = re.compile(r"(?P<low>\d+)\s*年以上")


def parse_experience_bucket(experience_req: str | None) -> str:
    if not experience_req:
        return "unknown"

    value = experience_req.strip()
    if not value:
        return "unknown"
    if "不限" in value or "应届" in value:
        return "0-3年"

    range_match = EXPERIENCE_RANGE_PATTERN.search(value)
    if range_match:
        low = int(range_match.group("low"))
        high = int(range_match.group("high"))
        if high <= 3:
            return "0-3年"
        if low >= 5:
            return "5年以上"
        return "3-5年"

    above_match = EXPERIENCE_ABOVE_PATTERN.search(value)
    if above_match:
        low = int(above_match.group("low"))
        if low <= 3:
            return "0-3年"
        if low < 5:
            return "3-5年"
        return "5年以上"

    return "unknown"


def clean_dataset(input_path: str, csv_output: str, json_output: str) -> dict[str, int]:
    records = _load_jsonl(input_path)
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for row in records:
        record = dict(row)
        salary_result = parse_salary(record.get("salary_raw"))

        if record.get("salary_min") is None:
            record["salary_min"] = salary_result.salary_min
        if record.get("salary_max") is None:
            record["salary_max"] = salary_result.salary_max
        record["salary_period"] = record.get("salary_period") or salary_result.salary_period
        record["salary_months"] = record.get("salary_months") or salary_result.salary_months
        record["salary_parsed"] = bool(record.get("salary_parsed") or salary_result.salary_parsed)
        record["experience_bucket"] = parse_experience_bucket(record.get("experience_req"))

        key = (
            _norm(record.get("job_url")),
            _norm(record.get("company_name")),
            _norm(record.get("job_title")),
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append(record)

    _write_csv(normalized, csv_output)
    _write_json(normalized, json_output)
    return {
        "raw_rows": len(records),
        "clean_rows": len(normalized),
        "dropped_duplicates": len(records) - len(normalized),
    }


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"input file not found: {source}")
    rows: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


def _write_csv(rows: list[dict[str, Any]], output_path: str) -> None:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("缺少 pandas，请先执行 pip install -r requirements.txt") from exc

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    preferred_columns = [
        "job_title",
        "salary_raw",
        "salary_min",
        "salary_max",
        "salary_period",
        "salary_months",
        "salary_parsed",
        "company_name",
        "industry",
        "city",
        "experience_req",
        "experience_bucket",
        "education_req",
        "job_url",
        "crawl_time",
    ]
    ordered = [column for column in preferred_columns if column in df.columns]
    remain = [column for column in df.columns if column not in ordered]
    df = df[ordered + remain]
    df.to_csv(output, index=False, encoding="utf-8-sig")


def _write_json(rows: list[dict[str, Any]], output_path: str) -> None:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())

