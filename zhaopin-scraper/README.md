# 智联招聘薪资数据抓取与分析工具

抓取智联招聘全行业、全城市的职位薪资数据，进行清洗、统计分析和可视化。

## 功能

- **全量抓取**：按城市 × 行业组合遍历智联招聘职位数据
- **API + Selenium 双模式**：默认走前端 API（快），被封时可降级为 Selenium 渲染
- **代理池**：支持 IP 轮换，规避反爬封禁
- **薪资解析**：自动解析 "8K-15K·13薪" 等格式为结构化数值
- **数据清洗**：去重、标准化经验/学历、薪资等级分类
- **统计分析**：行业/城市/经验/学历维度薪资报告
- **可视化图表**：薪资分布、行业对比、城市对比、经验趋势、热力图等
- **定时调度**：支持周期性自动抓取

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 全量抓取（所有城市 × 所有行业）
python main.py scrape

# 按关键词抓取
python main.py scrape --keyword "Python开发" --city 530

# 使用 Selenium 模式（处理动态页面）
python main.py scrape --selenium

# 清洗数据
python main.py clean

# 分析 + 生成图表
python main.py analyze

# 全流程：抓取 → 清洗 → 分析
python main.py all

# 启动定时抓取（默认每月一次）
python main.py schedule
```

## 项目结构

```
zhaopin-scraper/
├── config.py              # 全局配置（城市、行业、抓取参数）
├── main.py                # CLI 入口
├── scheduler.py           # 定时调度
├── requirements.txt       # Python 依赖
├── scraper/
│   ├── zhaopin.py         # 核心抓取器
│   ├── parser.py          # 数据解析（薪资、HTML、API JSON）
│   ├── proxy.py           # 代理池管理
│   └── browser.py         # Selenium 浏览器自动化
├── analysis/
│   ├── clean.py           # 数据清洗与预处理
│   ├── analyze.py         # 统计分析
│   └── visualize.py       # 可视化图表生成
├── data/                  # 抓取数据存储（JSON/CSV）
└── output/                # 分析报告和图表输出
```

## 配置说明

编辑 `config.py` 自定义：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `CITIES` | 目标城市及代码 | 20 个主要城市 |
| `INDUSTRIES` | 目标行业及代码 | 13 个行业分类 |
| `REQUEST_DELAY_MIN/MAX` | 请求间隔（秒） | 2-5 秒 |
| `MAX_PAGES_PER_QUERY` | 每个搜索最大翻页 | 50 页 |
| `PROXY_LIST` | 代理列表 | 空（直连） |
| `SCHEDULE_INTERVAL_DAYS` | 定时抓取间隔 | 30 天 |

### 代理池配置

通过环境变量设置：

```bash
export ZHAOPIN_PROXIES="http://ip1:port,http://ip2:port"
```

或直接编辑 `config.py` 中的 `PROXY_LIST`。

## 输出数据格式

### CSV/JSON 字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `job_name` | 职位名称 | Python开发工程师 |
| `salary_raw` | 原始薪资文本 | 15K-25K·13薪 |
| `salary_min` | 最低月薪（元） | 15000 |
| `salary_max` | 最高月薪（元） | 25000 |
| `salary_months` | 年薪月数 | 13 |
| `salary_avg` | 平均月薪（元） | 20000 |
| `company_name` | 公司名称 | 某科技有限公司 |
| `industry` | 行业 | IT/互联网/游戏 |
| `city` | 城市 | 北京 |
| `experience` | 经验要求 | 3-5年 |
| `education` | 学历要求 | 本科 |

### 生成的图表

1. `salary_distribution.png` — 薪资分布直方图
2. `industry_salary.png` — 行业薪资对比
3. `city_salary.png` — 城市薪资对比
4. `experience_salary_curve.png` — 经验与薪资增长曲线
5. `education_salary.png` — 学历薪资箱线图
6. `salary_level_pie.png` — 薪资等级饼图
7. `city_industry_heatmap.png` — 城市×行业热力图
8. `salary_report.xlsx` — Excel 多 Sheet 分析报告

## 注意事项

- 请遵守智联招聘的使用条款和 robots.txt
- 建议配置代理池以避免 IP 被封
- 默认请求间隔 2-5 秒，可根据需要调整
- 全量抓取耗时较长，建议先按单个城市/行业测试
