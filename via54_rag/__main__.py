"""
via54_rag CLI — via54MedCreativeDB 命令行工具
用法:
  python3 -m via54_rag build [--force]   # 重建索引
  python3 -m via54_rag search <query>     # 直接搜索
  python3 -m via54_rag serve              # 启动 HTTP 服务
"""
from via54_rag import cmd_build, cmd_search

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
        from via54_rag import start_server
        start_server()
