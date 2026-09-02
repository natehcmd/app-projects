#!/usr/bin/env python3
"""
demo.py — run a batch of mixed simple/complex tasks through the CostRouter
and print a summary, so you can see cost routing working end-to-end without
having to type prompts one at a time.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python demo.py
"""

import os
import sys

from router import CostRouter

SAMPLE_TASKS = [
    "What is the capital of France?",
    "Rewrite this sentence to be more formal: 'hey can u send me the file asap'",
    "Design a rate-limiting algorithm for a distributed API gateway that handles "
    "10k requests/sec across 5 regions, and explain the tradeoffs of your approach.",
    "Convert 12 miles to kilometers.",
    "Write a Python function that finds the longest palindromic substring in a "
    "string, and explain its time complexity.",
]


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set. Get a key from https://console.anthropic.com/ "
            "and run:\n  export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)

    router = CostRouter()
    for i, task in enumerate(SAMPLE_TASKS, 1):
        print(f"\n=== Task {i} ===")
        print(f"Prompt: {task}")
        result = router.route(task)
        print(f"-> routed to {result['tier']} tier ({result['model']})")
        print(f"-> answer: {result['answer'][:200]}")

    print("\n" + "=" * 40)
    print(router.stats.summary())


if __name__ == "__main__":
    main()
