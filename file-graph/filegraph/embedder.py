"""Embed file previews with a local ollama model. Fully offline."""
import time
import numpy as np
import httpx
from . import config, db
from .extract import embedding_text

progress = {"state": "idle", "done": 0, "total": 0}


def _embed_batch(texts: list[str]) -> list[list[float]] | None:
    try:
        r = httpx.post(f"{config.OLLAMA_URL}/api/embed",
                       json={"model": config.EMBED_MODEL, "input": texts,
                             "truncate": True},
                       timeout=120)
        r.raise_for_status()
        return r.json()["embeddings"]
    except Exception:
        return None


def embed_pending(limit: int | None = None) -> dict:
    """Embed every file that has a preview and no up-to-date embedding."""
    con = db.connect()
    rows = con.execute(
        """SELECT id, path, name, kind, preview FROM files
           WHERE is_dir=0 AND preview != '' AND embedded_at < mtime
           ORDER BY mtime DESC""").fetchall()
    if limit:
        rows = rows[:limit]
    progress.update(state="embedding", done=0, total=len(rows))
    failed = 0
    BATCH = 16
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        vecs = _embed_batch([embedding_text(r) for r in chunk])
        if vecs is None:
            failed += len(chunk)
            continue
        now = time.time()
        for row, vec in zip(chunk, vecs):
            arr = np.asarray(vec, dtype=np.float32)
            arr /= (np.linalg.norm(arr) or 1.0)
            con.execute(
                """INSERT INTO embeddings(file_id, vector, dim, model)
                   VALUES(?,?,?,?)
                   ON CONFLICT(file_id) DO UPDATE SET vector=excluded.vector,
                     dim=excluded.dim, model=excluded.model""",
                (row["id"], arr.tobytes(), len(arr), config.EMBED_MODEL))
            con.execute("UPDATE files SET embedded_at=? WHERE id=?",
                        (now, row["id"]))
        con.commit()
        progress["done"] = min(i + BATCH, len(rows))
    con.close()
    progress["state"] = "idle"
    return {"embedded": progress["total"] - failed, "failed": failed}


def embed_query(text: str) -> np.ndarray | None:
    vecs = _embed_batch([text])
    if not vecs:
        return None
    arr = np.asarray(vecs[0], dtype=np.float32)
    arr /= (np.linalg.norm(arr) or 1.0)
    return arr
