# Mission Control

Local, single-user "agentic OS" dashboard. A FastAPI backend (`server.py`, ~30 endpoints)
serves a vanilla-JS single-page UI at **http://localhost:8450**. Everything runs on this
machine — local SQLite, local Ollama for briefs, local CLI agents for chat/swarm. Nothing
is deployed publicly.

## Tabs

| Tab | What it does |
|---|---|
| Chat | Talk to a local CLI agent engine; conversation never leaves the machine |
| Home | Daily check-in score ring, urgent goals, quick stats |
| Reels | Instagram reel vault — curated saves with transcripts, topics, verdicts |
| Life HQ | Goals pad, subscriptions, net-worth snapshots, daily check-ins |
| Briefs | Morning CEO briefs generated via Ollama (`qwen2.5-coder:32b`) |
| Term | Launch/watch shell jobs, snapshot Terminal + browser tabs and CLI processes |
| Swarm | Fan-out multi-agent runs |
| Flows | Saved multi-step agent chains, plan + run + history |
| Tools | System toolbox: status, models, cron overview |

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

Dev run (creates `.venv` and installs pinned deps if missing):

```bash
./run.sh            # serves on 127.0.0.1:8450 (override with PORT=…)
```

Quick health check:

```bash
curl http://localhost:8450/api/status
```

## launchd (the real entry point)

Three agents in `~/Library/LaunchAgents/`:

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
