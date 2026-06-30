#!/usr/bin/env python3
"""
案例扩充 URL 抓取器 — via54ADIdeahub
功能：
  1. 从 metadata.json 的 text_preview 中提取源 URL
  2. 用 curl 直接抓取原文页面
  3. 从页面内容中提取：案例正文、图片URL、获奖信息、效果数据
  4. 用新闻搜索补充相关报道（通过URL推断）
  5. 更新 enriched.md + links.md
"""
import re, json, sys, time, subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

PYTHON_BIN = "C:/Users/via54/AppData/Local/hermes/venv/Scripts/python.exe"
CASES_DIR   = Path.home() / "Desktop" / "创意案例库_扩充"

# ─── URL 提取 ───
def extract_urls_from_text(text: str) -> list:
    """从文本中提取所有 URL"""
    url_pattern = re.compile(r'https?://[^\s<>\"\')\]]+')
    return list(set(url_pattern.findall(text)))

# ─── curl 抓取 ───
def curl_fetch(url: str, timeout: int = 15) -> str:
    """用 curl 获取页面内容"""
    try:
        result = subprocess.run(
            ['curl', '-s', '--max-time', str(timeout), '-L', '-A',
             'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
             url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        return result.stdout
    except Exception as e:
        return f"<!-- ERROR: {e} -->"

def extract_article_text(html: str) -> str:
    """从 HTML 中提取正文文本"""
    # 移除 script/style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', html)
    # 清理空白
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

def extract_images_from_html(html: str) -> list:
    """从 HTML 中提取图片 URL"""
    img_pattern = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
    return [url.strip() for url in img_pattern.findall(html)
            if not url.startswith('data:') and 'logo' not in url.lower()
            and len(url) > 20]

def extract_meta_description(html: str) -> str:
    """提取 meta description"""
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
                  html, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
                  html, re.IGNORECASE)
    return m.group(1) if m else ""

# ─── 新闻源搜索（直接 URL 构造）───
NEWS_SOURCES = {
    "adquan":  "https://www.adquan.com/{path}",
    "digitaling": "https://www.digitaling.com/search?q={q}",
    "meihua":   "https://www.meihua.info/search?q={q}",
    "sina":    "https://search.sina.com.cn/?q={q}&c=news",
    "sohu":    "https://search.sohu.com/?keyword={q}",
    "baidu":   "https://www.baidu.com/s?wd={q}",
}

def build_news_urls(case_name: str) -> dict:
    """为案例构造可能的新闻来源 URL"""
    q = case_name.replace(' ', '+')
    return {
        "adquan":  f"https://www.adquan.com/search?q={q}",
        "digitaling": f"https://www.digitaling.com/search?q={q}",
        "meihua":   f"https://www.meihua.info/search?q={q}",
        "baidu_news": f"https://www.baidu.com/s?wd={q}+案例&rn=20",
        "sina_news":  f"https://search.sina.com.cn/?q={q}+营销案例&c=news",
    }

# ─── 处理单个案例 ───
def process_case(case_path: Path) -> dict:
    """
    处理单个案例文件夹
    Returns: {"status", "case_name", "urls_found", "article_text", "images", "error"}
    """
    case_name = case_path.name

    # 读取 metadata.json
    meta_file = case_path / "metadata.json"
    if not meta_file.exists():
        return {"status": "skip", "case_name": case_name, "error": "no metadata.json"}

    with open(meta_file) as f:
        meta = json.load(f)

    text_preview = meta.get("text_preview", "")
    urls_in_text = extract_urls_from_text(text_preview)
    search_keywords = meta.get("search_keywords", [])

    results = {
        "status": "done",
        "case_name": case_name,
        "source_urls": [],
        "article_texts": [],
        "images": [],
        "news_urls": [],
        "error": None
    }

    # 1. 抓取 text_preview 中的 URL
    for url in urls_in_text:
        if len(url) > 10:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # 跳过重复的根域名
            if not domain:
                continue

            print(f"    🌐 {domain}: {url[:80]}")
            html = curl_fetch(url)

            if "<!-- ERROR:" in html or len(html) < 200:
                print(f"       ❌ 抓取失败")
                continue

            # 提取文章文本
            article_text = extract_article_text(html)
            if len(article_text) > 200:
                results["article_texts"].append({
                    "url": url,
                    "domain": domain,
                    "text": article_text[:3000]
                })
                results["source_urls"].append(url)

            # 提取图片
            imgs = extract_images_from_html(html)
            for img in imgs[:5]:  # 最多5张
                if img.startswith('http') and img not in results["images"]:
                    results["images"].append(img)

            print(f"       ✅ {len(article_text)} 字符, {len(imgs)} 张图")
            time.sleep(0.5)

    # 2. 构造新闻搜索 URL
    news_urls = build_news_urls(case_name)
    for name, url in news_urls.items():
        print(f"    📰 {name}: {url[:80]}")
        results["news_urls"].append({"source": name, "url": url})

    return results

# ─── 更新 enriched.md ───
def update_enriched(case_path: Path, case_name: str, meta: dict,
                    article_texts: list, source_urls: list, images: list):
    """用真实文章内容更新 enriched.md"""

    # 合并文章文本（取最长的前3段）
    combined_text = ""
    for at in sorted(article_texts, key=lambda x: len(x["text"]), reverse=True)[:3]:
        combined_text += f"\n\n### 来源: {at['domain']}\n{at['text'][:2000]}"

    # 生成来源链接 markdown
    links_md = f"\n## 来源链接\n\n"
    seen_domains = set()
    for url in source_urls:
        domain = urlparse(url).netloc
        if domain and domain not in seen_domains:
            links_md += f"- **{domain}**: {url}\n"
            seen_domains.add(domain)

    # 生成图片 markdown
    imgs_md = ""
    if images:
        imgs_md = "\n## 相关图片\n\n"
        for i, img in enumerate(images[:10], 1):
            imgs_md += f"- 图片{i}: {img}\n"

    # 构建完整 enriched.md
    case_title = case_name.replace('_', ' ')

    # 从 article_text 提取有价值的内容片段
    key_content = combined_text[:4000] if combined_text else (
        f"\n\n## 案例正文（来自 PDF + 网络补充）\n\n"
        f"原文摘要: {meta.get('text_preview', '')[:1000]}"
    )

    enriched = f"""---
title: {case_title}
description: 12维医学传播创意案例分析
version: 1.0
date: 2026-06-23
source: {meta.get('source_pdf', '')}
status: web_enriched
dimensions: [D1,D2,D3,D4,D5,D6,D7,D8,D9,D10,D11,D12]
---

# {case_title}

> 网络扩充版 · 2026-06-23 · via54ADIdeahub

## 案例概述

（基于 PDF 原文 + 网络来源补充）

{key_content if key_content else '（待补充）'}

{imgs_md}

{links_md}

## 12维框架分析

### D1 · 品牌背景

### D2 · 竞争定位

### D3 · 人群洞察

### D4 · 需求洞察

### D5 · 社媒偏好

### D6 · 传播创意

### D7 · 整合营销

### D8 · 渠道触点

### D9 · 执行亮点

### D10 · 合规伦理

### D11 · 成果ROI

### D12 · 传播类型
"""

    enriched_file = case_path / f"{case_name}.enriched.md"
    with open(enriched_file, 'w', encoding='utf-8') as f:
        f.write(enriched)

    # 更新 metadata.json
    meta["status"] = "web_enriched"
    meta["web_enriched_at"] = datetime.now().isoformat()
    meta["source_urls"] = source_urls
    meta["news_urls"] = [n["url"] for n in article_texts]
    meta["images"] = images[:10]
    with open(case_path / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return len(combined_text)

# ─── 批量处理 ───
def main():
    cases_dir = CASES_DIR
    total = 0
    success = 0
    failed = []

    print(f"📂 案例目录: {cases_dir}")
    print(f"⏰ 开始时间: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    # 按子目录遍历
    for case_path in sorted(cases_dir.iterdir()):
        if not case_path.is_dir() or case_path.name.startswith('_'):
            continue
        if case_path.name.startswith('.'):
            continue

        total += 1
        print(f"\n[{total}] 📁 {case_path.name}")

        try:
            result = process_case(case_path)

            if result["article_texts"]:
                char_count = update_enriched(
                    case_path,
                    case_path.name,
                    json.loads((case_path / "metadata.json").read_text()),
                    result["article_texts"],
                    result["source_urls"],
                    result["images"]
                )
                print(f"   ✅ 更新 enriched.md ({char_count} 字符)")
                success += 1
            else:
                # 仍更新 links.md
                meta = json.loads((case_path / "metadata.json").read_text())
                meta["status"] = "web_enriched_no_content"
                json.dump(meta, open(case_path / "metadata.json", 'w'), ensure_ascii=False, indent=2)
                print(f"   ⚠️ 无内容可更新（仅更新 metadata）")
                success += 1

        except Exception as e:
            print(f"   ❌ 错误: {e}")
            failed.append(case_path.name)

    print("\n" + "=" * 60)
    print(f"✅ 完成: {success}/{total} 案例")
    if failed:
        print(f"❌ 失败: {', '.join(failed)}")
    print(f"⏰ 结束时间: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == "__main__":
    main()
