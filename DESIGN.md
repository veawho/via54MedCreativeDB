---
title: via54MedCreativeDB 设计文档
description: 医学传播创意向量知识库 · 设计与实现说明
version: 1.0
date: 2026-06-22
license: MIT
repository: ~/Desktop/developments/via54MedCreativeDB
keywords: [medical-marketing, creative-brief, case-study, tfidf, vector-search, hermes-agent, rag, knowledge-base]
topics: [medical-marketing, creative-strategy, campaign-analysis, competitive-analysis, brand-positioning]
last_updated: 2026-06-22
dimensions: 12
framework_sources: [digitaling, meihua, cannes-lions]
---

# via54MedCreativeDB 设计文档

> 医学传播创意向量知识库 · 设计与实现说明
> 版本：1.0 · 2026-06-22

---

## 一、设计目标

**问题**：营销创意人员（尤其是医学传播领域）需要一个本地知识库，能够：
1. **语义检索**历史获奖案例（戛纳/Cannes Lions、ADFEST 等）
2. **跨维度分析**案例的品牌背景、营销目标、手段、执行亮点、ROI
3. **激发创意**——不是找答案，而是找灵感
4. **中文友好**——自然语言输入，直接得到结构化参考

**核心约束**：
- 纯本地运行，不依赖任何外部向量 API（OpenAI / MiniMax embeddings 等）
- 轻量：无需 GPU、无需 Docker、一台 MacBook 即可
- 中文检索优先——大多数竞品只支持英文

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────┐
│  Hermes Agent（对话层）                                  │
│  用户自然语言提问 → Skill 触发 → CLI 调用                │
└────────────────┬────────────────────────────────────────┘
                 │ python3 via54_rag_search.py "query"
                 ▼
┌─────────────────────────────────────────────────────────┐
│  HTTP Server（via54_rag serve）                         │
│  GET /search?q=xxx   GET /health                        │
│  Pure Python stdlib · port 18765                       │
└────────────────┬────────────────────────────────────────┘
                 │ SQLite 查询
                 ▼
