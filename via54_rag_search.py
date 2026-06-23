#!/usr/bin/env python3
"""
via54_rag_search.py — via54MedCreativeDB 查询 CLI
用法: python3 via54_rag_search.py <搜索query> [top_k]
示例: python3 via54_rag_search.py "医药品牌情感创意" 5
"""
import sys, json, urllib.request, urllib.parse

PORT = 18765

def search(query: str, top_k: int = 5) -> list:
    url = f"http://127.0.0.1:{PORT}/search?q={urllib.parse.quote(query)}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.load(r)

def format_results(results: list, query: str) -> str:
    if not results:
        return f"未找到与「{query}」相关的结果"
    lines = [f"🔍 查询「{query}」— {len(results)} 个结果:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"\n【{i}】{r['title']}  (相关度: {r['score']:.2f})")
        lines.append(f"   📄 {r['doc']}")
        lines.append(f"   💬 {r['text'][:300]}...")
    return '\n'.join(lines)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: via54_rag_search.py <搜索query> [top_k]")
        sys.exit(1)
    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    try:
        results = search(query, top_k)
        print(format_results(results, query))
    except Exception as e:
        print(f"❌ 检索失败: {e}")
        sys.exit(1)
