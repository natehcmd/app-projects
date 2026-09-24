# Command Center + Hammond backlog (from Nate, 2026-09-24)

Status: `[ ]` todo · `[~]` in progress · `[x]` done — **nothing moves to done until Nate checks it.**

## P0 — broken / blocking
_2026-09-24: old July copy in iCloud/Applications (no remote server) trashed; engine+model picker and link chip added to the chat window; CC→Hammond verified end to end (reply in 12s). Awaiting Nate's check._
- [~] **Hammond is the old build in places** — installed app must match `cc-v2`; one build, one install path.
- [~] **Can't choose the model in Hammond** — visible model picker (local / Claude / Claude Code / agy) in the chat window.
- [~] **Can't connect Hammond ↔ Mission Control** — must connect with zero setup, show connected state clearly.
- [~] **"Done" only when Nate moves it** — no item auto-marks done anywhere (projects, reels, to-dos, build queue).
- [~] **Views cut off when swiping** — every tab fills the window; full-screen / fill-window mode.
- [~] **Tab bar too small, scrolls** — bigger nav that fits all tabs without horizontal scroll (group or two rows / sidebar).

## P1 — app-wide
- [ ] **Theme switcher** — change the whole app theme anytime; each tab keeps its own accent within the theme.
- [ ] **Quick-note button, top-left, on every page** — voice or keyboard; notes saved where Claude/Hammond can read and act on them.
- [ ] **Plain English everywhere** — brief bullet points, no slop; explain what each tab is for in one line.

## P2 — per tab
- **Home** — Jarvis look: dials + graphs (system, agents, budget, reels, to-dos); merged **to-do list** incl. reels to review.
- **Apps / Tools** — each app card: **screenshot + logo**, says what it is (app / tool / skill); **Run opens the actual app**, not a terminal.
- **Projects** — pin-board: where each project lives, **what's missing to be perfect**, Nate's notes, status Nate controls.
- **Pipeline** — **roots diagram**: Nate at top → Claude → branches down (subagents, agy, Gemini, local); roots **light up live** when any AI works; more agents = more roots, uncluttered. agy reviews a screenshot of it and leaves notes.
- **AgentDrop + Reels (merge)** — each reel: thumbnail from the downloaded video, playable, link to Instagram, title = reel's name, what it's about; **Build** button + **progress** view; **Auto** mode walks one by one and waits for Nate's OK; reels to review land in the Home to-do list.
- **Life HQ** — pull from Siri/Reminders/Calendar (or ask Nate) and remember.
- **Learn** — more scholarly; random facts, coding terms, code snippets that show how to do things.
- **Briefs** — short bullet points, simple English.
- **Term** — unclear purpose → explain it or fold it into another tab.
- **Swarm vs Flows vs Workflows** — explain the difference or merge; improve.
- **Artifacts** — unclear + stale → explain or remove.
- **Tools** — more interactive; label what each is.
- **Reel Tools** — merge with Reels/AgentDrop.
- **Compare** — compare Claude modes, agents, local models, Gemini; also real devices (e.g. headphones) after research.
- **Workflows** — duplicate of others → merge.
- **File Graph** — show files + what's in them; pan/zoom by swiping; fill the window.
- **Control** — more controls.

## Method
Each item: build on `cc-v2` → smoke test (`tests/smoke_api.py`) → screenshot → Nate checks → only then `[x]`.
