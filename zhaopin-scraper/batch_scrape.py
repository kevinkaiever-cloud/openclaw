#!/usr/bin/env python3
"""按关键词列表批量抓取智联招聘职位数据。

对无结果的关键词自动尝试相近词降级搜索。
"""

from __future__ import annotations

import json
import logging
import random
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from scraper.parser import JobItem, parse_html_job_list

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("batch")

# ── 关键词降级映射：搜不到时用更通用的词 ─────────────────
FALLBACK_MAP: dict[str, list[str]] = {
    "AIGC视频导演": ["AIGC导演", "视频导演", "视频制作"],
    "AIGC设计师": ["AIGC", "AI设计师", "设计师"],
    "AI产品经理": ["AI产品", "产品经理"],
    "AI伦理官": ["AI伦理", "AI治理", "伦理合规"],
    "AI内容创作者": ["AI内容", "内容创作", "AIGC"],
    "AI商业顾问": ["AI顾问", "商业顾问", "AI咨询"],
    "AI安全治理专家": ["AI安全", "AI治理", "信息安全"],
    "AI工程师": ["AI开发", "人工智能工程师"],
    "AI提示词工程师": ["提示词工程师", "Prompt工程师", "AI提示词"],
    "AI教育导师": ["AI教育", "AI培训", "教育导师"],
    "AI知识库工程师": ["知识库", "知识图谱工程师"],
    "AI算法工程师": ["算法工程师"],
    "AI训练师": ["AI训练", "数据标注", "模型训练"],
    "AI质检师": ["AI质检", "质检工程师", "智能质检"],
    "ESG分析师": ["ESG", "可持续发展", "碳排放分析"],
    "IC验证工程师": ["IC验证", "芯片验证"],
    "IT支持工程师": ["IT支持", "技术支持工程师"],
    "MLOps工程师": ["MLOps", "机器学习运维", "AI运维"],
    "PMO": ["项目管理办公室", "项目管理"],
    "RPA流程设计师": ["RPA", "流程自动化", "RPA开发"],
    "上门维修师": ["上门维修", "家电维修师", "维修工程师"],
    "临床研究协调员": ["临床研究", "CRA", "临床协调员"],
    "事业单位管理": ["事业单位", "行政管理"],
    "二手交易商": ["二手交易", "闲鱼", "二手车"],
    "二手车经纪人": ["二手车", "汽车经纪"],
    "云计算架构师": ["云计算", "云架构师"],
    "低代码自动化工程师": ["低代码", "自动化开发"],
    "储能系统工程师": ["储能工程师", "储能系统", "新能源储能"],
    "光伏工程师": ["光伏", "太阳能工程师"],
    "公共卫生专员": ["公共卫生", "卫生管理"],
    "公共资源交易管理": ["公共资源交易", "招投标管理"],
    "冷链司机": ["冷链", "冷链物流", "冷藏车司机"],
    "占星咨询师": ["占星", "星座咨询", "命理咨询"],
    "多模态算法工程师": ["多模态", "多模态算法", "计算机视觉"],
    "地图算法工程师": ["地图算法", "导航算法", "GIS工程师"],
    "增长产品经理": ["增长", "用户增长产品"],
    "数字人产品经理": ["数字人", "虚拟人产品"],
    "数据标注经理": ["数据标注", "标注管理"],
    "数据治理工程师": ["数据治理", "数据管理"],
    "数据可视化工程师": ["数据可视化", "BI工程师"],
    "智能体设计师": ["智能体", "AI Agent", "AI设计"],
    "智能客服训练师": ["智能客服", "客服训练", "对话训练"],
    "机器人产品经理": ["机器人产品", "机器人"],
    "独立咨询顾问": ["咨询顾问", "独立顾问"],
    "独立游戏开发者": ["独立游戏", "游戏开发"],
    "碳管理经理": ["碳管理", "碳中和", "碳排放"],
    "算力调度工程师": ["算力调度", "算力", "GPU调度"],
    "精益生产工程师": ["精益生产", "精益工程师"],
    "联邦学习工程师": ["联邦学习", "隐私计算"],
    "自动化运营专家": ["自动化运营", "运营自动化"],
    "虚拟人运营": ["虚拟人", "数字人运营"],
    "解决方案架构师": ["解决方案", "方案架构师"],
    "语音算法工程师": ["语音算法", "语音识别"],
    "跨境电商运营": ["跨境电商", "跨境运营"],
    "风控分析师": ["风控", "风险分析师"],
    "食品安全工程师": ["食品安全", "食品质量"],
    "高空作业工": ["高空作业", "蜘蛛人", "外墙作业"],
    "修鞋匠": ["修鞋", "皮具修复", "鞋类维修"],
    "手工艺人": ["手工艺", "手工制作"],
    "穿搭顾问": ["穿搭", "形象顾问", "服装搭配"],
    "摆摊商贩": ["摆摊", "小商贩", "夜市"],
    "微商": ["微商", "社交电商", "微信营销"],
    "渔民": ["渔业", "水产养殖"],
    "矿工": ["矿山工人", "采矿工"],
    "农民": ["农业", "种植"],
    "果农": ["果园", "水果种植"],
    "养殖工": ["养殖", "畜牧"],
    "政府信息化工程师": ["政务信息化", "政务数字化"],
    "自然语言处理工程师": ["NLP工程师", "自然语言处理"],
    "计算机视觉工程师": ["计算机视觉", "CV工程师"],
    "自动驾驶工程师": ["自动驾驶", "无人驾驶"],
    "新能源电池工程师": ["新能源电池", "电池工程师"],
    "旅行定制师": ["旅行定制", "定制旅游"],
    "摄影工作室主理人": ["摄影工作室", "摄影师"],
    "模特经纪": ["模特经纪人", "经纪人"],
}