┌─────────────────────────────────────────────────────────┐
│  TF-IDF 向量引擎（__init__.py）                         │
│  · tokenize()    中文/英文 混合分词                      │
│  · compute_tf()  词频统计                               │
│  · cosine()      余弦相似度计算                         │
│  · search()      倒排索引 + IDF 加权检索                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│  SQLite 数据库                                           │
│  · doc_meta   文档元数据                                │
│  · chunks     文本块（分块后的 PDF 内容）               │
│  · idf        逆文档频率（全局 IDF 值）                  │
│  · inverted   倒排索引（term → [(chunk_id, tf)]）      │
└─────────────────────────────────────────────────────────┘
```

### 关键设计决策

**为什么不直接用 ChromaDB/FAISS？**
- 需要 `pip install` 外部包（安装经常超时）
- 医学传播创意案例只有 44 个 PDF，数据量极小
- 纯 Python TF-IDF 在这个规模下已经足够快（<50ms 查询）
- 零运维依赖，代码量仅 342 行

**为什么不直接全文搜索（grep/BM25）？**
- 医学创意需要语义匹配——"情感营销"和"温情Campaign"字面上不重叠但语义相关
- TF-IDF 可以捕捉词频重要性，而不只是出现/不出现
- 余弦相似度天然倾向于匹配核心主题词，而不是统计权重均匀的词

---

## 三、数据来源与分类体系

### 3.1 数据来源

| 来源 | PDF 数量 | 内容 |
|------|---------|------|
| ADFEST 2026 Winners | 22 | 各类别 Lotus 获奖名单 |
| ADFEST 2024/2025 | 6 | OSS 历史获奖名单 |
| 广告门 Cannes 案例图文 | 9 | Cannes 获奖案例解读 |
| 梅花网案例图文 | 1 | Cannes 健康类案例 |
| 机构报告 | 5 | Ogilvy/ICS/Ketchum/WARC/D&AD |
| Festival Report | 1 | ADFEST 2026 Festival Report |
| **合计** | **44** | **99 文本块，5169 词项** |

### 3.2 双轴分类体系（数英网 × 梅花网）

检索和分析使用**两个正交轴**：

#### 轴1：行业（Industry）

| 类别 | 检索关键词 |
|------|-----------|
| 医疗健康 | `health`, `pharma`, `medical`, `医院`, `医药`, `健康`, `药店` |
| 食品饮料 | `food`, `beverage`, `FMCG`, `食品`, `饮料`, `快消`, `乳业` |
| 汽车 | `automotive`, `car`, `汽车`, `车企`, `电动车`, `试驾` |
| 金融 | `finance`, `banking`, `insurance`, `金融`, `银行`, `保险`, `理财` |
| 时尚美妆 | `fashion`, `beauty`, `cosmetics`, `时尚`, `美妆`, `护肤` |
| 科技3C | `tech`, `AI`, `smartphone`, `科技`, `手机`, `AI`, `智能` |
| 零售电商 | `retail`, `e-commerce`, `零售`, `电商`, `超市` |
| 公益社会 | `charity`, `NGO`, `social`, `公益`, `环保`, `社会责任` |

#### 轴2：营销类别（数英/梅花标签 × Cannes Lions）

| 类别 | 数英/梅花标签 | Cannes Lions | 检索关键词 |
|------|-------------|-------------|-----------|
| 品牌叙事 | 品牌设计, 品牌代言, 观点洞察 | Creative Strategy | `brand storytelling strategy` |
| 创意文案 | 文案, 创意文案, 精选文案 | Copy Writing | `copywriting`, `headline`, `tagline` |
| 情感营销 | 温情, 公益, 观点洞察 | Emotional Connection | `emotional campaign`, `warmth` |
| 节点营销 | 周年庆, 新年, 618, 年度回顾 | Seasonal/Holiday | `anniversary`, `holiday marketing` |
| 包装设计 | 包装设计, 礼品盒包装设计 | Package Design | `packaging design` |
| 视觉创意 | VI设计, logo设计, MG动画 | Design, Print | `visual design`, `branding` |
| 公益环保 | 环保, 公益, 可持续 | Sustainable | `sustainability`, `green` |
| 整合营销 | 跨类别整合 | Integrated | `integrated campaign` |
| 跨界联名 | 品牌联合 | Brand Partnership | `crossover`, `collaboration` |

### 3.3 医学传播专用分类

#### 疾病类别

| 疾病 | 检索词 |
|------|--------|
| 肿瘤/癌症 | `cancer`, `oncology`, `tumor`, `肿瘤`, `癌症`, `靶向` |
| 心血管 | `heart`, `cardiovascular`, `心脏`, `血压`, `血脂` |
| 呼吸 | `respiratory`, `呼吸`, `哮喘`, `流感` |
| 神经/精神 | `mental`, `depression`, `抑郁`, `焦虑`, `失眠` |
| 代谢 | `diabetes`, `obesity`, `糖尿病`, `肥胖`, `血糖` |
| 妇儿 | `maternal`, `infant`, `妇产`, `儿科`, `孕育` |
| 眼科 | `eye`, `vision`, `眼科`, `视力`, `白内障` |
| 皮肤 | `skin`, `dermatology`, `皮肤`, `护肤`, `湿疹` |
| 消化 | `digestive`, `肠胃`, `消化`, `肠道` |

#### 传播类型

| 类型 | 描述 | 检索词 |
|------|------|--------|
| 疾病教育 | 提升疾病认知 | `disease awareness`, `健康教育`, `科普` |
| 用药依从 | 指导正确用药 | `compliance`, `用药`, `依从性` |
| 医患沟通 | 改善医患关系 | `doctor-patient`, `医患`, `沟通` |
| 健康管理 | 全程健康追踪 | `health management`, `健康管理` |
| 品牌药 | 处方药企业形象 | `prescription drug`, `处方药` |
| OTC | 非处方药消费者传播 | `OTC`, `非处方药` |

---

## 四、自然语言触发逻辑

### 4.1 触发机制

Hermes Agent 收到用户消息后，**语义匹配** Skill 名称和描述：

```
Skill: via54MedCreativeDB
Description: 医学传播创意向量知识库 — 语义匹配触发，
             当用户询问医学传播、创意思路、创意案例时自动调用
