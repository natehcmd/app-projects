#!/usr/bin/env python3
"""Vibe-coding prompt library — 3 real prompts extracted from on-screen text
in reel DZsq1Ervqk7 (@kevinfremon), verified by reading the actual video
frames (the cached caption only linked to hellotrillion.ai/prompts, not the
prompt text itself).

Usage:
    python3 prompts.py           # list all prompts
    python3 prompts.py 2         # print prompt 2 only, ready to copy/paste
"""
import argparse
import sys

PROMPTS = {
    1: {
        "name": "Confidence-gated planning",
        "text": ("...please do not create a plan until you have over 96% confidence "
                  "you know what to plan for. Ask me follow up questions until you "
                  "reach that confidence level."),
    },
    2: {
        "name": "Risk-ranked plan review",
        "text": ("Please review your plan and identify the areas that introduce the "
                  "most amount of product risk and list them out from the most to "
                  "least risky. Then add to your plan to reduce the implementation "
                  "risk for each item."),
    },
    3: {
        "name": "Senior-engineer self code review",
        "text": ("I want you to act as a senior engineer and do a thorough code "
                  "review of your work and identify all errors, inconsistent logic, "
                  "inefficiencies, and anything that can create bugs. Prioritize "
                  "your findings in list of the most critical to least critical "
                  "before you fix them."),
    },
}


def main():
    parser = argparse.ArgumentParser(description="Vibe-coding prompt library")
    parser.add_argument("number", nargs="?", type=int, choices=[1, 2, 3],
                         help="print just this prompt's text (for copy/paste)")
    args = parser.parse_args()

    if args.number:
        print(PROMPTS[args.number]["text"])
        return

    for n, p in PROMPTS.items():
        print(f"[{n}] {p['name']}\n    {p['text']}\n")


if __name__ == "__main__":
    sys.exit(main())
