#!/usr/bin/env python3
"""
案例扩充引擎 — via54ADIdeahub
用法:
  python3 enrich_case.py --pdf /path/to/case.pdf --output ~/Desktop/创意案例库_扩充
  python3 enrich_case.py --batch --pdf-dir /path/to/pdfs --output ~/Desktop/创意案例库_扩充

功能:
  1. 从PDF提取文本
  2. 从文件名推断案例名称
  3. 生成12维分析prompt（供Hermes agent调用LLM）
  4. 建立归档文件夹结构（不含LLM分析结果，由agent完成）
  5. 批量模式：扫描目录所有PDF，逐个创建文件夹骨架
"""
import sys, os, json, sqlite3, re, hashlib
from pathlib import Path
from datetime import datetime

# ─────────────────────────────────────────────
# 路径配置
# ─────────────────────────────────────────────
PDF_DIR   = Path("/Users/david/Desktop/创意案例库")
OUTPUT_DIR = Path.home() / "Desktop" / "创意案例库_扩充"
DB_PATH    = Path(__file__).parent.parent / "via54_rag" / "vector.db"
PYTHON_BIN = "C:/Users/via54/AppData/Local/hermes/venv/Scripts/python.exe"

# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────
def sanitize_folder_name(name: str) -> str:
    """去除非法文件名字符，空格→下划线"""
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    name = re.sub(r'\s+', '_', name)
    return name.strip('_')

def infer_case_name(pdf_path: Path) -> str:
    """
    从PDF文件名推断案例名称
    规则：
      - 去除扩展名
      - 去除数字ID前缀（如 344467_）
      - 去除平台前缀（如 广告门_、梅花网_）
      - 去除戛纳/ADFEST/Cannes等标识
      - 保留中文品牌/活动名
    """
    name = pdf_path.stem  # 无扩展名

    # 去除常见前缀
    prefixes = [
        r'^广告门_\d+_',
        r'^梅花网_\d+_',
        r'^数英网_\d+_',
        r'^\d{10,}_',           # 10位以上数字ID
        r'^ADFEST\s*',          # ADFEST前缀
        r'^Cannes\s*',          # Cannes前缀
        r'^ICS\s*',             # ICS前缀
    ]
    for p in prefixes:
        name = re.sub(p, '', name, flags=re.IGNORECASE)

    # 去除 .key 等残留扩展名
    name = re.sub(r'\.(key|pages|numbers)$', '', name, flags=re.IGNORECASE)

    return name.strip()

def extract_pdf_text(pdf_path: Path) -> str:
    """用 pypdf 提取 PDF 文本，失败返回空字符串"""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        texts = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                texts.append(txt)
        return '\n'.join(texts)
    except Exception as e:
        print(f"  ⚠️ pypdf 提取失败: {e}")
        return ""

def extract_images_from_pdf(pdf_path: Path, output_dir: Path) -> list:
    """
    从PDF提取图片
    返回提取到的图片路径列表
    """
    try:
        import pypdf
        from PIL import Image
        import io

        reader = pypdf.PdfReader(str(pdf_path))
        images = []
        img_counter = 0

        for page_num, page in enumerate(reader.pages):
            if '/XObject' in page['/Resources']:
                xobjects = page['/Resources']['/XObject'].get_object()
                for obj in xobjects:
                    if xobjects[obj]['/Subtype'] == '/Image':
                        try:
                            data = xobjects[obj].get_data()
                            if data:
                                img_counter += 1
                                img_path = output_dir / f"images" / f"page{page_num+1}_img{img_counter}.png"
                                img_path.parent.mkdir(parents=True, exist_ok=True)
                                # 尝试用PIL保存
                                try:
                                    img = Image.open(io.BytesIO(data))
                                    img.save(img_path)
                                    images.append(img_path)
                                except Exception:
                                    pass
                        except Exception:
                            pass
        return images
    except Exception as e:
        print(f"  ⚠️ 图片提取失败: {e}")
        return []

def build_search_keywords(case_name: str) -> list:
    """从案例名称生成检索关键词（用于来源链接搜索）"""
    keywords = [case_name]

    # 品牌名提取（常见品牌词）
    brands = ['奥利奥', '万事达卡', '三星', '宜家', 'iFood', '加拿大宜家',
              'FILSA', 'COLUMBIA', 'Ogilvy', 'WARC', 'Ketchum', 'DAD']
    for brand in brands:
        if brand.lower() in case_name.lower():
            keywords.append(brand)

    # 添加通用检索词
    keywords.append(f"{case_name} 案例")
    keywords.append(f"{case_name} campaign")
    keywords.append(f"{case_name} digitaling OR meihua OR Cannes")

    return keywords

