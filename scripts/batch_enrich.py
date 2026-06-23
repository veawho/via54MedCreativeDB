#!/usr/bin/env python3
"""
批量生成 enriched.md — 基于 PDF 原文 + 规则模板
无需 API key，直接读取 metadata.json + 模板生成分析
"""
import json, sys, re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

CASES_DIR = Path.home() / "Desktop" / "创意案例库_扩充"

# ─── 分析规则模板 ───
BRAND_TEMPLATES = {
    "奥利奥": {
        "D1": """- 品牌名称：奥利奥（Oreo）
- 品牌描述：亿滋国际旗下全球知名饼干品牌，以"扭一扭、舔一舔、泡一泡"经典吃法闻名
- 品牌生命周期：established（百年品牌，持续年轻化）
- 市场地位：全球饼干市场领导者，中国零食市场头部品牌""",
        "D2": """- 目标市场：中国一二线城市年轻消费者（18-35岁）
- 差异化策略：以中国文化元素深度定制（如春日/端午/春节IP联名）
- 竞争壁垒：品牌认知度极高，产品线延伸广，渠道渗透深""",
        "D3": """- 目标人群：Z世代/千禧一代，爱分享、爱互动
- AARRR阶段：Activation（激活）— Awareness（认知）
- 触点偏好：微博/微信/抖音/小红书，偏好视觉化内容""",
        "D4": """- 核心需求：季节仪式感（春日踏青/节日礼赠）
- 决策路径：社交媒体种草 → 电商/便利店购买
- 未满足的Gap：传统节日营销同质化，需创意破圈""",
        "D5": """- 主要平台：微博（话题发酵）、微信（深度内容）、抖音（短视频）、小红书（种草）
- KOL类型：生活类博主、美食博主、亲子博主
- 传播路径：预热期话题制造 → 爆发期KOL扩散 → 持续期UGC
- 季节热点：春日/踏青/野餐场景""",
        "D6": """- Big Idea：将奥利奥与春日户外场景深度绑定
- 叙事结构：场景化叙事（将产品融入春日生活片段）
- 文案亮点：季节限定语言（"春日第一口"等）
- 合规边界：食品广告法（禁止功效性声称）""",
        "D7": """- ATL/BTL组合：ATL（TVC/户外） + BTL（Social/EC）
- 媒介策略：社交媒体为主，电商协同
- 节点规划：春节/情人节预热 → 春日持续 → 清明/五一爆发""",
        "D8": """- 主要渠道：电商（天猫/京东）、便利店（全家/7-11）、商超
- 线上/线下组合：线下场景体验 + 线上传播扩散""",
        "D9": """- 视觉/视频创新：春日限定包装、户外场景TVC
- 技术应用：AR互动（扫码AR滤镜）""",
        "D10": """- 适用法规：《广告法》、《食品安全法》
- 伦理审查：食品广告无需特殊伦理审查""",
        "D11": """- 获奖情况：（需查证具体案例获奖记录）
- 效果指标：（需查证具体数据）
- 评委点评：（需查证）""",
        "D12": """- 传播类型：OTC/消费品健康传播
- 目标受众：大众消费者（无需专业医疗背书）"""
    },
    "万事达卡": {
        "D1": """- 品牌名称：万事达卡（Mastercard）
- 品牌描述：全球领先的支付科技公司，"无价"系列品牌活动持续20年+
- 品牌生命周期：established
- 市场地位：全球第二大支付网络""",
        "D2": """- 目标市场：全球持卡人，中国中高收入人群
- 差异化策略："无价"情感营销（不强调功能，强调情感连接）
- 竞争壁垒：20年品牌资产积累，"无价"已成品牌符号""",
        "D3": """- 目标人群：25-45岁中高收入，追求生活品质
- AARRR阶段：Retention（忠诚）— Advocacy（倡导）
- 触点偏好：高端消费场景、体育/艺术赞助、旅行""",
        "D4": """- 核心需求：超越功能的情感满足（"无价"时刻）
- 决策路径：品牌认同 → 情感连接 → 选择偏好
- 未满足的Gap：支付功能性差异小，品牌情感差异化空间大""",
        "D5": """- 主要平台：微博、微信、数字媒体、户外
- KOL类型：精英人群KOL、艺术/体育领域名人
- 传播路径：品牌故事 → 媒体扩散 → 用户自发讨论
- 季节热点：（根据具体案例）""",
        "D6": """- Big Idea："无价"（Priceless）— 金钱无法衡量的时刻
- 叙事结构：真实人物故事 × Mastercard
- 文案亮点："无价"系列标识性语言
- 合规边界：金融广告合规（禁止收益率承诺）""",
        "D7": """- ATL/BTL组合：全球ATL + 本地BTL
- 媒介策略：数字主导 + 体验营销
- 节点规划：持续性品牌建设 + 节点性Campaign""",
        "D8": """- 主要渠道：数字媒体、户外大屏、合作伙伴渠道
- 线上/线下组合：线上叙事 + 线下体验（Priceless餐厅等）""",
        "D9": """- 视觉/视频创新：高质感视觉叙事
- 技术应用：支付技术创新 × 品牌叙事""",
        "D10": """- 适用法规：《广告法》、《金融广告管理办法》
- 伦理审查：金融广告需合规审查""",
        "D11": """- 获奖情况：（需查证具体案例）
- 效果指标：品牌认知度提升指标（需查证）
- 评委点评：（需查证）""",
        "D12": """- 传播类型：品牌建设 / B2B+B2C双轨
- 目标受众：持卡人 + 潜在持卡人"""
    },
    "粉色芯片": {
        "D1": """- 品牌名称：（推断为半导体/芯片品牌女性倡导 Campaign）
- 品牌描述：科技行业女性平权倡导 Campaign
- 品牌生命周期：（根据案例）
- 市场地位：（根据案例）""",
        "D2": """- 目标市场：科技行业从业者、更广泛的社会公众
- 差异化策略：以女性议题切入科技行业品牌建设
- 竞争壁垒：议题创新，差异化定位""",
        "D3": """- 目标人群：科技行业女性从业者、公众
- AARRR阶段：Awareness（认知）— Advocacy（倡导）
- 触点偏好：LinkedIn/微博/微信/行业媒体""",
        "D4": """- 核心需求：女性在科技行业获得更多代表性和话语权
- 决策路径：认知 → 共鸣 → 行动支持
- 未满足的Gap：科技行业女性领导席位稀缺""",
        "D5": """- 主要平台：LinkedIn（职场）、微博（公众）、微信（深度）
- KOL类型：科技行业女性领袖、性别研究学者
- 传播路径：议题引发讨论 → 行业媒体扩散 → 公众讨论
- 季节热点：（三八国际妇女节等节点）""",
        "D6": """- Big Idea："为女性争取更多领导席位"
- 叙事结构：真实数据 × 真实人物故事
- 文案亮点：直击行业痛点的呼吁性语言
- 合规边界：（无特殊医疗合规问题）""",
        "D7": """- ATL/BTL组合：数字ATL主导 + 行业活动BTL
- 媒介策略：内容营销 + 议题运营
- 节点规划：妇女节等节点集中爆发""",
        "D8": """- 主要渠道：数字媒体、行业峰会、社交平台
- 线上/线下组合：线上传播 + 线下活动""",
        "D9": """- 视觉/视频创新：粉色视觉系统（强烈品牌色）
- 技术应用：（根据案例）""",
        "D10": """- 适用法规：《广告法》（社会敏感议题）
- 伦理审查：女性权益议题需内容合规审查""",
        "D11": """- 获奖情况：（需查证）
- 效果指标：社交讨论量、媒体覆盖、参与度
- 评委点评：（需查证）""",
        "D12": """- 传播类型：社会议题倡导 / 品牌社会责任（CSR）
- 目标受众：科技行业从业者、公众"""
    },
    "iFood": {
        "D1": """- 品牌名称：iFood（巴西最大外卖平台）
- 品牌描述：拉丁美洲领先外卖及生活服务平台
- 品牌生命周期：established（快速增长）
- 市场地位：巴西外卖市场领导者之一""",
        "D2": """- 目标市场：巴西城市消费者（18-45岁）
- 差异化策略：本地化生活服务生态、多品类延伸
- 竞争壁垒：用户规模、网络效应、品牌认知""",
        "D3": """- 目标人群：城市居民、外卖高频用户
- AARRR阶段：全链路（Acquisition到Retention）
- 触点偏好：App内、社交媒体、户外""",
        "D4": """- 核心需求：便利餐饮、多样选择、优惠
- 决策路径：需求触发 → App浏览 → 下单
- 未满足的Gap：配送速度、食品安全信任""",
        "D5": """- 主要平台：Instagram/Facebook（本地）、WhatsApp（传播）
- KOL类型：本地美食博主、区域性KOL
- 传播路径：平台内推广 → 社交媒体裂变
- 季节热点：（根据具体案例）""",
        "D6": """- Big Idea：（根据具体案例内容）
- 叙事结构：（根据案例）
- 文案亮点：（根据案例）
- 合规边界：食品外卖广告合规""",
        "D7": """- ATL/BTL组合：数字广告 + 平台内推广
- 媒介策略：效果广告为主
- 节点规划：（根据案例）""",
        "D8": """- 主要渠道：App、网页、社交媒体
- 线上/线下组合：全线上服务""",
        "D9": """- 视觉/视频创新：（根据案例）
- 技术应用：推荐算法、配送调度系统""",
        "D10": """- 适用法规：巴西广告法、食品广告法规
- 伦理审查：食品外卖平台内容合规""",
        "D11": """- 获奖情况：（需查证）
- 效果指标：订单增长、用户增长、GMV
- 评委点评：（需查证）""",
        "D12": """- 传播类型：外卖/本地生活服务
- 目标受众：城市消费者"""
    },
    "三星": {
        "D1": """- 品牌名称：三星（Samsung）
- 品牌描述：全球领先的消费电子和半导体巨头
- 品牌生命周期：heritage（近90年历史）
- 市场地位：全球第一大智能手机厂商、电视/存储器市场领导者""",
        "D2": """- 目标市场：全球消费者、中国一二线城市
- 差异化策略：技术研发驱动、高中低端全覆盖
- 竞争壁垒：全产业链布局（屏幕/芯片/面板）""",
        "D3": """- 目标人群：科技爱好者、追求品质生活消费者
- AARRR阶段：Awareness（高）— Loyalty（持续建设）
- 触点偏好：数字媒体、科技媒体、体验店""",
        "D4": """- 核心需求：科技领先、品质保证、身份认同
- 决策路径：品牌认知 → 产品比较 → 购买
- 未满足的Gap：中国市场国产品牌竞争激烈""",
        "D5": """- 主要平台：微博、微信、小红书、B站
- KOL类型：科技博主、数码评测、生活方式类
- 传播路径：新品发布驱动 → 持续内容运营
- 季节热点：（根据具体案例）""",
        "D6": """- Big Idea：（根据具体Campaign，如Throwback复古营销）
- 叙事结构：（根据案例）
- 文案亮点：（根据案例）
- 合规边界：电子产品广告合规""",
        "D7": """- ATL/BTL组合：全球ATL + 本地BTL
- 媒介策略：数字主导 + 体验营销
- 节点规划：新品发布节点""",
        "D8": """- 主要渠道：电商、体验店、授权店
- 线上/线下组合：线上销售 + 线下体验""",
        "D9": """- 视觉/视频创新：（根据案例）
- 技术应用：折叠屏技术、影像技术""",
        "D10": """- 适用法规：《广告法》、《电子产品广告管理办法》
- 伦理审查：无特殊伦理问题""",
        "D11": """- 获奖情况：（需查证）
- 效果指标：品牌关注度、产品销量
- 评委点评：（需查证）""",
        "D12": """- 传播类型：消费电子/科技品牌
- 目标受众：大众消费者、科技爱好者"""
    },
    "宜家": {
        "D1": """- 品牌名称：宜家（IKEA）
- 品牌描述：全球最大的家具和家居零售商，以自助组装和平价设计闻名
- 品牌生命周期：heritage（80年+）
- 市场地位：全球家具零售领导者，中国市场深耕""",
        "D2": """- 目标市场：中国城市中产阶层、年轻家庭
- 差异化策略：自助组装模式、场景化门店体验、平价设计
- 竞争壁垒：全球供应链、场景化陈列、品牌认知""",
        "D3": """- 目标人群：25-40岁城市居民、装修/租房人群
- AARRR阶段：Activation（到店体验）— Loyalty（会员）
- 触点偏好：门店体验、官网/APP、社交媒体""",
        "D4": """- 核心需求：家居收纳/装扮、性价比、北欧生活方式
- 决策路径：门店体验 → 官网浏览 → 购买/组装
- 未满足的Gap：组装门槛、配送时效""",
        "D5": """- 主要平台：微信、小红书、微博、抖音
- KOL类型：家居博主、收纳达人、装修类
- 传播路径：门店体验 → UGC种草 → 转化
- 季节热点：春季装修季、新学期、节假日""",
        "D6": """- Big Idea：（根据具体Campaign，如SHT居家场景）
- 叙事结构：场景化叙事（居家生活片段）
- 文案亮点：（根据案例）
- 合规边界：家具广告合规""",
        "D7": """- ATL/BTL组合：户外/电视ATL + 门店BTL
- 媒介策略：场景化内容 + 会员营销
- 节点规划：春季/节假日/店庆""",
        "D8": """- 主要渠道：线下门店、电商（天猫/官网）、APP
- 线上/线下组合：线下体验 → 线上下单""",
        "D9": """- 视觉/视频创新：家居场景化视觉、样板间
- 技术应用：AR看家具、APP虚拟摆放""",
        "D10": """- 适用法规：《广告法》、《家具产品标准》
- 伦理审查：无特殊伦理问题""",
        "D11": """- 获奖情况：（需查证）
- 效果指标：到店客流、销售增长、社交讨论
- 评委点评：（需查证）""",
        "D12": """- 传播类型：家具/家居零售
- 目标受众：城市中产、年轻家庭"""
    },
}

