# Multi-agent Claude workflow with cost-based model routing

## About the source reel

The reel this came from ([`DY_SoPGKv2A`](../../)) is comment-for-link
engagement bait: "comment FLOW and I'll DM you the link" to some external,
unnamed "60-agent Claude workflow" that's supposedly "#1 for agent
frameworks on GitHub." No actual architecture, config, code, or technique is
described in the caption — just the vague claims that (a) many agents run
in parallel and share memory, and (b) it does "cost routing" between a free
tier and a more capable model.

There's nothing to reverse-engineer or extract from that — the entire value
of the reel is gated behind a DM. So instead of building "the reel's tool"
(which doesn't exist here as a spec), this is a small, honest, from-scratch
implementation of the two concrete ideas the caption actually names:
multiple specialized agents collaborating with shared context, and routing
each agent call to a cheaper or more capable model based on task
complexity. Nothing here evades any platform's terms, harvests anything, or
touches bot/fraud detection — it's just a CLI script that calls the
Anthropic API a few times.

## What it does

`orchestrator.py` takes a single feature request (e.g. "Build a rate
limiter for a Flask API") and runs it through four small agents:

1. **Planner** — writes a short implementation plan.
2. **Coder** — implements the plan.
3. **Tester** and **Security reviewer** — run *in parallel* against the
   planner's and coder's output (both share the same "memory," which is
   just the plan + code text passed into their prompts).

Each agent call is independently routed to one of three Claude models —
`claude-haiku-4-5` (cheap), `claude-sonnet-5` (standard), or
`claude-opus-4-8` (most capable) — based on a simple heuristic: the agent's
role (e.g. security review never drops to the cheap tier) and whether the
task description contains complexity-signaling keywords (security,
concurrency, distributed, performance, etc.). This is the "cost routing"
piece from the caption, implemented transparently instead of as a black
box — see `route_model()` in `orchestrator.py` if you want to tune it.

At the end of a run it prints (and saves) the token usage and an estimated
dollar cost for the run, plus what the same run would have cost if every
agent had used the most capable model, so you can see what routing bought
you.

This is a toy/demo scale of "multi-agent" (4 agents, one dependency chain),
not literally 60 parallel agents — that number in the reel is unverifiable
marketing copy, not a spec. The pattern (plan → parallel fan-out → shared
context → routed models) is the same one you'd scale up.

## Setup

```bash
cd reels-build/DY_SoPGKv2A
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # get one at https://console.anthropic.com/
```

No other setup, accounts, or "free tier" signup is required — cost routing
here means "route to a cheaper Anthropic model," not "route to a separate
free service." You need a paid Anthropic API key; there's no way to run
this for literally $0.

## Running it

```bash
python orchestrator.py "Build a rate limiter for a Flask API"
```

Output (plan, implementation, tests, security review, and a JSON run
summary with token/cost stats) is written to `runs/<timestamp>/` by
default. Override with `--out`:

```bash
python orchestrator.py "Build a rate limiter for a Flask API" --out ./runs/rate-limiter
```

To compare against *not* routing (i.e. force every agent onto the most
capable model, as a quality/cost baseline):

```bash
python orchestrator.py "Build a rate limiter for a Flask API" --force-model claude-opus-4-8
```

## Notes / limitations

- The model-routing heuristic is intentionally simple (keyword + role
  based). It's meant to be transparent and easy to tune, not a learned
  classifier. Swap in your own logic in `route_model()` if you want
  something smarter (e.g. a cheap Haiku call that scores task complexity
  before routing the real call).
- The "shared memory" is literally just a Python dict (`SharedMemory` in
  `orchestrator.py`) whose contents get concatenated into later agents'
  prompts. There's no vector store, no persistence between runs, and no
  cross-process coordination — it's the simplest thing that actually
  satisfies "agents share context," nothing more.
- Pricing in `PRICING_PER_MTOK` is a snapshot for the cost estimate printed
  at the end of a run; check
  [platform.claude.com/docs/en/pricing](https://platform.claude.com/docs/en/pricing)
  if you need current numbers.
