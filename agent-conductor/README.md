# Agent Conductor — Cmux Control Tower

Workspace orchestrator and multi-agent execution pipeline for macOS. It watches
and coordinates:

- **cmux** terminal surfaces (via the Unix socket at `/tmp/cmux.sock`)
- **Google Chrome** tabs (via JXA, and optionally the DevTools Protocol)
- **local dev processes** (via `ps` / `lsof` — port ↔ PID ↔ git repo)
- a **multi-agent swarm pipeline** (Critic → Router → Workers → context wipe)
  guarded by an out-of-band **Sentinel** log watcher

A background **daemon** fuses all of this into a JSON snapshot broadcast once a
second over a WebSocket; a **React 18 + Tailwind** Control Tower renders it as a
Project Folder Matrix grouped by git repository.

---

## Layout

```
agent-conductor/
├── src/
│   ├── shared/
│   │   └── types.ts            # wire contracts shared by daemon + UI
│   ├── daemon/
│   │   ├── cmux-ipc.ts         # resilient Unix-socket JSON-RPC client (§1)
│   │   ├── chrome-harvester.ts # JXA tab scan + CDP explorer (§2)
│   │   ├── process-discovery.ts# ps/lsof/git OS integration layer (§2.3, §3)
│   │   ├── dedup-engine.ts     # exact-dup / port-conflict / heuristics (§5)
│   │   ├── swarm-pipeline.ts   # Critic + Router prompts/schemas, routing,
│   │   │                       # KV-cache purge, pipeline state machine (§4)
│   │   ├── sentinel.ts         # halt-on-break log watcher (§4.5)
│   │   ├── state-aggregator.ts # fuses sources into one snapshot
│   │   ├── websocket-server.ts # SERVER_STATE_UPDATE + control RPC (§7)
│   │   ├── logger.ts
│   │   └── index.ts            # daemon entry point — wires it together
│   └── ui/
│       ├── Dashboard.tsx           # Project Folder Matrix (§6.1)
│       ├── SurfaceCard.tsx         # (§6.2)
│       ├── DuplicateResolverModal.tsx  # (§6.3)
│       ├── TerminalModal.tsx       # xterm.js live stream (§6.4)
│       ├── useConductorSocket.ts   # the one WebSocket connection
│       ├── main.tsx / index.html / styles.css
```

---

## Quick start

```bash
cd agent-conductor
npm install
cp .env.example .env        # adjust ports / socket path if needed

# terminal 1 — the daemon
npm run daemon              # ws://127.0.0.1:8787

# terminal 2 — the Control Tower
npm run ui:dev              # http://localhost:5273
```

Type-check everything without emitting:

```bash
npm run typecheck
```

### Optional integrations

| Feature | Requirement |
| :-- | :-- |
| cmux surfaces | `cmux` running, socket at `CMUX_SOCKET_PATH` (default `/tmp/cmux.sock`) |
| Chrome tabs | Google Chrome running; first run triggers a macOS Automation permission prompt |
| Chrome DevTools features | launch Chrome with `--remote-debugging-port=9222` |
| llama-server context wipe | `llama-server` reachable at `LLAMA_HOST:LLAMA_PORT`, `/slots/<id>?action=erase` enabled |

The daemon degrades gracefully: if cmux or Chrome is absent it simply reports
empty collections and keeps retrying.

---

## Wiring real swarm workers

`src/daemon/index.ts` builds the `SwarmPipeline` with a **stub** `runWorker`.
Replace it with your provider calls:

- `LOCAL_CODEGEN` → `llama-server` / Ollama (Qwen-Coder etc.)
- `GEMINI_COMPLEX_UI` → your cloud model for AppKit/Swift/large-context work

`determineModelRouting()` and the Critic/Router **system prompts + JSON
schemas** are exported from `src/daemon/swarm-pipeline.ts`. After each sub-task
the pipeline always runs Tier 4: `purgeLlamaSlot()` for local slots,
`freshOllamaThread()` (drop the conversation) for the rest.

---

## WebSocket API (summary)

Server → client: `SERVER_STATE_UPDATE` (1000 ms), `COMMAND_EXEC_OK`,
`COMMAND_EXEC_ERROR`, `TERMINAL_DATA`.

Client → server: `PRUNE_SURF_REQUEST`, `FOCUS_SURF_REQUEST`,
`RESOLVE_CONFLICT_REQUEST`, `TERMINAL_SUBSCRIBE`, `RESET_SENTINEL_REQUEST`.

Full types: [`src/shared/types.ts`](./src/shared/types.ts).

---

## Notes & limitations

- `PRUNE_SURF_REQUEST` sends the signal to the surface's **direct** PID. Killing
  a whole process tree (npm → node → …) is left as an integration choice.
- Terminal streaming polls cmux's `buffer_tail` every 250 ms and emits the
  appended suffix; if cmux gains a push channel, swap it into `TerminalStreamer`.
- `SurfaceState` heuristics (`dedup-engine.ts`) are pure and unit-testable.
