"""Walk the home directory and index file metadata into SQLite.

Cloud-streamed folders (Google Drive / OneDrive) are indexed by metadata only —
their contents are never opened, so nothing gets downloaded.
"""
import os
import time
from pathlib import Path
from . import config, db
from .extract import extract_preview

# module-level progress so the API can report on a running scan
progress = {"state": "idle", "scanned": 0, "current": "", "started": 0.0}


def _skip_dir(name: str, path: str, depth: int) -> bool:
    if name in config.EXCLUDE_DIR_NAMES:
        return True
    if name.startswith(".") and name not in {".claude", ".config"}:
        return True
    if depth == 0 and name in config.EXCLUDE_TOP_LEVEL:
        return True
    return False


def scan(root: Path = config.HOME) -> dict:
    con = db.connect()
    progress.update(state="scanning", scanned=0, started=time.time())
    seen_paths: set[str] = set()
    batch = []

    def flush():
        if not batch:
            return
        con.executemany(
            """INSERT INTO files(path, name, ext, dir, size, mtime, kind,
                                 is_dir, is_cloud, is_project_root, indexed_at, preview)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(path) DO UPDATE SET
                 size=excluded.size, mtime=excluded.mtime,
                 is_project_root=excluded.is_project_root,
                 indexed_at=excluded.indexed_at,
                 preview=CASE WHEN files.mtime != excluded.mtime
                              THEN excluded.preview ELSE files.preview END,
                 embedded_at=CASE WHEN files.mtime != excluded.mtime
                                  THEN 0 ELSE files.embedded_at END""",
            batch)
        con.commit()
        batch.clear()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        depth = len(Path(dirpath).relative_to(root).parts)
        # prune excluded dirs and treat bundles as opaque
        pruned = []
        for d in list(dirnames):
            if _skip_dir(d, dirpath, depth):
                dirnames.remove(d)
            elif d.endswith(config.BUNDLE_SUFFIXES):
                dirnames.remove(d)
                pruned.append(d)  # record bundle as a single entry
        now = time.time()
        cloud = config.is_cloud_path(dirpath)

        for d in dirnames + pruned:
            p = os.path.join(dirpath, d)
            seen_paths.add(p)
            is_root = 1 if any(
                os.path.exists(os.path.join(p, m)) for m in config.PROJECT_MARKERS
            ) else 0
            batch.append((p, d, "", dirpath, 0, 0, "folder", 1, cloud, is_root, now, ""))

        for f in filenames:
            if f == ".DS_Store":
                continue
            p = os.path.join(dirpath, f)
            seen_paths.add(p)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            ext = os.path.splitext(f)[1].lower()
            preview = ""
            if not cloud:
                preview = extract_preview(p, ext, st.st_size)
            batch.append((p, f, ext, dirpath, st.st_size, st.st_mtime,
                          config.kind_of(ext), 0, cloud, 0, now, preview))
            progress["scanned"] += 1

        progress["current"] = dirpath
        if len(batch) >= 500:
            flush()
    flush()

    # remove records for files that no longer exist under this root
    root_s = str(root)
    stale = [r["path"] for r in con.execute(
        "SELECT path FROM files WHERE path LIKE ? || '/%'", (root_s,))
        if r["path"] not in seen_paths]
    for i in range(0, len(stale), 500):
        chunk = stale[i:i + 500]
        con.execute(
            f"DELETE FROM files WHERE path IN ({','.join('?' * len(chunk))})", chunk)
    con.commit()
    db.set_meta(con, "last_scan", str(time.time()))
    
    build_graph(con)
    
    total = con.execute("SELECT COUNT(*) c FROM files").fetchone()["c"]
    con.close()
    progress.update(state="idle", current="")
    return {"scanned": progress["scanned"], "total_indexed": total,
            "removed_stale": len(stale)}

def build_graph(con):
    from collections import defaultdict
    from pathlib import Path
    from .extract import extract_relations
    
    rows = con.execute("SELECT id, path, ext, preview FROM files WHERE is_dir=0 AND preview != ''").fetchall()
    name_to_ids = defaultdict(list)
    for r in rows:
        name = Path(r["path"]).stem
        name_to_ids[name].append(r["id"])
    
    new_rels = []
    for r in rows:
        refs = extract_relations(r["preview"], r["ext"])
        for ref in refs:
            target_name = ref.split('/')[-1].split('.')[0]
            if target_name in name_to_ids:
                for tid in name_to_ids[target_name]:
                    if tid != r["id"]:
                        new_rels.append((r["id"], tid, "references"))

    con.execute("DELETE FROM relations")
    con.executemany("INSERT OR IGNORE INTO relations(source_id, target_id, kind) VALUES(?,?,?)", new_rels)
    con.commit()
