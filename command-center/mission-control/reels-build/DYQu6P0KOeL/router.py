#!/usr/bin/env python3
"""
cost_router.py — route tasks to the cheapest Claude model that can handle them.

The reel this was built from ("60-agent Claude workflow with cost routing")
was mostly engagement bait with no real architecture disclosed — no repo,
no code, no config, just "comment FLOW for the link." The one concrete,
buildable idea in it was the "cost routing" concept: send basic tasks to a
cheap/fast model and only escalate to a bigger model when the task actually
needs it. That's a real, well-known pattern (also called "model cascading"
or "LLM routing"), so this script implements a small, honest version of it
using the real Anthropic API — no 60 fake agents, no unverifiable claims.

How it works
------------
1. A cheap, fast model (Haiku) looks at the incoming task and scores it
   "simple" or "complex" in a single short classification call.
2. Simple tasks are answered by Haiku directly.
3. Complex tasks are escalated to a stronger model (Sonnet by default,
   configurable) to actually do the work.
4. The script prints which model handled the request and tracks a running
   tally of how many requests were routed to each tier, so you can see the
   cost savings for yourself instead of taking a reel's word for it.

This is a single-process, single-file router you can call from the CLI or
import as a library. It is NOT a multi-agent framework — there's no shared
memory bus, no planner/coder/tester/security-checker swarm here, because
the source material never actually described how those pieces work. If you
want that, this router is a reasonable starting building block: point
different "agent" scripts at `route()` instead of hardcoding one model.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

try:
    import anthropic
except ImportError:
    print(
        "Missing dependency. Install it with:\n  pip install anthropic",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Model tiers. Swap these for whatever's current/cheapest when you run this —
# model names and pricing change over time, so don't treat these as gospel.
# ---------------------------------------------------------------------------
CHEAP_MODEL = os.environ.get("ROUTER_CHEAP_MODEL", "claude-haiku-4-5-20251001")
STRONG_MODEL = os.environ.get("ROUTER_STRONG_MODEL", "claude-sonnet-5")

CLASSIFY_PROMPT = """You are a routing classifier. Read the task below and decide \
if it is SIMPLE (a short factual question, basic formatting, a one-line \
lookup, simple rewrite) or COMPLEX (requires multi-step reasoning, writing \
non-trivial code, analysis, planning, or anything where a wrong answer would \
be costly).

Respond with exactly one word: SIMPLE or COMPLEX.

Task:
\"\"\"
{task}
\"\"\""""


@dataclass
class RouterStats:
    simple_count: int = 0
    complex_count: int = 0
    history: list = field(default_factory=list)

    def record(self, task: str, tier: str, model: str):
        if tier == "simple":
            self.simple_count += 1
        else:
            self.complex_count += 1
        self.history.append({"task": task, "tier": tier, "model": model})

    def summary(self) -> str:
        total = self.simple_count + self.complex_count
        if total == 0:
            return "No requests routed yet."
        pct_cheap = 100 * self.simple_count / total
        return (
            f"{total} requests routed — {self.simple_count} simple "
            f"({pct_cheap:.0f}%) on {CHEAP_MODEL}, {self.complex_count} complex "
            f"on {STRONG_MODEL}."
        )


class CostRouter:
    """Routes a task to CHEAP_MODEL or STRONG_MODEL based on a cheap classification pass."""

    def __init__(self, client: Optional["anthropic.Anthropic"] = None):
        self.client = client or anthropic.Anthropic()
        self.stats = RouterStats()

    def classify(self, task: str) -> str:
        """Return 'simple' or 'complex' using a fast, cheap model call."""
        resp = self.client.messages.create(
            model=CHEAP_MODEL,
            max_tokens=5,
            messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(task=task)}],
        )
        verdict = resp.content[0].text.strip().upper()
        return "complex" if "COMPLEX" in verdict else "simple"

    def route(self, task: str, force_tier: Optional[str] = None) -> dict:
        """Classify the task (unless a tier is forced) and run it on the right model."""
        tier = force_tier or self.classify(task)
        model = STRONG_MODEL if tier == "complex" else CHEAP_MODEL

        resp = self.client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": task}],
        )
        answer = resp.content[0].text

        self.stats.record(task, tier, model)
        return {"tier": tier, "model": model, "answer": answer}


def main():
    parser = argparse.ArgumentParser(
        description="Route a task to a cheap or strong Claude model based on complexity."
    )
    parser.add_argument("task", nargs="?", help="The task/prompt to run. Omit to read from stdin.")
    parser.add_argument(
        "--force",
        choices=["simple", "complex"],
        help="Skip classification and force a tier (useful for testing/cost comparisons).",
    )
    parser.add_argument("--json", action="store_true", help="Print result as JSON.")
    args = parser.parse_args()

    task = args.task or sys.stdin.read().strip()
    if not task:
        parser.error("No task provided (pass as an argument or pipe via stdin).")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set. Get a key from https://console.anthropic.com/ "
            "and run:\n  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)

    router = CostRouter()
    result = router.route(task, force_tier=args.force)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[routed to {result['tier']} tier -> {result['model']}]\n")
        print(result["answer"])
        print(f"\n---\n{router.stats.summary()}")


if __name__ == "__main__":
    main()
