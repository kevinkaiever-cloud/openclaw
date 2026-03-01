#!/usr/bin/env python3
"""对按关键词抓取的数据进行清洗、分析和可视化。"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("analyze")

plt.rcParams["axes.unicode_minus"] = False
for _f in ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]:
    if _f in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.sans-serif"] = [_f]
        break

COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
    "#4ECDC4", "#FF6B6B", "#45B7D1", "#96CEB4", "#FFEAA7",
]


def load_and_clean() -> pd.DataFrame:
    path = config.DATA_DIR / "zhaopin_keywords.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    logger.info("加载: %d 条", len(df))

    # 去重
    before = len(df)
    df.drop_duplicates(subset=["job_name", "company_name", "city", "salary_raw"], inplace=True)
    logger.info("去重: %d → %d", before, len(df))

    # 薪资处理
    from scraper.parser import parse_salary
    mask = df["salary_min"].isna() & df["salary_raw"].notna() & (df["salary_raw"] != "")
    for idx in df[mask].index:
        s_min, s_max, months = parse_salary(str(df.at[idx, "salary_raw"]))
        df.at[idx, "salary_min"] = s_min
        df.at[idx, "salary_max"] = s_max
        df.at[idx, "salary_months"] = months

    df["salary_avg"] = df.apply(
        lambda r: (r["salary_min"] + r["salary_max"]) / 2
        if pd.notna(r["salary_min"]) and pd.notna(r["salary_max"])
        else None, axis=1)
    df["has_salary"] = df["salary_min"].notna()
    df["city"] = df["city"].str.replace(r"市$", "", regex=True)

    logger.info("清洗完成: %d 条, 有薪资 %d 条", len(df), df["has_salary"].sum())
    return df


def keyword_salary_table(df: pd.DataFrame) -> pd.DataFrame:
    """每个搜索关键词的薪资统计。"""
    valid = df[df["has_salary"]].copy()
    stats = valid.groupby("search_keyword")["salary_avg"].agg(
        样本数="count",
        平均薪资="mean",
        中位数="median",
        最低="min",
        最高="max",
    ).round(0).astype(int, errors="ignore")
    stats = stats.sort_values("中位数", ascending=False).reset_index()
    stats.rename(columns={"search_keyword": "搜索关键词"}, inplace=True)
    return stats


def save_fig(fig, name):
    out = config.OUTPUT_DIR / f"{name}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("图表: %s", out)
    return out


def plot_top_bottom_salary(df: pd.DataFrame):
    """薪资最高/最低的职位关键词 TOP 20。"""
    valid = df[df["has_salary"]].copy()
    kw_median = valid.groupby("search_keyword")["salary_avg"].agg(["median", "count"])
    kw_median = kw_median[kw_median["count"] >= 3]

    # TOP 20
    top = kw_median.nlargest(25, "median")
    fig, ax = plt.subplots(figsize=(14, 10))
    bars = ax.barh(range(len(top)), top["median"].values / 1000, color=COLORS[0], height=0.6)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top.index, fontsize=9)
    ax.set_xlabel("月薪中位数 (千元)", fontsize=12)
    ax.set_title("薪资最高的 25 个岗位", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, (_, row) in zip(bars, top.iterrows()):
        ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                f"{row['median']/1000:.1f}K (n={int(row['count'])})", va="center", fontsize=8)
    save_fig(fig, "kw_top25_salary")

    # BOTTOM 20
    bottom = kw_median.nsmallest(25, "median")
    fig, ax = plt.subplots(figsize=(14, 10))
    bars = ax.barh(range(len(bottom)), bottom["median"].values / 1000, color=COLORS[3], height=0.6)
    ax.set_yticks(range(len(bottom)))
    ax.set_yticklabels(bottom.index, fontsize=9)
    ax.set_xlabel("月薪中位数 (千元)", fontsize=12)
    ax.set_title("薪资最低的 25 个岗位", fontsize=14, fontweight="bold")
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    for bar, (_, row) in zip(bars, bottom.iterrows()):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{row['median']/1000:.1f}K (n={int(row['count'])})", va="center", fontsize=8)
    save_fig(fig, "kw_bottom25_salary")


def plot_salary_distribution_by_category(df: pd.DataFrame):
    """按职位类别(AI/传统/蓝领)分类的薪资分布。"""
    valid = df[df["has_salary"]].copy()

    def categorize(kw):
        kw = str(kw)
        if any(t in kw for t in ["AI", "AIGC", "算法", "机器学习", "NLP", "计算机视觉", "自动驾驶",
                                  "MLOps", "多模态", "联邦学习", "智能体", "数字人", "虚拟人"]):
            return "AI/科技前沿"
        if any(t in kw for t in ["工人", "司机", "工", "焊", "维修", "搬运", "收银", "洗车",
                                  "厨师", "服务员", "保安", "农", "渔", "矿", "养殖"]):
            return "蓝领/体力劳动"
        if any(t in kw for t in ["经理", "总监", "顾问", "分析师", "架构师", "产品"]):
            return "管理/专业"
        return "其他白领"

    valid["category"] = valid["search_keyword"].map(categorize)

    fig, ax = plt.subplots(figsize=(12, 6))
    cats = ["AI/科技前沿", "管理/专业", "其他白领", "蓝领/体力劳动"]
    cat_data = [valid[valid["category"] == c]["salary_avg"].dropna() / 1000 for c in cats]
    cat_data = [d for d, c in zip(cat_data, cats) if len(d) > 0]
    cat_labels = [c for d, c in zip(
        [valid[valid["category"] == c]["salary_avg"].dropna() for c in cats], cats) if len(d) > 0]

    bp = ax.boxplot(cat_data, labels=cat_labels, patch_artist=True, widths=0.5, showfliers=False)
    for patch, color in zip(bp["boxes"], COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("月薪 (千元)", fontsize=12)
    ax.set_title("不同职业类型薪资对比", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, "kw_category_salary")


def plot_all_keywords_scatter(df: pd.DataFrame):
    """所有关键词薪资中位数散点图。"""
    valid = df[df["has_salary"]].copy()
    kw_stats = valid.groupby("search_keyword")["salary_avg"].agg(["median", "count"])
    kw_stats = kw_stats[kw_stats["count"] >= 3].sort_values("median", ascending=False)

    fig, ax = plt.subplots(figsize=(16, 10))
    x = range(len(kw_stats))
    scatter = ax.scatter(x, kw_stats["median"] / 1000, s=kw_stats["count"] * 3,
                         c=kw_stats["median"], cmap="RdYlGn", alpha=0.7, edgecolors="gray", linewidth=0.5)

    # 标注最高 & 最低 10 个
    for i, (kw, row) in enumerate(kw_stats.head(10).iterrows()):
        ax.annotate(kw, (list(kw_stats.index).index(kw), row["median"] / 1000),
                    fontsize=7, rotation=30, ha="left")
    for i, (kw, row) in enumerate(kw_stats.tail(10).iterrows()):
        ax.annotate(kw, (list(kw_stats.index).index(kw), row["median"] / 1000),
                    fontsize=7, rotation=30, ha="left")

    fig.colorbar(scatter, ax=ax, label="中位数月薪 (元)", shrink=0.6)
    ax.set_xlabel("岗位排名（按薪资降序）", fontsize=12)
    ax.set_ylabel("月薪中位数 (千元)", fontsize=12)
    ax.set_title("192 个岗位薪资中位数全景图", fontsize=14, fontweight="bold")
    ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)
    save_fig(fig, "kw_all_scatter")


def main():
    df = load_and_clean()

    # 保存清洗数据
    df.to_csv(config.DATA_DIR / "zhaopin_keywords_clean.csv", index=False, encoding=config.CSV_ENCODING)
    logger.info("清洗数据已保存")

    # 关键词薪资表
    kw_table = keyword_salary_table(df)
    kw_table.to_csv(config.OUTPUT_DIR / "keyword_salary_table.csv", index=False, encoding=config.CSV_ENCODING)
    logger.info("关键词薪资表已保存")

    # 保存 Excel
    with pd.ExcelWriter(config.OUTPUT_DIR / "keyword_salary_report.xlsx", engine="openpyxl") as writer:
        kw_table.to_excel(writer, sheet_name="关键词薪资", index=False)

        # 按城市汇总
        valid = df[df["has_salary"]]
        city_kw = valid.groupby(["search_keyword", "city"])["salary_avg"].median().round(0).unstack()
        city_kw.to_excel(writer, sheet_name="关键词×城市")

    # 打印概要
    print("\n" + "=" * 80)
    print("  192 个岗位关键词薪资排名（中位数降序）")
    print("=" * 80)
    print(kw_table.to_string(index=False))

    # 生成图表
    plot_top_bottom_salary(df)
    plot_salary_distribution_by_category(df)
    plot_all_keywords_scatter(df)

    # 汇总统计
    print("\n" + "=" * 60)
    print("  数据概览")
    print("=" * 60)
    print(f"  总职位数: {len(df)}")
    print(f"  有薪资: {df['has_salary'].sum()}")
    print(f"  覆盖关键词: {df['search_keyword'].nunique()}")
    print(f"  覆盖城市: {df['city'].nunique()}")
    print(f"  覆盖公司: {df['company_name'].nunique()}")
    print(f"  全局薪资中位数: {df[df['has_salary']]['salary_avg'].median():.0f} 元/月")


if __name__ == "__main__":
    main()
