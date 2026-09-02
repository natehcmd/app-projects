# Command Center → one native app (no Python)

**Goal (your call, 2026-09-02):** full native rewrite. Replace the Python/FastAPI
backend (`mission-control/server.py`) with Swift so there is **no `localhost:8450`
Python process** and no `.venv`. One `HandsAI.xcodeproj`, shared code, builds
macOS + iOS. Fold in **file-graph** and **agent-conductor**.

**Reality check:** `server.py` is 53 routes / ~1,540 lines, plus `apps_scanner.py`
(369) and `projects_tracker.py` (173). It touches 11 SQLite tables, the Plaid
REST API, Ollama over HTTP, and spawns CLI subprocesses (`claude` / `codex` /
`ollama` / arbitrary shell) with streamed output. This is a multi-week port, not
a one-session job. The plan below is built so **every stage ships a working app** —
you are never mid-rewrite with a broken dashboard.

---

## Target shape

Keep the existing project; add two targets, merge two.

```
HandsAI.xcodeproj  (rename product → "Command Center" once C is done)
├─ CommandCenterKit        NEW  — framework: models, SQLite (GRDB), the embedded
│                                  HTTP server, all business logic. Shared by every target.
├─ CommandCenter (macOS)   = today's CommandCenterApp + HandsAI menu-bar target, MERGED.
│                            WKWebView host for the existing web UI + menu bar + FlyingFox
│                            Remote server. Runs CommandCenterKit.Server in-process.
├─ CommandCenterMobile(iOS) = today's HandsAIMobile, EXPANDED. Runs the same
│                            CommandCenterKit.Server in-process; WKWebView loads it.
└─ (HandsAI target folded into CommandCenter — one app, one icon)
```

**Big decision — keep the web UI.** `static/os.js` is 83 KB of working tab code
that already talks to `/api/*`. Do **not** rewrite 15 tabs as SwiftUI. Serve
`static/` from an embedded Swift HTTP server and port only the ~53 `/api/*`
routes. The WKWebView loads `http://127.0.0.1:<port>/` where the server now runs
**inside the app process** (started in `applicationDidFinishLaunching` / iOS
`init`), not as a detached `uvicorn`.

- **HTTP layer:** FlyingFox (already a dependency of HandsAI for the Remote
  server — `swhitty/FlyingFox`, pure-Swift, async, works on iOS). One
  `HTTPHandler` per route group.
- **DB layer:** GRDB.swift (`groue/GRDB.swift`). Point it at the *same*
  `data/mission.db` on macOS so nothing is lost; on iOS it creates its own in
  the app container. Model the 11 tables as `Codable` `FetchableRecord`/
  `PersistableRecord` structs.
- **JSON parity:** the web UI depends on exact response shapes. For every ported
  route, capture the Python response (`curl localhost:8450/api/... > fixtures/`)
  and assert the Swift response matches (`ROUTE_CONTRACT.md` has the shapes).

**iOS constraint — say it out loud:** iOS **cannot spawn subprocesses**. Every
route in Stage D (term / swarm / flows-run / pipeline / hardware+software
control / *open) is **macOS-only**. On iOS those tabs render read-only or
disabled. This is inherent, not a shortcut.

---

## Strangler-fig: usable at every step

`CommandCenterKit.Server` has a **fallback proxy**: any route not yet ported is
forwarded to the old Python server if it's running.

```
request /api/foo → ported?  yes → Swift handler
                            no  → proxy → http://127.0.0.1:8450/api/foo
```

So Stage 1 can ship with 12 routes native and 41 proxied; the app already runs
without a browser. Each stage moves routes from "proxied" to "native". When the
list of proxied routes hits zero, delete the proxy, delete `mission-control/`'s
Python, uninstall the `com.natehoward.mission-control` LaunchAgent. Done.

---

## Stages (each independently shippable)

### Stage 0 — foundation (~1 session)
- Commit the current uncommitted `command-center/` migration first. Non-negotiable base.
- Add `CommandCenterKit` framework target to `project.yml`; add GRDB + wire
  FlyingFox into it.
- `Server.swift`: FlyingFox server, static-file route for `static/`, the
  fallback proxy, a `/api/health` native route.
- macOS `CommandCenter` target starts `Server` in-process on launch; WKWebView
  points at it. Verify every tab still works (all via proxy).
- **Ship:** identical behaviour, but the app owns the server lifecycle.

### Stage A — pure reads, no external deps (~12 routes, 1 session)
`/api/status` `/api/vitals` `/api/activity` `/api/search` `/api/tools`
`/api/compare` `/api/apps` `/api/projects` `/api/agentdrop/library`
`/api/agentdrop/synced` `/api/agentdrop` `/api/learn/history` `/api/flows`
`/api/briefs` `/api/term/options` `/api/term/jobs`
- Port `apps_scanner.py` + `projects_tracker.py` to Swift here (filesystem walk +
  `git` shell-out on macOS; on iOS these return empty/cached).
- `vitals`: replace `vm_stat`/`sysctl` shell-outs with `host_statistics64` +
  `sysctlbyname` (macOS) / `os_proc_available_memory` + `ProcessInfo` (iOS).
- SQLite reads via GRDB.

