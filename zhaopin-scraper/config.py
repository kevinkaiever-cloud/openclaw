"""智联招聘薪资数据抓取 — 全局配置"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── 抓取目标 ──────────────────────────────────────────────
BASE_URL = "https://www.zhaopin.com"
SEARCH_API = "https://fe-api.zhaopin.com/c/i/sou"

# 搜索 API 的通用请求头
HEADERS = {
    "Referer": "https://www.zhaopin.com/",
    "Accept": "application/json",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# ── 城市列表（城市代码 → 名称）──────────────────────────
CITIES: dict[str, str] = {
    "530":  "北京",
    "538":  "上海",
    "763":  "广州",
    "765":  "深圳",
    "653":  "杭州",
    "635":  "南京",
    "551":  "成都",
    "749":  "武汉",
    "599":  "西安",
    "719":  "天津",
    "736":  "苏州",
    "613":  "长沙",
    "681":  "青岛",
    "801":  "重庆",
    "854":  "郑州",
    "752":  "厦门",
    "639":  "合肥",
    "565":  "大连",
    "600":  "无锡",
    "773":  "东莞",
}

# ── 行业分类 ──────────────────────────────────────────────
INDUSTRIES: dict[str, str] = {
    "10100":  "IT/互联网/游戏",
    "10200":  "电子/通信/半导体",
    "10300":  "房地产/建筑",
    "10400":  "金融",
    "10500":  "消费品/零售/贸易",
    "10600":  "汽车/机械/制造",
    "10700":  "制药/医疗",
    "10800":  "教育/培训",
    "10900":  "广告/传媒/文化",
    "11000":  "服务业",
    "11100":  "物流/运输",
    "11200":  "能源/环保/化工",
    "11300":  "政府/非盈利/农业",
}

# ── 抓取控制参数 ──────────────────────────────────────────
REQUEST_DELAY_MIN = 2          # 最小请求间隔（秒）
REQUEST_DELAY_MAX = 5          # 最大请求间隔（秒）
MAX_PAGES_PER_QUERY = 50       # 每次搜索最多翻页数
PAGE_SIZE = 60                 # 每页职位数
MAX_RETRIES = 3                # 单次请求失败重试次数
RETRY_BACKOFF = 2              # 重试退避基数（秒）

# ── 代理池（可选，留空则直连）────────────────────────────
# 格式: ["http://ip:port", "https://user:pass@ip:port", ...]
PROXY_LIST: list[str] = []

# 也可从环境变量读取，逗号分隔
_env_proxies = os.environ.get("ZHAOPIN_PROXIES", "")
if _env_proxies:
    PROXY_LIST.extend(p.strip() for p in _env_proxies.split(",") if p.strip())

# ── Selenium（处理动态页面时使用）─────────────────────────
SELENIUM_HEADLESS = True
SELENIUM_TIMEOUT = 15          # 页面加载超时（秒）

# ── 输出 ──────────────────────────────────────────────────
CSV_ENCODING = "utf-8-sig"     # Excel 兼容
JSON_INDENT = 2

# ── 定时任务 ──────────────────────────────────────────────
SCHEDULE_ENABLED = False       # 是否启用定时抓取
SCHEDULE_INTERVAL_DAYS = 30    # 抓取间隔（天）
