#!/usr/bin/env python3
"""高考专业 K 线图分析引擎

基于「报考热度（供给端）」和「就业市场需求（需求端）」构建专业价值指数，
以类似股票 K 线的形式呈现各专业的历年走势和当前状态。

数据源:
- 掌上高考 API: 专业关注度(view_total/view_month)、毕业薪资(salaryavg/fivesalaryavg)
- 智联招聘: 岗位数量、薪资中位数（就业需求端）

K 线定义:
- 开盘价 = 年初综合指数
- 收盘价 = 年末综合指数
- 最高价 = 年内峰值
- 最低价 = 年内谷值
- 阳线(红) = 指数上升（专业升温）
- 阴线(绿) = 指数下降（专业降温）
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch

from gaokao import config as gk_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kline")

plt.rcParams["axes.unicode_minus"] = False
for _f in ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "DejaVu Sans"]:
    if _f in {f.name for f in fm.fontManager.ttflist}:
        plt.rcParams["font.sans-serif"] = [_f]
        break


# ── 数据加载 ──────────────────────────────────────────────

def load_major_data() -> pd.DataFrame:
    path = gk_config.DATA_DIR / "all_majors.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    for col in ["fivesalaryavg", "salaryavg", "view_total", "view_month", "view_week", "boy_rate", "girl_rate"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


def load_job_data() -> pd.DataFrame:
    """加载已有的智联招聘数据。"""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import config as root_config
    path = root_config.DATA_DIR / "zhaopin_keywords.json"
    if not path.exists():
        return pd.DataFrame()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df["salary_avg"] = df.apply(
        lambda r: (r["salary_min"] + r["salary_max"]) / 2
        if pd.notna(r.get("salary_min")) and pd.notna(r.get("salary_max"))
        else None, axis=1)
    return df


# ── 专业价值指数计算 ──────────────────────────────────────

def compute_major_index(majors_df: pd.DataFrame, jobs_df: pd.DataFrame) -> pd.DataFrame:
    """计算每个专业的综合价值指数。

    综合指数 = 0.35 × 薪资指数 + 0.30 × 需求指数 + 0.20 × 热度指数 + 0.15 × 性价比指数

    - 薪资指数: 毕业5年薪资的百分位排名
    - 需求指数: 对应岗位的招聘数量百分位
    - 热度指数: 报考关注度的百分位（反向——热度越高竞争越大，压低指数）
    - 性价比指数: 薪资/热度 比值的百分位
    """
    df = majors_df.copy()

    # 薪资指数
    df["salary_score"] = df["fivesalaryavg"].rank(pct=True) * 100
    df.loc[df["fivesalaryavg"] == 0, "salary_score"] = 50  # 无数据取中间值

    # 需求指数（从智联数据匹配 + 掌上高考关注度综合判定）
    job_demand = _compute_job_demand(df, jobs_df)
    df = df.merge(job_demand, on="name", how="left")

    # 需求打分: 有就业匹配数据的走智联数据排名，无匹配的用关注度作代理
    df["demand_raw"] = df["job_count"].astype(float)
    no_match = df["job_count"] == 0
    if no_match.any():
        df.loc[no_match, "demand_raw"] = (df.loc[no_match, "view_total"].astype(float) / 1000).clip(upper=30)
    df["demand_score"] = df["demand_raw"].rank(pct=True) * 100

    # 热度指数: 适度竞争是好事，过热才降分
    # 用倒U型：关注度在 30-70 百分位最优，极高或极低都扣分
    pop_pct = df["view_total"].rank(pct=True)
    df["popularity_score"] = 100 - (abs(pop_pct - 0.5) * 200).clip(upper=100)
    df.loc[df["view_total"] == 0, "popularity_score"] = 20

    # 性价比指数: 薪资/关注度 但极冷门（关注度极低）不应获利
    df["value_ratio"] = df["fivesalaryavg"] / (df["view_total"].clip(lower=5000))
    df["value_ratio_score"] = df["value_ratio"].rank(pct=True) * 100
    # 极冷门惩罚: 关注度低于 10 百分位的打 5 折
    cold_threshold = df["view_total"].quantile(0.10)
    df.loc[df["view_total"] < cold_threshold, "value_ratio_score"] *= 0.5

    # 综合指数
    df["composite_index"] = (
        0.40 * df["salary_score"]
        + 0.30 * df["demand_score"]
        + 0.15 * df["popularity_score"]
        + 0.15 * df["value_ratio_score"]
    ).round(1)

    # 额外奖励: 有真实就业匹配数据的专业加 5 分（数据可信度高）
    df.loc[df["job_count"] > 0, "composite_index"] += 5
    df["composite_index"] = df["composite_index"].clip(upper=99)

    # 就业薪资中位数（从智联数据）
    df["market_salary"] = df["market_salary_median"].fillna(df["fivesalaryavg"])

    return df.sort_values("composite_index", ascending=False)


def _compute_job_demand(majors_df: pd.DataFrame, jobs_df: pd.DataFrame) -> pd.DataFrame:
    """为每个专业匹配就业市场数据。"""
    if jobs_df.empty:
        return pd.DataFrame({"name": majors_df["name"], "job_count": 0, "market_salary_median": None})

    major_job_map = gk_config.MAJOR_TO_JOBS
    rows = []
    for _, major in majors_df.iterrows():
        name = major["name"]
        keywords = major_job_map.get(name, [name])
        matched = jobs_df[jobs_df["search_keyword"].isin(keywords)]
        count = len(matched)
        sal_median = matched["salary_avg"].median() if len(matched) > 0 else None
        rows.append({"name": name, "job_count": count, "market_salary_median": sal_median})
    return pd.DataFrame(rows)


# ── K 线数据生成（模拟历年走势） ──────────────────────────

def generate_kline_data(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """基于当前指数和趋势因子，生成 2018-2026 年 K 线数据。

    趋势模型:
    - AI/芯片/新能源类: 近年快速上升
    - 土木/建筑: 近年下降
    - 金融/法律: 波动
    - 医学: 稳步上升
    - 传统工科: 平稳
    """
    years = list(range(2018, 2027))
    kline_data = {}

    # 趋势标签
    trend_tags = {
        "快速上升": ["计算机", "人工智能", "软件", "数据", "电子信息", "集成电路", "微电子",
                   "智能", "机器人", "物联网", "网络安全", "自动化", "新能源"],
        "稳步上升": ["临床医学", "口腔", "药学", "护理", "中医", "生物医学", "动物医学"],
        "近年下降": ["土木", "建筑学", "环境设计"],
        "波动震荡": ["金融", "会计", "经济", "法学", "工商管理"],
        "缓慢下降": ["农学", "旅游", "学前教育"],
    }

    for _, row in df.iterrows():
        name = row["name"]
        current = row["composite_index"]

        # 确定趋势类型
        trend = "平稳"
        for t, keywords in trend_tags.items():
            if any(k in name for k in keywords):
                trend = t
                break

        kline = _simulate_kline(name, current, trend, years)
        kline_data[name] = kline

    return kline_data


def _simulate_kline(
    name: str, current_index: float, trend: str, years: list[int]
) -> pd.DataFrame:
    """模拟单个专业的历年 K 线数据。"""
    np.random.seed(hash(name) % (2**31))

    n = len(years)
    # 趋势因子
    if trend == "快速上升":
        base_trend = np.linspace(-25, 0, n) + np.random.normal(0, 3, n)
    elif trend == "稳步上升":
        base_trend = np.linspace(-15, 0, n) + np.random.normal(0, 2, n)
    elif trend == "近年下降":
        base_trend = np.linspace(15, 0, n) + np.random.normal(0, 4, n)
    elif trend == "波动震荡":
        base_trend = np.sin(np.linspace(0, 3 * np.pi, n)) * 10 + np.random.normal(0, 3, n)
    elif trend == "缓慢下降":
        base_trend = np.linspace(10, 0, n) + np.random.normal(0, 2, n)
    else:  # 平稳
        base_trend = np.random.normal(0, 3, n)

    indices = current_index + base_trend
    indices = np.clip(indices, 5, 95)

    rows = []
    for i, year in enumerate(years):
        close = indices[i]
        volatility = np.random.uniform(2, 8)
        open_val = close + np.random.uniform(-volatility, volatility)
        high = max(open_val, close) + np.random.uniform(1, volatility)
        low = min(open_val, close) - np.random.uniform(1, volatility)
        high = min(high, 95)
        low = max(low, 5)
        volume = int(np.random.uniform(500, 5000))

        rows.append({
            "year": year,
            "open": round(open_val, 1),
            "close": round(close, 1),
            "high": round(high, 1),
            "low": round(low, 1),
            "volume": volume,
        })

    return pd.DataFrame(rows)


# ── K 线图绘制 ────────────────────────────────────────────

def plot_kline_single(name: str, kline_df: pd.DataFrame, current_info: dict,
                      output_dir: Optional[Path] = None) -> Path:
    """绘制单个专业的 K 线图。"""
    out = (output_dir or gk_config.OUTPUT_DIR)
    out.mkdir(exist_ok=True)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), height_ratios=[3, 1],
                                     gridspec_kw={"hspace": 0.08})

    years = kline_df["year"].values
    opens = kline_df["open"].values
    closes = kline_df["close"].values
    highs = kline_df["high"].values
    lows = kline_df["low"].values
    volumes = kline_df["volume"].values

    # K 线主图
    for i, year in enumerate(years):
        color = "#E74C3C" if closes[i] >= opens[i] else "#27AE60"
        # 实体
        body_bottom = min(opens[i], closes[i])
        body_height = abs(closes[i] - opens[i])
        ax1.bar(i, body_height, bottom=body_bottom, width=0.6,
                color=color, edgecolor=color, linewidth=0.8)
        # 上下影线
        ax1.vlines(i, lows[i], highs[i], color=color, linewidth=1)

    # 均线
    if len(closes) >= 3:
        ma3 = pd.Series(closes).rolling(3).mean()
        ax1.plot(range(len(years)), ma3, color="#3498DB", linewidth=1.5, label="MA3", alpha=0.8)
    if len(closes) >= 5:
        ma5 = pd.Series(closes).rolling(5).mean()
        ax1.plot(range(len(years)), ma5, color="#F39C12", linewidth=1.5, label="MA5", alpha=0.8)

    ax1.set_xlim(-0.5, len(years) - 0.5)
    ax1.set_xticks(range(len(years)))
    ax1.set_xticklabels([])
    ax1.set_ylabel("专业价值指数", fontsize=11)
    ax1.legend(fontsize=9)
    ax1.grid(alpha=0.2)
    ax1.spines[["top", "right"]].set_visible(False)

    # 标题信息
    sal = current_info.get("fivesalaryavg", 0)
    sal_str = f"{sal:,}" if sal else "暂无"
    idx = current_info.get("composite_index", 0)
    change = closes[-1] - closes[-2] if len(closes) >= 2 else 0
    change_pct = change / closes[-2] * 100 if len(closes) >= 2 and closes[-2] > 0 else 0
    change_color = "#E74C3C" if change >= 0 else "#27AE60"
    change_sym = "+" if change >= 0 else ""

    title = f"{name}  综合指数 {idx:.1f}  {change_sym}{change:.1f} ({change_sym}{change_pct:.1f}%)"
    ax1.set_title(title, fontsize=14, fontweight="bold", color=change_color, loc="left")

    info_text = (
        f"5年薪资: {sal_str}元 | "
        f"学科: {current_info.get('level2_name', '')} | "
        f"类别: {current_info.get('level3_name', '')} | "
        f"男女比: {current_info.get('boy_rate', 0)}:{current_info.get('girl_rate', 0)}"
    )
    ax1.text(0.99, 0.97, info_text, transform=ax1.transAxes, fontsize=8,
             va="top", ha="right", color="gray")

    # 成交量（关注度）
    for i in range(len(years)):
        color = "#E74C3C" if closes[i] >= opens[i] else "#27AE60"
        ax2.bar(i, volumes[i], width=0.6, color=color, alpha=0.6)

    ax2.set_xlim(-0.5, len(years) - 0.5)
    ax2.set_xticks(range(len(years)))
    ax2.set_xticklabels(years, fontsize=9)
    ax2.set_ylabel("关注度", fontsize=10)
    ax2.grid(alpha=0.2)
    ax2.spines[["top", "right"]].set_visible(False)

    safe_name = name.replace("/", "_").replace("\\", "_")
    filepath = out / f"kline_{safe_name}.png"
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return filepath


def plot_kline_grid(top_majors: pd.DataFrame, kline_data: dict,
                    title: str = "热门专业 K 线走势",
                    output_dir: Optional[Path] = None) -> Path:
    """多专业 K 线图网格（4x5 或自适应）。"""
    n = len(top_majors)
    cols = 4
    rows = math.ceil(n / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(24, rows * 4))
    if rows == 1:
        axes = axes.reshape(1, -1)

    for idx, (_, row) in enumerate(top_majors.iterrows()):
        r, c = idx // cols, idx % cols
        ax = axes[r][c]
        name = row["name"]

        if name not in kline_data:
            ax.set_visible(False)
            continue

        kl = kline_data[name]
        years = kl["year"].values
        opens = kl["open"].values
        closes = kl["close"].values
        highs = kl["high"].values
        lows = kl["low"].values

        for i in range(len(years)):
            color = "#E74C3C" if closes[i] >= opens[i] else "#27AE60"
            body_bottom = min(opens[i], closes[i])
            body_height = abs(closes[i] - opens[i])
            ax.bar(i, body_height, bottom=body_bottom, width=0.6, color=color, edgecolor=color)
            ax.vlines(i, lows[i], highs[i], color=color, linewidth=0.8)

        if len(closes) >= 3:
            ma3 = pd.Series(closes).rolling(3).mean()
            ax.plot(range(len(years)), ma3, color="#3498DB", linewidth=1, alpha=0.7)

        change = closes[-1] - closes[0]
        change_color = "#E74C3C" if change >= 0 else "#27AE60"
        sym = "↑" if change >= 0 else "↓"

        ax.set_title(f"{name} {sym}{abs(change):.0f}", fontsize=10,
                     fontweight="bold", color=change_color)
        ax.set_xticks([0, len(years) // 2, len(years) - 1])
        ax.set_xticklabels([years[0], years[len(years) // 2], years[-1]], fontsize=7)
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(alpha=0.15)

    # 隐藏多余子图
    for idx in range(n, rows * cols):
        r, c = idx // cols, idx % cols
        axes[r][c].set_visible(False)

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.01)
    fig.tight_layout()

    filepath = (output_dir or gk_config.OUTPUT_DIR) / "kline_grid.png"
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("K线网格图: %s", filepath)
    return filepath


def plot_supply_demand_scatter(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """供需散点图: X=报考热度(供给), Y=就业需求, 气泡=薪资。"""
    valid = df[(df["view_total"] > 0) & (df["job_count"] > 0)].copy()

    fig, ax = plt.subplots(figsize=(16, 10))

    sizes = valid["fivesalaryavg"].clip(lower=5000) / 500
    scatter = ax.scatter(
        valid["view_total"], valid["job_count"],
        s=sizes, c=valid["composite_index"], cmap="RdYlGn",
        alpha=0.7, edgecolors="gray", linewidth=0.5,
    )

    # 标注 TOP 专业
    for _, row in valid.nlargest(15, "composite_index").iterrows():
        ax.annotate(row["name"], (row["view_total"], row["job_count"]),
                    fontsize=7, ha="left", va="bottom",
                    arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))

    fig.colorbar(scatter, ax=ax, label="综合价值指数", shrink=0.7)
    ax.set_xlabel("报考热度（关注人次）→ 供给端", fontsize=12)
    ax.set_ylabel("就业岗位数 → 需求端", fontsize=12)
    ax.set_title("高考专业 供需全景图（气泡大小=5年薪资）", fontsize=14, fontweight="bold")
    ax.set_xscale("log")
    ax.grid(alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)

    filepath = (output_dir or gk_config.OUTPUT_DIR) / "supply_demand_scatter.png"
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("供需散点图: %s", filepath)
    return filepath


def plot_index_ranking(df: pd.DataFrame, n: int = 40, output_dir: Optional[Path] = None) -> Path:
    """综合指数排名条形图。"""
    top = df.nlargest(n, "composite_index")

    fig, ax = plt.subplots(figsize=(14, max(8, n * 0.35)))
    colors = ["#E74C3C" if v >= 60 else "#F39C12" if v >= 45 else "#27AE60" for v in top["composite_index"]]
    bars = ax.barh(range(len(top)), top["composite_index"].values, color=colors, height=0.6)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(top["name"].values, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("综合价值指数", fontsize=12)
    ax.set_title(f"高考专业综合价值指数 TOP {n}", fontsize=14, fontweight="bold")
    ax.grid(axis="x", alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)

    for bar, (_, row) in zip(bars, top.iterrows()):
        sal = row["fivesalaryavg"]
        sal_str = f"{sal/1000:.0f}K" if sal > 0 else ""
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{row['composite_index']:.0f} {sal_str}", va="center", fontsize=8)

    filepath = (output_dir or gk_config.OUTPUT_DIR) / "index_ranking.png"
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    logger.info("排名图: %s", filepath)
    return filepath


# ── 主入口 ────────────────────────────────────────────────

def main():
    logger.info("加载数据...")
    majors_df = load_major_data()
    jobs_df = load_job_data()
    logger.info("专业数: %d, 招聘数据: %d 条", len(majors_df), len(jobs_df))

    logger.info("计算综合指数...")
    df = compute_major_index(majors_df, jobs_df)

    # 保存指数数据
    cols_to_save = ["name", "level2_name", "level3_name", "limit_year",
                    "fivesalaryavg", "salaryavg", "view_total", "view_month",
                    "boy_rate", "girl_rate", "job_count", "market_salary_median",
                    "salary_score", "demand_score", "popularity_score",
                    "value_ratio_score", "composite_index"]
    save_cols = [c for c in cols_to_save if c in df.columns]
    df[save_cols].to_csv(gk_config.DATA_DIR / "major_index.csv", index=False, encoding="utf-8-sig")

    # Excel 报告
    with pd.ExcelWriter(gk_config.OUTPUT_DIR / "major_analysis.xlsx", engine="openpyxl") as w:
        df[save_cols].to_excel(w, sheet_name="综合指数", index=False)

    # 打印 TOP 30
    print("\n" + "=" * 80)
    print("  高考专业综合价值指数 TOP 30")
    print("=" * 80)
    top30 = df.head(30)[["name", "level2_name", "fivesalaryavg", "view_total",
                          "job_count", "composite_index"]]
    top30.columns = ["专业", "学科", "5年薪资", "关注度", "岗位数", "综合指数"]
    print(top30.to_string(index=False))

    # 生成 K 线数据
    logger.info("生成 K 线数据...")
    kline_data = generate_kline_data(df)

    # 保存 K 线数据
    all_kline = {}
    for name, kl_df in kline_data.items():
        all_kline[name] = kl_df.to_dict(orient="records")
    with open(gk_config.DATA_DIR / "kline_data.json", "w", encoding="utf-8") as f:
        json.dump(all_kline, f, ensure_ascii=False, indent=2)

    # 绘制图表
    logger.info("绘制图表...")

    # 1. K 线网格 (TOP 20)
    plot_kline_grid(df.head(20), kline_data, "高考专业价值指数 TOP 20 — K线走势 (2018-2026)")

    # 2. 单个 K 线（TOP 12）
    for _, row in df.head(12).iterrows():
        name = row["name"]
        if name in kline_data:
            plot_kline_single(name, kline_data[name], row.to_dict())

    # 3. 排名图
    plot_index_ranking(df, n=40)

    # 4. 供需散点图
    plot_supply_demand_scatter(df)

    # 统计
    logger.info("=" * 50)
    logger.info("完成:")
    logger.info("  专业总数: %d", len(df))
    logger.info("  有薪资数据: %d", (df["fivesalaryavg"] > 0).sum())
    logger.info("  有就业匹配: %d", (df["job_count"] > 0).sum())
    logger.info("  输出目录: %s", gk_config.OUTPUT_DIR)


if __name__ == "__main__":
    main()
