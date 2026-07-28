# Hands AI — Local AI Orchestration

A local AI assistant that routes requests to the best available provider — **Ollama** (local models), **Claude API**, or **OpenAI** — with automatic fallback. One daemon, three front doors: a REST/WebSocket API, a terminal CLI, and a global-shortcut Electron panel.

## Architecture

```
┌─────────────┐   ┌──────────────┐
│ Electron    │   │ CLI          │
│ panel (app/)│   │ hands (cli/) │
└──────┬──────┘   └──────┬───────┘
       │  HTTP / SSE / WS │
       ▼                  ▼
┌──────────────────────────────────┐
│ Daemon (agent/) — FastAPI        │
│ http://127.0.0.1:7721            │
│ /health /chat /models /config    │
│ /model/set /ws/chat              │
└──────┬────────┬────────┬─────────┘
       ▼        ▼        ▼
    Ollama    Claude    OpenAI
   (local)     API       API
```

- **agent/** — FastAPI daemon on `127.0.0.1:7721`. Owns provider routing, config, and streaming (SSE + WebSocket).
- **app/** — Electron tray/panel app. Toggles with a global shortcut, auto-starts the daemon if it isn't running.
- **cli/** — `hands` command (Python + click/rich). Also auto-starts the daemon on demand.

Provider auto-selection order: **Ollama → Claude → OpenAI** (first one available wins). If the configured provider goes away, the router falls back automatically.

## Quick Start (one command)

```bash
bash start-all.sh
```

First run bootstraps everything: creates `agent/.venv`, installs Python deps, runs `npm install` in `app/` (Electron download is large — first run is slow), then starts the daemon and launches the panel. Closing the app also stops the daemon that the script started.

Daemon only (no Electron):

```bash
bash start-all.sh --daemon-only
```

## Per-Component Setup

### Daemon
```bash
cd agent
bash start.sh   # auto-creates .venv and installs requirements on first run
# or manually: python -m uvicorn main:app --host 127.0.0.1 --port 7721
```

### CLI
```bash
cd cli && bash install.sh
```
Note: `install.sh` pip-installs `click requests rich` for your user and symlinks `hands.py` to `/usr/local/bin/hands` (falls back to `~/.local/bin/hands`) — i.e. it writes **outside the repo**. To uninstall: `rm /usr/local/bin/hands` (or `~/.local/bin/hands`).

```bash
hands status                          # daemon + provider availability
hands chat "hello world"              # streamed chat (auto-starts daemon)
hands model list                      # models across all providers
hands model set <model-id>
hands config set anthropic-key sk-ant-...
hands config show                     # keys are masked
hands start / hands stop              # manage the daemon
hands claude ... / hands codex ...    # passthrough to those CLIs if installed
```

### Electron App
```bash
cd app && bash setup.sh   # npm install + npm start
```

## Global Shortcut

**Option+Space** (Mac) / **Alt+Space** (Win/Linux) — toggle the Hands AI panel. The app lives in the tray; closing the window keeps it running.

## The Panel

A compact dark panel: header with a daemon status indicator (solid mint dot = online, hollow ring = connecting/offline) and a clickable provider/model badge that opens the model switcher, a streaming chat area with persisted history across sessions, and a slide-in settings pane for API keys and the Ollama host.

## Configuration

Stored at `~/.hands/config.json` (created on first daemon start, `0600` permissions; API keys are never logged and are masked by `GET /config` and `hands config show`).

| Key | Default | Meaning |
|---|---|---|
| `active_provider` | `ollama` | `ollama`, `claude`, `openai`, or `auto` |
| `active_model` | `phi4-mini:latest` | Model id for the active provider |
| `anthropic_api_key` | `""` | Enables the Claude provider |
| `openai_api_key` | `""` | Enables the OpenAI provider |
| `ollama_host` | `http://localhost:11434` | Ollama server URL |

## API (daemon on :7721)

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Status + provider availability |
| `/chat` | POST | Chat; `{"message", "stream", "history"}` — SSE when `stream: true` |
| `/ws/chat` | WS | Stateful streaming chat |
| `/models` | GET | Models from all providers |
| `/model/set` | POST | Switch provider/model (validated) |
| `/config` | GET/POST | Read (masked) / update config |

## Troubleshooting

- **Port 7721 busy** — `start-all.sh` exits with an error if the daemon never becomes healthy. Check what owns the port: `lsof -i :7721`. If it's a stale daemon: `hands stop`.
- **No Ollama** — the router falls back to Claude/OpenAI if an API key is set; otherwise chat returns an informative provider error. Install Ollama or add a key via `hands config set`.
- **Global shortcut not working** — another app may own Option+Space (e.g. Spotlight alternatives); the app logs a warning if registration fails.
- **Daemon logs** — `~/.hands/daemon.log` when started via the CLI or the app.
