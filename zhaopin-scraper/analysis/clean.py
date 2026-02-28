"""数据清洗与预处理"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

import config

logger = logging.getLogger(__name__)

# ── 经验年限标准化映射 ────────────────────────────────────
_EXP_MAP: dict[str, str] = {
    "不限": "不限",
    "无经验": "0年",
    "1年以下": "0-1年",
    "1-3年": "1-3年",
    "3-5年": "3-5年",
    "5-10年": "5-10年",
    "10年以上": "10年以上",
}

# ── 学历标准化映射 ─────────────────────────────────────────
_EDU_MAP: dict[str, str] = {
    "不限": "不限",
    "初中及以下": "初中",
    "中专/中技": "中专",
    "高中": "高中",
    "大专": "大专",
    "本科": "本科",
    "硕士": "硕士",
    "博士": "博士",
}


def load_raw_data(path: Optional[Path] = None) -> pd.DataFrame:
    """加载原始抓取数据（JSON 或 CSV）。"""
    if path is None:
        json_path = config.DATA_DIR / "zhaopin_jobs.json"
        csv_path = config.DATA_DIR / "zhaopin_jobs.csv"
        path = json_path if json_path.exists() else csv_path

    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在: {path}")

    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
    else:
        df = pd.read_csv(path, encoding=config.CSV_ENCODING)

    logger.info("加载原始数据: %d 条, 文件: %s", len(df), path)
    return df


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """对 DataFrame 执行全套清洗流程。"""
    df = df.copy()

    # 去除完全重复行
    before = len(df)
    df.drop_duplicates(subset=["job_name", "company_name", "city", "salary_raw"], inplace=True)
    logger.info("去重: %d → %d (移除 %d 条)", before, len(df), before - len(df))

    # 薪资清洗（如果 salary_min/max 为空但 salary_raw 有值，重新解析）
    from scraper.parser import parse_salary

    mask = df["salary_min"].isna() & df["salary_raw"].notna() & (df["salary_raw"] != "")
    for idx in df[mask].index:
        s_min, s_max, months = parse_salary(str(df.at[idx, "salary_raw"]))
        df.at[idx, "salary_min"] = s_min
        df.at[idx, "salary_max"] = s_max
        df.at[idx, "salary_months"] = months

    # 计算平均月薪
    df["salary_avg"] = df.apply(
        lambda r: (r["salary_min"] + r["salary_max"]) / 2
        if pd.notna(r["salary_min"]) and pd.notna(r["salary_max"])
        else None,
        axis=1,
    )

    # 计算年薪估算
    df["salary_annual_est"] = df.apply(
        lambda r: r["salary_avg"] * r.get("salary_months", 12)
        if pd.notna(r.get("salary_avg"))
        else None,
        axis=1,
    )

    # 标准化经验
    df["experience_std"] = df["experience"].map(lambda x: _standardize(x, _EXP_MAP))

    # 标准化学历
    df["education_std"] = df["education"].map(lambda x: _standardize(x, _EDU_MAP))

    # 经验数值化（取区间中点，用于绘图）
    df["experience_years"] = df["experience_std"].map(_exp_to_midpoint)

    # 薪资等级分类
    df["salary_level"] = df["salary_avg"].map(_salary_level)

    # 城市清洗（去除"市"后缀）
    df["city"] = df["city"].str.replace(r"市$", "", regex=True)

    # 去除薪资面议的行（可选，保留原始数据但标记）
    df["has_salary"] = df["salary_min"].notna()

    logger.info("清洗完成: %d 条数据, 其中 %d 条有薪资信息",
                len(df), df["has_salary"].sum())
    return df


def _standardize(val, mapping: dict[str, str]) -> str:
    if not val or pd.isna(val):
        return "不限"
    val = str(val).strip()
    for k, v in mapping.items():
        if k in val:
            return v
    return val


def _exp_to_midpoint(exp_std: str) -> Optional[float]:
    """将标准化经验转为数值中点。"""
    m = re.match(r"(\d+)-(\d+)", str(exp_std))
    if m:
        return (int(m.group(1)) + int(m.group(2))) / 2
    if "10年以上" in str(exp_std):
        return 12.0
    if exp_std == "0年":
        return 0.0
    return None


def _salary_level(avg: Optional[float]) -> str:
    if avg is None or pd.isna(avg):
        return "面议"
    if avg < 5000:
        return "5K以下"
    if avg < 10000:
        return "5K-10K"
    if avg < 15000:
        return "10K-15K"
    if avg < 20000:
        return "15K-20K"
    if avg < 30000:
        return "20K-30K"
    if avg < 50000:
        return "30K-50K"
    return "50K以上"


def save_clean_data(df: pd.DataFrame, name: str = "zhaopin_clean") -> tuple[Path, Path]:
    """保存清洗后的数据为 CSV 和 JSON。"""
    csv_path = config.DATA_DIR / f"{name}.csv"
    json_path = config.DATA_DIR / f"{name}.json"

    df.to_csv(csv_path, index=False, encoding=config.CSV_ENCODING)
    df.to_json(json_path, orient="records", force_ascii=False, indent=config.JSON_INDENT)

    logger.info("清洗数据已保存: %s, %s", csv_path, json_path)
    return csv_path, json_path
