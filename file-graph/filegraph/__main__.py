"""CLI: python -m filegraph [scan|embed|serve|mcp|stats]"""
import sys


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "scan":
        from . import scanner, embedder
        print("Scanning home directory…")
        result = scanner.scan()
        print(f"Scanned {result['scanned']:,} files "
              f"({result['total_indexed']:,} total indexed, "
              f"{result['removed_stale']:,} stale removed)")
        print("Embedding new/changed files…")
        r = embedder.embed_pending()
        print(f"Embedded {r['embedded']:,} files ({r['failed']} failed)")
    elif cmd == "embed":
        from . import embedder
        r = embedder.embed_pending()
        print(f"Embedded {r['embedded']:,} files ({r['failed']} failed)")
    elif cmd == "serve":
        from . import api, config
        print(f"File Graph UI → http://{config.SERVER_HOST}:{config.SERVER_PORT}")
        api.main()
    elif cmd == "mcp":
        from . import mcp_server
        mcp_server.main()
    elif cmd == "stats":
        from . import db
        con = db.connect()
        for row in con.execute(
                "SELECT kind, COUNT(*) c FROM files WHERE is_dir=0 "
                "GROUP BY kind ORDER BY c DESC"):
            print(f"{row['kind']:>10}  {row['c']:,}")
        emb = con.execute("SELECT COUNT(*) c FROM embeddings").fetchone()["c"]
        print(f"{'embedded':>10}  {emb:,}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
