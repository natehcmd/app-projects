# Agent Deck

A local, single-page tracker for terminal/agent sessions. Every agent gets a name, role, color, status, and home machine — and a **real PTY** hosted by the server, so you can open a live terminal on any agent, from any browser tab, and it survives reloads. Agents appear as an interactive graph where related agents can be linked (orchestrator → worker, generator → reviewer), plus a workflow mode for chatting with an agent persona and handing work between them.

See [PRODUCT.md](PRODUCT.md) for the product intent and design principles.

## Quick start

```sh
npm install        # node-pty is a native module — needs Xcode Command Line Tools on macOS
npm start          # → Agent Deck running → http://localhost:8444
```

Or just double-click `start.command` in Finder — it starts the server and opens the browser for you.

Override the port with `PORT=9000 npm start` (default is `8444`, bound to `127.0.0.1` only).

> The `postinstall` script (`chmod +x .../spawn-helper`) is load-bearing: node-pty's prebuilt spawn-helper sometimes lands without its exec bit, which breaks PTY spawning. Leave it in place.

## Architecture

- **`server.js`** — Node HTTP + WebSocket server. Serves static files (read per-request, so UI edits go live without a restart), maps `/vendor/*` to `node_modules`, and hosts one node-pty PTY per agent. The full WebSocket protocol (`attach`, `input`, `resize`, `relay`, `kill` → `output`, `scrollback`, `exit`, `live`, `relayed`) is documented in the header comment of `server.js`.
- **`index.html`** — the entire UI: sidebar list, SVG graph (pan/zoom/drag/link), per-agent xterm.js terminals, and workflow mode. Styled to the nate-default system (dark glass, oklch pastel accents, reduced-motion support).
- **`deck-state.json`** — server-side persistence for agents, links, and the viewport (`GET`/`POST /state`). PTYs are deliberately kept alive when tabs close, so sessions survive tab switches and reloads.
- **`workflows/`** — saved workflow runs (`/api/workflows`); user data, gitignored.

### HTTP endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | The app |
| `/state` | GET/POST | Load/save deck state (agents, links, view) |
| `/api/workflows` | GET/POST | List/save workflow runs |
| `/api/agent-turn` | POST | One-shot agent turn in workflow mode |
| `/vendor/*` | GET | Serves xterm.js assets from `node_modules` |

## State file policy

`deck-state.json` **is committed** on purpose: it is the durable board (agents, personas, links), and the repo history doubles as its backup ("autosnapshot" commits). Two things to know:

- The running server rewrites it on every save/pan/zoom, so commit a snapshot you've just looked at, and **never `git checkout`/`restore` it while the server is running** — you'd race the autosave and lose live state.
- It contains the agent persona prompts (no credentials). If you fork this and put secrets in agent notes, gitignore it first.

## A note on workflow mode

`POST /api/agent-turn` shells out to the local `claude` CLI with `--permission-mode acceptEdits`. That means workflow-mode agent turns can edit files in your home directory without prompting. Know that before you point personas at real goals.

## What it looks like

- **Graph view** — pastel glass nodes on a dotted dark canvas; each node shows initials, name, role, a status dot (with label), and a `>_` badge when its PTY is live. Drag to arrange, drag between nodes to link, scroll to zoom.
- **Terminals** — click a live agent to open its xterm panel; sessions persist server-side with 200KB of scrollback per agent for reattach.
- **Workflow mode** — pick an agent, give it a goal, and relay messages between linked agents' terminals.
