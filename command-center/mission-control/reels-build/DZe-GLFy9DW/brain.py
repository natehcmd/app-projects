#!/usr/bin/env python3
"""
brain.py — a tiny relational "second brain" CLI.

Thesis (from the source reel): markdown-backlink vaults (Obsidian-style)
optimize for *collecting* notes, not *operating* on them. A backlink only
says "these two notes mention each other" — it can't say "this task belongs
to this project, this project belongs to this client, this client is worth
$X, this task is overdue." Relations with typed fields can say all of that,
and can be queried.

This tool is the smallest possible version of that idea:
  - Entities (clients, projects, tasks, SOPs, or any type you want) live in
    a SQLite table with real fields: status, owner, priority, due date.
  - Relations between entities are typed and directional (e.g. task
    "belongs_to" project, project "belongs_to" client).
  - Because it's a real database, you can ask real questions of it — the
    flagship one being "what should I work on today?", which a pile of
    markdown files with backlinks structurally cannot answer.

No dependencies beyond the Python 3 standard library. No API keys required.
"""

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

DEFAULT_DB = Path(__file__).parent / "secondbrain.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,              -- client | project | task | sop | note | ...
    name        TEXT NOT NULL,
    status      TEXT DEFAULT 'open',        -- open | in_progress | done | blocked
    owner       TEXT,
    priority    INTEGER DEFAULT 3,          -- 1 (highest) .. 5 (lowest)
    due_date    TEXT,                       -- ISO date, optional
    notes       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS relations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id       INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_id         INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,            -- belongs_to | blocks | relates_to | ...
    UNIQUE(from_id, to_id, relation_type)
);
"""


def get_conn(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def cmd_init(args):
    conn = get_conn(args.db)
    conn.executescript(SCHEMA)
    conn.commit()
    print(f"Initialized database at {args.db}")


def cmd_add(args):
    conn = get_conn(args.db)
    conn.executescript(SCHEMA)  # tolerate init being skipped
    cur = conn.execute(
        """INSERT INTO entities (type, name, status, owner, priority, due_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (args.type, args.name, args.status, args.owner, args.priority,
         args.due, args.notes),
    )
    conn.commit()
    print(f"Added {args.type} #{cur.lastrowid}: {args.name}")


def cmd_link(args):
    conn = get_conn(args.db)
    _require_entity(conn, args.from_id)
    _require_entity(conn, args.to_id)
    conn.execute(
        """INSERT OR IGNORE INTO relations (from_id, to_id, relation_type)
           VALUES (?, ?, ?)""",
        (args.from_id, args.to_id, args.relation),
    )
    conn.commit()
    a = conn.execute("SELECT name FROM entities WHERE id=?", (args.from_id,)).fetchone()
    b = conn.execute("SELECT name FROM entities WHERE id=?", (args.to_id,)).fetchone()
    print(f"Linked: {a['name']} --[{args.relation}]--> {b['name']}")


def _require_entity(conn, entity_id):
    row = conn.execute("SELECT id FROM entities WHERE id=?", (entity_id,)).fetchone()
    if not row:
        sys.exit(f"Error: no entity with id {entity_id}")


def cmd_list(args):
    conn = get_conn(args.db)
    query = "SELECT * FROM entities"
    params = []
    if args.type:
        query += " WHERE type = ?"
        params.append(args.type)
    query += " ORDER BY priority ASC, id ASC"
    rows = conn.execute(query, params).fetchall()
    _print_table(rows)


def cmd_show(args):
    conn = get_conn(args.db)
    e = conn.execute("SELECT * FROM entities WHERE id=?", (args.id,)).fetchone()
    if not e:
        sys.exit(f"No entity with id {args.id}")
    print(f"#{e['id']} [{e['type']}] {e['name']}")
    print(f"  status: {e['status']}   owner: {e['owner'] or '-'}   "
          f"priority: {e['priority']}   due: {e['due_date'] or '-'}")
    if e["notes"]:
        print(f"  notes: {e['notes']}")

    out = conn.execute(
        """SELECT r.relation_type, e2.id, e2.type, e2.name
           FROM relations r JOIN entities e2 ON r.to_id = e2.id
           WHERE r.from_id = ?""", (args.id,)
    ).fetchall()
    inb = conn.execute(
        """SELECT r.relation_type, e2.id, e2.type, e2.name
           FROM relations r JOIN entities e2 ON r.from_id = e2.id
           WHERE r.to_id = ?""", (args.id,)
    ).fetchall()

    if out:
        print("  -> outgoing relations:")
        for r in out:
            print(f"     [{r['relation_type']}] -> #{r['id']} ({r['type']}) {r['name']}")
    if inb:
        print("  <- incoming relations:")
        for r in inb:
            print(f"     [{r['relation_type']}] <- #{r['id']} ({r['type']}) {r['name']}")


