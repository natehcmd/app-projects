# server.py route inventory → Swift port contract

53 routes. `M` = method. `iOS` = can this run on iOS (n = needs subprocess/macOS
shell). Line numbers are into `command-center/mission-control/server.py` @ 2026-09-02.
Before porting a route: `curl -s localhost:8450<path> > fixtures/<name>.json` and
diff the Swift output against it.

## Helper modules to port first
| Python | → Swift | Notes |
|---|---|---|
| `db()` / `init_db()` / `seed_reels()` | `Database.swift` (GRDB) | 11 tables (reels, goals, subscriptions, networth, checkins, flows, activity, plaid_items, accounts, budgets, txns). WAL, 30s busy timeout. macOS: open existing `data/mission.db`. **Never re-seed** personal tables. |
| `ollama_gen()` / `ollama_loaded()` | `Ollama.swift` | `URLSession` → `localhost:11434` `/api/generate`, `/api/tags`, `/api/ps`. |
| `sh(cmd)` | `Shell.swift` (`#if os(macOS)`) | `Process`, 15s timeout, returns stdout. |
| `log_activity()` | `Database.logActivity()` | best-effort insert, never throws. |
| `apps_scanner.py` (369 ln) | `AppsScanner.swift` | walks `~/Projects`, `~/Applications`, `~/.claude/skills`; categorises. macOS only (returns cached on iOS). |
| `projects_tracker.py` (173 ln) | `ProjectsTracker.swift` | `git` shell-out per repo under `~/Projects`; cross-refs running sessions. macOS only. |

---

## Stage A — pure reads (12) · all iOS-safe except where noted
| M | Path | L | Does | Source | iOS |
|---|---|---|---|---|---|
| GET | /api/status | 146 | ollama models, skills list, cron, latest brief, hardcoded links | Ollama + `~/.claude/skills` + `crontab -l` | y (cron empty) |
| GET | /api/vitals | 164 | cpu load / mem / disk / uptime | `getloadavg`+`vm_stat`+`sysctl`+`shutil` → `host_statistics64`/`sysctlbyname` | y (diff API) |
| GET | /api/activity?limit | 195 | last N activity rows | SQLite `activity` | y |
| GET | /api/search?q | 214 | cross-tab search (reels, goals, flows, briefs…) | SQLite + files | y |
| GET | /api/tools | 714 | static tool registry | in-code list | y |
| GET | /api/compare | 720 | comparison log | SQLite / `data/compare.json` | y |
| GET | /api/apps | 783 | every built app/skill/site | `AppsScanner` | n → cache |
| GET | /api/projects | 834 | git state of `~/Projects` repos | `ProjectsTracker` | n → cache |
| GET | /api/agentdrop/library | 284 | reels library | `~/AgentDrop-Workspace` fs | n → cache |
| GET | /api/agentdrop/synced | 299 | which reels pushed to NotebookLM | `.nblm-pushed-*.json` | n → cache |
| GET | /api/agentdrop | 313 | combined agentdrop view | fs | n → cache |
| GET | /api/learn/history | 900 | past Learn plans | SQLite / files | y |
| GET | /api/flows | 1438 | saved flows | SQLite `flows` | y |
| GET | /api/briefs | 668 | list generated briefs | `data/briefs/*.md` | y (synced dir) |
| GET | /api/term/options | 911 | engine → model lists | Ollama tags + static | y |
| GET | /api/term/jobs | 1166 | running job list | `JobRunner` registry | n |

## Stage B — SQLite writes (10) · iOS-safe
| M | Path | L | Does |
|---|---|---|---|
| POST | /api/activity/log | 203 | append activity row (`kind` required, 400 if missing) |
| GET  | /api/reels | 349 | list reels |
| POST | /api/reels/add | 354 | insert reel |
| POST | /api/reels/update | 366 | update topic/verdict/notes |
| GET  | /api/lifehq | 379 | bundle: goals+subs+networth+checkins+budgets+txns |
| POST | /api/lifehq/txn_import | 425 | CSV → `txns` |
| POST | /api/lifehq/{table} | 471 | generic upsert; allow-list {goals,subscriptions,networth,checkins,budgets} |
| POST | /api/compare/add | 727 | insert comparison |
| POST | /api/flows | 1448 | create/update flow (steps JSON) |
| POST | /api/flows/{fid}/delete | 1459 | delete flow |

