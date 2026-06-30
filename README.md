---
title: via54ADIdeahub
description: 医学传播创意向量知识库 — 纯 Python TF-IDF + SQLite，无需外部向量 API
version: 1.0
date: 2026-06-22
license: MIT
repository: G:/agent/ai/projects/via54ADIdeahub
keywords: [medical-marketing, creative-brief, case-study, tfidf, vector-search, hermes-agent, rag, knowledge-base]
topics: [medical-marketing, creative-strategy, campaign-analysis, 12-dimension-framework]
framework_sources: [digitaling, meihua, cannes-lions]
dimensions: 12
python: "≥3.9"
last_updated: 2026-06-22
---

# via54ADIdeahub


> **🌐 Language**: [🇨🇳 中文](#) (current) | [🇺🇸 English](./README_EN.md)
>
> _This document is in Chinese. For English, click above._
> 医学传播创意向量知识库 — 纯 Python TF-IDF + SQLite，无需外部向量 API

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![12维框架](https://img.shields.io/badge/维度-12维-orange.svg)](#)
[![纯Python实现](https://img.shields.io/badge/依赖-纯Python标准库-yellow.svg)](#)
[![Hermes集成](https://img.shields.io/badge/Hermes-Agent-ready-purple.svg)](#)

基于数英网、梅花网 × Cannes Lions 三大来源，对 44 个 PDF 进行语义检索，支持医学传播 12 维深度分析。

## 目录结构

```
via54ADIdeahub/
├── DESIGN.md               # 完整设计文档（含12维框架）
├── README.md               # 本文档
├── LICENSE                 # MIT
├── requirements.txt        # fpdf2, pypdf
├── via54_rag/             # 核心向量引擎
│   ├── __init__.py         # TF-IDF + SQLite 实现
│   └── __main__.py         # CLI（build / serve / search）
├── via54_rag_search.py     # Hermes Skill 调用入口
├── agents/                 # Agent 行为规范
│   ├── case-analyzer.md    # 案例分析 Agent
│   ├── brief-writer.md     # 创意简报 Agent
│   └── insight-generator.md # 洞察生成 Agent
├── knowledge/              # 结构化知识索引
│   └── index.md            # 12维标签总索引
├── scripts/                # 运维脚本
│   ├── ingest_batch.py     # 批量 PDF 导入
│   └── evaluate_recall.py  # 召回率评估
└── compressed/             # LLM 压缩版（节省 token）
    └── summary.md          # 12维摘要速查
```

## 安装

```bash
pip install -r requirements.txt
```


## 🔗 集成 (v1.1.0 新增)

via54ADIdeahub v1.1.0 跟踪 3 个高星 RAG / Vector DB / AI scraper 项目, 评估 qdrant 集成:

- [qdrant/qdrant](https://github.com/qdrant/qdrant) (25K) - Vector database
- [chroma-core/chroma](https://github.com/chroma-core/chroma) (18K) - AI-native embedding database
- [ScrapeGraphAI/Scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) (27.8K) - Python scraper based on AI

详见 [integrations/README.md](integrations/README.md) 和 [REFERENCES.md](REFERENCES.md).

---

## 快速开始

```bash
# 构建索引（新增 PDF 后必须执行）
cd G:/agent/ai/projects/via54ADIdeahub
python3 -m via54_rag build --force

# 启动服务
python3 -m via54_rag serve
# 📡 http://127.0.0.1:18765

# 查询（CLI）
python3 via54_rag_search.py "医药品牌情感创意" 5
```

## 12维分析框架

检索后按 12 维输出结构化分析：

| 维度 | 名称 | 来源 |
|------|------|------|
| D1 | 品牌背景 | 数英网品牌库 × 梅花网生命周期 |
| D2 | 竞争定位 | 数英网行业分类 |
| D3 | 人群洞察 | 数英网受众 × AARRR |
| D4 | 需求洞察 | 4C 框架 |
| D5 | 社媒偏好 | 梅花网18形式 × 数英网25标签 |
| D6 | 传播创意 | Cannes Lions × 数英网文案 |
| D7 | 整合营销 | 数英网整合营销 × Cannes PR |
| D8 | 渠道触点 | 数英网电商 × 医学特殊渠道 |
| D9 | 执行亮点 | 梅花网18形式 × Cannes Craft |
| D10 | 合规伦理 | NMPA/FDA × 药物警戒 |
| D11 | 成果ROI | Cannes效果认证 × MMM归因 |
| D12 | 传播类型专项 | Cannes Pharma/Health/Devices |

## 核心功能

- **TF-IDF 向量检索**：纯 Python 实现，无需外部向量 API
- **语义匹配**：支持中文 + 英文双语检索
- **12维分析**：D1-D12 完整框架（基于数英网 × 梅花网 × Cannes Lions）
- **PDF 原生 ingestion**：从 44 个 PDF 直连建库
- **Hermes Agent 集成**：cron + Skill + session memory

## 依赖

| 包 | 版本 | 用途 |
|----|------|------|
| pypdf | ≥4.0 | PDF 解析 |
| fpdf2 | ≥2.7 | 中文 PDF 生成 |

> **无需** numpy/sklearn/chromadb/faiss — 纯 Python 标准库实现

## 启动服务

```bash
python3 -m via54_rag serve
```

launchd 守护：`com.via54.rag`（KeepAlive=true）

## 数据来源

- ADFEST 2026 Winners（22 PDF）
- ADFEST 2024/2025（6 PDF）
- 广告门 Cannes 案例图文（9 PDF）
- 梅花网案例（1 PDF）
- 机构报告 Ogilvy/ICS/Ketchum/WARC/D&AD（5 PDF）
- Festival Report（1 PDF）