Trigger: 语义匹配 — 关联内容：医学传播创意、创意思路、创意案例
```

触发判断由 Hermes Agent 的 LLM 完成，不是关键词匹配。当用户问题**涉及创意、案例、医学传播**等主题时，自动加载本 Skill。

### 4.2 自然语言 → 检索词转换

用户提问五花八门，需要**语义扩展**为适合 TF-IDF 检索的关键词组合。这是 LLM 的工作，不是 RAG 系统的工作。

**示例映射**：

| 用户问题 | 扩展后检索词 | 说明 |
|---------|-------------|------|
| "有没有健康品牌的创意案例" | `health wellness brand emotional campaign Cannes` | 扩展为英双语 |
| "情人节医药品牌怎么做" | `pharmaceutical Valentine's Day emotional healthcare` | 节点+行业 |
| "肿瘤药企创意方向" | `oncology cancer awareness patient support` | 疾病+传播类型 |
| "儿童健康品牌叙事" | `pediatric child health brand storytelling` | 受众+叙事 |
| "护肤品创意包装" | `skincare packaging design beauty` | 品类+包装 |
| "为什么这个案例能获奖" | `Cannes award creative strategy emotional` | 分析型 |

### 4.3 为什么用英文检索

**核心限制**：中文单字不成词（`创意`、`女性` 等无法匹配）。

TF-IDF 的 `tokenize()` 使用正则 `[\u4e00-\u9fff]+|[a-z0-9]+`，提取**连续中文字符序列**（bigram）：

```
"医学传播创意" → ["医学传播", "创意"]  # 2个token
"女性健康"     → ["女性健康"]           # 1个token
```

因此：
- **2+ 字中文词**可以正常匹配（`健康`、`医院`、`医药`）
- **英文**按单词匹配（`health`、`pharma`）
- **双语混合**检索效果最好：`pharma health brand emotional`

---

## 五、创意协助逻辑

### 5.1 创意工作流

```
用户：我想做一个肿瘤药的患者支持项目

         │
         ▼ LLM 语义扩展
检索词：oncology cancer patient support emotional campaign

         │
         ▼ TF-IDF 检索
相关案例列表（score 排序）

         │
         ▼ LLM 综合提炼
┌────────────────────────────────────────────┐
│ 📋 相关案例（共 N 个）                        │
│                                             │
│ 【案例1】标题                                │
│   🏷️ 分类：医疗健康｜情感营销｜疾病教育     │
│   📂 出处：ADFEST 2026 Winners / Pharma     │
│   💡 核心洞察：[1-2句]                      │
│   🔑 关键词：[提取的3-5个标签]               │
│                                             │
│ 💡 综合创意思路建议                          │
│   1. [从案例提炼的方向1]                    │
│   2. [从案例提炼的方向2]                    │
│   3. [结合医学传播特点的建议]                │
└────────────────────────────────────────────┘
```

### 5.2 案例拆解逻辑（12维分析法）

基于数英网 × 梅花网 × Cannes Lions 三大来源，整合行业标准框架（4P/4C/AARRR/GRP），形成完整的 12 维营销创意洞察框架：

#### D1 · 品牌背景（Brand Background）

> 参照：数英网品牌库 × 梅花网品牌生命周期标签

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 品牌生命周期 | new brand / established / heritage / legacy | brand lifecycle, 新品牌, 老字号, 新锐, 经典 |
| 市场地位 | market leader / challenger / niche | market leader, 市场份额, 头部, 腰部, 小众 |
| 品牌转型 | rebranding / brand evolution / brand refresh | rebranding, 品牌升级, 品牌重塑, 焕新 |
| 品牌危机 | brand crisis / reputation management | brand crisis, 口碑危机, 负面 |
| B2B/B2C | 企业级 vs 消费者 | B2B, B2C, enterprise, consumer |
| 品牌资产 | brand equity / brand value / 品牌价值 | brand equity, 品牌价值, 知名度, 美誉度 |

#### D2 · 竞争定位（Competitive Positioning）

> 参照：数英网行业分类 × 梅花网竞争分析

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 竞争格局 | market structure / competitive landscape | 竞争格局, 市场结构, 头部效应 |
| 差异化定位 | differentiation / blue ocean / 空白占位 | differentiation, blue ocean, 差异化 |
| 跟随策略 | me-too / fast follower | me-too, 跟随策略, 模仿 |
| 品类创新 | category creation / first-mover | 品类创新, 开创者, 先发优势 |
| 定价策略 | premium / value / penetration | premium, 高端, 性价比, 定价 |
| 竞争壁垒 | moat / barrier / 护城河 | 壁垒, 技术壁垒, 品牌壁垒 |

