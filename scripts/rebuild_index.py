"""
rebuild_index.py — 从扩充目录的 markdown 深度报告重建 TF-IDF 索引
修复：中文 bigram+trigram n-gram + 真实 IDF 公式
"""
import os, re, math, json, sqlite3
from pathlib import Path

DB_PATH = "/Users/david/Desktop/developments/via54MedCreativeDB/via54_rag/vector.db"
EXPAND_DIR = "/Users/david/Desktop/创意案例库_扩充"
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
MIN_CHUNK_LEN = 50

# ── 中文 n-gram ────────────────────────────────────
def _cn_ngrams(text: str):
    """提取中文 bigram(2-gram) + trigram(3-gram)"""
    cn_seqs = re.findall(r'[\u4e00-\u9fff]+', text)
    tokens = []
    for seq in cn_seqs:
        if len(seq) < 2:
            continue
        for i in range(len(seq)):
            for n in [2, 3]:
                if i + n <= len(seq):
                    tokens.append(seq[i:i+n])
    return tokens

def tokenize(text: str):
    text = text.lower()
    en_tokens = re.findall(r'[a-z0-9]+', text)
    cn_tokens = _cn_ngrams(text)
    all_tokens = en_tokens + cn_tokens
    stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '它', '他', '她', '们', '中', '为', '与', '但', '或', '以', '而', '及', '等', '其', '被', '把', '给', '让', '从', '用', '对', '于', '之', '所', '而后', '如果', '因为', '所以', '虽然', '但是', '然而', '并且', '或者', '以及', '当', '时', '后', '前', '里', '可', '能', '还', '又', '已', '曾', '正', '将'}
    return [t for t in all_tokens if len(t) >= 2 and t not in stopwords]

def compute_tf(tokens):
    if not tokens:
        return {}
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in freq.items()}

def chunk_text(texts):
    full = "\n".join(texts)
    paras = re.split(r'\n\s*\n', full)
    chunks = []
    current = ""
    for para in paras:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) < CHUNK_SIZE:
            current += " " + para
        else:
            if len(current) >= MIN_CHUNK_LEN:
                chunks.append(current.strip())
            current = para
    if len(current) >= MIN_CHUNK_LEN:
        chunks.append(current.strip())
    return chunks

def init_db(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id INTEGER,
        chunk_idx INTEGER,
        text TEXT,
        tokens TEXT,
        UNIQUE(doc_id, chunk_idx)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS doc_meta (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT UNIQUE,
        title TEXT,
        source_url TEXT,
        indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS idf (
        term TEXT PRIMARY KEY,
        doc_count INTEGER
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS inverted (
        term TEXT,
        chunk_id INTEGER,
        tf REAL,
        FOREIGN KEY (chunk_id) REFERENCES chunks(id)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_inverted_term ON inverted(term)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)")
    conn.commit()

def rebuild(force=True):
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    c = conn.cursor()

    if force:
        c.execute("DELETE FROM chunks")
        c.execute("DELETE FROM inverted")
        c.execute("DELETE FROM doc_meta")
        c.execute("DELETE FROM idf")
        conn.commit()
        print("  已清空旧索引（force=True）")

    # 扫描扩充目录
    md_files = []
    for entry in os.listdir(EXPAND_DIR):
        md_path = os.path.join(EXPAND_DIR, entry, f"{entry}_深度报告.md")
        if os.path.isfile(md_path):
            md_files.append((entry, md_path))

    print(f"  找到 {len(md_files)} 个深度报告")
    if not md_files:
        print("  未找到深度报告文件！")
        return

    all_chunks = []  # (doc_id, chunk_idx, text, tokens)
    N = 0

    for folder_name, md_path in md_files:
        # 读 markdown
        with open(md_path, encoding='utf-8') as f:
            content = f.read()

        # 提取标题
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else folder_name

        # 提取 source_url（第一条链接）
        url_match = re.search(r'https?://[^\s\)）]+', content)
        source_url = url_match.group(0) if url_match else ''

        # 提取正文（去掉 markdown 标题/表格符号）
        lines = content.split('\n')
        paragraphs = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('>'):
                continue
            # 去掉表格符号
            line = re.sub(r'\|.*\|', '', line)
            line = re.sub(r'[-=]{3,}', '', line)
            line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)  # 去掉 Bold
            line = re.sub(r'\*(.*?)\*', r'\1', line)  # 去掉 Italic
            if line:
                paragraphs.append(line)

        text_blocks = ['\n'.join(paragraphs)]
        chunks = chunk_text(text_blocks)
        N += 1

        # 写入 doc_meta
        c.execute("INSERT OR IGNORE INTO doc_meta (filename, title, source_url) VALUES (?, ?, ?)",
                  (folder_name, title, source_url))
        c.execute("SELECT id FROM doc_meta WHERE filename = ?", (folder_name,))
        doc_id = c.fetchone()[0]

        for ci, chunk in enumerate(chunks):
            tokens = tokenize(chunk)
            all_chunks.append((doc_id, ci, chunk, tokens))

        print(f"  [{N}] {folder_name}: {len(chunks)} chunks, title={title[:40]}")

    print(f"\n  总 {N} 个文档，{len(all_chunks)} 个 chunks")

    # 统计 doc_count
    doc_count = {}
    for doc_id, ci, chunk, tokens in all_chunks:
        for term in set(tokens):
            doc_count[term] = doc_count.get(term, 0) + 1

    # 写入 IDF（只存 doc_count，search 时实时算 idf）
    for term, dc in doc_count.items():
        c.execute("INSERT OR IGNORE INTO idf (term, doc_count) VALUES (?, ?)", (term, dc))

    conn.commit()
    print(f"  IDF 写入完成，{len(doc_count)} 个词项")

    # 写入 chunks + inverted
    c.execute("DELETE FROM inverted")
    for doc_id, ci, chunk, tokens in all_chunks:
        c.execute("INSERT INTO chunks (doc_id, chunk_idx, text, tokens) VALUES (?, ?, ?, ?)",
                 (doc_id, ci, chunk, json.dumps(tokens)))
        chunk_id = c.lastrowid
        tf = compute_tf(tokens)
        for term, tf_val in tf.items():
            c.execute("INSERT INTO inverted (term, chunk_id, tf) VALUES (?, ?, ?)",
                     (term, chunk_id, tf_val))

    conn.commit()
    print(f"  索引重建完成！")

    # 验证
    c.execute("SELECT COUNT(*) FROM chunks")
    print(f"  chunks: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM inverted")
    print(f"  inverted entries: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM idf")
    print(f"  idf terms: {c.fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    import sys
    force = '--force' in sys.argv
    print(f"🔨 重建索引（force={force}）...")
    rebuild(force=force)
    print("✅ 完成")
