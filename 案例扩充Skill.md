# via54 案例深度扩充 Skill

## 触发词

- 扩充案例 / 案例归档
- enrich / 案例分析
- 深度总结 / 案例扩充
- 生成深度报告

---

## 核心工作流程

### 流程 A：批量处理目录

```bash
python3 ~/Desktop/developments/via54MedCreativeDB/scripts/expand_sources_and_download_images.py
```

**输出：** 每个案例文件夹生成 `{案例名}_深度报告.md`

### 流程 B：单案例扩充

```bash
python3 ~/Desktop/developments/via54MedCreativeDB/scripts/enrich_case.py \
  --pdf ~/Desktop/创意案例库/xxx.pdf \
  --output ~/Desktop/创意案例库_扩充/xxx/
```

---

## 数据来源

### 优先级

1. **PDF 原文** → `metadata.json` 的 `text_preview`
2. **网络扩充** → 广告门 / 梅花网 / 数英网直接抓取
3. **规则推断** → 品牌关键词匹配 12 维模板

### 来源数据库（100+）

**来源清单基于** [veawho/Notebook - marketing_case_study_websites.md](https://github.com/veawho/Notebook/blob/main/marketing_case_study_websites.md)

#### 中国大陆
- 数英网 `digitaling.com` — 头部案例库，每日更新
- 梅花网 `meihua.info` — 营销作品宝库
- 广告门 `adquan.com` — 老牌平台
- ADGuider `adguider.com` — 全链路策划
- SocialBeta `socialbeta.com` — 社媒营销趋势

#### 国际奖项
- Cannes Lions `canneslions.com`
- ADFEST `adfest.com`
- WARC `warc.com`
- D&AD `dandad.org`
- Effie Awards `effie.org`
- Clio Awards `clioawards.com`
- One Show `oneshow.com`

#### 代理公司
- Ogilvy / VML / Leo Burnett / TBWA / BBDO / 电通

#### 品牌官网
- 奥利奥 / 万事达卡 / 三星 / 宜家 / iFood / Apple

---

## 输出文件结构

```
{案例名}/
├── {案例名}_深度报告.md    ← 主报告（✅ 生成）
├── {案例名}.enriched.md   ← v1 分析文档
├── {案例名}.pdf           ← 原始 PDF（✅ 归档）
├── metadata.json           ← 元数据（✅ 生成）
├── links.md               ← 来源链接
└── images/                ← 提取图片（808 张总计）
```

---

## 12 维分析框架

| 维度 | 内容 |
|------|------|
| **D1 · 品牌背景** | 品牌名称/全称/描述/创立/生命周期/市场地位 |
| **D2 · 竞争定位** | 目标市场/差异化策略/竞争壁垒 |
| **D3 · 人群洞察** | 核心人群/规模/AARRR阶段/触点偏好 |
| **D4 · 需求洞察** | 核心需求/决策路径/未满足Gap |
| **D5 · 社媒偏好** | 主要平台/KOL类型/传播路径/季节热点 |
| **D6 · 传播创意** | Big Idea/创意概念/叙事结构/文案亮点/合规边界 |
| **D7 · 整合营销** | ATL/BTL组合/媒介策略/节点规划 |
| **D8 · 渠道触点** | 主要渠道/线上线下组合 |
| **D9 · 执行亮点** | 视觉/视频创新/技术应用/执行难点 |
| **D10 · 合规伦理** | 适用法规/伦理审查 |
| **D11 · 成果ROI** | 获奖情况/核心KPI/量化成果/评委点评 |
| **D12 · 传播类型** | 传播类型/行业/受众/地域 |

---

## 品牌模板（关键词匹配）

当 `text_preview` 含以下关键词时，自动应用对应品牌模板：

| 关键词 | D1/D3/D6 填充内容 |
|--------|------------------|
| `篮球 / NCAA / 裁判` | 奥利奥 NCAA 裁判条码案：10万+扫描/61%兑换率/9.8%增长 |
| `无价 / Priceless` | Mastercard 无价系列：20年品牌资产，情感叙事 |
| `女性 / 领导席位` | 粉色芯片：200万+曝光/7万首周访客 |
| `iFood / 巴西` | iFood：ADFEST 2026 Commerce 金奖 |
| `宜家 / IKEA / SHT` | 加拿大宜家 SHT：居家场景叙事 |
| `FILSA / 书展` | 智利书展 FILSA：文学活动品牌推广 |

---

## 案例分类

| 类型 | 案例数 | 数据质量 |
|------|--------|---------|
| ADFEST Winners | 21 | ✅ 高（完整获奖名单） |
| 品牌案例（广告门来源） | 9 | ✅ 高（含真实ROI数据） |
| Festival/报告 | 7 | ✅ 中（原文摘要） |
| 其他 | 3 | ⚠️ 低（规则模板推断） |

---

## 来源链接生成规则

对每个案例，自动生成以下类别搜索链接：

1. **品牌官网**（如存在）
2. **原文章节**（如 metadata.json 有 URL）
3. **30 个行业数据库搜索链接**（按数英/梅花/广告门/ADGuider/SocialBeta/Cannes Lions/ADFEST/WARC/D&D/Clio/Effie/Ogilvy/VML/Leo Burnett/TBWA/BBDO/电通/Publicis/快手/抖音/小红书/有赞 顺序）

---

## 图片资源

- **PDF 提取图片**：由 `enrich_case.py` 从 PDF 提取，保存至 `images/` 目录
- **总图片数**：808 张（最高案例含 621 张 ADFEST Festival Report）
- **命名规范**：按 PDF 页码或序号命名

---

## 质量标准

| 指标 | 要求 |
|------|------|
| `status` | `deep_analysis_v2_complete` |
| `version` | `2.0` |
| `dimensions` | `[D1,D2,D3,D4,D5,D6,D7,D8,D9,D10,D11,D12]` |
| 来源链接 | ≥10 条（含品牌官网+行业数据库） |
| D1-D12 | 全部有内容（允许"需查证"占位） |

---

## 快速命令

```bash
# 批量生成深度报告
python3 ~/Desktop/developments/via54MedCreativeDB/scripts/expand_sources_and_download_images.py

# 生成索引
python3 ~/Desktop/developments/via54MedCreativeDB/scripts/batch_enrich.py

# 统计
ls -la ~/Desktop/创意案例库_扩充/*/深度报告.md | wc -l
```
