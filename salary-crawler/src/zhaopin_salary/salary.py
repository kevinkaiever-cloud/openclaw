from __future__ import annotations

import re
from typing import Final

from zhaopin_salary.models import SalaryParseResult

SALARY_NEGOTIABLE_KEYWORDS: Final[tuple[str, ...]] = (
    "面议",
    "薪资面议",
    "保密",
    "待定",
)

RANGE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<low>\d+(?:\.\d+)?)\s*(?P<unit_low>[kK千万元]?)\s*[-~至]\s*"
    r"(?P<high>\d+(?:\.\d+)?)\s*(?P<unit_high>[kK千万元]?)\s*(?:/|每)?\s*(?P<period>月|年|天|小时)?"
)
SINGLE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>[kK千万元]?)\s*(?:/|每)?\s*(?P<period>月|年|天|小时)?"
)
MONTHS_PATTERN: Final[re.Pattern[str]] = re.compile(r"[·\.\s]?(?P<months>\d{1,2})\s*薪")


def parse_salary(salary_raw: str | None) -> SalaryParseResult:
    raw = (salary_raw or "").strip()
    if not raw:
        return SalaryParseResult(raw="", salary_min=None, salary_max=None, salary_period=None, salary_months=None, salary_parsed=False)

    if any(keyword in raw for keyword in SALARY_NEGOTIABLE_KEYWORDS):
        return SalaryParseResult(
            raw=raw,
            salary_min=None,
            salary_max=None,
            salary_period=None,
            salary_months=_extract_salary_months(raw),
            salary_parsed=False,
        )

    months = _extract_salary_months(raw)
    range_match = RANGE_PATTERN.search(raw)
    if range_match:
        low = float(range_match.group("low"))
        high = float(range_match.group("high"))
        unit = range_match.group("unit_high") or range_match.group("unit_low") or ""
        period = range_match.group("period")
        salary_min = _to_monthly_int(low, unit, period)
        salary_max = _to_monthly_int(high, unit, period)
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            salary_min, salary_max = salary_max, salary_min
        return SalaryParseResult(
            raw=raw,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_period=_normalize_period(period),
            salary_months=months,
            salary_parsed=salary_min is not None and salary_max is not None,
        )

    single_match = SINGLE_PATTERN.search(raw)
    if single_match:
        value = float(single_match.group("value"))
        unit = single_match.group("unit") or ""
        period = single_match.group("period")
        monthly = _to_monthly_int(value, unit, period)
        return SalaryParseResult(
            raw=raw,
            salary_min=monthly,
            salary_max=monthly,
            salary_period=_normalize_period(period),
            salary_months=months,
            salary_parsed=monthly is not None,
        )

    return SalaryParseResult(raw=raw, salary_min=None, salary_max=None, salary_period=None, salary_months=months, salary_parsed=False)


def _extract_salary_months(raw: str) -> int | None:
    matched = MONTHS_PATTERN.search(raw)
    if not matched:
        return 12
    months = int(matched.group("months"))
    if 1 <= months <= 24:
        return months
    return 12


def _unit_multiplier(unit: str) -> float:
    unit = unit.lower()
    if unit in {"k", "千"}:
        return 1000.0
    if unit == "万":
        return 10000.0
    if unit in {"元", ""}:
        return 1.0
    return 1.0


def _normalize_period(period: str | None) -> str:
    if period == "年":
        return "yearly"
    if period == "月" or period is None:
        return "monthly"
    if period == "天":
        return "daily"
    if period == "小时":
        return "hourly"
    return "monthly"


def _to_monthly_int(value: float, unit: str, period: str | None) -> int | None:
    absolute_value = value * _unit_multiplier(unit)
    if absolute_value <= 0:
        return None

    if period in {None, "月"}:
        monthly = absolute_value
    elif period == "年":
        monthly = absolute_value / 12.0
    elif period == "天":
        monthly = absolute_value * 21.75
    elif period == "小时":
        monthly = absolute_value * 174.0
    else:
        monthly = absolute_value

    return int(round(monthly))

