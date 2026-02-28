from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class SalaryParseResult:
    raw: str
    salary_min: int | None
    salary_max: int | None
    salary_period: str | None
    salary_months: int | None
    salary_parsed: bool


@dataclass(slots=True)
class JobRecord:
    job_title: str | None
    salary_raw: str | None
    salary_min: int | None
    salary_max: int | None
    salary_period: str | None
    salary_months: int | None
    salary_parsed: bool
    company_name: str | None
    industry: str | None
    city: str | None
    experience_req: str | None
    education_req: str | None
    job_url: str
    crawl_time: str

    @classmethod
    def from_partial(cls, payload: dict[str, Any]) -> "JobRecord":
        return cls(
            job_title=payload.get("job_title"),
            salary_raw=payload.get("salary_raw"),
            salary_min=payload.get("salary_min"),
            salary_max=payload.get("salary_max"),
            salary_period=payload.get("salary_period"),
            salary_months=payload.get("salary_months"),
            salary_parsed=bool(payload.get("salary_parsed", False)),
            company_name=payload.get("company_name"),
            industry=payload.get("industry"),
            city=payload.get("city"),
            experience_req=payload.get("experience_req"),
            education_req=payload.get("education_req"),
            job_url=payload.get("job_url", ""),
            crawl_time=payload.get("crawl_time") or now_iso(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

