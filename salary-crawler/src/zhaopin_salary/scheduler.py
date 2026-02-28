from __future__ import annotations

from pathlib import Path


def monthly_cron_line(project_root: str) -> str:
    root = Path(project_root).resolve()
    log_file = root / "logs" / "monthly.log"
    return f"0 3 1 * * cd {root} && make crawl && make clean && make report >> {log_file} 2>&1"