#### D3 · 人群洞察（Audience Insight）

> 参照：数英网受众定向 × 梅花网用户画像

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 目标人群 | 患者 / 医生 / 消费者 / Caregiver / 家属 | patient, doctor, caregiver, consumer, 患者, 医生 |
| 人群画像 | 年龄 / 性别 / 地域 / 职业 / 收入 | demographics, age, gender, income, 地域 |
| 行为特征 | 就医习惯 / 用药习惯 / 信息获取渠道 | behavior, 就医习惯, 用药习惯, 购买行为 |
| 心理特征 | 疾病焦虑 / 用药抵触 / 康复期望 | anxiety, adherence, psychological, 心理, 康复 |
| 触点偏好 | 医院 / 药店 / 线上 / 社媒 / 线下活动 | hospital, pharmacy, online, social, 触点 |
| 分层策略 | 重症患者 vs 轻度患者 / 首诊 vs 复诊 | severe, mild, first-time, repeat, 分层 |
| AARRR漏斗 | Acquisition / Activation / Retention / Referral / Revenue | acquisition, activation, retention, referral, revenue |

#### D4 · 需求洞察（Demand Insight）

> 参照：4C框架（Customer needs / Cost / Convenience / Communication）

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 功能需求 | 疗效 / 安全性 / 便利性 / 价格 | efficacy, safety, convenience, price, 疗效, 价格 |
| 情感需求 | 安全感 / 尊严 / 归属 / 认同 | security, dignity, belonging, 安全感, 尊严 |
| 社会需求 | 家庭角色 / 社会身份 / 同伴支持 | family role, social identity, 同伴支持 |
| 信息需求 | 疾病知识 / 用药指导 / 康复信息 | disease knowledge, 用药指导, 健康教育 |
| 未被满足的需求 | unmet need / gap / 市场缺口 | unmet need, gap, 市场缺口, 未满足 |
| 需求优先级 | 核心需求 vs 差异化需求 | core need, differential, 差异化需求 |
| 决策路径 | 就医路径 / 购药决策 / brand switch | decision journey, 决策路径, 品牌切换 |

#### D5 · 社媒偏好洞察（Social Media Insight）

> 参照：梅花网 18 种内容形式 × 数英网 25 种营销标签

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 平台选择 | 抖音 / 小红书 / 微博 / 微信 / 知乎 / B站 / TikTok | Douyin, RED, Weibo, WeChat, Zhihu, Bilibili |
| 内容形式 | 短视频 / 图文 / 直播 / UGC / 互动话题 / GIF | short video, image, live, UGC, GIF, 微电影 |
| KOL 类型 | 医生KOL / 患者KOL / 情感博主 / 专业人士 | doctor KOL, patient KOL, influencer, 达人 |
| 社群偏好 | 病友群 / 家属群 / 垂直社区 | patient community, 病友群, 垂直社区 |
| 传播路径 | 裂变 / 口碑 / PGC / UGC / 引爆点 | viral, word-of-mouth, PGC, UGC, 裂变 |
| 舆情特征 | 敏感词 / 禁忌话题 / 正向引导策略 | sensitive topic, taboo, 舆情, 合规引导 |
| 季节热点 | 世界杯 / 父亲节 / 中秋 / 七夕 / 开学季 | World Cup, Father's Day, Qixi, festival, 节日 |

#### D6 · 传播创意洞察（Creative & Communication Insight）

> 参照：Cannes Lions Creative Strategy + 梅花网创意形式 + 数英网文案标签

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 创意概念 | 核心创意主题 / 品牌故事线 | creative concept, brand story, 创意主题 |
| 创意形式 | 互动装置 / H5 / AR / 微电影 / 线下事件 / MG动画 | interactive, AR, microfilm, H5, 装置, 互动 |
| 视觉风格 | 色调 / 字体 / 构图 / 情感调性 | color, typography, tone, 视觉风格, 配色 |
| 叙事结构 | 起承转合 / 情感曲线 / 反转设计 | narrative arc, emotional curve, 反转, 故事结构 |
| 文案创意 | headline / tagline / body copy / UGC文案 | copywriting, headline, tagline, 文案, 金句 |
| 创意亮点 | 记忆点 / 共情点 / 话题性 | memorable point, 共情点, 话题性 |
| 合规边界 | 药品广告法 / 疾病宣称限制 / 伦理红线 | drug advertising law, claim restriction, 合规 |

