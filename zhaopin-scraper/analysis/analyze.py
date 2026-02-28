"""统计分析模块 — 生成薪资分析报告"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def salary_stats_by_group(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """按指定列分组统计薪资（中位数、均值、25/75 分位数、样本量）。"""
    valid = df[df["has_salary"]].copy()
    stats = valid.groupby(group_col)["salary_avg"].agg(
        count="count",
        mean="mean",
        median="median",
        q25=lambda x: x.quantile(0.25),
        q75=lambda x: x.quantile(0.75),
        min="min",
        max="max",
    ).round(0).astype(int, errors="ignore")

    stats = stats.sort_values("median", ascending=False)
    return stats.reset_index()


def industry_salary_report(df: pd.DataFrame) -> pd.DataFrame:
    """各行业薪资统计报告。"""
    return salary_stats_by_group(df, "industry")


def city_salary_report(df: pd.DataFrame) -> pd.DataFrame:
    """各城市薪资统计报告。"""
    return salary_stats_by_group(df, "city")


def experience_salary_report(df: pd.DataFrame) -> pd.DataFrame:
    """各经验等级薪资统计报告。"""
    return salary_stats_by_group(df, "experience_std")


def education_salary_report(df: pd.DataFrame) -> pd.DataFrame:
    """各学历薪资统计报告。"""
    return salary_stats_by_group(df, "education_std")


def salary_level_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """薪资等级分布统计。"""
    order = ["5K以下", "5K-10K", "10K-15K", "15K-20K", "20K-30K", "30K-50K", "50K以上", "面议"]
    dist = df["salary_level"].value_counts().reindex(order).fillna(0).astype(int)
    total = dist.sum()
    result = pd.DataFrame({
        "salary_level": dist.index,
        "count": dist.values,
        "percentage": (dist.values / total * 100).round(1),
    })
    return result


def experience_salary_trend(df: pd.DataFrame) -> pd.DataFrame:
    """经验年限与薪资增长趋势。"""
    valid = df[df["has_salary"] & df["experience_years"].notna()].copy()
    trend = valid.groupby("experience_years")["salary_avg"].agg(
        count="count",
        median="median",
        mean="mean",
    ).round(0).astype(int, errors="ignore")

    return trend.sort_index().reset_index()


def top_paying_jobs(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """薪资最高的 N 个职位。"""
    valid = df[df["has_salary"]].copy()
    return (
        valid.nlargest(n, "salary_avg")
        [["job_name", "company_name", "city", "industry", "salary_raw", "salary_avg", "experience", "education"]]
        .reset_index(drop=True)
    )


def city_industry_heatmap_data(df: pd.DataFrame) -> pd.DataFrame:
    """城市 × 行业 的薪资中位数矩阵（用于热力图）。"""
    valid = df[df["has_salary"]].copy()
    pivot = valid.pivot_table(
        values="salary_avg",
        index="city",
        columns="industry",
        aggfunc="median",
    ).round(0)
    return pivot


def generate_full_report(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """一次性生成所有分析报告。"""
    reports = {
        "行业薪资": industry_salary_report(df),
        "城市薪资": city_salary_report(df),
        "经验薪资": experience_salary_report(df),
        "学历薪资": education_salary_report(df),
        "薪资分布": salary_level_distribution(df),
        "经验趋势": experience_salary_trend(df),
        "高薪职位TOP20": top_paying_jobs(df),
    }

    logger.info("已生成 %d 份分析报告", len(reports))
    for name, r in reports.items():
        logger.info("  %s: %d 行 × %d 列", name, len(r), len(r.columns))

    return reports