# ── 完整关键词列表 ────────────────────────────────────────
KEYWORDS = [
    "AIGC视频导演", "AIGC设计师", "AI产品经理", "AI伦理官", "AI内容创作者",
    "AI商业顾问", "AI安全治理专家", "AI工程师", "AI提示词工程师", "AI教育导师",
    "AI知识库工程师", "AI算法工程师", "AI训练师", "AI质检师", "ESG分析师",
    "IC验证工程师", "IT支持工程师", "MLOps工程师", "PMO", "RPA流程设计师",
    "上门维修师", "中学教师", "临床研究协调员", "事业单位管理", "二手交易商",
    "二手车经纪人", "云计算架构师", "交互设计师", "交通管理执法", "企业咨询顾问",
    "低代码自动化工程师", "保险代理人", "保险精算师", "信息安全经理", "修鞋匠",
    "储能系统工程师", "光伏工程师", "公交司机", "公共卫生专员", "公共资源交易管理",
    "公务员", "公立医院护士", "公立医院药师", "公立学校教师", "养殖工",
    "内容运营", "农民", "冷链司机", "出租车司机", "制药工人",
    "制衣工", "医疗产品经理", "半导体工艺工程师", "占星咨询师", "厨师长",
    "叉车司机", "合规经理", "售票员", "售货员", "商业分析师",
    "商业运营", "国企员工", "国有企业工程师", "国际物流专员", "在线教育运营",
    "地图算法工程师", "地铁站务员", "增长产品经理", "多模态算法工程师", "大学讲师",
    "婚礼策划师", "宠物美容师", "宠物训练师", "审计局工作人员", "客户成功经理",
    "客房服务员", "家政服务经理", "家电维修", "工厂工人", "市场监管专员",
    "康复治疗师", "建筑工人", "微商", "心理咨询师", "战略规划",
    "房地产中介", "房地产策划", "手工艺人", "手机维修", "技术写作",
    "投研分析师", "抹灰工", "插画师", "搬运工", "摄影后期",
    "摄影工作室主理人", "摆摊商贩", "收银员", "政府信息化工程师", "教育产品经理",
    "数字人产品经理", "数据产品经理", "数据可视化工程师", "数据标注经理", "数据治理工程师",
    "新能源电池工程师", "旅行定制师", "景区工作人员", "智能体设计师", "智能客服训练师",
    "机器人产品经理", "机器学习工程师", "材料工程师", "果农", "档案管理员",
    "检察官助理", "模特经纪", "水管工", "汽修工", "法院书记员",
    "泥瓦工", "洗车工", "测量员", "海关关员", "消防员",
    "渔民", "游戏策划", "游戏美术", "物联网工程师", "独立咨询顾问",
    "独立游戏开发者", "玻璃工", "理财经理", "生物信息分析师", "用户增长",
    "用户研究员", "电力公司员工", "电焊工", "直播带货", "直播电商运营",
    "石材工", "矿工", "碳管理经理", "社区社工", "票务员",
    "程序员", "税务专员", "穿搭顾问", "算力调度工程师", "精益生产工程师",
    "纹身师", "纺织工", "统计局工作人员", "网店店主", "美甲师",
    "联邦学习工程师", "自动化工程师", "自动化运营专家", "自动驾驶工程师", "自来水公司员工",
    "自然语言处理工程师", "自由撰稿人", "芯片设计工程师", "药剂师", "虚拟人运营",
    "街道办工作人员", "裁缝", "解决方案架构师", "警察", "计算机视觉工程师",
    "证券经纪人", "语音算法工程师", "课程讲师", "货车司机", "跨境电商运营",
    "邮政员工", "配音演员", "酒店经理", "金融顾问", "钟表维修",
    "钢筋工", "铁路调度员", "铝合金门窗工", "银行柜员", "锅炉工",
    "隧道工", "音乐制作人", "风控分析师", "食品加工工人", "食品安全工程师",
    "高校行政", "高空作业工",
]


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=opts)
    driver.set_page_load_timeout(30)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


