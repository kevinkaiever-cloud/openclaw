#!/usr/bin/env python3
"""分析 192 个岗位关键词的搜索质量，生成真实对应关系映射表。"""

import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pandas as pd
import config

with open(config.DATA_DIR / "batch_progress.json", encoding="utf-8") as f:
    progress = json.load(f)

# ── 每个岗位的匹配质量评估和真实对应关系 ──────────────────
# match_quality: A=精准匹配, B=基本匹配, C=部分相关, D=数据偏差大, X=无数据
# real_position: 在招聘市场上真实存在的对应职位名

MAPPING = {
    # ===== AI / 前沿科技 =====
    "AIGC视频导演":        {"quality": "B", "real": "AIGC导演 / AI视频制作", "note": "搜到AIGC相关但导演岗少"},
    "AIGC设计师":          {"quality": "A", "real": "AIGC设计师 / AI视觉设计师"},
    "AI产品经理":          {"quality": "A", "real": "AI产品经理"},
    "AI伦理官":            {"quality": "C", "real": "AI数据治理工程师 / AI合规经理", "note": "降级→AI治理，实际是治理/合规岗"},
    "AI内容创作者":        {"quality": "B", "real": "AI内容运营 / AI内容编辑", "note": "降级→AI内容"},
    "AI商业顾问":          {"quality": "B", "real": "AI售前顾问 / AI解决方案顾问", "note": "降级→AI顾问，偏销售端"},
    "AI安全治理专家":      {"quality": "A", "real": "AI安全工程师 / AI治理专家"},
    "AI工程师":            {"quality": "A", "real": "AI工程师 / 人工智能开发工程师"},
    "AI提示词工程师":      {"quality": "A", "real": "Prompt工程师 / AI提示词工程师"},
    "AI教育导师":          {"quality": "B", "real": "AI教育产品经理 / AI培训讲师", "note": "降级→AI教育"},
    "AI知识库工程师":      {"quality": "B", "real": "知识图谱工程师 / 知识库运营", "note": "降级→知识库"},
    "AI算法工程师":        {"quality": "A", "real": "AI算法工程师"},
    "AI训练师":            {"quality": "A", "real": "AI训练师 / 数据标注师", "note": "降级→AI训练，匹配度高"},
    "AI质检师":            {"quality": "C", "real": "质检工程师（传统质检）", "note": "降级→质检工程师，非AI专属"},
    "ESG分析师":           {"quality": "A", "real": "ESG分析师 / 可持续发展分析师"},
    "IC验证工程师":        {"quality": "A", "real": "IC验证工程师 / 芯片验证工程师"},
    "IT支持工程师":        {"quality": "A", "real": "IT技术支持工程师 / 桌面运维"},
    "MLOps工程师":         {"quality": "A", "real": "MLOps工程师 / AI运维工程师"},
    "PMO":                 {"quality": "A", "real": "PMO / 项目管理"},
    "RPA流程设计师":       {"quality": "B", "real": "RPA开发工程师 / RPA实施顾问", "note": "降级→RPA"},
    "低代码自动化工程师":  {"quality": "A", "real": "低代码开发工程师"},
    "云计算架构师":        {"quality": "A", "real": "云计算架构师 / 云平台工程师"},
    "多模态算法工程师":    {"quality": "B", "real": "多模态AI算法工程师", "note": "降级→多模态，含模态分析等噪声"},
    "储能系统工程师":      {"quality": "A", "real": "储能系统工程师"},
    "光伏工程师":          {"quality": "A", "real": "光伏工程师 / 光伏系统设计"},
    "半导体工艺工程师":    {"quality": "A", "real": "半导体工艺工程师"},
    "地图算法工程师":      {"quality": "A", "real": "地图算法工程师 / 导航算法工程师"},
    "增长产品经理":        {"quality": "A", "real": "增长产品经理 / 用户增长PM"},
    "数字人产品经理":      {"quality": "A", "real": "数字人产品经理 / 虚拟人PM"},
    "数据产品经理":        {"quality": "A", "real": "数据产品经理"},
    "数据可视化工程师":    {"quality": "A", "real": "数据可视化工程师 / BI工程师"},
    "数据标注经理":        {"quality": "A", "real": "数据标注经理 / 标注项目管理"},
    "数据治理工程师":      {"quality": "A", "real": "数据治理工程师 / 数据管理工程师"},
    "新能源电池工程师":    {"quality": "A", "real": "电池工程师 / 新能源研发工程师"},
    "智能体设计师":        {"quality": "A", "real": "AI Agent产品经理 / 智能体开发"},
    "智能客服训练师":      {"quality": "A", "real": "智能客服训练师 / 对话AI训练师"},
    "机器人产品经理":      {"quality": "A", "real": "机器人产品经理"},
    "机器学习工程师":      {"quality": "A", "real": "机器学习工程师"},
    "物联网工程师":        {"quality": "A", "real": "物联网工程师 / IoT开发工程师"},
    "算力调度工程师":      {"quality": "C", "real": "云计算平台工程师 / GPU资源运维", "note": "降级→算力调度，仅2条"},
    "精益生产工程师":      {"quality": "A", "real": "精益生产工程师 / IE工程师"},
    "联邦学习工程师":      {"quality": "A", "real": "联邦学习工程师 / 隐私计算工程师"},
    "自动化工程师":        {"quality": "A", "real": "自动化工程师"},
    "自动化运营专家":      {"quality": "A", "real": "自动化运营 / MarTech运营"},
    "自动驾驶工程师":      {"quality": "A", "real": "自动驾驶工程师"},
    "自然语言处理工程师":  {"quality": "A", "real": "NLP算法工程师", "note": "降级→NLP工程师，高度匹配"},
    "芯片设计工程师":      {"quality": "A", "real": "芯片设计工程师 / IC设计"},
    "计算机视觉工程师":    {"quality": "A", "real": "计算机视觉工程师 / CV算法工程师"},
    "语音算法工程师":      {"quality": "A", "real": "语音算法工程师 / ASR/TTS工程师"},
    "解决方案架构师":      {"quality": "A", "real": "解决方案架构师"},
    "虚拟人运营":          {"quality": "B", "real": "数字人运营 / 虚拟主播运营", "note": "降级→数字人运营"},

    # ===== 管理 / 专业白领 =====
    "交互设计师":       {"quality": "A", "real": "交互设计师 / UX设计师"},
    "企业咨询顾问":     {"quality": "A", "real": "管理咨询顾问 / 企业咨询"},
    "保险代理人":       {"quality": "A", "real": "保险代理人 / 保险销售"},
    "保险精算师":       {"quality": "A", "real": "精算师 / 保险精算"},
    "信息安全经理":     {"quality": "A", "real": "信息安全经理 / 网络安全负责人"},
    "合规经理":         {"quality": "A", "real": "合规经理 / 法务合规"},
    "商业分析师":       {"quality": "A", "real": "商业分析师 / BA"},
    "商业运营":         {"quality": "A", "real": "商业运营 / 品牌运营"},
    "客户成功经理":     {"quality": "A", "real": "客户成功经理 / CSM"},
    "战略规划":         {"quality": "A", "real": "战略规划经理 / 战略分析"},
    "投研分析师":       {"quality": "A", "real": "投研分析师 / 行业研究员"},
    "教育产品经理":     {"quality": "A", "real": "教育产品经理"},
    "材料工程师":       {"quality": "A", "real": "材料工程师 / 材料研发"},
    "用户增长":         {"quality": "A", "real": "用户增长 / Growth Hacker"},
    "用户研究员":       {"quality": "A", "real": "用户研究员 / UX Researcher"},
    "生物信息分析师":   {"quality": "A", "real": "生物信息分析师 / 生信工程师"},
    "理财经理":         {"quality": "A", "real": "理财经理 / 财富顾问"},
    "碳管理经理":       {"quality": "A", "real": "碳管理经理 / 碳资产管理"},
    "金融顾问":         {"quality": "A", "real": "金融顾问 / 理财规划师"},
    "风控分析师":       {"quality": "A", "real": "风控分析师 / 风险管理"},
    "医疗产品经理":     {"quality": "A", "real": "医疗产品经理 / 医疗器械PM"},
    "房地产中介":       {"quality": "A", "real": "房产经纪人 / 二手房销售"},
    "房地产策划":       {"quality": "A", "real": "房地产策划 / 营销策划"},

    # ===== 传统白领 / 文职 =====
    "内容运营":         {"quality": "A", "real": "内容运营 / 新媒体运营"},
    "在线教育运营":     {"quality": "A", "real": "在线教育运营 / 教育平台运营"},
    "国际物流专员":     {"quality": "A", "real": "国际物流专员 / 货代操作"},
    "技术写作":         {"quality": "A", "real": "技术文档工程师 / 技术写作"},
    "插画师":           {"quality": "A", "real": "插画师 / 原画师"},
    "摄影后期":         {"quality": "A", "real": "摄影后期修图师"},
    "游戏策划":         {"quality": "A", "real": "游戏策划 / 游戏设计师"},
    "游戏美术":         {"quality": "A", "real": "游戏美术 / 游戏原画"},
    "直播带货":         {"quality": "A", "real": "直播主播 / 带货主播"},
    "直播电商运营":     {"quality": "A", "real": "直播电商运营 / 抖音运营"},
    "程序员":           {"quality": "A", "real": "软件开发工程师 / 程序员"},
    "跨境电商运营":     {"quality": "A", "real": "跨境电商运营 / 亚马逊运营"},
    "自由撰稿人":       {"quality": "B", "real": "编辑 / 文案策划 / 撰稿人"},
    "配音演员":         {"quality": "A", "real": "配音演员 / 有声主播"},
    "音乐制作人":       {"quality": "A", "real": "音乐制作人 / 编曲师"},
    "课程讲师":         {"quality": "A", "real": "课程讲师 / 培训师"},
    "康复治疗师":       {"quality": "A", "real": "康复治疗师"},
    "心理咨询师":       {"quality": "A", "real": "心理咨询师"},
    "婚礼策划师":       {"quality": "A", "real": "婚礼策划师 / 婚庆策划"},
    "旅行定制师":       {"quality": "A", "real": "定制旅行顾问 / 旅游策划"},

    # ===== 体制内 / 公共事业 =====
    "中学教师":          {"quality": "A", "real": "中学教师（民办/培训为主）"},
    "公务员":            {"quality": "D", "real": "⚠ 招聘网无真正公务员岗，数据为培训讲师/销售假借名义", "note": "搜到的是\"像公务员的工作\"等营销话术"},
    "公立医院护士":      {"quality": "A", "real": "护士 / 护理人员（以民营医院为主）"},
    "公立医院药师":      {"quality": "A", "real": "执业药师 / 药房药师（以药店/民营为主）"},
    "公立学校教师":      {"quality": "B", "real": "教师（以民办/培训机构为主）"},
    "事业单位管理":      {"quality": "D", "real": "⚠ 搜到的是管理咨询/健康管理等混杂岗位", "note": "非真正事业编"},
    "大学讲师":          {"quality": "A", "real": "大学讲师 / 高校教师（以民办高校为主）"},
    "警察":              {"quality": "D", "real": "⚠ 搜到的是安防/保安/安全员", "note": "招聘网无真正警察岗位"},
    "消防员":            {"quality": "A", "real": "企业消防员 / 物业消防值班"},
    "海关关员":          {"quality": "X", "real": "⚠ 无数据，公务员编制不在招聘网发布"},
    "检察官助理":        {"quality": "D", "real": "⚠ 搜到的是各类助理岗（非司法系统）", "note": "法院/检察院通过公考招聘"},
    "法院书记员":        {"quality": "C", "real": "法院驻场文员 / 法律辅助人员", "note": "非正式编制书记员"},
    "交通管理执法":      {"quality": "B", "real": "交通管理 / 安全管理（企业端）"},
    "市场监管专员":      {"quality": "A", "real": "市场监管 / 合规专员（企业端）"},
    "税务专员":          {"quality": "A", "real": "税务专员 / 税务会计"},
    "审计局工作人员":    {"quality": "D", "real": "⚠ 降级搜索→审计局，搜到政府关系/审计合伙人", "note": "体制内不走招聘网"},
    "统计局工作人员":    {"quality": "D", "real": "⚠ 仅搜到1条保安岗", "note": "体制内不走招聘网"},
    "街道办工作人员":    {"quality": "D", "real": "⚠ 降级→街道办，搜到外联/拆迁相关", "note": "体制内不走招聘网"},
    "公共卫生专员":      {"quality": "B", "real": "公共卫生管理 / 卫生专员"},
    "公共资源交易管理":  {"quality": "C", "real": "⚠ 降级搜索，仅2条公共资源部经理", "note": "体制内岗位"},
    "政府信息化工程师":  {"quality": "A", "real": "政务信息化工程师 / 智慧城市工程师"},
    "社区社工":          {"quality": "A", "real": "社区社工 / 社区工作者"},
    "高校行政":          {"quality": "B", "real": "高校行政人员 / 教务管理"},

    # ===== 蓝领 / 技工 / 体力劳动 =====
    "上门维修师":       {"quality": "A", "real": "上门维修工程师 / 家电维修师"},
    "公交司机":         {"quality": "A", "real": "公交驾驶员"},
    "冷链司机":         {"quality": "A", "real": "冷链配送司机 / 冷藏车驾驶员"},
    "出租车司机":       {"quality": "B", "real": "网约车司机 / 货运司机（混合结果）"},
    "制药工人":         {"quality": "A", "real": "制药操作工 / 药品生产工"},
    "制衣工":           {"quality": "A", "real": "服装制作工 / 缝纫工"},
    "叉车司机":         {"quality": "A", "real": "叉车司机 / 叉车操作工"},
    "厨师长":           {"quality": "A", "real": "厨师长 / 行政总厨"},
    "售票员":           {"quality": "A", "real": "售票员 / 票务员"},
    "售货员":           {"quality": "A", "real": "导购员 / 销售员"},
    "客房服务员":       {"quality": "A", "real": "客房服务员 / 酒店保洁"},
    "宠物美容师":       {"quality": "A", "real": "宠物美容师"},
    "宠物训练师":       {"quality": "A", "real": "宠物训练师 / 宠物行为师"},
    "工厂工人":         {"quality": "A", "real": "普工 / 操作工"},
    "建筑工人":         {"quality": "A", "real": "建筑工 / 施工工人"},
    "收银员":           {"quality": "A", "real": "收银员"},
    "搬运工":           {"quality": "A", "real": "搬运工 / 装卸工"},
    "档案管理员":       {"quality": "A", "real": "档案管理员 / 资料员"},
    "测量员":           {"quality": "A", "real": "测量员 / 施工测量"},
    "洗车工":           {"quality": "A", "real": "洗车工 / 汽车美容"},
    "汽修工":           {"quality": "A", "real": "汽车维修工 / 汽车机修"},
    "电焊工":           {"quality": "A", "real": "电焊工 / 焊接工"},
    "纹身师":           {"quality": "A", "real": "纹身师"},
    "纺织工":           {"quality": "A", "real": "纺织操作工"},
    "美甲师":           {"quality": "A", "real": "美甲师"},
    "货车司机":         {"quality": "A", "real": "货车司机 / 物流司机"},
    "酒店经理":         {"quality": "A", "real": "酒店经理 / 酒店运营"},
    "钟表维修":         {"quality": "A", "real": "钟表维修师"},
    "锅炉工":           {"quality": "A", "real": "锅炉操作工"},
    "钢筋工":           {"quality": "A", "real": "钢筋工 / 钢筋翻样"},
    "铝合金门窗工":     {"quality": "B", "real": "门窗安装工 / 铝合金销售"},
    "隧道工":           {"quality": "B", "real": "隧道施工员 / 隧道安全员（偏管理）"},
    "高空作业工":       {"quality": "A", "real": "高空作业人员 / 外墙施工"},
    "石材工":           {"quality": "A", "real": "石材加工工 / 石材安装"},
    "玻璃工":           {"quality": "A", "real": "玻璃操作工 / 玻璃加工"},
    "食品加工工人":     {"quality": "A", "real": "食品加工操作工"},
    "食品安全工程师":   {"quality": "A", "real": "食品安全工程师 / 质量安全"},
    "家电维修":         {"quality": "A", "real": "家电维修工 / 售后工程师"},
    "手机维修":         {"quality": "A", "real": "手机维修技师"},
    "水管工":           {"quality": "A", "real": "水暖工 / 管道工"},
    "铁路调度员":       {"quality": "C", "real": "铁路操作员 / 物流调度", "note": "仅1条"},
    "地铁站务员":       {"quality": "A", "real": "地铁站务员"},
    "票务员":           {"quality": "A", "real": "票务员 / 售票员"},
    "家政服务经理":     {"quality": "A", "real": "家政服务经理 / 家政运营"},
    "药剂师":           {"quality": "A", "real": "执业药师 / 药店药剂师"},
    "裁缝":             {"quality": "A", "real": "裁缝 / 服装修改师"},
    "养殖工":           {"quality": "A", "real": "养殖工 / 畜牧养殖"},

    # ===== 特殊 / 自由职业 / 难匹配 =====
    "农民":             {"quality": "D", "real": "⚠ 搜到的是农业企业的普工/操作工", "note": "自耕农不走招聘网"},
    "果农":             {"quality": "D", "real": "⚠ 降级→果园，搜到的是商场导购/置业顾问", "note": "果农不走招聘网，薪资数据无效"},
    "渔民":             {"quality": "C", "real": "渔业技术员 / 水产养殖管理（非传统渔民）", "note": "降级→渔业"},
    "矿工":             {"quality": "C", "real": "矿山普工 / 护矿工", "note": "仅5条"},
    "微商":             {"quality": "D", "real": "⚠ 搜到的是普通销售岗", "note": "微商非正式招聘岗"},
    "摆摊商贩":         {"quality": "D", "real": "⚠ 降级→摆摊，搜到的是小区地推/业务员", "note": "非真正摆摊数据"},
    "网店店主":         {"quality": "B", "real": "电商运营 / 网店运营专员（非店主）"},
    "独立游戏开发者":   {"quality": "D", "real": "⚠ 搜到的是游戏代练/跑腿等低价兼职", "note": "薪资数据完全无效"},
    "独立咨询顾问":     {"quality": "C", "real": "课程咨询顾问", "note": "仅1条，不具代表性"},
    "占星咨询师":       {"quality": "D", "real": "⚠ 搜到的是工程咨询/教育咨询师", "note": "占星非主流招聘岗位"},
    "穿搭顾问":         {"quality": "B", "real": "服装搭配师 / 时尚顾问", "note": "仅2条"},
    "手工艺人":         {"quality": "C", "real": "手工艺设计师", "note": "降级→手工艺，仅3条"},
    "修鞋匠":           {"quality": "X", "real": "⚠ 无数据，传统手艺人不走招聘网"},
    "泥瓦工":           {"quality": "X", "real": "⚠ 无数据，通过工头/熟人介绍，招聘网极少"},
    "海关关员":         {"quality": "X", "real": "⚠ 无数据，公务员编制通过国考招录"},
    "证券经纪人":       {"quality": "X", "real": "⚠ 无数据（已被\"证券分析师/投资顾问\"替代）"},
    "抹灰工":           {"quality": "C", "real": "普工 / 建筑粉刷工", "note": "仅1条"},

    # ===== 其他 =====
    "国企员工":         {"quality": "D", "real": "⚠ 搜到的是国企外包客服/劳务派遣", "note": "非正式国企编制"},
    "国有企业工程师":   {"quality": "B", "real": "国企技术岗（偏电力/建筑方向）"},
    "电力公司员工":     {"quality": "B", "real": "电力工程师 / 电力施工员（非电网正编）"},
    "自来水公司员工":   {"quality": "D", "real": "⚠ 搜到的是普通公司员工/普工", "note": "关键词太宽泛"},
    "邮政员工":         {"quality": "B", "real": "邮政快递员 / 邮政客服（非正编）"},
    "景区工作人员":     {"quality": "A", "real": "景区服务员 / 景区管理", "note": "仅5条"},
    "银行柜员":         {"quality": "A", "real": "银行柜员 / 银行客户经理"},
    "二手交易商":       {"quality": "D", "real": "⚠ 降级→二手交易，搜到房产经纪", "note": "仅2条"},
    "二手车经纪人":     {"quality": "A", "real": "二手车销售 / 汽车经纪人"},
    "临床研究协调员":   {"quality": "A", "real": "临床研究协调员 / CRA / CRC"},
    "模特经纪":         {"quality": "C", "real": "艺人经纪人 / 家政经纪人", "note": "降级→经纪人，含多类"},
    "摄影工作室主理人": {"quality": "C", "real": "摄影师", "note": "仅1条"},
}

