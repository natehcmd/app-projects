"""Semantic + keyword search and related-file lookup over the graph."""
import numpy as np
from . import db
from .embedder import embed_query

_cache = {"matrix": None, "ids": None, "count": -1}


def _load_matrix(con):
    count = con.execute("SELECT COUNT(*) c FROM embeddings").fetchone()["c"]
    if count != _cache["count"]:
        rows = con.execute("SELECT file_id, vector, dim FROM embeddings").fetchall()
        if rows:
            dim = rows[0]["dim"]
            mat = np.zeros((len(rows), dim), dtype=np.float32)
            ids = np.zeros(len(rows), dtype=np.int64)
            for i, r in enumerate(rows):
                v = np.frombuffer(r["vector"], dtype=np.float32)
                if len(v) == dim:
                    mat[i] = v
                ids[i] = r["file_id"]
            _cache.update(matrix=mat, ids=ids, count=count)
        else:
            _cache.update(matrix=None, ids=None, count=0)
    return _cache["matrix"], _cache["ids"]


def _rows_by_ids(con, id_scores):
    if not id_scores:
        return []
    ids = [i for i, _ in id_scores]
    q = f"SELECT * FROM files WHERE id IN ({','.join('?' * len(ids))})"
    by_id = {r["id"]: r for r in con.execute(q, ids)}
    out = []
    for fid, score in id_scores:
        if fid in by_id:
            d = dict(by_id[fid])
            d["score"] = round(float(score), 4)
            out.append(d)
    return out


def semantic_search(con, query: str, k: int = 20) -> list[dict]:
    mat, ids = _load_matrix(con)
    if mat is None:
        return []
    qv = embed_query(query)
    if qv is None:
        return []
    sims = mat @ qv
    top = np.argsort(-sims)[: k * 3]  # overfetch; caller filters by access
    return _rows_by_ids(con, [(int(ids[i]), sims[i]) for i in top])


def keyword_search(con, query: str, k: int = 20) -> list[dict]:
    like = f"%{query}%"
    rows = con.execute(
        """SELECT * FROM files WHERE name LIKE ? OR path LIKE ?
           ORDER BY is_dir DESC, mtime DESC LIMIT ?""", (like, like, k * 3))
    return [dict(r) | {"score": 1.0} for r in rows]


def related(con, path: str, k: int = 12) -> dict:
    """Files related to `path`: siblings, same project, semantic neighbors."""
    row = con.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()
    if not row:
        return {"error": "not indexed", "path": path}
    out = {"file": dict(row), "siblings": [], "semantic": []}
    sibs = con.execute(
        "SELECT * FROM files WHERE dir=? AND path!=? ORDER BY mtime DESC LIMIT ?",
        (row["dir"], path, k)).fetchall()
    out["siblings"] = [dict(r) for r in sibs]
    emb = con.execute("SELECT vector, dim FROM embeddings WHERE file_id=?",
                      (row["id"],)).fetchone()
    if emb:
        mat, ids = _load_matrix(con)
        if mat is not None:
            v = np.frombuffer(emb["vector"], dtype=np.float32)
            sims = mat @ v
            top = np.argsort(-sims)[: k + 1]
            pairs = [(int(ids[i]), sims[i]) for i in top if int(ids[i]) != row["id"]]
            out["semantic"] = _rows_by_ids(con, pairs[:k])

    # Add explicit relationships
    rels = con.execute("""
        SELECT f.*, r.kind as relation_kind
        FROM relations r
        JOIN files f ON r.target_id = f.id
        WHERE r.source_id = ?
        UNION
        SELECT f.*, r.kind as relation_kind
        FROM relations r
        JOIN files f ON r.source_id = f.id
        WHERE r.target_id = ?
        LIMIT ?
    """, (row["id"], row["id"], k)).fetchall()
    out["linked"] = [dict(r) | {"score": 1.0} for r in rels]

    return out
