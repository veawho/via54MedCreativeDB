#!/usr/bin/env python3
"""
批量生成 enriched.md D1-D12 分析内容
调 MiniMax API，直接写入 enriched.md
"""
import json, time, subprocess, sys, re
from pathlib import Path
from datetime import datetime

PYTHON_BIN = "/Users/david/.hermes/hermes-agent/venv/bin/python3"
CASES_DIR   = Path.home() / "Desktop" / "创意案例库_扩充"
MINIMAX_API_KEY = "YOUR_API_KEY"  # 从环境变量读取

# ─── MiniMax API ───
def call_minimax(prompt: str, model: str = "MiniMax-M2.7-highspeed",
                  max_tokens: int = 4000) -> str:
    """调 MiniMax chat API"""
    import urllib.request, urllib.parse

    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        # 尝试从配置文件读取
        cfg = Path.home() / ".config" / "minimax" / "api_key"
        if cfg.exists():
            api_key = cfg.read_text().strip()

    if not api_key:
        return f"[ERROR: No API key found]"

    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }

    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[ERROR: {e}]"

import os

# ─── 分析生成 prompt ───
def build_analysis_prompt(case_name: str, article_text: str,
                          is_adfest: bool = False,
                          adfest_metadata: dict = None) -> str:
    """构建 D1-D12 分析 prompt"""
    title = case_name.replace('_', ' ')

    adfest_section = ""
    if is_adfest and adfest_metadata:
        winners = adfest_metadata.get("text_preview", "")
        adfest_section = f"""

## ADFEST 2026 获奖名单参考
{winners[:3000]}
"""

    prompt = f"""请为以下营销案例撰写完整的12维框架分析。

## 案例名称
{title}

## 案例原文/摘要
---
{article_text[:6000] if article_text else '(无原文，基于类别信息推断)'}
---
{adfest_section}

## 输出格式要求

请生成完整的12维分析，严格按照以下格式，每维必须有实质性内容（不能只写"待分析"）：

```markdown
## D1 · 品牌背景
- 品牌名称：
- 品牌生命周期：
- 市场地位：

## D2 · 竞争定位
- 目标市场：
- 差异化策略：
- 竞争壁垒：

## D3 · 人群洞察
- 目标人群：
- AARRR阶段：
- 触点偏好：

## D4 · 需求洞察
- 核心需求：
- 决策路径：
- 未满足的Gap：

## D5 · 社媒偏好
- 主要平台：
- KOL类型：
- 传播路径：
- 季节热点：

## D6 · 传播创意
- Big Idea：
- 叙事结构：
- 文案亮点：
- 合规边界（如适用）：

## D7 · 整合营销
- ATL/BTL组合：
- 媒介策略：
- 节点规划：

## D8 · 渠道触点
- 主要渠道：
- 线上/线下组合：

## D9 · 执行亮点
- 视觉/视频创新：
- 技术应用：

## D10 · 合规伦理（如适用）
- 适用法规：
- 伦理审查：

## D11 · 成果ROI
- 获奖情况：
- 效果指标：
- 评委点评（如有）：

## D12 · 传播类型
- 传播类型：
- 目标受众：
```

**要求：**
- 所有"待分析"必须替换为基于原文的实质性内容
- 如果原文信息不足，基于案例名称和类别合理推断
- 输出纯 markdown 内容，不含标题和前言
- ADFEST Winners：获奖名单填入 D11，案例名填入对应维度"""
    return prompt

# ─── 读案例内容 ───
def get_case_content(case_path: Path) -> dict:
    """读取案例内容"""
    meta_file = case_path / "metadata.json"
    if not meta_file.exists():
        return {"text": "", "is_adfest": False, "adfest_data": None}

    with open(meta_file) as f:
        meta = json.load(f)

    text = meta.get("text_preview", "")
    # 也读 enriched.md 的 web 内容
    enriched_file = case_path / f"{case_path.name}.enriched.md"
    if enriched_file.exists():
        content = enriched_file.read_text()
        # 提取 "来源:" 标记的文章内容
        m = re.search(r"### 来源:.*?\n(.*?)(?=\n## |\n# |\Z)", content, re.DOTALL)
        if m:
            text += "\n\n" + m.group(1)

    # 判断是否 ADFEST Winners
    is_adfest = "WINNER" in case_path.name.upper() or "ADFEST" in case_path.name.upper()

    return {
        "text": text[:8000],
        "is_adfest": is_adfest,
        "adfest_data": meta if is_adfest else None
    }

