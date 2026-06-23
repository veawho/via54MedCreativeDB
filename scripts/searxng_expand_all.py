#!/usr/bin/env python3
"""
searxng_expand_all.py — 全量案例 SearXNG 中英文内容扩充
遍历 ~/Desktop/创意案例库_扩充/ 所有案例目录，
从深度报告中提取品牌+活动名，分别用英文和中文 SearXNG 搜索，
结果保存到 searxng_results/。
"""

import json
import time
import urllib.request
import urllib.parse
import re
from pathlib import Path

SEARXNG_URL = "http://127.0.0.1:8888"
EXPAND_DIR = Path.home() / "Desktop/创意案例库_扩充"
OUT_DIR = EXPAND_DIR / "searxng_results"
OUT_DIR.mkdir(exist_ok=True)
SUMMARY_FILE = OUT_DIR / "_all_results.json"

# 停用词（用于构建中文搜索词）
STOPWORDS_CN = {"的", "了", "在", "是", "和", "与", "为", "与", "的", "及", "等", "其"}


def search_searxng(query, limit=10):
    """POST to SearXNG JSON API"""
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
        print(f"    [WARN] {e}")
        return {}


def extract_text_from_result(r):
    """从单条 SearXNG 结果提取 title + content 拼接文本"""
    parts = []
    title = r.get("title", "")
    content = r.get("content", "")
    url = r.get("url", "")
    if title:
        parts.append(title.strip())
    if content:
        parts.append(content.strip())
    if url:
        parts.append(f"来源: {url}")
    return " | ".join(parts)


def build_queries(case_dir):
    """从案例目录名和报告内容构建中英文搜索词"""
    name = case_dir.name

    # 品牌名提取（连续大写字母串）
    brands = re.findall(r'[A-Z][a-z]+|[A-Z]{2,}', name)
    brand = brands[0] if brands else name.split("_")[0]

    # 尝试读报告第一行获取活动描述
    report_files = list(case_dir.glob("*深度报告.md"))
    campaign_kw = ""
    if report_files:
        content = report_files[0].read_text(encoding="utf-8")
        # 取 meta description 或第一个 h1 后的内容
        m = re.search(r'description:\s*(.+)', content)
        if m:
            campaign_kw = m.group(1).strip()[:60]

    # 英文搜索词
    en_queries = [
        f"{brand} {campaign_kw} Cannes Lions 2024 2025 health campaign".strip(),
        f"{brand} healthcare creative campaign award 2024 2025".strip(),
        f"{brand} pharmaceutical advertising case study".strip(),
    ]
    # 中文搜索词
    zh_queries = [
        f"{brand} {campaign_kw} 营销案例 2024 2025".strip(),
        f"{brand} 医疗健康 广告创意 奖项".strip(),
    ]

    # 去重
    en_queries = list(dict.fromkeys(q for q in en_queries if len(q) > 5))
    zh_queries = list(dict.fromkeys(q for q in zh_queries if len(q) > 5))

    return en_queries, zh_queries


def process_case(case_dir):
    """处理单个案例：搜索 + 保存"""
    name = case_dir.name
    en_qs, zh_qs = build_queries(case_dir)
    all_results = []
    suggestions = set()
    langs_run = {"en": False, "zh": False}

    # 英文搜索（最多 2 个查询）
    for q in en_qs[:2]:
        print(f"    🌐 EN: {q[:70]}")
        data = search_searxng(q)
        if data.get("results"):
            langs_run["en"] = True
            for r in data["results"][:8]:
                txt = extract_text_from_result(r)
                if txt:
                    all_results.append(txt)
            for s in data.get("suggestions", []):
                if s:
                    suggestions.add(s)
        time.sleep(0.5)

    # 中文搜索（最多 1 个查询）
    for q in zh_qs[:1]:
        print(f"    🌐 ZH: {q[:70]}")
        data = search_searxng(q)
        if data.get("results"):
            langs_run["zh"] = True
            for r in data["results"][:8]:
                txt = extract_text_from_result(r)
                if txt:
                    all_results.append(txt)
            for s in data.get("suggestions", []):
                if s:
                    suggestions.add(s)
        time.sleep(0.5)

    # 去重（保留顺序）
    seen = set()
    deduped = []
    for r in all_results:
        key = r.split("|")[0].strip()[:60]
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    result = {
        "case_id": name,
        "query_used": f"{en_qs[0] if en_qs else ''}",
        "queries_en": en_qs,
        "queries_zh": zh_qs,
        "result_count": len(deduped),
        "results": deduped,
        "suggestions": sorted(list(suggestions))[:10],
        "langs_run": [k for k, v in langs_run.items() if v],
    }

    out_path = OUT_DIR / f"{name}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


def main():
    print("=" * 60)
    print("SearXNG 全量案例中英文扩充")
    print(f"案例目录: {EXPAND_DIR}")
    print(f"输出目录: {OUT_DIR}")
    print("=" * 60)

    # 收集所有案例目录
    case_dirs = sorted([
        d for d in EXPAND_DIR.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and d.name != "searxng_results"
    ])
    print(f"\n共 {len(case_dirs)} 个案例目录\n")

    # 检查已完成的（跳过已存在的，避免重复搜索）
    existing = {fp.stem for fp in OUT_DIR.glob("*.json") if not fp.stem.startswith("_")}
    to_process = [d for d in case_dirs if d.name not in existing]
    print(f"待处理: {len(to_process)}（已有 {len(existing)} 个）\n")

    all_results = []
    for i, case_dir in enumerate(to_process, 1):
        print(f"[{i}/{len(to_process)}] {case_dir.name}")
        try:
            result = process_case(case_dir)
            all_results.append({
                "case_id": result["case_id"],
                "result_count": result["result_count"],
                "langs": result.get("langs_run", []),
            })
            print(f"  ✅ {result['result_count']} 条结果\n")
        except Exception as e:
            print(f"  ❌ {e}\n")
        time.sleep(1)  # 避免 SearXNG 限流

    # 写汇总
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"✅ 完成！处理 {len(all_results)} 个案例")
    print(f"📁 结果: {OUT_DIR}")
    print(f"📋 汇总: {SUMMARY_FILE}")
    print("=" * 60)

    # 统计
    total_results = sum(r["result_count"] for r in all_results)
    with_results = sum(1 for r in all_results if r["result_count"] > 0)
    en_count = sum(1 for r in all_results if "en" in r.get("langs", []))
    zh_count = sum(1 for r in all_results if "zh" in r.get("langs", []))
    print(f"总结果数: {total_results}")
    print(f"有结果案例: {with_results}/{len(all_results)}")
    print(f"英文搜索: {en_count} 个案例")
    print(f"中文搜索: {zh_count} 个案例")


if __name__ == "__main__":
    main()