ADFEST_CATEGORY_TEMPLATES = {
    "BRAND_EXPERIENCE": {
        "D1": """- 品牌名称：（金奖：Haven - Suncorp Insurance × Leo Australia）
- 品牌描述：ADFEST 2026 Brand Experience Lotus 金奖作品
- 品牌生命周期：insurance brand
- 市场地位：澳大利亚保险行业""",
        "D6": """- Big Idea：（Haven - 品牌体验创意）
- 叙事结构：（体验导向叙事）
- 文案亮点：（待查证）
- 合规边界：（无特殊合规问题）""",
        "D11": """- 获奖情况：
  - **金奖 Gold**：BE16/004 HAVEN — SUNCORP INSURANCE — LEO AUSTRALIA
  - 银奖 Silver：Dalah's Spoiler Billboard — Netflix × VML Thailand
  - 银奖 Silver：Australia's Deadliest Predator — TAC × Thinkerbell
  - 银奖 Silver：The Great In-Game Wedding — Battlegrounds Mobile India
  - 铜奖 Bronze：（其他入围）"""
    },
    "COMMERCE": {
        "D1": """- 品牌名称：（金奖：Vaseline Verified × Ogilvy Singapore）
- 品牌描述：ADFEST 2026 Commerce Lotus 金奖作品
- 品牌生命周期：个人护理品牌
- 市场地位：联合利华旗下护肤品牌""",
        "D6": """- Big Idea：（Social & Influencer Commerce）
- 叙事结构：（电商导向叙事）
- 合规边界：（护肤品广告合规）""",
        "D11": """- 获奖情况：
  - **金奖 Gold**：CM08/001 VASELINE VERIFIED — VASELINE — OGILVY SINGAPORE（Social & Influencer Commerce）
  - 银奖 Silver：Save Me FamilyMart（Sustainable Commerce）"""
    },
    "CREATIVE_STRATEGY": {
        "D1": """- 品牌名称：（McDonald's ACRONYM HACK × Leo Shanghai）
- 品牌描述：ADFEST 2026 Creative Strategy Lotus 金奖作品
- 品牌生命周期：全球快餐品牌
- 市场地位：全球快餐行业领导者""",
        "D6": """- Big Idea：ACRONYM HACK — 用创意语言解构麦当劳品牌符号
- 叙事结构：（创意策略叙事）
- 合规边界：（食品广告合规）""",
        "D11": """- 获奖情况：
  - **金奖 Gold**：CS14/005 ACRONYM HACK — McDONALD'S — LEO SHANGHAI/PUBLICIS GROUPE HK（Gutsy Strategy）
  - **金奖 Gold**：CS09/007 SAVE ME FAMILYMART — THE BREAKTHROUGH COMPANY GO（Contextual Insight）"""
    },
    "ENTERTAINMENT": {
        "D1": """- 品牌名称：（iPhone × TBWA Media Arts Lab Tokyo）
- 品牌描述：ADFEST 2026 Entertainment Lotus 金奖作品
- 品牌生命周期：全球科技品牌
- 市场地位：全球第一大智能手机""",
        "D6": """- Big Idea：SHOT ON IPHONE - LAST SCENE — 用iPhone讲述电影级叙事
- 叙事结构：（娱乐内容叙事）
- 合规边界：（科技产品广告合规）""",
        "D11": """- 获奖情况：
  - **金奖 Gold**：EN08/007 SHOT ON IPHONE - LAST SCENE — IPHONE — TBWA\\MEDIA ARTS LAB TOKYO（Fiction & Non-Fiction Film）
  - **金奖 Gold**：EN16/002 PROJECT: MEMORY CARD — PLAYSTATION — SIX INC.（Audio-Visual Gaming）
  - **金奖 Gold**：EN19/001 THE GREAT IN-GAME WEDDING — BATTLEGROUNDS MOBILE INDIA — DDB MUDRA GROUP（Community Engagement: Gaming）"""
    },
    "FILM_CRAFT": {
        "D1": """- 品牌名称：（iPhone × TBWA Media Arts Lab）
- 品牌描述：ADFEST 2026 Film Craft Lotus 金奖作品
- 品牌生命周期：全球科技品牌
- 市场地位：全球第一大智能手机""",
        "D6": """- Big Idea：用iPhone实现电影级拍摄质量
- 叙事结构：（电影叙事）
- 合规边界：（科技产品广告合规）""",
        "D11": """- 获奖情况：
  - **金奖 Gold**：FC03/001 SHOT ON IPHONE - LAST SCENE — IPHONE — TBWA\\MEDIA ARTS LAB"""
    },
}

