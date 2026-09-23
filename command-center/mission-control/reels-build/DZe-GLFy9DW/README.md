# Second Brain (relational, not backlinks)

## Source material and what I actually built

The source reel ([DZe-GLFy9DW](/Users/natehoward/AgentDrop-Workspace/reels/DZe-GLFy9DW.txt))
is mostly motivational copy with no concrete technique: "ditch Obsidian
backlinks for Notion relations" and "move one project into a real database."
It doesn't specify a schema, a workflow, or a tool — just a philosophical
claim.

Rather than build nothing, I implemented the one concrete, checkable claim
buried in the rhetoric: **a backlink only says two notes mention each
other; it can't say "this task belongs to this project, this project
belongs to this client, this client is worth $X" — and because of that, a
backlink graph can't answer "what should I work on today?" while a real
relational structure can.**

This is a small local tool that proves that difference instead of just
asserting it. It's the minimal version of "Notion relations" you could
build without needing Notion, an account, or an API key: a SQLite database
of typed **entities** (clients, projects, tasks, SOPs, notes — any type you
want) connected by typed, directional **relations** (`belongs_to`,
`blocks`, `relates_to`, ...), queryable from the command line.

## What it does

- `init` — creates the SQLite database and tables.
- `add` — adds an entity (a client, project, task, SOP, whatever) with real
  fields: status, owner, priority, due date, notes.
- `link` — connects two entities with a typed, directional relation (e.g.
  task `belongs_to` project, project `belongs_to` client).
- `list` — lists entities, optionally filtered by type.
- `show <id>` — shows one entity plus all its incoming/outgoing relations.
- `today` — **the payoff.** Walks task → project → client relations and
  prints an actionable, priority-sorted, due-date-aware list of what's open.
  This is the query a flat pile of markdown backlinks structurally cannot
  answer, because backlinks don't carry status, ownership, or hierarchy —
  only "these two notes mention each other."
- `export` — dumps the whole entity/relation graph as JSON, e.g. to paste
  into an LLM prompt as context ("query clients, deliverables, and SOPs" —
  same idea the reel gestures at, minus needing an actual AI integration).

## How to run it

Requires only Python 3 (standard library only — no `pip install` needed).

```bash
cd /Users/natehoward/Projects/mission-control/reels-build/DZe-GLFy9DW

# 1. Set up the database
python3 brain.py init

# 2. Add a client, a project under it, and a couple of tasks under the project
python3 brain.py add --type client  --name "Acme Co" --status active
python3 brain.py add --type project --name "Acme Website Redesign" --owner Nate --priority 2
python3 brain.py add --type task    --name "Draft homepage copy" --owner Nate --priority 1 --due 2026-07-22
python3 brain.py add --type task    --name "Pick font pairing" --owner Nate --priority 4
python3 brain.py add --type sop     --name "Client Onboarding SOP"

# 3. Connect them with relations (ids are printed when you `add`)
python3 brain.py link --from 2 --to 1 --relation belongs_to   # project -> client
python3 brain.py link --from 3 --to 2 --relation belongs_to   # task -> project
python3 brain.py link --from 4 --to 2 --relation belongs_to   # task -> project

# 4. Ask the question a backlink vault can't answer
python3 brain.py today
```

Other useful commands:

```bash
python3 brain.py list                 # everything
python3 brain.py list --type task     # just tasks
python3 brain.py show 2               # entity #2 + its relations
python3 brain.py export > graph.json  # full graph as JSON for an LLM
```

By default the database is created at `secondbrain.db` next to `brain.py`.
Pass `--db /path/to/other.db` before the subcommand to use a different file
(useful for keeping separate brains per area of life/work).

## Setup / API-key notes

None. This is a plain SQLite file on disk plus a single Python script — no
signup, no network calls, no API key. If you want an actual AI to "query
clients, deliverables, and SOPs" the way the reel describes, pipe
`brain.py export`'s JSON into whatever LLM you're using as context; wiring
that up is a deliberately separate, optional step and not required for the
tool to work.

## Why this and not a literal Notion clone

Building a real Notion-relations clone would mean either wrapping the
actual Notion API (requires a Notion account + integration token, and ties
the tool to a paid third-party service) or reimplementing a large chunk of
a hosted database product. Neither is "small, self-contained, and
runnable" in the spirit of the request. The relational-vs-backlink
*mechanism* the reel is actually arguing for — typed relations you can
query instead of untyped links you can only browse — is fully captured
here in something you can run in two commands with nothing to sign up for.