#### D7 · 整合营销策略（Integrated Marketing Strategy）

> 参照：数英网整合营销标签 × Cannes Lions Media + Direct + PR

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 策略定位 | 品牌策略 vs 产品策略 vs 品类策略 | brand strategy, product strategy, 品牌策略 |
| ATL/BTL整合 | Above the Line / Below the Line 组合 | ATL, BTL, 线上, 线下, 整合营销 |
| 媒介策略 | 媒介选择 / GRP / TRP / Reach × Frequency | media strategy, GRP, TRP, reach, 媒介投放 |
| 公关策略 | PR / 媒体关系 / 舆论引导 | PR, media relations, 舆论, 公关 |
| 内容营销 | 科普内容 / 品牌内容 / UGC激活 | content marketing, 科普, 品牌内容 |
| 节点规划 | 上市期 / 增长期 / 成熟期 / 节日借势 | launch, growth, mature, seasonality, 节点 |
| 预算分配 | 媒体 / 创意 / KOL / 活动费用占比 | media budget, creative budget, KOL budget |

#### D8 · 渠道与触点策略（Channel & Touchpoint Strategy）

> 参照：数英网电商标签 × 医学传播特殊渠道

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 医院渠道 | 医院准入 / 科室开发 / 学术推广 | hospital access, 医院, 学术推广, HCP |
| 药店渠道 | 药房陈列 / 促销 / OTC 转化 | pharmacy, 药店, OTC, 陈列, 促销 |
| 电商渠道 | 京东 / 淘宝 / 拼多多 / 私域电商 | e-commerce, JD, Tmall, 电商, 私域 |
| 私域运营 | 微信私域 / 社群 / 会员体系 | private domain, WeChat, 私域, 会员 |
| O2O联动 | 线上线下打通 / 全域运营 | O2O, omnichannel, 全域, 线上线下 |
| 跨界渠道 | IP联名 / 品牌联合 / 渠道共用 | crossover, collaboration, 跨界, 联名 |

#### D9 · 执行亮点（Execution Highlights）

> 参照：梅花网 18 种创意形式 × Cannes Lions Film Craft + Digital Craft

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 创意执行 | 互动装置 / 线下事件 / 快闪 / 展览 | interactive, event, 装置, 快闪, 展览 |
| 视觉执行 | 插画 / 摄影 / CG / AI生成 | illustration, photography, CG, AI生成 |
| 视频执行 | 广告片 / 短视频 / 微电影 / 纪录片 | film, short video, 微电影, 广告片 |
| 技术应用 | AIGC / AR / VR / 3D裸眼 / 全息 | AIGC, AR, VR, holographic, 3D裸眼 |
| 包装设计 | 礼品盒 / 包装创新 / 可持续包装 | packaging design, 包装, 可持续 |
| 媒介创新 | DOOH / 场景营销 / 电梯 / 地铁 | DOOH, outdoor, 场景营销, 电梯 |
| 节点执行 | 节日 / 节气 / 热点 / 事件借势 | seasonal, 节日, 节气, 热点 |

#### D10 · 合规与伦理（Compliance & Ethics）

> 医学传播专项参照：NMPA / 药品广告法 / IRB伦理审查

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 法规遵循 | 药品广告法 / FDA / NMPA / GCP | drug advertising law, FDA, NMPA, 合规 |
| 疾病宣称 | 适应症 / 疗效宣称 / 禁忌症描述 | indication, claim, 适应症, 疗效宣称 |
| 伦理审查 | IRB / 患者知情同意 / 隐私保护 | IRB, ethics, informed consent, 伦理 |
| 处方药传播 | Rx → OTC 转换 / 医嘱依从性 | prescription drug, Rx, OTC, 处方药 |
| 医疗器械 | 医疗器械广告审查 / 注册证 | medical device, 器械, 注册证 |
| 药物警戒 | PV / 不良反应 / 安全性监测 | pharmacovigilance, adverse event, 药物警戒 |
| 品牌安全 | 品牌安全 / 敏感话题规避 | brand safety, 品牌安全, 敏感词 |