### Stage B — SQLite writes (~10 routes, 1 session)
`/api/activity/log` `/api/reels` `/api/reels/add` `/api/reels/update`
`/api/lifehq` `/api/lifehq/txn_import` `/api/lifehq/{table}` `/api/compare/add`
`/api/flows` (POST) `/api/flows/{fid}/delete`
- The dynamic `/api/lifehq/{table}` route (goals/subscriptions/networth/checkins/
  budgets) → one generic upsert keyed by an allow-list of table names.
- CSV import for `txn_import`.

### Stage C — external HTTP (~8 routes, 1–2 sessions)
`/api/plaid/status` `/api/plaid/link-token` `/api/plaid/exchange`
`/api/plaid/accounts` `/api/plaid/unlink` `/api/briefs/generate`
`/api/learn/plan` `/api/overseer`
- Plaid: no official Swift SDK — call the REST API directly with `URLSession`
  (5 endpoints: `/link/token/create`, `/item/public_token/exchange`,
  `/accounts/balance/get`, item remove). Credentials from `.env` today →
  Keychain in the native app.
- `briefs/generate` / `learn/plan` / `overseer`: `URLSession` POST to
  `http://localhost:11434/api/generate` (Ollama). Same on iOS if Ollama is
  reachable on the LAN, else disabled.

### Stage D — subprocess orchestration (~15 routes, MACOS ONLY, 2–3 sessions)
`/api/term/run` `/api/term/out/{jid}` `/api/term/snapshot` `/api/term/stop`
`/api/swarm/run` `/api/swarm/runs` `/api/swarm/{rid}` `/api/flows/plan`
`/api/flows/{fid}/run` `/api/flows/runs` `/api/flows/run/{rid}`
`/api/pipeline` `/api/hardware/control` `/api/software/control`
`/api/apps/open` `/api/agentdrop/open`
- `JobRunner` actor: `Foundation.Process` + `AsyncStream<Data>` for stdout;
  job registry with incremental `/out/{jid}?off=` polling (matches os.js's
  `poll()` loop exactly).
- Swarm/Flows = a `Process` per step, sequential, JSON persisted via GRDB.
- `hardware/control` / `software/control` → `osascript` / `pmset` / `open -a`.
- iOS build compiles these files out (`#if os(macOS)`); the tabs show a
  "macOS only" state.

### Stage E — fold in adjacent tools (2–4 sessions)
- **file-graph** (`~/Projects/app-projects/file-graph`, Python FastAPI + SQLite +
  Ollama embeddings, :8437): port its routes into `CommandCenterKit` as a
  `FileGraphRoutes` group with its own GRDB database. `/api/filegraph/relations`
  (already in server.py, currently proxies to :8437) becomes native. Retire the
  `com.natehoward.filegraph` LaunchAgent.
- **agent-conductor** (`~/Projects/app-projects/agent-conductor`, TS daemon +
  React UI, untracked): two-phase. Phase 1 — the macOS app supervises the
  existing `node` daemon as a managed subprocess and embeds its React UI in a
  tab (iframe/WKWebView). Phase 2 (optional) — port the daemon (Critic→Router→
  Workers loop) to a Swift actor in `CommandCenterKit`. Phase 1 is enough to
  call it "one app".

### Stage F — cut the cord
- All routes native → delete the proxy, delete `mission-control/*.py` +
  `requirements.txt` + `.venv`, `launchctl bootout` the three
  `com.natehoward.*` LaunchAgents (mission-control, filegraph; keep ollama or
  remove per the existing cleanup task).
- Rename: `project.yml` product name `HandsAI` → `Command Center`; single
  `.app`. Archive `mission-control/` and `file-graph/` source under `legacy/`.

---

## Risks / unknowns to settle before Stage 0

| Risk | Note |
|---|---|
| SPM resolution needs network | GRDB + FlyingFox fetch on first `xcodegen`/build. Fine on a dev machine; a sandboxed CI won't. |
| Uncommitted base | `command-center/` has ~264 uncommitted changes mid-migration. Commit before starting or the port sits on sand. |
| Response-shape drift | `os.js` parses fields positionally in places. Fixture-diff every route or tabs break silently. |
| iOS scope | Term / Swarm / Flows-run / Pipeline / Control tabs can't work on iOS. Product decision: hide vs. read-only. |
| Plaid on iOS | Link SDK is a separate iOS pod; balance-only view can use REST. |
| `data/mission.db` | Point macOS GRDB at the existing file so real data (Life HQ, net worth, check-ins — your actual tracker) is preserved. Never re-seed. |
| Menu-bar + WindowGroup in one target | Merging `HandsAI` (menu bar `MenuBarExtra`) and `CommandCenterApp` (`WindowGroup`) — one `App` with both scenes. Straightforward but test the agent Remote server still binds. |

## Effort estimate

Stage 0–B: ~3–4 focused sessions → a native app doing all read/write tabs, Plaid
and subprocess tabs still proxied.
Stage C–D: ~4–5 sessions → Python only needed for nothing; proxy can be deleted.
Stage E–F: ~3–5 sessions → file-graph + agent-conductor absorbed, LaunchAgents
gone, one renamed `.app`.

**Total: ~10–14 sessions.** Ship after every one.
