# cost-router

A small, honest implementation of the one real idea buried in this reel.

## About the source reel

The reel (`@kayvon.ai`, shortcode `DYQu6P0KOeL`) claims someone built a
"Claude workflow with 60 agents working together at the same time" —
a planner, a coder, a tester, a security checker, all running in parallel
with shared memory, plus "cost routing" that sends basic tasks to a free
tier and advanced tasks to a bigger model — and that it's "ranked #1 for
agent frameworks on GitHub." None of that is backed up with a repo, code,
config, architecture diagram, or even a tool name in the actual post. The
entire "value" of the reel is gated behind commenting "FLOW" and following
the account to get a DM with a link — classic engagement bait, not a
technique disclosure.

There's nothing concrete to reproduce about the "60 agents" or "shared
memory" claims — no numbers, no architecture, no code. But **cost routing**
(send cheap/simple requests to a fast, inexpensive model; escalate only
when a task actually needs a stronger model) is a real, well-documented
pattern in production LLM systems, sometimes called model cascading or
LLM routing. That part is buildable and useful on its own, so that's what
this tool implements — a minimal, working version, not a recreation of the
reel's unverifiable claims.

## What it does

`router.py` defines a `CostRouter` that:

1. Uses a cheap, fast model (Haiku, by default) to classify an incoming
   task as `SIMPLE` or `COMPLEX` with a single short classification call.
2. Routes `SIMPLE` tasks to the cheap model and `COMPLEX` tasks to a
   stronger model (Sonnet, by default) to actually do the work.
3. Tracks how many requests went to each tier so you can see the
   cost-routing behavior for yourself, rather than taking a reel's word
   for it.

It's a single Python file, no framework, no external services beyond the
Anthropic API. You can run it from the CLI, pipe text into it, or import
`CostRouter` into your own code to route calls from multiple scripts/agents
through one place instead of hardcoding a model everywhere.

## Setup

```bash
cd reels-build/DYQu6P0KOeL
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # from https://console.anthropic.com/
```

## Running it

Single task from the command line:

```bash
python router.py "What is the capital of France?"
```

Pipe a task in via stdin:

```bash
echo "Design a caching layer for a high-traffic API and explain the tradeoffs" | python router.py
```

Force a tier (useful for testing/comparing cost without relying on the
classifier):

```bash
python router.py --force complex "2+2?"
```

Get JSON output (for scripting):

```bash
python router.py --json "Summarize this in one sentence: ..."
```

Run the batch demo (5 mixed simple/complex sample tasks, prints a routing
summary at the end):

```bash
python demo.py
```

## Configuration

Override the models used for each tier with environment variables (model
names/pricing change over time — check the current lineup at
https://docs.claude.com/en/docs/about-claude/models before relying on
these defaults):

```bash
export ROUTER_CHEAP_MODEL=claude-haiku-4-5
export ROUTER_STRONG_MODEL=claude-sonnet-4-5
```

## Notes / limitations

- This is intentionally small — one classification call, one execution
  call, two model tiers. It is not a multi-agent orchestration framework
  with planner/coder/tester/security-checker roles or shared memory, because
  the reel never actually described how any of that works.
- The classification step itself costs a small amount (a few tokens on the
  cheap model), so cost routing pays off on workloads with a meaningful mix
  of simple and complex tasks — not on every single call.
- No bot evasion, scraping, or credential harvesting is involved anywhere
  in this tool — it only calls the official Anthropic API with your own key.