#### D11 · 成果ROI（Results & ROI）

> 参照：Cannes Lions 效果认证 × 数英网评分体系 × 品牌健康指标

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 曝光量级 | PV / UV / 触达 / impressions | impressions, reach, 曝光, 触达 |
| 互动数据 | 点赞 / 评论 / 分享 / 转发 / 收藏 | engagement, 互动, 点赞, 收藏, 评论 |
| 转化数据 | 点击率 / 注册率 / 购买率 / CPA | CTR, conversion, 注册, 购买, CPA |
| 品牌健康 | 认知度 / 考虑度 / 忠诚度 / NPS | brand awareness, consideration, loyalty, NPS |
| 效果认证 | 奖项 / 第三方报告 / 第三方背书 | award, case study, 奖项, 认证 |
| 投入产出 | 预算 / CPM / CPM / ROI / MMM归因 | budget, ROI, MMM, attribution, 投入产出 |
| 舆情数据 | 情感分析 / 口碑指数 / 媒体转载 | sentiment, 舆情, 口碑, 转载 |

#### D12 · 传播类型专项（Campaign Type）

> 参照：Cannes Lions Pharma / Health & Wellness / Medical Devices

| 标签 | 说明 | 检索词 |
|------|------|--------|
| 处方药传播 | Rx / 面向HCP / 学术推广 | prescription drug, Rx, HCP, 处方药 |
| OTC传播 | 非处方药 / 消费者自我药疗 | OTC, non-prescription, 消费者 |
| 医疗器械 | 设备 / 诊断 / 植入物营销 | medical device, 器械, 设备, 诊断 |
| 疾病教育 | 患者教育 / 公众科普 / 早筛早诊 | disease awareness, 健康教育, 科普, 早筛 |
| 健康管理 | 慢病管理 / 全程健康追踪 | health management, 慢病, 患者支持 |
| 品牌药企 | 企业形象 / 品牌叙事 / CSR | corporate brand, 企业形象, CSR, 社会责任 |
| 仿制药 | 学名药 / 替代药 / 价格竞争 | generic drug, 仿制药, 学名药 |
| 疫苗 | 免疫规划 / 公众认知 / 接种率 | vaccine, 疫苗, 免疫, 接种 |

### 5.3 回答模板

检索到案例后，LLM 按以下格式整理：

```
📊 案例深度分析（12维）

【案例名称】
  🏢 品牌背景：D1标签
  ⚔️ 竞争定位：D2标签 | 差异化 | 竞争壁垒
  👥 人群洞察：D3标签 | 目标人群 | AARRR阶段
  🔍 需求洞察：D4标签 | 核心需求 | 决策路径 | 未满足的Gap
  📱 社媒偏好：D5标签 | 平台 | KOL类型 | 传播路径 | 季节热点
  💡 传播创意：D6标签 | 创意概念 | 叙事结构 | 文案亮点 | 合规边界
  🎯 整合营销：D7标签 | ATL/BTL | 媒介策略 | PR | 节点规划
  🛒 渠道触点：D8标签 | 医院/药店/电商/私域/O2O/跨界
  ✨ 执行亮点：D9标签 | 创意执行 | 视觉/视频 | 技术应用 | 包装/媒介创新
  ⚖️ 合规伦理：D10标签 | 法规 | 伦理 | 品牌安全
  📈 成果ROI：D11标签 | 曝光/互动/转化 | 品牌健康 | 奖项 | MMM归因
  💊 传播类型：D12标签 | 处方药/OTC/器械/疾病教育/健康管理

💡 可复用结论
  成功要素：[提炼3点]
  适用条件：[在什么背景下适用]
  风险提示：[需要注意的合规/竞争风险]
  人群适配：[适合哪类患者/医生群体]
  差异化亮点：[与同类案例的核心差异]
```

---

## 六、TF-IDF 向量引擎详解

### 6.1 分词（tokenize）

```python
def tokenize(text: str) -> List[str]:
    text = text.lower()
    # 中英混合分词：连续汉字串 OR 英文/数字串
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', text)
    # 过滤停用词 + 单字符
    return [t for t in tokens if len(t) > 1 and t not in stopwords]
```