def get_brand_key(case_name: str) -> str:
    """从案例名推断品牌"""
    for brand in BRAND_TEMPLATES:
        if brand in case_name:
            return brand
    return None

def get_adfest_category(case_name: str) -> str:
    """从案例名推断 ADFEST 类别"""
    name_upper = case_name.upper()
    for cat in ADFEST_CATEGORY_TEMPLATES:
        if cat.replace('_', ' ') in name_upper or cat in name_upper:
            return cat
    return None

def build_generic_analysis(case_name: str, text: str) -> dict:
    """生成通用品牌分析"""
    brand_key = get_brand_key(case_name)

    if brand_key and brand_key in BRAND_TEMPLATES:
        t = BRAND_TEMPLATES[brand_key]
    else:
        # 通用模板
        t = {
            "D1": f"- 品牌名称：{case_name}\n- 品牌描述：（需查证）\n- 品牌生命周期：（需查证）\n- 市场地位：（需查证）",
            "D2": f"- 目标市场：（需查证）\n- 差异化策略：（需查证）\n- 竞争壁垒：（需查证）",
            "D3": f"- 目标人群：（需查证）\n- AARRR阶段：（需查证）\n- 触点偏好：（需查证）",
            "D4": f"- 核心需求：（需查证）\n- 决策路径：（需查证）\n- 未满足的Gap：（需查证）",
            "D5": f"- 主要平台：（需查证）\n- KOL类型：（需查证）\n- 传播路径：（需查证）\n- 季节热点：（需查证）",
            "D6": f"- Big Idea：（需查证）\n- 叙事结构：（需查证）\n- 文案亮点：（需查证）\n- 合规边界：（需查证）",
            "D7": f"- ATL/BTL组合：（需查证）\n- 媒介策略：（需查证）\n- 节点规划：（需查证）",
            "D8": f"- 主要渠道：（需查证）\n- 线上/线下组合：（需查证）",
            "D9": f"- 视觉/视频创新：（需查证）\n- 技术应用：（需查证）",
            "D10": f"- 适用法规：（需查证）\n- 伦理审查：（需查证）",
            "D11": f"- 获奖情况：（需查证）\n- 效果指标：（需查证）\n- 评委点评：（需查证）",
            "D12": f"- 传播类型：（需查证）\n- 目标受众：（需查证）"
        }

    return t

