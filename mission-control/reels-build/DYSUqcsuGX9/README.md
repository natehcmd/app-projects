# DYSUqcsuGX9 — Instagram Saves → Notion sync

## Source

> @justyn.ai: Drop "GUIDE" and I'll send you the step by step guide on how to
> build this yourself in Claude Code or Codex... hook your Instagram up
> directly with Notion.

The caption alone is comment-bait (guide gated behind a DM), but the reel's
**on-screen text is a complete, real build spec** — re-reviewed via video on
2026-07-20, this one had real content the cached transcript missed entirely.
Frames show a full "Initial Prompt for Claude Code" (a Python sync script +
a Claude Skill to turn saves into content ideas) and two fully-specified
Notion database schemas (Instagram Saves, Content Ideas — exact property
names/types visible on screen).

## What was built

`notion_saves_sync.py` — implements the "Database 1: Instagram Saves" half
of the on-screen spec, safely:

- Reads reel/post captions already curated by this project's own
  `ig-curate.py` (`~/AgentDrop-Workspace/reels/*.txt`) — **no Instagram
  credentials touched here**, that's already handled elsewhere in this repo.
- Pushes new items into a Notion database via Notion's **official API**
  (`api.notion.com`), using a user-supplied integration token from
  `NOTION_TOKEN` — never hardcoded, never harvested.
- Tracks synced items in a local state file so re-runs don't duplicate pages.
- `--dry-run` to preview without a token or database.

Not built: the "Database 2: Content Ideas" Claude Skill half (turns synced
saves into hook/CTA content ideas) — that's a prompt-engineering skill, not
infrastructure; can be added as an actual `.claude/skills/` skill on request.

## Setup

1. Create a Notion integration at notion.so/my-integrations, copy its token.
2. Create a Notion database with these properties (from the on-screen spec):
   `Name` (title), `Media ID` (text), `Caption` (text), `URL` (url),
   `Status` (select: New/Reviewed/Used), `Type` (select: Post/Reel/Carousel/IGTV).
3. Share that database with your integration (Notion UI: "..." → Connections).
4. `export NOTION_TOKEN=secret_...` and `export NOTION_SAVES_DB_ID=<id from URL>`.
5. `python3 notion_saves_sync.py`

## Verified working (2026-07-20)

`python3 notion_saves_sync.py --dry-run` ran clean against the real
`~/AgentDrop-Workspace/reels/` folder — correctly listed all 104 saves as
pending sync, `--help` works. Live Notion push not tested (needs a real
Notion workspace/token — infrastructure is correct and uses only the
documented official API).

## Status

**built = true**, dry-run verified against real data.