# 生成表格
rows = []
for kw in sorted(MAPPING.keys()):
    info = MAPPING[kw]
    jobs = progress.get(kw, [])
    count = len(jobs)
    salaries = [(j["salary_min"] + j["salary_max"]) / 2 for j in jobs if j.get("salary_min")]
    median = int(sorted(salaries)[len(salaries) // 2]) if salaries else 0
    rows.append({
        "原始岗位": kw,
        "数据质量": info["quality"],
        "招聘市场真实对应": info["real"],
        "样本数": count,
        "中位月薪": median if median else "无",
        "备注": info.get("note", ""),
    })

df = pd.DataFrame(rows)
df = df.sort_values(["数据质量", "原始岗位"])

# 保存
csv_path = config.OUTPUT_DIR / "job_mapping_table.csv"
df.to_csv(csv_path, index=False, encoding=config.CSV_ENCODING)

xlsx_path = config.OUTPUT_DIR / "job_mapping_report.xlsx"
with pd.ExcelWriter(xlsx_path, engine="openpyxl") as w:
    df.to_excel(w, sheet_name="岗位对应关系", index=False)
    # 按质量分类汇总
    summary = df.groupby("数据质量").agg(岗位数=("原始岗位", "count")).reset_index()
    summary.to_excel(w, sheet_name="质量汇总", index=False)

print(f"已保存: {csv_path}")
print(f"已保存: {xlsx_path}")
print()

# 打印汇总
print("=" * 90)
print("  数据质量汇总")
print("=" * 90)
for q in ["A", "B", "C", "D", "X"]:
    sub = df[df["数据质量"] == q]
    labels = {"A": "精准匹配", "B": "基本匹配", "C": "部分相关", "D": "数据偏差大", "X": "无数据"}
    print(f"  {q} ({labels[q]}): {len(sub)} 个岗位")

print()
print("=" * 90)
print("  降级搜索 + 数据偏差 + 无数据的岗位详细说明")
print("=" * 90)
for _, row in df[df["数据质量"].isin(["C", "D", "X"])].iterrows():
    print(f"  [{row['数据质量']}] {row['原始岗位']}")
    print(f"      → 实际对应: {row['招聘市场真实对应']}")
    if row["备注"]:
        print(f"      → 说明: {row['备注']}")
    print()


if __name__ == "__main__":
    pass
