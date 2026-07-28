#!/usr/bin/env python3
"""Sync Instagram saves into a Notion database.

Reads reel/post metadata already curated by this project's ig-curate.py
(~/AgentDrop-Workspace/reels/*.txt caption sidecars) and pushes new items into
a Notion "Instagram Saves" database via Notion's official API, using a
state file to avoid duplicate syncs.

Uses the real Notion API only (api.notion.com) with a user-supplied
integration token. No Instagram credentials are touched here — that side is
already handled by ig-curate.py, which owns the IG session.
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
STATE_FILE = Path.home() / "AgentDrop-Workspace" / ".notion-sync-state.json"
REELS_DIR = Path.home() / "AgentDrop-Workspace" / "reels"


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {"synced": []}
    return {"synced": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def notion_request(token, method, path, payload=None):
    req = urllib.request.Request(
        f"{NOTION_API}{path}",
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def collect_saves():
    """Every reel/post caption sidecar not yet synced."""
    items = []
    for txt in sorted(REELS_DIR.glob("*.txt")):
        code = txt.stem
        if ".fdash" in code:
            continue
        caption = txt.read_text(encoding="utf-8", errors="replace").strip()
        items.append({"id": code, "caption": caption[:2000],
                       "url": f"https://www.instagram.com/reel/{code}/"})
    return items


def push_to_notion(token, database_id, item, dry_run=False):
    properties = {
        "Name": {"title": [{"text": {"content": item["id"]}}]},
        "Media ID": {"rich_text": [{"text": {"content": item["id"]}}]},
        "Caption": {"rich_text": [{"text": {"content": item["caption"][:2000]}}]},
        "URL": {"url": item["url"]},
        "Status": {"select": {"name": "New"}},
        "Type": {"select": {"name": "Reel"}},
    }
    if dry_run:
        print(f"[dry-run] would create page for {item['id']}")
        return True
    try:
        notion_request(token, "POST", "/pages", {
            "parent": {"database_id": database_id},
            "properties": properties,
        })
        return True
    except Exception as e:
        print(f"  failed to sync {item['id']}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Sync new Instagram saves into a Notion 'Instagram Saves' database.")
    parser.add_argument("--database-id", default=os.environ.get("NOTION_SAVES_DB_ID"),
                         help="Notion database ID (or set NOTION_SAVES_DB_ID)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would sync, don't call Notion")
    args = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN")
    if not token and not args.dry_run:
        print("Set NOTION_TOKEN to a Notion integration token (https://www.notion.so/my-integrations).\n"
              "Or pass --dry-run to preview without a token.", file=sys.stderr)
        sys.exit(1)
    if not args.database_id and not args.dry_run:
        print("Pass --database-id or set NOTION_SAVES_DB_ID (share your Notion database with the integration first).",
              file=sys.stderr)
        sys.exit(1)

    state = load_state()
    synced = set(state["synced"])
    items = collect_saves()
    new_items = [i for i in items if i["id"] not in synced]

    print(f"{len(items)} saves on disk, {len(new_items)} not yet synced.")
    for item in new_items:
        ok = push_to_notion(token, args.database_id, item, dry_run=args.dry_run)
        if ok and not args.dry_run:
            synced.add(item["id"])

    if not args.dry_run:
        state["synced"] = sorted(synced)
        save_state(state)
    print(f"Done. {len(synced)} total synced." if not args.dry_run else "Dry run complete, nothing written.")


if __name__ == "__main__":
    main()
