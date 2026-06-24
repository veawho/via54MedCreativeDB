#!/usr/bin/env python3
"""
inject_vector_db.py
将 ~/Desktop/创意案例库_扩充/ 中所有案例的深度报告向量化并写入 vector.db

流程：
1. 遍历每个案例目录，找 *_深度报告.md
2. 分块（按 ## 标题 或 固定token数）
3. tokenize（简单空格分词 + unicode过滤）
4. 写入 doc_meta + chunks 表
"""

import sqlite3, json, re, os, sys
from pathlib import Path

EXPAND_DIR = Path.home() / "Desktop/创意案例库_扩充"
DB_PATH    = Path.home() / "Desktop/developments/via54MedCreativeDB/via54_rag/vector.db"

# ── 分块逻辑 ──────────────────────────────────────────────
def chunk_text(text: str, max_tokens: int = 300) -> list[str]:
    """按段落+固定token数分块"""
    # 先按 ## 分割成 sections
    sections = re.split(r'\n(?=## )', text)
    chunks = []
    current = []
    current_tokens = 0

    for section in sections:
        lines = section.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            tokens = tokenize(line)
            if current_tokens + len(tokens) > max_tokens and current:
                chunks.append('\n'.join(current))
                current = []
                current_tokens = 0
            current.append(line)
            current_tokens += len(tokens)

    if current:
        chunks.append('\n'.join(current))
    return chunks

def tokenize(text: str) -> list[str]:
    """与 via54_rag/__init__.py 保持一致：中文连续字块为独立token"""
    text = text.lower()
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', text)
    stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '它', '他', '她', '们', '中', '为', '与', '但', '或', '以', '而', '及', '等', '其', '被', '把', '给', '让', '从', '用', '对', '于', '之', '所', '因为', '所以', '虽然', '但是', '然而', '并且', '或者', '以及', '当', '时', '后', '前', '里', '可', '能', '还', '又', '已', '曾', '正', '将', '这个', '那个', '什么', '如何', '为什么'}
    return [t for t in tokens if len(t) > 1 and t not in stopwords]

def extract_title(text: str) -> str:
    """从markdown提取标题"""
    m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    return m.group(1).strip() if m else 'Unknown'

def extract_source_url(text: str) -> str:
    """从报告提取来源链接"""
    urls = re.findall(r'https?://[^\s）\)）\]\n]+', text)
    # 优先取 adquan / meihua / cans / lions 等广告奖官网
    priority = [u for u in urls if any(p in u for p in ['adquan','meihua','cannes','lions','d&ad','effie','clio'])]
    return priority[0] if priority else (urls[0] if urls else '')

# ── 数据库写入 ─────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def clear_existing(conn):
    """清空旧数据"""
    cur = conn.cursor()
    cur.execute("DELETE FROM chunks")
    cur.execute("DELETE FROM doc_meta")
    cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('chunks','doc_meta')")
    conn.commit()

def upsert_doc(conn, filename: str, title: str, source_url: str) -> int:
    """写入 doc_meta，返回 doc_id"""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO doc_meta (filename, title, source_url) VALUES (?, ?, ?)",
        (filename, title, source_url)
    )
    return cur.lastrowid

def insert_chunks(conn, doc_id: int, chunks: list):
    """批量写入 chunks"""
    cur = conn.cursor()
    rows = []
    for idx, chunk in enumerate(chunks):
        tokens = tokenize(chunk)
        rows.append((doc_id, idx, chunk, json.dumps(tokens, ensure_ascii=False)))
    cur.executemany(
        "INSERT INTO chunks (doc_id, chunk_idx, text, tokens) VALUES (?, ?, ?, ?)",
        rows
    )

# ── 主流程 ─────────────────────────────────────────────────
def main():
    conn = get_conn()
    clear_existing(conn)

    cases = sorted([
        d for d in os.listdir(EXPAND_DIR)
        if os.path.isdir(os.path.join(EXPAND_DIR, d))
        and d not in ['_key_images', 'searxng_results']
    ])

    print(f"发现 {len(cases)} 个案例目录，开始向量化...\n")
    total_chunks = 0

    for case in cases:
        case_dir = EXPAND_DIR / case
        # 找深度报告
        report_files = list(case_dir.glob("*深度报告*.md"))
        if not report_files:
            # fallback 找 enriched md
            report_files = list(case_dir.glob("*.enriched.md"))
        if not report_files:
            print(f"  ⚠ {case}: 无报告文件，跳过")
            continue

        report_path = report_files[0]
        try:
            text = report_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"  ⚠ {case}: 读取失败 {e}，跳过")
            continue

        # 清理markdown干扰符号
        text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)  # 注释
        text = re.sub(r'---+\n', '\n', text)  # 分隔线
        text = re.sub(r'\|\s*---+\s*\|.*?(?=\n|$)', '', text)  # 表格头
        text = re.sub(r'\*\*\s*', '', text)  # 加粗
        text = re.sub(r'>\s*', '', text)  # 引用

        title       = extract_title(text)
        source_url  = extract_source_url(text)
        chunks      = chunk_text(text)
        doc_id      = upsert_doc(conn, case, title, source_url)
        insert_chunks(conn, doc_id, chunks)
        conn.commit()
        total_chunks += len(chunks)
        print(f"  ✅ {case[:40]:<40} | {len(chunks):3d} chunks | {title[:40]}")

    # 更新 IDF 表（词频统计）
    _update_idf(conn)

    print(f"\n✅ 完成：{len(cases)} 个案例，{total_chunks} 个 chunks 已写入")
    conn.close()

def _update_idf(conn):
    """从所有 tokens 重建 IDF 表"""
    cur = conn.cursor()
    cur.execute("DELETE FROM idf")
    cur.execute("DELETE FROM inverted")

    # 收集所有词
    doc_count = cur.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks").fetchone()[0]
    if doc_count == 0:
        return

    cur.execute("SELECT tokens FROM chunks")
    term_doc_count = {}
    for (tokens_json,) in cur.fetchall():
        tokens = set(json.loads(tokens_json))
        for t in tokens:
            term_doc_count[t] = term_doc_count.get(t, 0) + 1

    idf_rows = [(t, c) for t, c in term_doc_count.items()]
    cur.executemany("INSERT INTO idf (term, doc_count) VALUES (?, ?)", idf_rows)

    # inverted index: term -> chunk_ids
    cur.execute("SELECT id, tokens FROM chunks")
    inv = {}
    for (cid, tokens_json) in cur.fetchall():
        for t in set(json.loads(tokens_json)):
            inv.setdefault(t, []).append(cid)
    inv_rows = [(t, json.dumps(cids)) for t, cids in inv.items()]
    cur.executemany("INSERT INTO inverted (term, chunk_ids) VALUES (?, ?)", inv_rows)
    conn.commit()
    print(f"  📊 IDF表重建：{len(idf_rows)} terms")

if __name__ == "__main__":
    main()
