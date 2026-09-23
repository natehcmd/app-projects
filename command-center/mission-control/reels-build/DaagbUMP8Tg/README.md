# Claude Code Setup Advisor

## What this is (and isn't)

The source reel for this build ("Comment PLUGIN to get this Claude Code
Setup plugin...") is a comment-for-link engagement post. It claims Anthropic
"just dropped an official free plugin called Claude Code Setup" that scans
your codebase and recommends hooks/skills/subagents/MCP servers — but
discloses zero actual technique, algorithm, or implementation detail. The
entire value proposition in the reel is the gated download behind a
comment, not anything explained. There is no such official Anthropic
plugin as of this writing, and nothing here claims to be it.

Rather than reproduce vaporware, this is a small, honest, standalone tool
that does the one concrete thing the reel gestures at: **look at what's
actually in a project and suggest which Claude Code building blocks fit
it.**

## What it does

`scan_setup.py` scans a project directory **locally and offline** — no
network calls, no telemetry, nothing installed or modified — for common
signals:

- `package.json` dependencies (Next.js, React, Express, Prisma, Jest,
  ESLint, Stripe SDK, ...)
- Python manifests (`requirements.txt`, `pyproject.toml`, `Pipfile`) for
  Django, Flask, FastAPI, pytest, SQLAlchemy/Alembic
- `Dockerfile` / `docker-compose.yml` (and which services it references —
  Postgres, Redis, Mongo)
- `.github/workflows/` for CI
- `terraform/` or `*.tf` files for infrastructure-as-code
- Presence/absence of a test directory
- `.env.example` **keys only** (never values) to spot referenced services
  like Stripe or Slack

Based on what it finds, it prints a plain Markdown report suggesting:

- **Hooks** — pre-commit/pre-push automation (lint, type-check, test-on-push)
- **Skills** — packaged instructions for repeatable tasks specific to your
  stack
- **Subagents** — focused reviewers you could wire up (API review, DB
  migration review, CI triage, infra review)
- **MCP servers** — which live-service connectors would actually be useful
  (Postgres, GitHub, Stripe, Vercel, etc.), based on what your project
  really uses

It does **not** install, configure, download, or connect anything on your
behalf. It's a read-only advisor — you review the suggestions and set up
whatever you like by hand (e.g. via Claude Code's own `/plugin` or MCP
config, or your own hooks in `.claude/settings.json`).

## How to run it

Requires only Python 3 (standard library, no `pip install` needed).

```bash
python3 scan_setup.py /path/to/your/project
```

Or, from inside the project you want scanned:

```bash
cd /path/to/your/project
python3 /path/to/scan_setup.py
```

Example output:

```
# Claude Code Setup Report — /path/to/your/project

## What was detected
- Node project (package.json found)
- TypeScript in use
- Next.js framework detected
- Prisma ORM detected

## Suggested hooks (pre-commit / pre-push automation)
- pre-commit: run `tsc --noEmit` to block type errors before commit

## Suggested skills (packaged instructions for repeatable tasks)
- next-js-app-router-helper: scaffold routes/loaders following App Router conventions

## Suggested subagents (focused reviewers you can invoke)
- db-migration-reviewer: checks new Prisma migrations for destructive changes

## Suggested mcp_servers (connect Claude to live services)
- postgres (or your Prisma datasource) — inspect schema/data from chat
```

## Setup / API-key notes

None. This script reads only files already on disk in the target
directory and makes no outbound requests, so there's nothing to
authenticate and no keys to configure. If you act on its suggestions (e.g.
adding an MCP server for Postgres or Stripe), you'll set up credentials for
*that* separately, following the normal Claude Code / MCP server docs for
whichever integration you choose — this tool has no involvement in that
step.

## Extending it

The detection logic lives entirely in `scan(...)` in `scan_setup.py` — add
new `if` blocks there to recognize more frameworks/manifests and call
`f.suggest(category, "...")` to add recommendations. It's intentionally a
single flat file so it's easy to read and modify in one sitting.
