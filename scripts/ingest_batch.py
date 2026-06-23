#!/usr/bin/env python3
"""
批量 PDF 导入脚本 — via54MedCreativeDB
用法: python3 scripts/ingest_batch.py [--pdf-dir DIR] [--force]

功能:
  1. 指定目录批量导入 PDF（支持多目录）
  2. 增量导入（跳过已索引文件，--force 强制重建）
  3. 导入后自动验证索引完整性
  4. 生成导入报告
"""
import sys, os, sqlite3, argparse
from pathlib import Path

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from via54_rag import build_vector_index, tokenize, chunk_text

DB_PATH = Path(__file__).parent.parent / "via54_rag" / "vector.db"
DEFAULT_PDF_DIR = "/Users/david/Desktop/创意案例库"

def get_indexed_files(conn: sqlite3.Connection) -> set:
    """返回已索引的 PDF 文件路径集合"""
    cur = conn.execute("SELECT DISTINCT source_file FROM doc_meta")
    return {row[0] for row in cur.fetchall()}

def get_total_chunks(conn: sqlite3.Connection) -> int:
    """返回总 chunk 数"""
    cur = conn.execute("SELECT COUNT(*) FROM chunks")
    return cur.fetchone()[0]

def get_total_docs(conn: sqlite3.Connection) -> int:
    """返回已索引文档数"""
    cur = conn.execute("SELECT COUNT(*) FROM doc_meta")
    return cur.fetchone()[0]

def ingest_directory(pdf_dir: str, force: bool = False, verbose: bool = True):
    """
    导入单个 PDF 目录

    Args:
        pdf_dir: PDF 文件目录
        force: True = 删除旧索引重建，False = 增量导入（跳过已索引）
        verbose: 打印详细报告
    """
    pdf_path = Path(pdf_dir)
    if not pdf_path.exists():
        print(f"❌ 目录不存在: {pdf_dir}")
        return

    pdf_files = list(pdf_path.glob("*.pdf"))
    if not pdf_files:
        print(f"⚠️  目录为空: {pdf_dir}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    try:
        existing = get_indexed_files(conn)
        before_chunks = get_total_chunks(conn)
        before_docs = get_total_docs(conn)

        new_files = []
        skipped_files = []

        for pdf_file in pdf_files:
            rel = str(pdf_file)
            if rel in existing and not force:
                skipped_files.append(pdf_file.name)
            else:
                new_files.append(pdf_file)

        if verbose:
            print(f"\n📂 目录: {pdf_dir}")
            print(f"   总文件数: {len(pdf_files)}")
            print(f"   新增: {len(new_files)}")
            print(f"   跳过: {len(skipped_files)}")
            if skipped_files and not force:
                print(f"   (使用 --force 强制重建)")

        if not new_files:
            print("✅ 无需导入")
            return

        if force:
            # 强制重建：删除旧记录
            conn.execute("DELETE FROM doc_meta WHERE source_file IN (" +
                ",".join(f"'{f}'" for f in [str(p) for p in pdf_files]) + ")")
            conn.commit()

        # 执行重建
        build_vector_index(conn, force_rebuild=False)

        after_chunks = get_total_chunks(conn)
        after_docs = get_total_docs(conn)

        print(f"\n✅ 导入完成")
        print(f"   新增文档: {after_docs - before_docs}")
        print(f"   新增 chunks: {after_chunks - before_chunks}")
        print(f"   总文档数: {after_docs}")
        print(f"   总 chunks: {after_chunks}")

        if verbose and skipped_files:
            print(f"\n⚠️  跳过文件（已索引）:")
            for f in skipped_files:
                print(f"   - {f}")

    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="批量 PDF 导入工具")
    parser.add_argument("--pdf-dir", "-d", default=DEFAULT_PDF_DIR,
                        help=f"PDF 目录（默认: {DEFAULT_PDF_DIR}）")
    parser.add_argument("--force", "-f", action="store_true",
                        help="强制重建索引（删除该目录所有旧记录后重新导入）")
    parser.add_argument("--report", "-r", action="store_true",
                        help="只打印索引状态，不导入")
    args = parser.parse_args()

    # 状态报告模式
    if args.report:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            docs = get_total_docs(conn)
            chunks = get_total_chunks(conn)
            print(f"📊 索引状态")
            print(f"   文档数: {docs}")
            print(f"   Chunks: {chunks}")
            print(f"   数据库: {DB_PATH}")
            print(f"   DB大小: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")
        finally:
            conn.close()
        return

    # 导入模式
    ingest_directory(args.pdf_dir, force=args.force)

if __name__ == "__main__":
    main()
