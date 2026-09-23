# Mission Control

Local, single-user "agentic OS" dashboard. A FastAPI backend (`server.py`, ~30 endpoints)
serves a vanilla-JS single-page UI at **http://localhost:8450**. Everything runs on this
machine — local SQLite, local Ollama for briefs, local CLI agents for chat/swarm. Nothing
is deployed publicly.

## Tabs

| Tab | What it does |
|---|---|
| Chat | Talk to a local CLI agent engine; conversation never leaves the machine |
| Hands AI | Live WebSocket link to the native Hands AI Mac app (`ws://127.0.0.1:8787/agent`) — same agent, tools, and conversation as the native app, just from this dashboard. Needs Hands AI → Settings → Remote turned on. |
| Home | Daily check-in score ring, urgent goals, quick stats |
| Reels | Instagram reel vault — curated saves with transcripts, topics, verdicts |
| Life HQ | Goals pad, subscriptions, net-worth snapshots, daily check-ins |
| Briefs | Morning CEO briefs generated via Ollama (`qwen3-coder:30b`) |
| Term | Launch/watch shell jobs, snapshot Terminal + browser tabs and CLI processes |
| Swarm | Fan-out multi-agent runs |
| Flows | Saved multi-step agent chains, plan + run + history |
| Tools | System toolbox: status, models, cron overview |
| Reel Tools | Runs the real scripts cataloged in `reels-build/tools_manifest.json` |
| Learn | Ollama-generated curriculum + quiz for a subject, cached to `data/learn/` |
| Compare | Records real side-by-side Claude-vs-Gemini feature comparisons you've actually done — not auto-generated, since there's no honest way to synthesize what the other side actually built |
| Workflows | Test buttons for a small fixed allowlist of local scripts (Reel Archive tooling) |
| FileGraph | Embeds the separate File Graph app's graph view (needs it running on :8437 — see its own repo) |
| Control | Hardware/app control via `osascript`/`pmset` |

This table used to only list 9 of these 15 — kept it in sync with `static/index.html`'s dock this time.

UI style is "nate-default": dark glass panels, pastel accents, floating bottom dock
(`static/os.css` is the reference implementation of the house style).

## Layout

```
server.py            FastAPI app: status, chat, reels, lifehq, briefs, term, swarm, flows
static/              index.html + os.js (SPA views) + os.css (design system)
scripts/             morning_brief.py, sync_agentdrop_reels.py, add_reels.py (launchd cron jobs)
data/                live runtime state (SQLite mission.db, reel media/meta, logs) — gitignored
models/              ggml-base.en.bin Whisper model (141 MB) — gitignored, do not delete
.venv/               virtualenv used by launchd — gitignored
```

## Run

Normal operation is via launchd (see below) — the server is probably already running.

**First run on a fresh checkout** (e.g. after the monorepo consolidation): `data/` is
gitignored and won't exist yet — `mkdir data` before starting, or `init_db()` fails with
`sqlite3.OperationalError: unable to open database file`.

Dev run (creates `.venv` and installs pinned deps if missing):

```bash
mkdir -p data   # only needed once, on a fresh checkout
./run.sh            # serves on 127.0.0.1:8450 (override with PORT=…)
```

Quick health check:

```bash
curl http://localhost:8450/api/status
```

## launchd (the real entry point)

Three agents are *documented* below but were never actually installed on this Mac as of
2026-08-25 (consolidation brought the repo over without them) — none of
`~/Library/LaunchAgents/com.nate.mission-control*.plist` exist here yet. Until they're
installed, the server only runs for as long as a manually-started `./run.sh` process
stays alive (it will not survive a reboot or logout). Install them with `launchctl
bootstrap` below if you want the always-on behavior described here.

| Plist | Role | Log |
|---|---|---|
| `com.nate.mission-control.plist` | uvicorn server on :8450, KeepAlive | `data/server.log` |
| `com.nate.mission-control.morningbrief.plist` | daily 08:00 brief via Ollama | `data/briefs/cron.log` |
| `com.nate.mission-control.reelsync.plist` | daily 07:20 AgentDrop reel sync | `data/reels_sync.log` |

```bash
# Restart the server (the ONLY sanctioned way):
launchctl kickstart -k gui/501/com.nate.mission-control

# Install / uninstall an agent:
launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.nate.mission-control.plist
launchctl bootout   gui/501/com.nate.mission-control
```

## Cautions

- `/api/term/run`, `/api/swarm/run`, and `/api/flows/*/run` execute real shell commands
  and CLI agents (with timeouts). Don't exercise them casually.
- `data/mission.db` is live while the server runs; don't edit it directly.
- Reel sync reads browser cookies via gallery-dl — never commit cookie files or
  `data/` logs. `data/`, `.env*`, and `data-backup/` are gitignored; the DB backup
  stays local only (it contains personal finance/check-in data).
- Never touch the Agent Deck server on port 8444.