def search_keyword(driver: webdriver.Chrome, keyword: str, max_pages: int = 3) -> list[JobItem]:
    """搜索单个关键词，返回职位列表。"""
    all_items: list[JobItem] = []

    for page in range(1, max_pages + 1):
        url = f"https://sou.zhaopin.com/?kw={keyword}&p={page}"
        try:
            driver.get(url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".joblist-box__item"))
            )
            time.sleep(1)
        except Exception:
            break

        items = parse_html_job_list(driver.page_source)
        if not items:
            break

        # 标记搜索关键词
        for j in items:
            if not j.job_type:
                j.job_type = keyword

        all_items.extend(items)

        if len(items) < 15:
            break

        time.sleep(random.uniform(1.5, 3))

    return all_items


def scrape_with_fallback(
    driver: webdriver.Chrome,
    keyword: str,
    max_pages: int = 3,
) -> tuple[list[JobItem], str]:
    """搜索关键词，无结果时尝试降级关键词。

    Returns: (items, actual_keyword_used)
    """
    items = search_keyword(driver, keyword, max_pages)
    if items:
        return items, keyword

    # 降级搜索
    fallbacks = FALLBACK_MAP.get(keyword, [])
    # 通用降级：去掉"工程师/经理/专家/分析师"等后缀后重搜
    if not fallbacks:
        for suffix in ["工程师", "经理", "分析师", "专家", "设计师", "顾问", "工作人员", "专员"]:
            if keyword.endswith(suffix) and len(keyword) > len(suffix):
                fallbacks.append(keyword[:-len(suffix)])
                break

    for fb in fallbacks:
        items = search_keyword(driver, fb, max_pages=2)
        if items:
            logger.info("  ↳ 降级搜索: '%s' → '%s' (%d 条)", keyword, fb, len(items))
            for j in items:
                j.job_type = f"{keyword}→{fb}"
            return items, fb

    return [], keyword


def main():
    output_path = config.DATA_DIR / "zhaopin_keywords.json"
    progress_path = config.DATA_DIR / "batch_progress.json"

    # 加载进度（支持断点续传）
    done: dict[str, list[dict]] = {}
    if progress_path.exists():
        with open(progress_path, encoding="utf-8") as f:
            done = json.load(f)
        logger.info("恢复进度: 已完成 %d / %d 关键词", len(done), len(KEYWORDS))

    remaining = [kw for kw in KEYWORDS if kw not in done]
    logger.info("待抓取: %d 个关键词", len(remaining))

    # 每 10 个关键词重启浏览器
    batch_size = 10
    no_result_kws: list[str] = []

    for batch_start in range(0, len(remaining), batch_size):
        batch = remaining[batch_start:batch_start + batch_size]
        driver = None
        try:
            driver = make_driver()
            for kw in tqdm(batch, desc=f"批次 {batch_start//batch_size+1}", unit="词"):
                items, actual_kw = scrape_with_fallback(driver, kw, max_pages=3)
                done[kw] = [j.to_dict() for j in items]
                if not items:
                    no_result_kws.append(kw)

                # 定期保存进度
                if len(done) % 5 == 0:
                    with open(progress_path, "w", encoding="utf-8") as f:
                        json.dump(done, f, ensure_ascii=False, indent=1)

                time.sleep(random.uniform(1, 2))
        except Exception as exc:
            logger.warning("批次异常: %s", exc)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
            time.sleep(2)

    # 最终保存
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(done, f, ensure_ascii=False, indent=1)

    # 汇总为扁平列表
    all_jobs = []
    for kw, job_list in done.items():
        for j in job_list:
            j["search_keyword"] = kw
            all_jobs.append(j)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_jobs, f, ensure_ascii=False, indent=2)

    import pandas as pd
    df = pd.DataFrame(all_jobs)
    csv_path = config.DATA_DIR / "zhaopin_keywords.csv"
    df.to_csv(csv_path, index=False, encoding=config.CSV_ENCODING)

    logger.info("=" * 60)
    logger.info("抓取完成:")
    logger.info("  关键词总数: %d", len(KEYWORDS))
    logger.info("  有结果: %d", len(KEYWORDS) - len(no_result_kws))
    logger.info("  无结果: %d → %s", len(no_result_kws), no_result_kws[:20])
    logger.info("  总职位数: %d", len(all_jobs))
    logger.info("  保存: %s, %s", output_path, csv_path)


if __name__ == "__main__":
    main()
