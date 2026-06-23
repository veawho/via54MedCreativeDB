"""
via54MedCreativeDB - 医学传播创意向量知识库
Pure Python TF-IDF + SQLite 轻量向量检索
不依赖 numpy/sklearn/chromadb/faiss
"""
import os, re, math, json, sqlite3, hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import pypdf

# ── 配置 ──────────────────────────────────────────
DB_PATH = "/Users/david/Desktop/developments/via54MedCreativeDB/via54_rag/vector.db"
PDF_DIR = os.path.expanduser("/Users/david/Desktop/创意案例库")
CHUNK_SIZE = 300        # 每段字符数
CHUNK_OVERLAP = 50      # 重叠字符数
MIN_CHUNK_LEN = 50      # 最小段长度

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# ── SQLite 初始化 ──────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    # TF-IDF 表：term -> (doc_count, idf)
    c.execute("""CREATE TABLE IF NOT EXISTS idf (
        term TEXT PRIMARY KEY,
        doc_count INTEGER
    )""")
    # 倒排索引：term -> [(chunk_id, tf)]
    c.execute("""CREATE TABLE IF NOT EXISTS inverted (
        term TEXT,
        chunk_id INTEGER,
        tf REAL,
        FOREIGN KEY (chunk_id) REFERENCES chunks(id)
    )""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_inverted_term ON inverted(term)""")
    c.execute("""CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)""")
    conn.commit()
    return conn

# ── 文本预处理 ────────────────────────────────────
def tokenize(text: str) -> List[str]:
    text = text.lower()
    # 中英混合分词
    tokens = re.findall(r'[\u4e00-\u9fff]+|[a-z0-9]+', text)
    # 过滤停用词
    stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '那', '它', '他', '她', '们', '中', '为', '与', '但', '或', '以', '而', '及', '等', '其', '被', '或', '把', '给', '让', '从', '用', '对', '于', '之', '所', '而后', '如果', '因为', '所以', '虽然', '但是', '然而', '并且', '或者', '以及', '当', '时', '后', '前', '里', '可', '能', '还', '又', '已', '曾', '正', '被', '将', '被'}
    return [t for t in tokens if len(t) > 1 and t not in stopwords]

def compute_tf(tokens: List[str]) -> Dict[str, float]:
    if not tokens:
        return {}
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    total = len(tokens)
    return {t: c / total for t, c in freq.items()}

# ── PDF 读取 ──────────────────────────────────────
def extract_pdf_text(pdf_path: str) -> List[str]:
    try:
        reader = pypdf.PdfReader(pdf_path)
        texts = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                texts.append(t)
        return texts
    except Exception as e:
        print(f"  PDF 读取失败 {pdf_path}: {e}")
        return []

def chunk_text(texts: List[str], chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> List[str]:
    """将多页文本合并后分块"""
    full = "\n".join(texts)
    # 按段落分割
    paras = re.split(r'\n\s*\n', full)
    chunks = []
    current = ""
    for para in paras:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) < chunk_size:
            current += " " + para
        else:
            if len(current) >= MIN_CHUNK_LEN:
                chunks.append(current.strip())
            current = para
    if len(current) >= MIN_CHUNK_LEN:
        chunks.append(current.strip())
    return chunks

