"""SQLite storage. One local file at ~/.filegraph/filegraph.db."""
import sqlite3
from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    ext TEXT DEFAULT '',
    dir TEXT NOT NULL,
    size INTEGER DEFAULT 0,
    mtime REAL DEFAULT 0,
    kind TEXT DEFAULT 'other',
    is_dir INTEGER DEFAULT 0,
    is_cloud INTEGER DEFAULT 0,
    is_project_root INTEGER DEFAULT 0,
    indexed_at REAL DEFAULT 0,
    embedded_at REAL DEFAULT 0,
    preview TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_files_dir ON files(dir);
CREATE INDEX IF NOT EXISTS idx_files_name ON files(name);
CREATE INDEX IF NOT EXISTS idx_files_kind ON files(kind);

CREATE TABLE IF NOT EXISTS embeddings (
    file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
    vector BLOB NOT NULL,
    dim INTEGER NOT NULL,
    model TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relations (
    source_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    target_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, kind)
);

-- Per-path-prefix AI access rules. Most specific (longest) prefix wins.
CREATE TABLE IF NOT EXISTS access_rules (
    id INTEGER PRIMARY KEY,
    prefix TEXT UNIQUE NOT NULL,
    allow INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def connect() -> sqlite3.Connection:
    config.APP_DIR.mkdir(exist_ok=True)
    con = sqlite3.connect(config.DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(SCHEMA)
    return con


def set_meta(con, key: str, value: str):
    con.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    con.commit()


def get_meta(con, key: str, default: str = "") -> str:
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default
