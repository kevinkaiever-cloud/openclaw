# Zhaopin Salary Crawler

一个可扩展的招聘薪资采集与分析项目，目标是对职位薪资进行结构化抓取、清洗、统计分析与可视化。

## 功能概览

- 基于 **Scrapy** 的职位列表/详情抓取流程（支持分页）
- 使用 **BeautifulSoup** 解析页面，提取职位核心字段
- 提供 **Selenium** 动态渲染兜底（按需启用）
- 薪资字符串解析（如 `8k-15k/月`、`20-30万/年`、`15-20k·13薪`）
- 清洗与标准化输出（CSV + JSON）
- 生成分析报告与图表（行业、城市、经验维度）
- 提供月度定时任务（cron）示例

## 合规说明

请确保抓取行为满足以下要求：

1. 遵守目标站点 robots.txt 与服务条款
2. 不绕过验证码、登录保护或访问控制机制
3. 合理限速，避免高频请求影响目标站点稳定性

## 目录结构

```text
salary-crawler/
├── config/
│   └── targets.json
├── data/
│   ├── clean/
│   └── raw/
├── reports/
│   └── figures/
├── src/
│   └── zhaopin_salary/
│       ├── analysis.py
│       ├── cleaning.py
│       ├── cli.py
│       ├── models.py
│       ├── parsers.py
│       ├── pipelines.py
│       ├── salary.py
│       ├── scheduler.py
│       ├── selenium_fetcher.py
│       └── spiders/
│           └── zhaopin_spider.py
├── tests/
│   ├── test_cleaning.py
│   └── test_salary.py
├── Makefile
└── requirements.txt
```

## 快速开始

### 1) 安装依赖

```bash
cd /workspace/salary-crawler
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) 执行全流程

```bash
make crawl
make clean
make report
```

或一键：

```bash
make all
```

### 3) 运行单元测试

```bash
make test
```

## 关键命令

- `make crawl`：抓取职位原始数据，写入 `data/raw/jobs_raw.jsonl`
- `make clean`：清洗数据并输出：
  - `data/clean/jobs_clean.csv`
  - `data/clean/jobs_clean.json`
- `make report`：生成图表和 `reports/summary.md`
- `make schedule`：输出 cron 月度执行示例
- `PYTHONPATH=src python3 -m zhaopin_salary.cli discover --output config/targets.auto.json`：
  从首页提取行业/城市配置

## 可配置项

`config/targets.json` 中可以配置城市与行业抓取范围。示例字段：

- `cities`: 城市代码 + 名称
- `industries`: 行业代码 + 名称

## 字段说明

输出字段包含（每个职位一条）：

- `job_title`
- `salary_raw`
- `salary_min`
- `salary_max`
- `salary_period`
- `salary_months`
- `salary_parsed`
- `company_name`
- `industry`
- `city`
- `experience_req`
- `education_req`
- `job_url`
- `crawl_time`

## 定时任务示例

项目会生成如下 cron 示例（每月 1 号凌晨 3 点执行）：

```cron
0 3 1 * * cd /path/to/salary-crawler && make crawl && make clean && make report >> logs/monthly.log 2>&1
```

