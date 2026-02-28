from __future__ import annotations

from pathlib import Path


def generate_report(clean_csv: str, figure_dir: str, summary_path: str) -> dict[str, int]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
        import seaborn as sns
    except ImportError as exc:
        raise RuntimeError("缺少分析依赖，请先执行 pip install -r requirements.txt") from exc

    source = Path(clean_csv)
    if not source.exists():
        raise FileNotFoundError(f"clean csv not found: {source}")

    output_fig_dir = Path(figure_dir)
    output_fig_dir.mkdir(parents=True, exist_ok=True)
    summary_file = Path(summary_path)
    summary_file.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(source)
    if df.empty:
        summary_file.write_text("# Salary Report\n\n数据为空，未生成图表。\n", encoding="utf-8")
        return {"rows": 0, "figures": 0}

    for column in ("salary_min", "salary_max"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df["salary_mid"] = (df["salary_min"] + df["salary_max"]) / 2.0
    raw_df = df.copy()
    df = df[df["salary_mid"].notna() & (df["salary_mid"] > 0)]

    figure_count = 0
    sns.set_theme(style="whitegrid")

    if "industry" in df.columns and not df["industry"].dropna().empty:
        top_industries = (
            df.groupby("industry", dropna=True)["salary_mid"].median().sort_values(ascending=False).head(12).index.tolist()
        )
        dist_df = df[df["industry"].isin(top_industries)].copy()
        if not dist_df.empty:
            plt.figure(figsize=(13, 6))
            sns.boxplot(data=dist_df, x="industry", y="salary_mid")
            plt.xticks(rotation=45, ha="right")
            plt.title("行业薪资分布（按月薪中位数）")
            plt.xlabel("行业")
            plt.ylabel("月薪（元）")
            plt.tight_layout()
            plt.savefig(output_fig_dir / "industry_salary_distribution.png", dpi=180)
            plt.close()
            figure_count += 1

    if "city" in df.columns and not df["city"].dropna().empty:
        city_df = df.groupby("city", dropna=True)["salary_mid"].median().sort_values(ascending=False).head(15).reset_index()
        if not city_df.empty:
            plt.figure(figsize=(12, 6))
            sns.barplot(data=city_df, x="city", y="salary_mid")
            plt.xticks(rotation=45, ha="right")
            plt.title("城市薪资对比（月薪中位数）")
            plt.xlabel("城市")
            plt.ylabel("月薪（元）")
            plt.tight_layout()
            plt.savefig(output_fig_dir / "city_salary_compare.png", dpi=180)
            plt.close()
            figure_count += 1

    if "experience_bucket" in df.columns and not df["experience_bucket"].dropna().empty:
        order = ["0-3年", "3-5年", "5年以上", "unknown"]
        exp_df = (
            df.groupby("experience_bucket", dropna=True)["salary_mid"]
            .median()
            .reindex(order)
            .dropna()
            .reset_index()
            .rename(columns={"experience_bucket": "bucket"})
        )
        if not exp_df.empty:
            plt.figure(figsize=(10, 5))
            sns.lineplot(data=exp_df, x="bucket", y="salary_mid", marker="o")
            plt.title("经验年限与薪资关系曲线")
            plt.xlabel("经验分组")
            plt.ylabel("月薪中位数（元）")
            plt.tight_layout()
            plt.savefig(output_fig_dir / "experience_salary_trend.png", dpi=180)
            plt.close()
            figure_count += 1

    if all(column in df.columns for column in ("industry", "city")):
        pivot = df.pivot_table(index="industry", columns="city", values="salary_mid", aggfunc="median")
        if not pivot.empty:
            top_rows = pivot.mean(axis=1).sort_values(ascending=False).head(10).index
            top_cols = pivot.mean(axis=0).sort_values(ascending=False).head(10).index
            heat_df = pivot.loc[top_rows, top_cols]
            plt.figure(figsize=(12, 8))
            sns.heatmap(heat_df, cmap="YlOrRd", linewidths=0.3, linecolor="#eeeeee")
            plt.title("行业-城市薪资热力图（月薪中位数）")
            plt.xlabel("城市")
            plt.ylabel("行业")
            plt.tight_layout()
            plt.savefig(output_fig_dir / "industry_city_heatmap.png", dpi=180)
            plt.close()
            figure_count += 1

    summary = _build_summary(raw_df, analyzed_rows=int(len(df)))
    summary_file.write_text(summary, encoding="utf-8")
    return {"rows": int(len(df)), "figures": figure_count}


def _build_summary(df, analyzed_rows: int) -> str:  # type: ignore[no-untyped-def]
    sample_count = int(len(df))
    salary_missing_rate = (
        float((df["salary_min"].isna() | df["salary_max"].isna()).mean())
        if "salary_min" in df and "salary_max" in df
        else 1.0
    )
    company_missing_rate = float(df["company_name"].isna().mean()) if "company_name" in df else 1.0
    title_missing_rate = float(df["job_title"].isna().mean()) if "job_title" in df else 1.0

    lines: list[str] = [
        "# 招聘薪资分析报告",
        "",
        "## 样本概览",
        "",
        f"- 样本总量: **{sample_count}**",
        f"- 可分析样本量: **{analyzed_rows}**",
        f"- 薪资缺失率: **{salary_missing_rate:.2%}**",
        f"- 公司名缺失率: **{company_missing_rate:.2%}**",
        f"- 职位名缺失率: **{title_missing_rate:.2%}**",
        "",
    ]

    if "industry" in df.columns and not df["industry"].dropna().empty:
        lines.extend(["## 行业月薪中位数 Top 10", ""])
        top_industry = (
            df.groupby("industry", dropna=True)["salary_mid"].median().sort_values(ascending=False).head(10).reset_index()
        )
        for _, row in top_industry.iterrows():
            lines.append(f"- {row['industry']}: {row['salary_mid']:.0f} 元")
        lines.append("")

    if "city" in df.columns and not df["city"].dropna().empty:
        lines.extend(["## 城市月薪中位数 Top 10", ""])
        top_city = df.groupby("city", dropna=True)["salary_mid"].median().sort_values(ascending=False).head(10).reset_index()
        for _, row in top_city.iterrows():
            lines.append(f"- {row['city']}: {row['salary_mid']:.0f} 元")
        lines.append("")

    return "\n".join(lines)