def get_pdf_info(pdf_path: Path) -> dict:
    """获取PDF元信息"""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(pdf_path))
        return {
            "pages": len(reader.pages),
            "encrypted": reader.is_encrypted,
            "file_size_mb": round(pdf_path.stat().st_size / 1024 / 1024, 2),
        }
    except Exception:
        return {"pages": "unknown", "encrypted": False, "file_size_mb": round(pdf_path.stat().st_size / 1024 / 1024, 2)}

def generate_analysis_prompt(case_name: str, text: str, source_links: list) -> str:
    """生成12维LLM分析prompt（供Hermes agent使用）"""
    # 将文本截断（避免token溢出）
    max_chars = 8000
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[... 内容截断 ...]"

    links_md = "\n".join(f"{i+1}. {name}: {url}" for i, (name, url) in enumerate(source_links)) or "（暂无来源链接）"

    prompt = f"""请对以下医学传播/营销案例进行12维框架深度分析。

## 案例名称
{case_name}

## 原始案例文本
---
{text}
---

## 已收集的来源链接
{links_md}

## 分析要求

请按以下12维框架输出，每维包含：**标签** + **具体描述**：

### D1 · 品牌背景
- 品牌名称：
- 品牌生命周期：new brand / established / heritage
- 市场地位：market leader / challenger / niche

### D2 · 竞争定位
- 目标市场：
- 差异化策略：
- 竞争壁垒：

### D3 · 人群洞察
- 目标人群：
- AARRR阶段：
- 触点偏好：

### D4 · 需求洞察
- 核心需求：
- 决策路径：
- 未满足的Gap：

### D5 · 社媒偏好
- 主要平台：
- KOL类型：
- 传播路径：
- 季节热点：

### D6 · 传播创意
- Big Idea：
- 叙事结构：
- 文案亮点：
- 合规边界：

### D7 · 整合营销
- ATL/BTL组合：
- 媒介策略：
- 节点规划：

### D8 · 渠道触点
- 主要渠道：
- 线上/线下组合：

### D9 · 执行亮点
- 视觉/视频创新：
- 技术应用：

### D10 · 合规伦理
- 适用法规：
- 伦理审查：

### D11 · 成果ROI
- 曝光/互动/转化指标：
- 获奖情况：

### D12 · 传播类型
- 传播类型：Rx / OTC / 器械 / 疫苗 / 疾病教育 / 健康管理
- 目标受众：HCP / 患者 / 消费者

完成后请将分析结果写入案例文件夹中的 `{case_name}.enriched.md` 文件，格式参考 skill `via54-case-enrichment` 的 Step 6 模板。
"""
    return prompt