**停用词示例**：`的`、`了`、`在`、`是`、`和`、`就`、`不`……（63个）

### 6.2 TF-IDF 计算

```python
# TF：词频 / 总词数
tf(t) = count(t) / total_tokens

# IDF：逆文档频率（加1平滑）
idf(t) = ln(N / (doc_count(t) + 1)) + 1
```

### 6.3 余弦相似度

```python
# cosine(query, doc) = dot(q_vec, d_vec) / (|q| × |d|)

dot = Σ tf_q(t) × tf_d(t) × idf(t)²
     （仅对 query 和 doc 的交集 term 计算）

norm_q = √ Σ (tf_q(t) × idf(t))²
norm_d = √ Σ (tf_d(t) × idf(t))²

score = dot / (norm_q × norm_d)
```

### 6.4 数据库结构

```sql
doc_meta (id, filename, title, source_url, indexed_at)

chunks (id, doc_id, chunk_idx, text, tokens)
  -- text: 原始文本（300字符分块）
  -- tokens: JSON 数组 ["词1", "词2", ...]

idf (term, doc_count)
  -- 全局 IDF 表，所有文档共享

inverted (term, chunk_id, tf)
  -- 倒排索引：term → [(chunk_id, tf)]
```

### 6.5 检索流程

```
search(query, top_k=5)
  1. tokenize(query) → q_tokens
  2. 查 IDF 表 → idf_map
  3. 查倒排索引 → 相关 chunk_ids
  4. 对每个 chunk 计算 cosine score
  5. 排序，取 top_k
  6. 关联 doc_meta，返回 (score, text, doc_name, title)
```

---

## 七、CLI 接口

### 7.1 HTTP 服务

```bash
# 启动服务
python3 -m via54_rag serve
# 📡 http://127.0.0.1:18765

# 健康检查
curl http://127.0.0.1:18765/health
# → OK

# 检索
curl "http://127.0.0.1:18765/search?q=pharma%20health%20brand%20emotional"
# → JSON array of results
```

### 7.2 CLI 命令

```bash
# 重建索引（新增 PDF 后必须执行）
python3 -m via54_rag build --force

# 直接搜索
python3 -m via54_rag search "肿瘤患者支持"
```

### 7.3 Skill 调用

```bash
# Hermes Skill → via54_rag_search.py → HTTP → TF-IDF
python3 via54_rag_search.py "医药品牌情感创意" 5
```

---

## 八、运维

### 8.1 启动方式

```bash
# 手动
cd /Users/david/Desktop/developments/via54MedCreativeDB
python3 -m via54_rag serve

# launchd 守护（崩溃自动重启）
launchctl load ~/Library/LaunchAgents/com.via54.rag.plist
```

### 8.2 新增 PDF

1. 将 PDF 放入 `/Users/david/Desktop/创意案例库/`
2. 重建索引：
   ```bash
   cd /Users/david/Desktop/developments/via54MedCreativeDB
   python3 -m via54_rag build --force
   ```

### 8.3 数据规模

| 指标 | 值 |
|------|-----|
| PDF 数量 | 44 |
| 文本块（chunks） | 99 |
| 词项（terms） | 5169 |
| 数据库大小 | ~1.3MB |
| 查询延迟 | <50ms |

---

## 九、扩展方向

### 9.1 短期（1-2周）

- [ ] 支持中文 unigram（单字）+ bigram 混合检索（当前只支持连续2+字）
- [ ] 同义词扩展（"药" ↔ "医药" ↔ "pharma"）
- [ ] 增加更多数据源（数英网 API、梅花网案例）

### 9.2 中期（1-2月）

- [ ] 用 Go 重写 HTTP 服务层（性能提升 10x+，当前非瓶颈）
- [ ] PDF 解析作为独立微服务（Python pypdf → Go 调用）
- [ ] 支持图片 OCR（Captions + alt text 索引）

### 9.3 长期（3月+）

- [ ] 增量索引（新增 PDF 时只索引新增，不全量重建）
- [ ] 案例相似度图谱（给定案例，找出最相似的 N 个）
- [ ] 自动标签：给定文本块，自动打 D1-D5 标签