# ── 向量化 ────────────────────────────────────────
def build_vector_index(conn: sqlite3.Connection, force_rebuild: bool = False):
    """构建 TF-IDF 索引"""
    c = conn.cursor()
    
    # 检查是否已有数据
    c.execute("SELECT COUNT(*) FROM doc_meta")
    existing = c.fetchone()[0]
    if existing > 0 and not force_rebuild:
        print(f"  索引已有 {existing} 个文档，跳过构建（force_rebuild=True 强制重build）")
        return
    
    # 扫描 PDF
    pdf_files = []
    for root, dirs, files in os.walk(PDF_DIR):
        for f in files:
            if f.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, f))
    
    print(f"  找到 {len(pdf_files)} 个 PDF 文件")
    
    all_chunks = []  # (doc_id, chunk_idx, text, tokens, tf_dict)
    N = 0  # 总文档数
    
    for i, pdf_path in enumerate(pdf_files):
        rel_path = os.path.relpath(pdf_path, PDF_DIR)
        print(f"  [{i+1}/{len(pdf_files)}] 处理: {rel_path[:60]}")
        
        # 检查是否已索引
        c.execute("SELECT id FROM doc_meta WHERE filename = ?", (rel_path,))
        row = c.fetchone()
        if row:
            doc_id = row[0]
            # 删除旧 chunks
            c.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        else:
            c.execute("INSERT INTO doc_meta (filename, title) VALUES (?, ?)",
                      (rel_path, rel_path.replace('.pdf', '')))
            doc_id = c.lastrowid
        
        texts = extract_pdf_text(pdf_path)
        chunks = chunk_text(texts)
        N += 1
        
        for ci, chunk in enumerate(chunks):
            tokens = tokenize(chunk)
            tf = compute_tf(tokens)
            all_chunks.append((doc_id, ci, chunk, tokens, tf))
    
    print(f"  总 {N} 个文档，{len(all_chunks)} 个文本块")
    
    # 统计词频（多少个文档包含该词）
    doc_count = {}  # term -> 包含文档数
    for doc_id, ci, chunk, tokens, tf in all_chunks:
        for term in set(tokens):
            doc_count[term] = doc_count.get(term, 0) + 1
    
    # 计算 IDF 并写入
    for term, dc in doc_count.items():
        idf = math.log(N / (dc + 1)) + 1  # 加1平滑
        c.execute("INSERT OR REPLACE INTO idf (term, doc_count) VALUES (?, ?)", (term, dc))
    
    conn.commit()
    print(f"  IDF 写入完成，共 {len(doc_count)} 个词项")
    
    # 写入 chunks 和倒排索引
    c.execute("DELETE FROM inverted")
    for doc_id, ci, chunk, tokens, tf in all_chunks:
        c.execute("INSERT INTO chunks (doc_id, chunk_idx, text, tokens) VALUES (?, ?, ?, ?)",
                 (doc_id, ci, chunk, json.dumps(tokens)))
        chunk_id = c.lastrowid
        for term, tf_val in tf.items():
            c.execute("INSERT INTO inverted (term, chunk_id, tf) VALUES (?, ?, ?)",
                     (term, chunk_id, tf_val))
    
    conn.commit()
    print(f"  索引构建完成！")

