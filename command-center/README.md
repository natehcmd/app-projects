# Command Center

One project, two pieces, working together:

| | |
|---|---|
| **`hands-ai-mac/`** | Native SwiftUI macOS app + iOS remote client. Headless by design — no floating panel, no voice, no orb locally. It runs the actual agent engine (backends, tools, profiles, skills) and a WebSocket Remote server, plus a menu bar icon that starts/opens the dashboard below. |
| **`mission-control/`** | The dashboard — FastAPI + vanilla JS, `http://localhost:8450`. 15 tabs (Chat, Hands AI, Home, Reels, Life HQ, Briefs, Term, Swarm, Flows, Tools, Reel Tools, Learn, Compare, Workflows, FileGraph, Control). This is where all real conversation with Hands AI actually happens — its "Hands AI" tab is a plain browser WebSocket client to the Mac app's Remote server. |

Different tech stacks for good reasons (native macOS/iOS tooling vs. a
browser-based dashboard you can also reach from your phone) — they're one
project because the Mac app's whole job is to run the agent engine that
Command Center's UI drives, not because the code is merged.

## Launching it

Open **Hands AI.app** (or run it from Xcode) — the menu bar icon's **"Open
Command Center"** starts `mission-control`'s server if it isn't already
running and opens `http://localhost:8450` in your browser. That's the one
click that gets you the whole system.

## Where things are documented

See the `command-center` Claude Code skill
(`~/.claude/skills/command-center/SKILL.md`) for the full architecture, known
gotchas (model names, engine capabilities, the Plaid integration, why Gusto
isn't pursued), and conventions for adding a new dashboard tab.