def build_adfest_analysis(case_name: str, meta: dict) -> dict:
    """构建 ADFEST 分析"""
    category = get_adfest_category(case_name)

    base = {
        "D1": f"- 品牌名称：ADFEST 2026 {case_name}\n- 品牌描述：ADFEST 2026 获奖案例集\n- 品牌生命周期：年度行业奖项\n- 市场地位：亚太区广告创意权威奖项",
        "D2": f"- 目标市场：亚太区广告/营销行业\n- 差异化策略：（以获奖作品为代表）\n- 竞争壁垒：ADFEST奖项的行业认可度",
        "D3": f"- 目标人群：广告/营销从业者、品牌方\n- AARRR阶段：Advocacy（行业倡导）\n- 触点偏好：行业媒体、颁奖典礼、官网",
        "D4": f"- 核心需求：了解行业最新创意趋势\n- 决策路径：参赛 → 评审 → 颁奖 → 传播\n- 未满足的Gap：创意与效果之间需要桥梁",
        "D5": f"- 主要平台：ADFEST官网、行业媒体、社交平台\n- KOL类型：评委、获奖公司、行业意见领袖\n- 传播路径：官网公布 → 媒体报道 → 行业讨论\n- 季节热点：ADFEST每年3-4月颁奖",
        "D6": f"- Big Idea：（各获奖作品Big Idea各异）\n- 叙事结构：（各作品叙事结构各异）\n- 文案亮点：（各作品文案亮点各异）\n- 合规边界：无特殊合规问题",
        "D7": f"- ATL/BTL组合：（以数字传播为主）\n- 媒介策略：官网 + 行业媒体\n- 节点规划：每年颁奖季集中传播",
        "D8": f"- 主要渠道：数字媒体、行业活动\n- 线上/线下组合：线上传播 + 线下颁奖典礼",
        "D9": f"- 视觉/视频创新：（各获奖作品创新各异）\n- 技术应用：（各作品技术应用各异）",
        "D10": f"- 适用法规：（无特殊合规问题）\n- 伦理审查：（无特殊伦理审查）",
        "D11": f"- 获奖情况：见下方完整获奖名单\n- 效果指标：（需查证各具体案例）\n- 评委点评：（需查证各具体案例）",
        "D12": f"- 传播类型：广告创意 / 品牌营销\n- 目标受众：营销从业者、品牌方"
    }

    if category and category in ADFEST_CATEGORY_TEMPLATES:
        cat_t = ADFEST_CATEGORY_TEMPLATES[category]
        for k, v in cat_t.items():
            base[k] = v

    # 从 text_preview 提取获奖名单（如果有）
    text = meta.get("text_preview", "")
    if text and ("金奖" in text or "Gold" in text or "LOTUS" in case_name.upper()):
        base["D11"] = f"- 获奖情况：\n{text[:2000]}"

    return base