# ─── 写 enriched.md ───
def write_enriched(case_path: Path, case_name: str, analysis: str,
                   source_urls: list, images: list, meta: dict):
    """写入完整的 enriched.md"""
    title = case_name.replace('_', ' ')

    # 链接
    links_md = "## 来源链接\n\n"
    for url in (source_urls or []):
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        if domain:
            links_md += f"- {domain}: {url}\n"
    if not source_urls:
        links_md += "- （待补充）\n"

    # 图片
    imgs_md = "## 相关图片\n\n"
    if images:
        for i, img in enumerate(images[:5], 1):
            imgs_md += f"- 图片{i}: {img}\n"
    else:
        imgs_md += "- （见 images/ 目录）\n"

    full_md = f"""---
title: {title}
description: 12维医学传播创意案例分析
version: 1.0
date: 2026-06-23
source: {meta.get('source_pdf', '')}
status: llm_analysis_done
dimensions: [D1,D2,D3,D4,D5,D6,D7,D8,D9,D10,D11,D12]
web_enriched: true
---

# {title}

> 网络扩充 + D1-D12框架分析版 · 2026-06-23 · via54MedCreativeDB

## 案例概述

{analysis[:500] if analysis else '（见下方12维分析）'}

{analysis}

{imgs_md}

{links_md}
"""

    enriched_file = case_path / f"{case_name}.enriched.md"
    with open(enriched_file, 'w', encoding='utf-8') as f:
        f.write(full_md)

    # 更新 metadata
    meta["status"] = "llm_analysis_done"
    meta["llm_analysis_at"] = datetime.now().isoformat()
    with open(case_path / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return len(full_md)

# ─── 主循环 ───
def main():
    total = 0
    success = 0
    skipped = 0
    failed = 0

    print(f"📂 案例目录: {CASES_DIR}")
    print(f"⏰ 开始: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    for case_path in sorted(CASES_DIR.iterdir()):
        if not case_path.is_dir():
            continue
        if case_path.name.startswith('_') or case_path.name.startswith('.'):
            continue

        case_name = case_path.name
        total += 1

        # 读 metadata
        meta_file = case_path / "metadata.json"
        if not meta_file.exists():
            print(f"[{total}] ⏭️ {case_name}: 无 metadata.json")
            skipped += 1
            continue

        with open(meta_file) as f:
            meta = json.load(f)

        # 检查是否已分析
        if meta.get("status") == "llm_analysis_done":
            # 检查 enriched.md 是否已有内容
            enriched_file = case_path / f"{case_name}.enriched.md"
            if enriched_file.exists():
                content = enriched_file.read_text()
                # 有实质内容（非"待分析"）
                if "待分析" not in content and len(content) > 3000:
                    print(f"[{total}] ⏭️ {case_name}: 已完成，跳过")
                    skipped += 1
                    continue

        print(f"[{total}] 🔍 {case_name}")

        # 读取案例内容
        content_data = get_case_content(case_path)
        text = content_data["text"]
        is_adfest = content_data["is_adfest"]
        adfest_data = content_data["adfest_data"]

        if not text and not is_adfest:
            print(f"   ⚠️ 无内容，跳过")
            skipped += 1
            continue

        # 生成分析
        prompt = build_analysis_prompt(case_name, text, is_adfest, adfest_data)
        print(f"   📝 生成分析中...")
        analysis = call_minimax(prompt)
        print(f"   ✅ 分析生成完成 ({len(analysis)} 字符)")

        # 写 enriched.md
        source_urls = meta.get("source_urls", [])
        images = meta.get("images", [])
        size = write_enriched(case_path, case_name, analysis,
                             source_urls, images, meta)
        print(f"   💾 写入 {size} 字节")

        success += 1
        time.sleep(1)  # API 限速

    print("\n" + "=" * 60)
    print(f"✅ 完成: {success}/{total} | ⏭️ 跳过: {skipped} | ❌ 失败: {failed}")
    print(f"⏰ 结束: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