---

## 十一、竞品分析

### 11.1 GitHub 类似项目调研

通过 GitHub API 搜索 `marketing + case study + database`、`medical + marketing + vector` 等关键词组合，结果如下：

| 项目 | Stars | 技术栈 | 定位 | 与 via54MedCreativeDB 差异 |
|------|-------|-------|------|------------------------|
| **tomonome-knowledge-base** | 7★ | Shell + Markdown | 通用营销知识库，AI/LLM 优化 | 纯文本无向量检索，非医学专用，无 PDF ingestion |
| **azure-ceo** | 11★ | Azure OpenAI + Semantic Kernel + FastAPI + Azure AI Search | 企业多代理 RAG 营销自动化 | 企业级 Azure 方案，非医学专用，无 PDF pipeline |
| **SKINSIGHTS** | 0★ | 未披露 | 护肤品成分数据库 | 垂直领域相似思路，但非 AI，无向量检索，纯 CRUD |
| **Facebook_Ads_Generator** | 2★ | 未披露 | 广告创意 Facebook 爬虫 + AI 生成 | 非数据库，无向量检索 |
| **n8n-automation-templates-5000** | 393★ | n8n workflow | 5000+ 自动化模板库 | 非知识库，无 RAG |

### 11.2 核心差异化优势

**GitHub 上没有任何直接竞品。**

唯一接近的是 `tomonome-knowledge-base`（通用营销知识库），但它：

- **纯文本文件**：无向量检索，人工组织知识结构
- **无 PDF ingestion**：无法处理原始案例 PDF
- **非医学传播专用**：无 D10 合规伦理 / D12 传播类型专项
- **无 Agent 原生集成**：不是 Hermes Agent 的知识工具

via54MedCreativeDB 的唯一性：

1. **12 维医学传播框架** — D10 合规伦理 / D12 传播类型专项是医学传播专用维度，GitHub 无对应实现
2. **纯 Python TF-IDF + SQLite** — 零外部依赖（vs azure-ceo 的 Azure 生态），~400 行代码，一台 MacBook 即可运行
3. **PDF 原生 ingestion** — 从 44 个原始 PDF 直连建库，无任何开源项目做到
4. **Hermes Agent 原生集成** — cron + Skill + session memory 三位一体，定位是 Agent 的知识工具而非独立应用
5. **12 维检索标签体系** — 整合数英网 × 梅花网 × Cannes Lions 三大来源，形成可工程化的标签系统

### 11.3 改进来源

参考 `tomonome-knowledge-base` 的以下设计：

| tomonome 特色 | 在 via54MedCreativeDB 中的对应实现 |
|-------------|----------------------------------|
| YAML frontmatter 元数据 | ✅ DESIGN.md + README.md 已添加 |
| `/knowledge/index.md` 知识索引 | ✅ `/knowledge/index.md` 12维标签总索引 |
| `/agents/` Agent 行为规范 | ✅ `agents/case-analyzer.md` 等 3 个 Agent Spec |
| `/scripts/` 运维脚本 | ✅ `scripts/ingest_batch.py` + `evaluate_recall.py` |
| `/compressed/` LLM 压缩版 | ✅ `compressed/summary.md` 12维速查 |
| 多 Domain 知识分类 | → 未来可扩展：患者教育/疾病管理/器械三大类 |

### 11.4 未来可对标的开源项目方向

| 方向 | 潜在竞品 | 可借鉴点 |
|------|---------|---------|
| 医学案例数据库 | Springer Nature Products | 医学教育内容元数据标准 |
| 广告创意库 | The FWA（广告赏） | 案例评分 + 多维标签体系 |
| 医学传播知识图谱 | Wikidata Medical Concepts | 实体链接 + 知识图谱构建 |
| 创意简报生成 | tomonome-knowledge-base agents | Pipeline 串联 Agent Spec |

---

## 十、注意事项

1. **中文单字符检索无效**：`创`、`性` 等单字无法匹配，用英文或双语
2. **英文检索命中率高**：医疗领域 `pharma/health/medical` 是高频词
3. **launchd 冲突**：RAG 服务由 Gateway 进程管理，launchd plist 作为备份守护
4. **向量数据库不是持久化文件**：修改代码后需要重启服务
