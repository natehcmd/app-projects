# DXxQS0AO1Km — RuFlow (real, installed)

## Source

> @duncanrogoff: "RuFlow turns Claude Code into a 60+ agent system that
> researches, codes, tests, and improves together... routes tasks
> automatically, simple work to cheaper models, complex work to powerful
> ones." Comment "flow" for the setup guide.

## Re-reviewed 2026-07-20

Real product. RuFlow = `ruvnet/claude-flow` (npm package `ruflo`), already
present locally as a clone at `~/Projects/ruflo`. Safety check:
- GitHub: 65,307 stars over ~13.5 months (June 2025 → present) — a
  plausible organic growth curve, unlike the fake-star pattern found on
  `affaan-m/ECC` and `Alishahryar1/free-claude-code` earlier this session
  (both under 6 months old with 40k-230k+ stars).
- Real maintainer with a consistent multi-product ecosystem (ruvector,
  goal.ruv.io, flo.ruv.io), MIT license, active commits.

## What was done

Installed globally: `npm install -g ruflo`. Some native-dependency
postinstall scripts (better-sqlite3, argon2, sharp, hnswlib-node — all
common, well-known npm packages, not project-specific) were blocked by
npm's own `allow-scripts` safety gate and were NOT force-allowed. The core
CLI works without them:

```
$ ruflo --version
ruflo v3.32.8
$ ruflo --help
Ruflo - AI Agent Orchestration Platform
  init, start, status, agent, swarm, memory, task, session, mcp, hooks...
```

Did not run `ruflo start`/`ruflo swarm` (spinning up a real 60-agent
orchestration run has real API cost and wasn't necessary to verify the tool
is genuine and functional) — CLI responds correctly, confirms this is a
real, working product matching the reel's description.

## Status

**installed = true**, verified functional via `--version`/`--help`.