# ─────────────────────────────────────────────
# 单案例扩充
# ─────────────────────────────────────────────
def enrich_single_case(pdf_path: Path, output_dir: Path, force: bool = False) -> dict:
    """
    对单个PDF案例进行扩充

    Returns:
        dict: {
            "status": "created" | "skipped" | "error",
            "case_name": str,
            "folder": str,
            "analysis_prompt": str,  # 供LLM使用的分析prompt
            "pdf_info": dict,
            "search_keywords": list,
            "images": list,
            "error": str | None
        }
    """
    case_name = infer_case_name(pdf_path)
    folder_name = sanitize_folder_name(case_name)
    folder = output_dir / folder_name

    # 检查是否已存在
    if folder.exists() and not force:
        md_file = folder / f"{folder_name}.enriched.md"
        if md_file.exists():
            return {"status": "skipped", "case_name": case_name, "folder": str(folder), "error": None}

    # 创建文件夹结构
    images_dir = folder / "images"
    folder.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(exist_ok=True)

    # 复制原始PDF
    dest_pdf = folder / f"{folder_name}.pdf"
    if not dest_pdf.exists():
        import shutil
        shutil.copy2(pdf_path, dest_pdf)

    # 提取文本
    print(f"  📄 提取文本: {pdf_path.name}")
    text = extract_pdf_text(pdf_path)
    text_preview = text[:200].replace('\n', ' ') if text else "（提取失败）"

    # 获取PDF信息
    pdf_info = get_pdf_info(pdf_path)

    # 提取图片（可选，PDF图片提取较复杂）
    print(f"  🖼️  提取图片...")
    extracted_imgs = extract_images_from_pdf(pdf_path, folder)
    if extracted_imgs:
        print(f"     提取到 {len(extracted_imgs)} 张图片")

    # 生成检索关键词
    search_keywords = build_search_keywords(case_name)

    # 生成来源链接（待补充）
    source_links = [
        ("Google搜索", f"https://www.google.com/search?q={case_name}+campaign+case+study"),
        ("数英网", f"https://digitaling.com/search?q={case_name}"),
        ("梅花网", f"https://meihua.info/search?q={case_name}"),
    ]

    # 生成分析prompt
    analysis_prompt = generate_analysis_prompt(case_name, text, source_links)

    # 创建占位文件（供LLM后续填充）
    placeholder_md = folder / f"{folder_name}.enriched.md"
    placeholder_content = f"""---
title: {case_name}
description: 12维医学传播创意案例分析
version: 1.0
date: {datetime.now().strftime('%Y-%m-%d')}
source: {pdf_path.name}
status: pending_llm_analysis
dimensions: [D1, D2, D3, D4, D5, D6, D7, D8, D9, D10, D11, D12]
---

# {case_name}

> ⚠️ 此文档由 `enrich_case.py` 自动生成骨架
> LLM 12维分析待填充（分析prompt已生成）
> 扩充日期：{datetime.now().strftime('%Y-%m-%d')}
> 来源：{pdf_path.name}

## 案例概述

（LLM分析填充处）

## 12维深度分析

### D1 · 品牌背景
（LLM分析填充处）

### D2 · 竞争定位
（LLM分析填充处）

### D3 · 人群洞察
（LLM分析填充处）

### D4 · 需求洞察
（LLM分析填充处）

### D5 · 社媒偏好
（LLM分析填充处）

### D6 · 传播创意
（LLM分析填充处）

### D7 · 整合营销
（LLM分析填充处）

### D8 · 渠道触点
（LLM分析填充处）

### D9 · 执行亮点
（LLM分析填充处）

### D10 · 合规伦理
（LLM分析填充处）

### D11 · 成果ROI
（LLM分析填充处）

### D12 · 传播类型
（LLM分析填充处）

## 来源链接

（待补充来源链接，可参考以下搜索词：）
{chr(10).join(f'- {kw}' for kw in search_keywords)}

## 相关图片

（图片存放于 `images/` 目录）

## 原始文件

- 原PDF：[{folder_name}.pdf]({folder_name}.pdf)
"""
    # 避免重复写入（如果文件已存在且有内容）
    if not placeholder_md.exists():
        with open(placeholder_md, 'w', encoding='utf-8') as f:
            f.write(placeholder_content)

    # 创建 metadata.json
    metadata = {
        "case_name": case_name,
        "folder_name": folder_name,
        "source_pdf": str(pdf_path),
        "dest_pdf": str(dest_pdf),
        "created_at": datetime.now().isoformat(),
        "status": "pending_llm_analysis",
        "dimensions": ["D1","D2","D3","D4","D5","D6","D7","D8","D9","D10","D11","D12"],
        "pdf_info": pdf_info,
        "text_preview": text_preview[:500],
        "text_length": len(text),
        "search_keywords": search_keywords,
        "source_links": source_links,
        "images": [str(p) for p in extracted_imgs],
        "analysis_prompt": analysis_prompt,  # 供agent使用的prompt
    }
    with open(folder / "metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 创建 links.md
    links_content = f"""# 来源链接

## 案例名称
{case_name}

## 检索关键词
{chr(10).join(f'- {kw}' for kw in search_keywords)}

## 来源链接

### Google 搜索
- [搜索案例](https://www.google.com/search?q={case_name}+campaign+case+study)

### 数英网
- [搜索结果](https://digitaling.com/search?q={case_name})

### 梅花网
- [搜索结果](https://meihua.info/search?q={case_name})

### Cannes Lions
- [官网](https://www.canneslions.com)

### ADFEST
- [官网](https://adfest.com)

---
*此文件由 enrich_case.py 自动生成，来源链接待手动补充*
"""
    with open(folder / "links.md", 'w', encoding='utf-8') as f:
        f.write(links_content)

    print(f"  ✅ 创建归档文件夹: {folder_name}/")

    return {
        "status": "created",
        "case_name": case_name,
        "folder": str(folder),
        "folder_name": folder_name,
        "analysis_prompt": analysis_prompt,
        "pdf_info": pdf_info,
        "text_length": len(text),
        "images": [str(p) for p in extracted_imgs],
        "error": None
    }


# ─────────────────────────────────────────────
# 批量处理
# ─────────────────────────────────────────────
def process_batch(pdf_dir: Path, output_dir: Path, force: bool = False) -> dict:
    """批量处理目录下所有PDF"""
    pdf_dir = Path(pdf_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 收集所有PDF
    all_pdfs = sorted(pdf_dir.rglob("*.pdf"))
    if not all_pdfs:
        print(f"❌ 目录下没有PDF文件: {pdf_dir}")
        return {"total": 0, "created": 0, "skipped": 0, "errors": 0}

    print(f"📂 找到 {len(all_pdfs)} 个PDF文件")
    print(f"📁 输出目录: {output_dir}")
    print(f"🔄 模式: {'强制重建' if force else '增量（跳过已有）'}")
    print()

    results = []
    for i, pdf_path in enumerate(all_pdfs):
        case_name = infer_case_name(pdf_path)
        print(f"[{i+1}/{len(all_pdfs)}] {case_name}")
        try:
            result = enrich_single_case(pdf_path, output_dir, force=force)
            results.append(result)
            status_icon = "✅" if result["status"] == "created" else ("⏭️" if result["status"] == "skipped" else "❌")
            print(f"  {status_icon} {result['status']} | {result.get('folder_name', 'N/A')}")
        except Exception as e:
            print(f"  ❌ 错误: {e}")
            results.append({"status": "error", "case_name": case_name, "error": str(e)})

    # 生成总索引
    create_index(output_dir, results)

    # 统计
    created = sum(1 for r in results if r["status"] == "created")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    print()
    print("=" * 50)
    print(f"📊 批量处理完成")
    print(f"   总数: {len(all_pdfs)}")
    print(f"   新建: {created}")
    print(f"   跳过: {skipped}")
    print(f"   错误: {errors}")

    return {"total": len(all_pdfs), "created": created, "skipped": skipped, "errors": errors, "results": results}


def create_index(output_dir: Path, results: list):
    """生成全部案例总索引"""
    cases = []
    for r in results:
        if r["status"] in ("created", "skipped") and "folder" in r:
            folder = Path(r["folder"])
            metadata_file = folder / "metadata.json"
            dims = []
            if metadata_file.exists():
                with open(metadata_file) as f:
                    m = json.load(f)
                    dims = m.get("dimensions", [])
                    cases.append({
                        "case_name": r["case_name"],
                        "folder": r["folder_name"],
                        "status": m.get("status", ""),
                        "dimensions": dims,
                        "text_length": m.get("text_length", 0),
                        "pdf_info": m.get("pdf_info", {}),
                    })
            else:
                cases.append({
                    "case_name": r["case_name"],
                    "folder": r["folder_name"],
                    "status": r["status"],
                    "dimensions": dims,
                })

    # 写 _index.md
    index_md = f"""# 案例总索引

> 自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}

共 {len(cases)} 个案例。

## 索引表

| # | 案例名称 | 状态 | 维度 | PDF页数 |
|---|---------|------|------|---------|
"""
    for i, c in enumerate(cases, 1):
        status_icon = "✅已分析" if c.get("status") == "llm_analysis_done" else "⏳待LLM"
        pages = c.get("pdf_info", {}).get("pages", "?")
        index_md += f"| {i} | [{c['case_name']}]({c['folder']}/README.md) | {status_icon} | {len(c.get('dimensions', []))} | {pages} |\n"

    with open(output_dir / "_index.md", 'w', encoding='utf-8') as f:
        f.write(index_md)

    # 写 _stats.json
    stats = {
        "generated_at": datetime.now().isoformat(),
        "total": len(cases),
        "by_status": {
            "pending_llm_analysis": sum(1 for c in cases if c.get("status") == "pending_llm_analysis"),
            "llm_analysis_done": sum(1 for c in cases if c.get("status") == "llm_analysis_done"),
        }
    }
    with open(output_dir / "_stats.json", 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="案例扩充引擎")
    parser.add_argument("--pdf", type=str, help="单个PDF路径")
    parser.add_argument("--pdf-dir", type=str, help="批量PDF目录")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR),
                        help=f"输出目录（默认: {OUTPUT_DIR}）")
    parser.add_argument("--force", "-f", action="store_true",
                        help="强制重建（覆盖已有文件夹）")
    parser.add_argument("--links-only", action="store_true",
                        help="仅检索来源链接，不重建文件夹")
    args = parser.parse_args()

    output = Path(args.output)

    if args.pdf:
        result = enrich_single_case(Path(args.pdf), output)
        print(f"\n{'✅' if result['status'] == 'created' else '⏭️'} {result['case_name']}")
        if result.get("analysis_prompt"):
            print(f"\n📋 分析prompt已写入 metadata.json")
            print(f"   案例文件夹: {result['folder']}")
    elif args.pdf_dir:
        stats = process_batch(Path(args.pdf_dir), output, force=args.force)
    else:
        parser.print_help()
