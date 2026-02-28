from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


def discover_targets(homepage_url: str, output_path: str) -> dict[str, list[dict[str, str]]]:
    from zhaopin_salary.parsers import extract_cities_from_homepage, extract_industries_from_homepage

    html = _fetch_html(homepage_url)
    industries = extract_industries_from_homepage(html, homepage_url)
    cities = extract_cities_from_homepage(html, homepage_url)
    payload = {"cities": cities, "industries": industries}

    target_file = Path(output_path)
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _fetch_html(url: str, timeout: int = 20) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        data = response.read()
    return data.decode("utf-8", errors="ignore")

