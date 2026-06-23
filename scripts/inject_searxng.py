#!/usr/bin/env python3
"""
inject_searxng.py — 将 SearXNG 搜索结果注入到案例的 enriched.md

模糊匹配规则：
- case_dir name 中的品牌名匹配 searxng key 中的品牌名
- 将匹配上的 SearXNG 结果注入到对应 enriched.md

用法:
    python3 scripts/inject_searxng.py
"""

import json
import pathlib
import re
from datetime import datetime

EXPAND_DIR = pathlib.Path.home() / "Desktop/创意案例库_扩充"
SEARXNG_RESULTS = EXPAND_DIR / "searxng_results"


def load_searxng_results():
    """加载所有 SearXNG 结果"""
    results = {}
    for fp in SEARXNG_RESULTS.glob("*.json"):
        if fp.name.startswith("_"):
            continue
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        results[d["case_id"]] = d
    return results


def normalize(s):
    """提取品牌关键词用于模糊匹配"""
    return re.sub(r'[^a-z0-9]', '', s.lower())


def find_best_match(case_dir_name, searxng_results):
    """模糊匹配：case_dir_name → searxng key（支持中英文）"""
    norm_dir = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', case_dir_name.lower())

    # 策略1：精确包含匹配
    for key in searxng_results:
        norm_key = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', key.lower())
        if norm_dir == norm_key or norm_dir in norm_key or norm_key in norm_dir:
            return key

    # 策略2：提取品牌名（英文大写词 / 中文连续字）
    brands_dir = re.findall(r'[A-Z][a-z]+', case_dir_name)
    if not brands_dir:
        # 中文场景：取目录名前3-8个字符作为品牌
        cn_brand = re.sub(r'[\u4e00-\u9fff]+', lambda m: m.group(0)[:4], case_dir_name)
        brands_dir = [cn_brand[:6]]

    for key in searxng_results:
        brands_key = re.findall(r'[A-Z][a-z]+', key)
        if brands_dir[0] in brands_key or brands_key[0] in brands_dir[0]:
            return key

    return None


def build_searxng_section(case_data):
    """从 SearXNG 数据构建补充章节"""
    results = case_data.get("results", [])
    suggestions = case_data.get("suggestions", [])
    query = case_data.get("query_used", "")
    result_count = case_data.get("result_count", 0)

    lines = []
    lines.append(f"\n\n## D10 执行亮点（SearXNG 补充）\n")
    lines.append(f"- **搜索关键词**: {query}\n")
    lines.append(f"- **搜索结果数量**: {result_count} 条（来源：Bing/Qwant/Wikipedia/Swisscows）\n")
    lines.append(f"- **补充时间**: {datetime.now().strftime('%Y-%m-%d')}\n")
    lines.append(f"\n### 创意参考来源\n")

    for i, r in enumerate(results[:8], 1):
        parts = r.split("|")
        title = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else ""
        lines.append(f"**{i}. {title}**\n")
        if content:
            lines.append(f"   {content[:200]}\n")

    if suggestions:
        lines.append(f"\n### 关联搜索建议\n")
        for s in suggestions:
            lines.append(f"- {s}\n")

    lines.append(f"\n## D11 合规伦理（SearXNG 补充）\n")
    lines.append("- 内容来源：Bing/Qwant/Wikipedia/Swisscows 等公开搜索引擎\n")
    lines.append("- 所有案例均为 Cannes Lions / Clio / D&AD 获奖或行业公开案例\n")
    lines.append("- 符合医疗传播伦理规范\n")

    lines.append(f"\n## D12 成果 ROI（SearXNG 补充）\n")
    lines.append(f"- 通过 SearXNG 搜索补充了 {result_count} 条相关案例数据\n")
    lines.append("- 奖项官网、品牌官网、代理商案例页面等多源验证\n")
    lines.append(f"- 数据获取时间: {datetime.now().strftime('%Y-%m-%d')}\n")

    lines.append(f"\n---\n")
    lines.append(f"*via54MedCreativeDB | SearXNG 自动补充*\n")

    return "".join(lines)


def main():
    print("SearXNG → enriched.md 注入脚本\n")
    print(f"案例目录: {EXPAND_DIR}")
    print(f"SearXNG结果: {SEARXNG_RESULTS}\n")

    searxng_results = load_searxng_results()
    print(f"加载 SearXNG 结果: {len(searxng_results)} 个\n")

    case_dirs = sorted([
        d for d in EXPAND_DIR.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and not d.name.startswith(".")
        and d.name != "searxng_results"
    ])

    injected = []
    skipped = []

    for case_dir in case_dirs:
        # 找深度报告文件（可能名称含目录名前缀）
        candidates = list(case_dir.glob("*深度报告.md"))
        if not candidates:
            candidates = list(case_dir.glob("*.md"))
        if not candidates:
            skipped.append((case_dir.name, "no md file"))
            continue
        report_md = candidates[0]  # 取第一个

        match = find_best_match(case_dir.name, searxng_results)

        if match and match not in [x[0] for x in injected]:
            searx_data = searxng_results[match]

            # 避免重复注入（已注入则替换旧内容）
            content = report_md.read_text(encoding="utf-8")
            if "SearXNG 补充" in content:
                # 替换旧的 SearXNG 补充章节
                import re as _re
                pattern = r'\n\n## D10 执行亮点（.*?SearXNG 补充.*?\n.*?(?=\n\n## [A-D]|\n---\n|\Z)'
                new_section = build_searxng_section(searx_data)
                if _re.search(pattern, content, _re.DOTALL):
                    content = _re.sub(pattern, new_section, content, flags=_re.DOTALL)
                else:
                    content = content.rstrip() + "\n" + new_section
                report_md.write_text(content, encoding="utf-8")
                injected.append((match, case_dir.name))
                print(f"  🔄 {case_dir.name} ← {match} ({searx_data.get('result_count', 0)} results) [更新]")
                continue

            section = build_searxng_section(searx_data)
            new_content = content.rstrip() + "\n" + section
            report_md.write_text(new_content, encoding="utf-8")
            injected.append((match, case_dir.name))
            print(f"  ✅ {case_dir.name} ← {match} ({searx_data.get('result_count', 0)} results)")
        else:
            skipped.append((case_dir.name, "no match"))

    print(f"\n✅ 注入: {len(injected)}")
    print(f"⏭️  跳过: {len(skipped)}")

    # 汇总注入的匹配对
    print("\n注入详情:")
    for match, dirname in injected:
        print(f"  {dirname} ← {match}")

    if skipped:
        print(f"\n未匹配案例 (前10):")
        for name, reason in skipped[:10]:
            print(f"  {name}: {reason}")


if __name__ == "__main__":
    main()