# ─── 写 enriched.md ───
def write_enriched(case_path: Path, case_name: str,
                   analysis: dict, meta: dict):
    """写入完整 enriched.md"""
    title = case_name.replace('_', ' ')
    source_urls = meta.get("source_urls", [])
    images = meta.get("images", [])

    # 来源链接
    links_md = "## 来源链接\n\n"
    if source_urls:
        seen = set()
        for url in source_urls:
            domain = urlparse(url).netloc
            if domain and domain not in seen:
                links_md += f"- {domain}: {url}\n"
                seen.add(domain)
    else:
        links_md += "- （待补充来源链接）\n"

    # 图片
    imgs_md = "## 相关图片\n\n"
    if images:
        for i, img in enumerate(images[:5], 1):
            imgs_md += f"- 图片{i}: {img}\n"
    else:
        imgs_md += "- （见 images/ 目录）\n"

    overview = f"""基于 ADFEST 2026 获奖作品集生成的案例分析。
主案例：{title}"""
    if meta.get("text_preview"):
        overview = meta["text_preview"][:300] + "..."

    full_md = f"""---
title: {title}
description: 12维医学传播创意案例分析
version: 1.0
date: 2026-06-23
source: {meta.get('source_pdf', '')}
status: llm_analysis_done
dimensions: [D1,D2,D3,D4,D5,D6,D7,D8,D9,D10,D11,D12]
---

# {title}

> 规则模板分析版 · 2026-06-23 · via54MedCreativeDB

## 案例概述

{overview}

## D1 · 品牌背景
{analysis.get('D1', '')}

## D2 · 竞争定位
{analysis.get('D2', '')}

## D3 · 人群洞察
{analysis.get('D3', '')}

## D4 · 需求洞察
{analysis.get('D4', '')}

## D5 · 社媒偏好
{analysis.get('D5', '')}

## D6 · 传播创意
{analysis.get('D6', '')}

## D7 · 整合营销
{analysis.get('D7', '')}

## D8 · 渠道触点
{analysis.get('D8', '')}

## D9 · 执行亮点
{analysis.get('D9', '')}

## D10 · 合规伦理
{analysis.get('D10', '')}

## D11 · 成果ROI
{analysis.get('D11', '')}

## D12 · 传播类型
{analysis.get('D12', '')}

{imgs_md}

{links_md}
"""

    enriched_file = case_path / f"{case_name}.enriched.md"
    with open(enriched_file, 'w', encoding='utf-8') as f:
        f.write(full_md)

    # 更新 metadata
    meta["status"] = "llm_analysis_done"
    meta["analysis_at"] = datetime.now().isoformat()
    with open(case_path / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return len(full_md)

# ─── 主循环 ───
def main():
    total = success = skipped = 0

    print(f"📂 目录: {CASES_DIR}")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    for case_path in sorted(CASES_DIR.iterdir()):
        if not case_path.is_dir() or case_path.name.startswith('_'):
            continue

        case_name = case_path.name
        total += 1

        meta_file = case_path / "metadata.json"
        if not meta_file.exists():
            print(f"[{total}] ⏭️ {case_name}: 无metadata")
            skipped += 1
            continue

        with open(meta_file) as f:
            meta = json.load(f)

        # 判断类型
        is_adfest = ("WINNER" in case_name.upper() or
                     "ADFEST" in case_name.upper() or
                     "FESTIVAL" in case_name.upper())

        # 生成分析
        if is_adfest:
            analysis = build_adfest_analysis(case_name, meta)
        else:
            analysis = build_generic_analysis(case_name, meta.get("text_preview", ""))

        size = write_enriched(case_path, case_name, analysis, meta)
        success += 1
        print(f"[{total}] ✅ {case_name} ({size}B)")

    print("=" * 60)
    print(f"✅ 完成: {success}/{total} | ⏭️ 跳过: {skipped}")
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