# ── 检索 ─────────────────────────────────────────
def search(query: str, top_k: int = 5) -> List[Dict]:
    """
    TF-IDF 余弦相似度检索
    返回 top_k 个最相关文本块
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    q_tokens = tokenize(query)
    if not q_tokens:
        return []
    
    # 查询 tokens 的 IDF
    placeholders = ','.join(['?'] * len(q_tokens))
    c.execute(f"SELECT term, doc_count FROM idf WHERE term IN ({placeholders})", q_tokens)
    idf_map = {row[0]: row[1] for row in c.fetchall()}
    
    c.execute("SELECT COUNT(*) FROM doc_meta")
    N = c.fetchone()[0] or 1
    
    # 计算 query TF
    q_tf = compute_tf(q_tokens)
    
    # 查询相关 chunk_ids
    relevant_terms = [t for t in q_tokens if t in idf_map]
    if not relevant_terms:
        return []
    
    # 获取所有相关 chunk
    placeholders2 = ','.join(['?'] * len(relevant_terms))
    c.execute(f"""SELECT DISTINCT chunk_id FROM inverted WHERE term IN ({placeholders2})""",
             relevant_terms)
    chunk_ids = [row[0] for row in c.fetchall()]
    
    # 计算每个 chunk 与 query 的余弦相似度
    scores = []
    for cid in chunk_ids:
        c.execute("SELECT text, tokens FROM chunks WHERE id = ?", (cid,))
        row = c.fetchone()
        if not row:
            continue
        text, tokens_str = row
        tokens = json.loads(tokens_str)
        chunk_tf = compute_tf(tokens)
        
        # cosine(query, chunk) = dot(q_tf, d_tf) / (|q|, |d|)
        dot = sum(q_tf.get(t, 0) * chunk_tf.get(t, 0) * idf_map.get(t, 0)**2
                  for t in set(q_tokens) & set(tokens))
        
        q_norm = math.sqrt(sum((q_tf.get(t, 0) * idf_map.get(t, 0))**2 for t in q_tokens))
        d_norm = math.sqrt(sum((chunk_tf.get(t, 0) * idf_map.get(t, 0))**2 for t in tokens))
        
        if q_norm > 0 and d_norm > 0:
            score = dot / (q_norm * d_norm)
            scores.append((score, text, cid))
    
    scores.sort(reverse=True)
    
    results = []
    for score, text, cid in scores[:top_k]:
        c.execute("""SELECT d.filename, d.title FROM doc_meta d 
                      JOIN chunks c ON c.doc_id = d.id WHERE c.id = ?""", (cid,))
        row = c.fetchone()
        results.append({
            "score": round(score, 4),
            "text": text[:500],
            "doc": row[0] if row else "?",
            "title": row[1] if row else "?"
        })
    
    conn.close()

    # ── SearXNG Web 补充 ────────────────────────────────────
    try:
        import urllib.request, urllib.parse
        searxng_url = "http://127.0.0.1:8888"
        data = urllib.parse.urlencode({"q": query, "format": "json"}).encode()
        req = urllib.request.Request(
            f"{searxng_url}/search", data=data,
            headers={"User-Agent": "via54-rag/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            web_data = json.loads(resp.read())
        for r in web_data.get("results", [])[:3]:
            results.append({
                "score": 0.0,
                "text": (r.get("content") or "")[:300],
                "doc": "🌐 " + (r.get("url") or "")[:80],
                "title": (r.get("title") or "")[:80],
                "source": "searxng"
            })
    except Exception:
        pass  # SearXNG 离线不影响本地向量检索

    return results

def start_server(port=18765):
    import http.server, json, urllib.parse

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/health":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'OK')
            elif parsed.path == "/search":
                q = urllib.parse.parse_qs(parsed.query).get('q', [''])[0]
                results = search(q)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(results, ensure_ascii=False).encode())
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, fmt, *args):
            pass

    server = http.server.HTTPServer(('127.0.0.1', port), Handler)
    print(f"📡 http://127.0.0.1:{port}")
    server.serve_forever()

# ── CLI 接口 ─────────────────────────────────────
def cmd_build(force=False):
    print(f"🔨 构建向量索引: {PDF_DIR}")
    conn = init_db()
    build_vector_index(conn, force_rebuild=force)
    conn.close()
    print("✅ 索引构建完成")

def cmd_search(query: str, top_k: int = 5):
    results = search(query, top_k=top_k)
    print(f"\n🔍 查询: {query}")
    print(f"找到 {len(results)} 个结果:\n")
    for i, r in enumerate(results, 1):
        print(f"【{i}】{r['title']} (score={r['score']})")
        print(f"   {r['text'][:200]}...")
        print()
    return results

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python -m via54_rag build|search|serve")
    elif sys.argv[1] == "build":
        cmd_build(force='--force' in sys.argv)
    elif sys.argv[1] == "search":
        q = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else "Cannes 健康"
        cmd_search(q)
    elif sys.argv[1] == "serve":
        print("RAG 服务启动中...")
        # 简单的 HTTP 接口
        import http.server, json, urllib.parse
        
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path == "/health":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'OK')
                elif parsed.path == "/search":
                    q = urllib.parse.parse_qs(parsed.query).get('q', [''])[0]
                    results = search(q)
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(results, ensure_ascii=False).encode())
                else:
                    self.send_response(404)
                    self.end_headers()
            def log_message(self, fmt, *args):
                pass
        
        server = http.server.HTTPServer(('127.0.0.1', 18765), Handler)
        print("📡 http://127.0.0.1:18765")
        server.serve_forever()
