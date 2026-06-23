#!/usr/bin/env python3
"""
searxng_expand.py — 用 SearXNG 补充案例内容
从 ~/Desktop/创意案例库_扩充/ 读取案例，通过 SearXNG 搜索补充 D1-D12 数据，
并将结果写入案例的 enriched.md。
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import re
from pathlib import Path

# ─── 配置 ────────────────────────────────────────────────
SEARXNG_URL = "http://127.0.0.1:8888"
EXPAND_DIR = Path.home() / "Desktop/创意案例库_扩充"
OUT_DIR = EXPAND_DIR / "searxng_results"
OUT_DIR.mkdir(exist_ok=True)

# 28 个缺图案例的搜索关键词（品牌 + 奖项 + 年份）
CASES = [
    # Cannes 系列
    {"id": "GILEAD_Until", "query": "Gilead Sciences Until Then campaign Cannes Lions 2024 health", "type": "Cannes"},
    {"id": "Moderna_HPV", "query": "Moderna HPV vaccine Cannes Lions 2024 creative campaign", "type": "Cannes"},
    {"id": "BreastCancerNow_TheChat", "query": "Breast Cancer Now The Chat campaign Cannes Lions 2024", "type": "Cannes"},
    {"id": "Novartis_Fabry", "query": "Novartis Fabry disease awareness Cannes Lions 2024", "type": "Cannes"},
    {"id": "AbbVie_Skin", "query": "AbbVie skincare psoriasis campaign Cannes Lions 2024", "type": "Cannes"},
    {"id": "J&J_Skin", "query": "Johnson Johnson skin health Cannes Lions 2024 creative", "type": "Cannes"},
    {"id": "Moderna_Flu", "query": "Moderna influenza flu vaccine Cannes Lions 2024 campaign", "type": "Cannes"},
    # Clio 系列
    {"id": "GILEAD_Press", "query": "Gilead HIV press campaign Clio Awards 2024 healthcare", "type": "Clio"},
    {"id": "Moderna_mRNA", "query": "Moderna mRNA technology healthcare campaign Clio Awards 2024", "type": "Clio"},
    {"id": "Pfizer_Disease", "query": "Pfizer disease awareness Clio Awards 2024 healthcare", "type": "Clio"},
    {"id": "J&J_MedTech", "query": "Johnson Johnson medical technology Clio Awards 2024", "type": "Clio"},
    {"id": "AbbVie_AI", "query": "AbbVie AI healthcare innovation Clio Awards 2024", "type": "Clio"},
    {"id": "AZ_Asthma", "query": "AstraZeneca asthma respiratory Clio Awards 2024", "type": "Clio"},
    {"id": "Novartis_Eye", "query": "Novartis eye health vision Clio Awards 2024", "type": "Clio"},
    {"id": "Roche_Eye", "query": "Roche eye disease vision care Clio Awards 2024", "type": "Clio"},
    # D&AD 系列
    {"id": "BMS_Cancer", "query": "Bristol Myers Squibb cancer immunotherapy D&AD 2024 health", "type": "D&AD"},
    {"id": "Roche_Diagnostics", "query": "Roche diagnostics D&AD 2024 healthcare creative", "type": "D&AD"},
    {"id": "Omron_CVD", "query": "Omron cardiovascular heart health D&AD 2024 campaign", "type": "D&AD"},
    # 药企公益系列
    {"id": "GILEAD_HIV", "query": "Gilead HIV prevention awareness campaign 2024 creative", "type": "Pharma"},
    {"id": "Pfizer_Mental", "query": "Pfizer mental health youth campaign 2024 healthcare", "type": "Pharma"},
    {"id": "Dove_Mental", "query": "Dove mental health self-esteem campaign 2024", "type": "Pharma"},
    {"id": "Allergy_UK", "query": "Allergy UK awareness campaign 2024 creative", "type": "Pharma"},
    {"id": "Moderna_Side", "query": "Moderna vaccine side effects awareness 2024 campaign", "type": "Pharma"},
    {"id": "Roche_Alzheimer", "query": "Roche Alzheimer dementia awareness 2024 campaign", "type": "Pharma"},
    {"id": "JNJ_Wound", "query": "Johnson Johnson wound care chronic illness 2024 campaign", "type": "Pharma"},
    {"id": "NCI_HPV", "query": "National Cancer Institute HPV vaccine awareness 2024", "type": "Pharma"},
    # Key 文件补充
    {"id": "Eurofarma", "query": "Eurofarma healthcare Latin America campaign 2024", "type": "Key"},
    {"id": "ZIP", "query": "ZIP healthcare campaign creative 2024", "type": "Key"},
    {"id": "Working", "query": "Working healthcare creative agency campaign 2024", "type": "Key"},
    {"id": "Partners", "query": "Partners healthcare creative campaign 2024", "type": "Key"},
]

def search_searxng(query, limit=10):
    """POST to SearXNG JSON API，返回结果列表"""
    data = urllib.parse.urlencode({"q": query, "format": "json"}).encode()
    req = urllib.request.Request(
        f"{SEARXNG_URL}/search",
        data=data,
        headers={"User-Agent": "via54-searxng-expand/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  [ERROR] {e}")
        return {}


def extract_text_from_result(r):
    """从 SearXNG 结果提取文本片段"""
    texts = []
    if r.get("content"):
        texts.append(r["content"])
    if r.get("title"):
        texts.append(r["title"])
    return " | ".join(texts)


def search_case(case):
    """对一个案例搜索，返回结构化结果"""
    query = case["query"]
    print(f"\n🔍 [{case['id']}] {query[:60]}...")
    
    results = search_searxng(query, limit=15)
    items = results.get("results", [])
    suggestions = results.get("suggestions", [])
    unresponsive = results.get("unresponsive_engines", [])
    
    print(f"  → {len(items)} results | {len(suggestions)} suggestions | {len(unresponsive)} unresponsive")
    
    # 提取前 10 个结果文本
    result_texts = []
    for item in items[:10]:
        text = extract_text_from_result(item)
        if text:
            result_texts.append(text)
    
    return {
        "case_id": case["id"],
        "query_used": query,
        "result_count": len(items),
        "results": result_texts,
        "suggestions": suggestions[:5],
        "unresponsive_engines": [u[0] for u in unresponsive[:5]],
    }


def main():
    print(f"SearXNG Expansion Script")
    print(f"URL: {SEARXNG_URL}")
    print(f"Output: {OUT_DIR}")
    print(f"Cases: {len(CASES)}")
    
    # 验证 SearXNG 在线
    try:
        test = search_searxng("test", limit=1)
        print(f"\n✅ SearXNG 在线: {len(test.get('results',[]))} test results\n")
    except Exception as e:
        print(f"\n❌ SearXNG 离线: {e}")
        sys.exit(1)
    
    all_results = []
    
    for i, case in enumerate(CASES):
        result = search_case(case)
        all_results.append(result)
        
        # 每个案例单独存 JSON
        case_out = OUT_DIR / f"{case['id']}.json"
        with open(case_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ Saved → {case_out.name}")
        
        # 限速：避免触发引擎限制
        if i < len(CASES) - 1:
            time.sleep(2)
    
    # 全量汇总
    summary_path = OUT_DIR / "_all_results.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n✅ Done! {len(all_results)} cases expanded")
    print(f"📁 Results: {OUT_DIR}")


if __name__ == "__main__":
    main()
