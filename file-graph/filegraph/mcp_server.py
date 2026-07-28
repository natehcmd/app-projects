"""MCP server — this is what Claude (and other MCP clients) talk to.

Every tool result is filtered through the access rules you set in the web UI:
denied folders are invisible to AIs. Runs over stdio; nothing leaves the Mac.
"""
from mcp.server.fastmcp import FastMCP
from . import db, access, search as searchmod

mcp = FastMCP("file-graph")


def _con():
    con = db.connect()
    access.ensure_defaults(con)
    return con


def _slim(r: dict) -> dict:
    return {k: r.get(k) for k in
            ("path", "name", "kind", "size", "mtime", "is_dir", "is_cloud",
             "is_project_root", "score") if k in r}


def _allowed_only(con, rows: list[dict]) -> list[dict]:
    rules = access.list_rules(con)
    return [r for r in rows if access.is_allowed(rules, r["path"])]


@mcp.tool()
def search_files(query: str, mode: str = "semantic", limit: int = 15) -> list[dict]:
    """Search the user's local file knowledge graph.

    mode='semantic' finds files by meaning (e.g. 'notes about job interviews');
    mode='keyword' matches file names/paths. Results respect the user's
    privacy rules — some folders may be hidden."""
    con = _con()
    rows = (searchmod.semantic_search(con, query, limit) if mode == "semantic"
            else searchmod.keyword_search(con, query, limit))
    out = [_slim(r) for r in _allowed_only(con, rows)][:limit]
    con.close()
    return out


@mcp.tool()
def get_file_context(path: str) -> dict:
    """Get rich context for one file: metadata, a text preview, files in the
    same folder, and semantically similar files across the whole graph."""
    con = _con()
    rules = access.list_rules(con)
    if not access.is_allowed(rules, path):
        con.close()
        return {"error": "access to this path is blocked by the user's privacy rules"}
    rel = searchmod.related(con, path)
    if "error" in rel:
        con.close()
        return rel
    row = con.execute("SELECT preview FROM files WHERE path=?", (path,)).fetchone()
    out = {
        "file": _slim(rel["file"]),
        "preview": (row["preview"][:3000] if row and row["preview"] else ""),
        "same_folder": [_slim(r) for r in rel["siblings"]
                        if access.is_allowed(rules, r["path"])][:10],
        "similar_files": [_slim(r) for r in rel["semantic"]
                          if access.is_allowed(rules, r["path"])][:10],
        "linked_files": [_slim(r) for r in rel.get("linked", [])
                         if access.is_allowed(rules, r["path"])][:10],
    }
    con.close()
    return out


@mcp.tool()
def list_folder(path: str) -> list[dict]:
    """List the indexed contents of a folder in the knowledge graph."""
    con = _con()
    rules = access.list_rules(con)
    if not access.is_allowed(rules, path):
        con.close()
        return [{"error": "access to this path is blocked by the user's privacy rules"}]
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM files WHERE dir=? ORDER BY is_dir DESC, name LIMIT 200",
        (path,))]
    out = [_slim(r) for r in rows if access.is_allowed(rules, r["path"])]
    con.close()
    return out


@mcp.tool()
def graph_overview() -> dict:
    """Overview of the user's file landscape: counts by kind, and the project
    folders (repos, apps) found on the machine. A good first call."""
    con = _con()
    rules = access.list_rules(con)
    projects = [dict(r) for r in con.execute(
        "SELECT path, name FROM files WHERE is_project_root=1 ORDER BY path LIMIT 300")]
    out = {
        "total_files": con.execute(
            "SELECT COUNT(*) c FROM files WHERE is_dir=0").fetchone()["c"],
        "by_kind": {r["kind"]: r["c"] for r in con.execute(
            "SELECT kind, COUNT(*) c FROM files WHERE is_dir=0 GROUP BY kind")},
        "projects": [p for p in projects if access.is_allowed(rules, p["path"])],
        "note": "Use search_files (semantic) to find files by topic, "
                "get_file_context for deep context on one file.",
    }
    con.close()
    return out


@mcp.tool()
def explain_codebase_module(module_name: str) -> str:
    """Uses vector search to locate files associated with a module name and returns their structural overview."""
    con = _con()
    rows = searchmod.keyword_search(con, module_name, limit=5)
    
    summary = []
    for r in rows:
        summary.append(f"File: {r['path']}\nKind: {r['kind']}\nPreview:\n{r['preview'][:500]}")
    con.close()
    
    return "\n\n---\n\n".join(summary)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