def cmd_today(args):
    """The whole point: a backlink graph can't answer this. A relational one can."""
    conn = get_conn(args.db)
    rows = conn.execute(
        """
        SELECT t.id, t.name, t.priority, t.due_date, t.owner,
               p.name AS project_name, c.name AS client_name
        FROM entities t
        LEFT JOIN relations rp ON rp.from_id = t.id AND rp.relation_type = 'belongs_to'
        LEFT JOIN entities p ON p.id = rp.to_id AND p.type = 'project'
        LEFT JOIN relations rc ON rc.from_id = p.id AND rc.relation_type = 'belongs_to'
        LEFT JOIN entities c ON c.id = rc.to_id AND c.type = 'client'
        WHERE t.type = 'task' AND t.status IN ('open', 'in_progress')
        ORDER BY
            CASE WHEN t.due_date IS NULL THEN 1 ELSE 0 END,
            t.due_date ASC,
            t.priority ASC
        """
    ).fetchall()

    if not rows:
        print("Nothing open. Either you're done, or nothing's in the database yet.")
        return

    today = date.today().isoformat()
    print(f"What to work on today ({today}):\n")
    for r in rows:
        overdue = " OVERDUE" if r["due_date"] and r["due_date"] < today else ""
        ctx = " / ".join(x for x in [r["client_name"], r["project_name"]] if x)
        ctx = f"  [{ctx}]" if ctx else ""
        due = f"  due {r['due_date']}" if r["due_date"] else ""
        owner = f"  owner:{r['owner']}" if r["owner"] else ""
        print(f"  P{r['priority']}  #{r['id']:<4} {r['name']}{ctx}{due}{owner}{overdue}")


def cmd_export(args):
    """Dump the whole graph as JSON — e.g. to hand to an LLM as context."""
    conn = get_conn(args.db)
    entities = [dict(row) for row in conn.execute("SELECT * FROM entities").fetchall()]
    relations = [dict(row) for row in conn.execute("SELECT * FROM relations").fetchall()]
    print(json.dumps({"entities": entities, "relations": relations}, indent=2))


def _print_table(rows):
    if not rows:
        print("(no entities)")
        return
    for r in rows:
        due = f"  due {r['due_date']}" if r["due_date"] else ""
        owner = f"  owner:{r['owner']}" if r["owner"] else ""
        print(f"#{r['id']:<4} [{r['type']:<8}] P{r['priority']}  {r['status']:<11} "
              f"{r['name']}{owner}{due}")


def build_parser():
    p = argparse.ArgumentParser(
        description="A tiny relational second brain: entities + typed relations, "
                     "queryable instead of just linkable."
    )
    p.add_argument("--db", type=Path, default=DEFAULT_DB,
                    help=f"path to the SQLite database (default: {DEFAULT_DB})")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the database and tables").set_defaults(func=cmd_init)

    a = sub.add_parser("add", help="add an entity (client/project/task/sop/note/...)")
    a.add_argument("--type", required=True)
    a.add_argument("--name", required=True)
    a.add_argument("--status", default="open")
    a.add_argument("--owner", default=None)
    a.add_argument("--priority", type=int, default=3)
    a.add_argument("--due", default=None, help="ISO date, e.g. 2026-08-01")
    a.add_argument("--notes", default=None)
    a.set_defaults(func=cmd_add)

    l = sub.add_parser("link", help="create a typed relation between two entities")
    l.add_argument("--from", dest="from_id", type=int, required=True)
    l.add_argument("--to", dest="to_id", type=int, required=True)
    l.add_argument("--relation", default="belongs_to",
                    help="e.g. belongs_to, blocks, relates_to")
    l.set_defaults(func=cmd_link)

    ls = sub.add_parser("list", help="list entities, optionally filtered by --type")
    ls.add_argument("--type", default=None)
    ls.set_defaults(func=cmd_list)

    s = sub.add_parser("show", help="show one entity and all its relations")
    s.add_argument("id", type=int)
    s.set_defaults(func=cmd_show)

    sub.add_parser("today", help="what should I work on today?").set_defaults(func=cmd_today)

    sub.add_parser("export", help="dump the full graph as JSON").set_defaults(func=cmd_export)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
