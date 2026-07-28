"""Local web API + UI server. Binds to 127.0.0.1 only."""
import threading
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from . import db, config, scanner, embedder, access, search

app = FastAPI(title="File Graph", docs_url=None, redoc_url=None)
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _con():
    con = db.connect()
    access.ensure_defaults(con)
    return con


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/stats")
def stats():
    con = _con()
    s = {
        "files": con.execute("SELECT COUNT(*) c FROM files WHERE is_dir=0").fetchone()["c"],
        "folders": con.execute("SELECT COUNT(*) c FROM files WHERE is_dir=1").fetchone()["c"],
        "embedded": con.execute("SELECT COUNT(*) c FROM embeddings").fetchone()["c"],
        "projects": con.execute("SELECT COUNT(*) c FROM files WHERE is_project_root=1").fetchone()["c"],
        "cloud": con.execute("SELECT COUNT(*) c FROM files WHERE is_cloud=1 AND is_dir=0").fetchone()["c"],
        "kinds": {r["kind"]: r["c"] for r in con.execute(
            "SELECT kind, COUNT(*) c FROM files WHERE is_dir=0 GROUP BY kind")},
        "last_scan": db.get_meta(con, "last_scan"),
        "scan": scanner.progress,
        "embed": embedder.progress,
    }
    con.close()
    return s


@app.get("/api/tree")
def tree(path: str = str(config.HOME)):
    con = _con()
    rules = access.list_rules(con)
    rows = con.execute(
        """SELECT path, name, ext, kind, is_dir, is_cloud, is_project_root, size, mtime,
             (SELECT COUNT(*) FROM files f2 WHERE f2.dir = files.path) AS child_count
           FROM files WHERE dir=? ORDER BY is_dir DESC, name COLLATE NOCASE""",
        (path,)).fetchall()
    out = [dict(r) | {"allowed": access.is_allowed(rules, r["path"])} for r in rows]
    con.close()
    return {"path": path, "children": out}


@app.get("/api/search")
def do_search(q: str, mode: str = "semantic", k: int = 20):
    con = _con()
    rows = (search.semantic_search(con, q, k) if mode == "semantic"
            else search.keyword_search(con, q, k))
    rules = access.list_rules(con)
    for r in rows:
        r["allowed"] = access.is_allowed(rules, r["path"])
        r.pop("preview", None)
    con.close()
    return {"query": q, "mode": mode, "results": rows[:k]}


@app.get("/api/related")
def do_related(path: str):
    con = _con()
    out = search.related(con, path)
    if "file" in out:
        out["file"].pop("preview", None)
        for lst in ("siblings", "semantic"):
            for r in out[lst]:
                r.pop("preview", None)
    con.close()
    return out


@app.get("/api/rules")
def get_rules():
    con = _con()
    rules = access.list_rules(con)
    con.close()
    return {"rules": rules}


class Rule(BaseModel):
    prefix: str
    allow: bool


@app.post("/api/rules")
def post_rule(rule: Rule):
    con = _con()
    access.set_rule(con, rule.prefix, rule.allow)
    rules = access.list_rules(con)
    con.close()
    return {"rules": rules}


@app.delete("/api/rules/{rule_id}")
def del_rule(rule_id: int):
    con = _con()
    access.delete_rule(con, rule_id)
    rules = access.list_rules(con)
    con.close()
    return {"rules": rules}


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.post("/api/agent/chat")
def agent_chat(req: ChatRequest):
    from fastapi.responses import StreamingResponse
    from . import agent

    def stream():
        import json as _json
        for event in agent.run_agent(req.message, req.history):
            yield f"data: {_json.dumps(event)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/scan")
def trigger_scan():
    if scanner.progress["state"] == "scanning":
        return {"status": "already running"}

    def run():
        scanner.scan()
        embedder.embed_pending()

    threading.Thread(target=run, daemon=True).start()
    return {"status": "started"}


def main():
    import uvicorn
    uvicorn.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT,
                log_level="warning")


if __name__ == "__main__":
    main()
