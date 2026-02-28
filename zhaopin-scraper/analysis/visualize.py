"""数据可视化模块 — 生成薪资分析图表"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 非交互后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

import config

logger = logging.getLogger(__name__)

# ── 中文字体配置 ──────────────────────────────────────────
plt.rcParams["axes.unicode_minus"] = False

_CN_FONTS = ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]
for _f in _CN_FONTS:
    if _f in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.sans-serif"] = [_f]
        break

# 配色方案
COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
    "#4ECDC4", "#FF6B6B", "#45B7D1", "#96CEB4", "#FFEAA7",
]


def _savefig(fig: plt.Figure, name: str, output_dir: Optional[Path] = None) -> Path:
    out = (output_dir or config.OUTPUT_DIR) / f"{name}.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("图表已保存: %s", out)
    return out


# ── 1. 薪资分布直方图 ─────────────────────────────────────

def plot_salary_distribution(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """所有职位的薪资分布直方图。"""
    valid = df[df["has_salary"]]["salary_avg"].dropna()

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.hist(valid / 1000, bins=50, color=COLORS[0], edgecolor="white", alpha=0.85)
    ax.set_xlabel("月薪 (千元)", fontsize=12)
    ax.set_ylabel("职位数量", fontsize=12)
    ax.set_title("职位薪资分布", fontsize=14, fontweight="bold")
    ax.axvline(valid.median() / 1000, color=COLORS[3], linestyle="--", linewidth=1.5,
               label=f"中位数: {valid.median()/1000:.1f}K")
    ax.axvline(valid.mean() / 1000, color=COLORS[1], linestyle="--", linewidth=1.5,
               label=f"均值: {valid.mean()/1000:.1f}K")
    ax.legend(fontsize=11)
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    return _savefig(fig, "salary_distribution", output_dir)


# ── 2. 行业薪资对比条形图 ─────────────────────────────────

def plot_industry_salary(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """各行业薪资中位数对比（水平条形图）。"""
    valid = df[df["has_salary"]].copy()
    stats = valid.groupby("industry")["salary_avg"].median().sort_values()

    fig, ax = plt.subplots(figsize=(12, max(6, len(stats) * 0.5)))
    bars = ax.barh(range(len(stats)), stats.values / 1000, color=COLORS[:len(stats)], height=0.6)
    ax.set_yticks(range(len(stats)))
    ax.set_yticklabels(stats.index, fontsize=10)
    ax.set_xlabel("月薪中位数 (千元)", fontsize=12)
    ax.set_title("各行业薪资对比", fontsize=14, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    for bar, val in zip(bars, stats.values):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"{val/1000:.1f}K", va="center", fontsize=9)

    return _savefig(fig, "industry_salary", output_dir)


# ── 3. 城市薪资对比条形图 ─────────────────────────────────

def plot_city_salary(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """各城市薪资中位数对比。"""
    valid = df[df["has_salary"]].copy()
    stats = valid.groupby("city")["salary_avg"].agg(["median", "count"])
    stats = stats[stats["count"] >= 5].sort_values("median")  # 至少 5 条数据

    fig, ax = plt.subplots(figsize=(12, max(6, len(stats) * 0.45)))
    bars = ax.barh(range(len(stats)), stats["median"].values / 1000,
                   color=COLORS[0], height=0.6, alpha=0.85)
    ax.set_yticks(range(len(stats)))
    ax.set_yticklabels(stats.index, fontsize=10)
    ax.set_xlabel("月薪中位数 (千元)", fontsize=12)
    ax.set_title("各城市薪资水平对比", fontsize=14, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    for bar, val, cnt in zip(bars, stats["median"].values, stats["count"].values):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                f"{val/1000:.1f}K (n={cnt})", va="center", fontsize=9)

    return _savefig(fig, "city_salary", output_dir)


# ── 4. 经验年限与薪资增长曲线 ─────────────────────────────

def plot_experience_salary_curve(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """经验年限与薪资的关系曲线。"""
    valid = df[df["has_salary"] & df["experience_years"].notna()].copy()
    trend = valid.groupby("experience_years")["salary_avg"].agg(["median", "mean", "count"])
    trend = trend[trend["count"] >= 3].sort_index()

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(trend.index, trend["median"] / 1000, "o-", color=COLORS[0],
            linewidth=2, markersize=8, label="中位数")
    ax.plot(trend.index, trend["mean"] / 1000, "s--", color=COLORS[1],
            linewidth=1.5, markersize=6, alpha=0.7, label="均值")

    ax.fill_between(trend.index,
                    trend["median"] / 1000 * 0.8,
                    trend["median"] / 1000 * 1.2,
                    alpha=0.1, color=COLORS[0])

    ax.set_xlabel("工作经验 (年)", fontsize=12)
    ax.set_ylabel("月薪 (千元)", fontsize=12)
    ax.set_title("经验年限与薪资增长趋势", fontsize=14, fontweight="bold")
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    for x, y, n in zip(trend.index, trend["median"].values, trend["count"].values):
        ax.annotate(f"{y/1000:.0f}K\n(n={n})", (x, y / 1000),
                    textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=8, color=COLORS[0])

    return _savefig(fig, "experience_salary_curve", output_dir)


# ── 5. 学历薪资对比箱线图 ─────────────────────────────────

def plot_education_salary(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """不同学历的薪资分布箱线图。"""
    valid = df[df["has_salary"]].copy()
    edu_order = ["高中", "大专", "本科", "硕士", "博士"]
    valid = valid[valid["education_std"].isin(edu_order)]

    edu_groups = [valid[valid["education_std"] == e]["salary_avg"].dropna() / 1000 for e in edu_order]
    edu_groups = [g for g, e in zip(edu_groups, edu_order) if len(g) > 0]
    edu_labels = [e for g, e in zip(
        [valid[valid["education_std"] == e]["salary_avg"].dropna() for e in edu_order],
        edu_order
    ) if len(g) > 0]

    fig, ax = plt.subplots(figsize=(10, 6))
    bp = ax.boxplot(edu_groups, labels=edu_labels, patch_artist=True,
                    widths=0.5, showfliers=False)
    for patch, color in zip(bp["boxes"], COLORS):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("月薪 (千元)", fontsize=12)
    ax.set_title("不同学历薪资分布", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

    return _savefig(fig, "education_salary", output_dir)


# ── 6. 薪资等级饼图 ───────────────────────────────────────

def plot_salary_level_pie(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """薪资等级分布饼图。"""
    order = ["5K以下", "5K-10K", "10K-15K", "15K-20K", "20K-30K", "30K-50K", "50K以上"]
    counts = df[df["has_salary"]]["salary_level"].value_counts()
    counts = counts.reindex(order).dropna().astype(int)
    counts = counts[counts > 0]

    fig, ax = plt.subplots(figsize=(10, 8))
    wedges, texts, autotexts = ax.pie(
        counts.values,
        labels=counts.index,
        autopct="%1.1f%%",
        colors=COLORS[:len(counts)],
        startangle=90,
        pctdistance=0.8,
    )
    for t in autotexts:
        t.set_fontsize(9)
    ax.set_title("薪资等级分布", fontsize=14, fontweight="bold")

    return _savefig(fig, "salary_level_pie", output_dir)


# ── 7. 城市 × 行业 热力图 ─────────────────────────────────

def plot_city_industry_heatmap(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """城市 × 行业薪资中位数热力图。"""
    valid = df[df["has_salary"]].copy()
    pivot = valid.pivot_table(values="salary_avg", index="city", columns="industry", aggfunc="median")
    pivot = pivot.dropna(axis=0, how="all").dropna(axis=1, how="all") / 1000

    fig, ax = plt.subplots(figsize=(max(12, len(pivot.columns) * 1.2), max(8, len(pivot) * 0.5)))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=10)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.iloc[i, j]
            if pd.notna(val):
                ax.text(j, i, f"{val:.0f}K", ha="center", va="center", fontsize=8,
                        color="white" if val > pivot.values[~np.isnan(pivot.values)].mean() else "black")

    fig.colorbar(im, ax=ax, label="月薪中位数 (千元)", shrink=0.8)
    ax.set_title("城市 × 行业 薪资中位数热力图", fontsize=14, fontweight="bold")

    return _savefig(fig, "city_industry_heatmap", output_dir)


# ── 一键生成全部图表 ──────────────────────────────────────

def generate_all_charts(df: pd.DataFrame, output_dir: Optional[Path] = None) -> list[Path]:
    """生成全部可视化图表，返回文件路径列表。"""
    charts = []
    chart_funcs = [
        plot_salary_distribution,
        plot_industry_salary,
        plot_city_salary,
        plot_experience_salary_curve,
        plot_education_salary,
        plot_salary_level_pie,
        plot_city_industry_heatmap,
    ]

    for func in chart_funcs:
        try:
            path = func(df, output_dir)
            charts.append(path)
        except Exception:
            logger.exception("生成图表失败: %s", func.__name__)

    logger.info("共生成 %d / %d 张图表", len(charts), len(chart_funcs))
    return charts
