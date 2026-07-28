"""Per-folder AI access control.

Rules are path prefixes with allow/deny. The longest matching prefix wins.
The MCP server (what Claude and other AIs talk to) filters EVERYTHING through
is_allowed(); the web UI (for the human) sees the full graph and manages rules.
"""
from . import db

# Denied out of the box — can be re-enabled in the UI if you really want.
DEFAULT_DENY = [
    str(db.config.HOME / ".ssh"),
    str(db.config.HOME / ".aws"),
    str(db.config.HOME / ".gnupg"),
    str(db.config.HOME / ".config"),
]


def ensure_defaults(con):
    for prefix in DEFAULT_DENY:
        con.execute(
            "INSERT OR IGNORE INTO access_rules(prefix, allow) VALUES(?, 0)",
            (prefix,))
    con.commit()


def list_rules(con) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT id, prefix, allow FROM access_rules ORDER BY prefix")]


def set_rule(con, prefix: str, allow: bool):
    prefix = prefix.rstrip("/")
    con.execute(
        """INSERT INTO access_rules(prefix, allow) VALUES(?, ?)
           ON CONFLICT(prefix) DO UPDATE SET allow=excluded.allow""",
        (prefix, 1 if allow else 0))
    con.commit()


def delete_rule(con, rule_id: int):
    con.execute("DELETE FROM access_rules WHERE id=?", (rule_id,))
    con.commit()


def is_allowed(rules: list[dict], path: str) -> bool:
    """Longest matching prefix decides; default is allow."""
    best_len, allow = -1, True
    for r in rules:
        p = r["prefix"]
        if (path == p or path.startswith(p + "/")) and len(p) > best_len:
            best_len, allow = len(p), bool(r["allow"])
    return allow


def filter_rows(con, rows):
    rules = list_rules(con)
    return [r for r in rows if is_allowed(rules, r["path"] if not isinstance(r, dict) else r["path"])]
