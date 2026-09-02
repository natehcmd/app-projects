#!/usr/bin/env python3
"""
Multi-agent Claude workflow with cost-based model routing.

The reel this was built from was vague hype ("60 agents", "number one
framework on GitHub", comment-for-link engagement bait) with zero real
technique disclosed. This is a small, honest, standalone implementation of
the two concrete ideas actually named in the caption:

  1. Several specialized agents (planner, coder, tester, security reviewer)
     collaborate on one task, running in parallel where their work doesn't
     depend on each other, and sharing a common memory of what's been
     produced so far.

  2. "Cost routing": each agent call is routed to a cheaper or more capable
     Claude model based on how complex its specific sub-task looks, instead
     of paying frontier-model prices for every step.

This is NOT the reel's actual (undisclosed) tool -- it's a clean,
from-scratch implementation of what the caption describes, so you can run
something real instead of commenting "FLOW" for a link.

Usage:
    python orchestrator.py "Build a rate limiter for a Flask API"
    python orchestrator.py "Build a rate limiter for a Flask API" --force-model claude-opus-4-8
    python orchestrator.py "..." --out ./runs/rate-limiter

Requires ANTHROPIC_API_KEY in the environment (see README.md).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:  # pragma: no cover
    print("Missing dependency: run `pip install -r requirements.txt` first.", file=sys.stderr)
    raise

# ---------------------------------------------------------------------------
# Model tiers and (approximate) per-million-token pricing, used only to
# print an estimated cost / estimated savings summary at the end of a run.
# Update these if Anthropic's pricing changes -- they are not fetched live.
# ---------------------------------------------------------------------------

CHEAP_MODEL = "claude-haiku-4-5-20251001"
STANDARD_MODEL = "claude-sonnet-5"
CAPABLE_MODEL = "claude-opus-4-8"

PRICING_PER_MTOK = {
    # model: (input $/MTok, output $/MTok)
    CHEAP_MODEL: (1.00, 5.00),
    STANDARD_MODEL: (3.00, 15.00),
    CAPABLE_MODEL: (5.00, 25.00),
}

COMPLEX_KEYWORDS = (
    "architecture", "security", "concurrency", "distributed", "algorithm",
    "optimi", "vulnerab", "race condition", "performance", "scal",
    "cryptograph", "consensus", "migration", "auth", "encrypt",
)


def route_model(role: str, task_text: str, force_model: Optional[str] = None) -> str:
    """Pick a model for this agent call.

    This is the "cost routing" piece described in the reel: cheap/mechanical
    work goes to a cheap model automatically, and anything that looks
    structurally hard -- by role (planning, security review) or by keyword
    match over the task description -- goes to a more capable model.

    This is a simple, transparent heuristic, not a learned router. Swap it
    out for something smarter (e.g. a cheap classification call, or your
    own routing rules) if you need better accuracy.
    """
    if force_model:
        return force_model

    text = task_text.lower()
    word_count = len(text.split())
    looks_complex = any(k in text for k in COMPLEX_KEYWORDS)

    if role == "security":
        # Security review is the one place a false "looks simple" is most
        # costly, so it only ever drops to the standard tier, never cheap.
        return CAPABLE_MODEL if (looks_complex or word_count > 40) else STANDARD_MODEL
    if role in ("plan", "code", "review"):
        return CAPABLE_MODEL if looks_complex else STANDARD_MODEL
    if role == "test":
        return CHEAP_MODEL if not looks_complex and word_count < 60 else STANDARD_MODEL
    return STANDARD_MODEL


# ---------------------------------------------------------------------------
# Agent roles
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS = {
    "plan": (
        "You are the planning agent in a small multi-agent engineering team. "
        "Given a feature request, produce a short, concrete implementation plan: "
        "the approach, the files/functions involved, and any edge cases to handle. "
        "Do not write full code -- that is a different agent's job. Be concise."
    ),
    "code": (
        "You are the coding agent in a small multi-agent engineering team. "
        "You are given a feature request and an implementation plan written by the "
        "planning agent. Write the actual implementation. Output only code, in a "
        "single fenced code block, with brief inline comments where non-obvious. "
        "Follow the plan unless it is clearly wrong, in which case note the deviation "
        "in a one-line comment above the code block."
    ),
    "test": (
        "You are the testing agent in a small multi-agent engineering team. "
        "You are given a feature request, a plan, and an implementation written by "
        "another agent. Write a focused test suite for the implementation, covering "
        "the normal case and the edge cases named in the plan. Output only code, in a "
        "single fenced code block."
    ),
    "security": (
        "You are the security review agent in a small multi-agent engineering team. "
        "You are given a feature request, a plan, and an implementation written by "
        "another agent. Review the implementation for security issues: injection, "
        "unsafe deserialization, missing auth/validation, resource exhaustion, secrets "
        "handling, etc. If you find nothing implementation-specific, say so plainly -- "
        "do not invent issues. Output a short bulleted list, worst issue first."
    ),
}


@dataclass
class AgentResult:
    role: str
    model: str
    text: str
    input_tokens: int
    output_tokens: int
    seconds: float


@dataclass
class SharedMemory:
    """The 'shared memory across the whole system' from the reel caption,
    implemented honestly: a plain dict that later agents read from and
    earlier agents write to. No magic -- just passing context explicitly.
    """
    task: str
    entries: dict = field(default_factory=dict)

    def context_for(self, role: str) -> str:
        """Build the shared context block a given role should see."""
        parts = [f"Feature request:\n{self.task}\n"]
        if role != "plan" and "plan" in self.entries:
            parts.append(f"Plan (from planning agent):\n{self.entries['plan']}\n")
        if role in ("test", "security") and "code" in self.entries:
            parts.append(f"Implementation (from coding agent):\n{self.entries['code']}\n")
        return "\n".join(parts)

    def record(self, role: str, text: str) -> None:
        self.entries[role] = text


async def run_agent(
    client: "anthropic.AsyncAnthropic",
    role: str,
    memory: SharedMemory,
    force_model: Optional[str],
) -> AgentResult:
    model = route_model(role, memory.task, force_model)
    user_content = memory.context_for(role)
    started = time.monotonic()

    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPTS[role],
        messages=[{"role": "user", "content": user_content}],
    )
    elapsed = time.monotonic() - started

    text = "".join(block.text for block in response.content if block.type == "text")
    return AgentResult(
        role=role,
        model=model,
        text=text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        seconds=elapsed,
    )


def estimate_cost(results: list[AgentResult]) -> float:
    total = 0.0
    for r in results:
        in_price, out_price = PRICING_PER_MTOK.get(r.model, PRICING_PER_MTOK[STANDARD_MODEL])
        total += r.input_tokens / 1_000_000 * in_price
        total += r.output_tokens / 1_000_000 * out_price
    return total


def estimate_cost_if_all_capable(results: list[AgentResult]) -> float:
    in_price, out_price = PRICING_PER_MTOK[CAPABLE_MODEL]
    total = 0.0
    for r in results:
        total += r.input_tokens / 1_000_000 * in_price
        total += r.output_tokens / 1_000_000 * out_price
    return total


# ---------------------------------------------------------------------------
# Orchestration: plan first, then code, then test + security in parallel.
# This mirrors the reel's description (agents work in parallel and share
# memory) while respecting the real dependency graph -- you can't write
# tests or a security review for code that doesn't exist yet.
# ---------------------------------------------------------------------------

async def run_workflow(task: str, force_model: Optional[str], out_dir: Path) -> None:
    client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
    memory = SharedMemory(task=task)
    results: list[AgentResult] = []

    print(f"\n=== Planning ===")
    plan = await run_agent(client, "plan", memory, force_model)
    memory.record("plan", plan.text)
    results.append(plan)
    print(f"[plan] model={plan.model} in={plan.input_tokens} out={plan.output_tokens} "
          f"time={plan.seconds:.1f}s")

    print(f"\n=== Coding ===")
    code = await run_agent(client, "code", memory, force_model)
    memory.record("code", code.text)
    results.append(code)
    print(f"[code] model={code.model} in={code.input_tokens} out={code.output_tokens} "
          f"time={code.seconds:.1f}s")

    print(f"\n=== Testing + Security review (parallel) ===")
    test_task = run_agent(client, "test", memory, force_model)
    security_task = run_agent(client, "security", memory, force_model)
    test_result, security_result = await asyncio.gather(test_task, security_task)
    memory.record("test", test_result.text)
    memory.record("security", security_result.text)
    results.extend([test_result, security_result])
    print(f"[test]     model={test_result.model} in={test_result.input_tokens} "
          f"out={test_result.output_tokens} time={test_result.seconds:.1f}s")
    print(f"[security] model={security_result.model} in={security_result.input_tokens} "
          f"out={security_result.output_tokens} time={security_result.seconds:.1f}s")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "plan.md").write_text(plan.text)
    (out_dir / "implementation.md").write_text(code.text)
    (out_dir / "tests.md").write_text(test_result.text)
    (out_dir / "security_review.md").write_text(security_result.text)
    (out_dir / "run_summary.json").write_text(json.dumps({
        "task": task,
        "agents": [
            {
                "role": r.role,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "seconds": round(r.seconds, 2),
            }
            for r in results
        ],
        "estimated_cost_usd": round(estimate_cost(results), 4),
        "estimated_cost_usd_if_all_capable_model": round(estimate_cost_if_all_capable(results), 4),
    }, indent=2))

    total_cost = estimate_cost(results)
    capable_cost = estimate_cost_if_all_capable(results)
    savings_pct = (1 - total_cost / capable_cost) * 100 if capable_cost > 0 else 0.0

    print(f"\n=== Done ===")
    print(f"Output written to: {out_dir}/")
    print(f"Estimated cost:            ${total_cost:.4f}")
    print(f"Estimated cost (all-{CAPABLE_MODEL}): ${capable_cost:.4f}")
    print(f"Estimated savings from cost routing: {savings_pct:.0f}%")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("task", help="Feature request / task description for the agent team")
    parser.add_argument(
        "--force-model",
        default=None,
        help="Skip cost routing and use this exact model for every agent "
             "(e.g. claude-opus-4-8). Useful for comparing quality vs. the routed run.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory (default: ./runs/<timestamp>)",
    )
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else Path("runs") / time.strftime("%Y%m%d-%H%M%S")

    try:
        asyncio.run(run_workflow(args.task, args.force_model, out_dir))
    except anthropic.AuthenticationError:
        print(
            "\nAuthentication failed. Set ANTHROPIC_API_KEY in your environment "
            "(see README.md) and try again.",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