## Stage C — external HTTP (8)
| M | Path | L | Does | iOS |
|---|---|---|---|---|
| GET  | /api/plaid/status | 553 | are Plaid creds configured (never lies) | y |
| POST | /api/plaid/link-token | 562 | Plaid `/link/token/create` | y |
| POST | /api/plaid/exchange | 582 | `/item/public_token/exchange` → store token | y |
| GET  | /api/plaid/accounts | 601 | `/accounts/balance/get` across items | y |
| POST | /api/plaid/unlink | 633 | `/item/remove` + delete row | y |
| POST | /api/briefs/generate | 673 | Ollama → write `data/briefs/<date>.md` | y* |
| POST | /api/learn/plan | 858 | Ollama → curriculum + quiz JSON | y* |
| POST | /api/overseer | 650 | Ollama one-shot "overseer" prompt | y* |
\* needs Ollama reachable; disable gracefully if not.

## Stage D — subprocess (16) · **macOS only** (`#if os(macOS)`; iOS = disabled tab)
| M | Path | L | Does |
|---|---|---|---|
| POST | /api/term/run | 1116 | spawn engine/shell job, return `{id}` |
| GET  | /api/term/out/{jid}?off= | 1170 | incremental stdout (os.js polls this every 1s) |
| GET  | /api/term/snapshot | 1094 | running terminal/claude/codex sessions (`ps`, tmux) |
| POST | /api/term/stop | 1182 | kill job |
| POST | /api/swarm/run | 1276 | Critic→Router→Workers multi-engine run |
| GET  | /api/swarm/runs | 1297 | list swarm runs |
| GET  | /api/swarm/{rid} | 1303 | one run detail |
| POST | /api/flows/plan | 1346 | Ollama planner → step list |
| POST | /api/flows/{fid}/run | 1464 | execute a saved flow (Process per step) |
| GET  | /api/flows/runs | 1483 | list flow runs |
| GET  | /api/flows/run/{rid} | 1488 | one flow run |
| GET  | /api/pipeline | 812 | live Claude/agy/Codex/Ollama processes (`ps`) + ollama `/api/ps` |
| POST | /api/hardware/control | 1498 | `pmset` / `caffeinate` / display sleep |
| POST | /api/software/control | 1516 | `open -a` / `killall` an app |
| POST | /api/apps/open | 787 | reveal/open a scanned app |
| POST | /api/agentdrop/open | 334 | open a reel / workspace path |

## Stage misc — already partly native-facing
| M | Path | L | Does | Stage |
|---|---|---|---|---|
| GET | /api/hands/token | 113 | read `com.natehoward.handsai` defaults for the Remote token | A (macOS `defaults`; iOS returns unconfigured) |
| GET | /api/filegraph/relations | 1363 | currently proxies to file-graph :8437 | E (becomes native `FileGraphRoutes`) |

---

## Response-shape gotchas (from reading `static/os.js`)
- `/api/status` → `links` is an object `{label: url}` rendered as-is.
- `/api/vitals` → nested `{cpu:{load1,load5,load15,cores,pct}, mem:{used,total,pct}, disk:{used,total,pct}, uptime, ollama_loaded}`; `ollama_loaded` is `null` when Ollama is down (UI branches on `=== null`).
- `/api/activity` → bare JSON array, newest first, `{id,ts,kind,detail}`.
- `/api/term/out/{jid}` → `{text, off, status}`; `status` in `{"running","done",...}`; os.js loops on `status === "running"` and passes `off` back.
- `/api/projects` → array of `{name,branch,status_label,last_touched,remote,recent_commits:[{hash,message,when}],uncommitted:[{status,path}],unpushed_count,active_session?}`.
- `/api/pipeline` → `{processes:[{engine,args,pid,etime,cpu,mem}], ollama_loaded:[{name|model,size_vram,expires_at}] | null}`.
