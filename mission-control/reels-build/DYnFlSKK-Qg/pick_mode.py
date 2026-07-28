#!/usr/bin/env python3
"""
pick_mode.py — "Chat vs. Cowork vs. Code: Which Should You Use?"

A tiny, dependency-free decision tool that helps you pick which mode of an
AI assistant (Chat, Cowork/agentic-collaboration, or Code) fits a task.

Why this exists
----------------
The source reel for this build was just a bare title/caption with no
transcript or technique description: "Chat vs. Cowork vs. Code - Which
Should You Use?" There was nothing concrete to lift a "technique" from, but
the title itself names a real, useful comparison that AI assistants
(including Claude) commonly expose as three different working modes:

  * Chat   — a single back-and-forth conversation. Best for quick questions,
             brainstorming, explanations, drafting short text, or anything
             where you stay in the loop turn-by-turn.
  * Cowork — a longer-running, more autonomous collaboration session where
             the assistant can juggle multiple steps/files/tools toward a
             goal with you checking in periodically rather than every turn.
             Best for multi-step research, planning, or content projects
             that span more than one exchange.
  * Code   — a coding-focused mode/agent with access to a filesystem,
             shell, and dev tools. Best for anything that involves reading,
             writing, running, or debugging actual code/repos.

This script does NOT call any AI API or model. It's a small, self-contained
heuristic scorer: you answer a handful of yes/no questions (interactively,
or by passing flags), it tallies weighted scores per mode, and it prints a
recommendation with the reasoning. No network access, no API keys.

Usage
-----
Interactive mode (asks you questions):
    python3 pick_mode.py

Non-interactive / scriptable mode (answer flags directly, 'y' or 'n'):
    python3 pick_mode.py \
        --touches-code n \
        --multi-step y \
        --needs-files-or-shell n \
        --single-quick-question n \
        --long-running-project y \
        --wants-tool-use y

Run with --help to see all flags and short descriptions.

No setup or API keys required — pure standard library.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field


@dataclass
class Question:
    flag: str          # argparse dest name
    prompt: str         # shown to the user in interactive mode
    weights: dict       # points awarded to each mode if answered "yes"


QUESTIONS: list[Question] = [
    Question(
        "touches_code",
        "Does the task involve reading, writing, running, or debugging code/a repo?",
        {"code": 3},
    ),
    Question(
        "needs_files_or_shell",
        "Does it need direct access to files, a terminal, or dev tools to get done?",
        {"code": 2, "cowork": 1},
    ),
    Question(
        "single_quick_question",
        "Is this basically one question or a short back-and-forth you'll finish in a turn or two?",
        {"chat": 3},
    ),
    Question(
        "multi_step",
        "Does the task have several dependent steps (research, then draft, then revise, etc.)?",
        {"cowork": 2},
    ),
    Question(
        "long_running_project",
        "Will this span multiple sessions or a longer stretch of autonomous work before you check back in?",
        {"cowork": 3},
    ),
    Question(
        "wants_tool_use",
        "Do you want the assistant actively using tools (search, files, apps) rather than just talking?",
        {"cowork": 1, "code": 1},
    ),
    Question(
        "just_thinking_out_loud",
        "Are you mostly brainstorming, explaining, or thinking something through conversationally?",
        {"chat": 2},
    ),
]

MODE_INFO = {
    "chat": (
        "Chat",
        "Best for quick questions, explanations, brainstorming, and short "
        "back-and-forth exchanges where you stay in the loop every turn.",
    ),
    "cowork": (
        "Cowork",
        "Best for longer, multi-step collaborations — research, planning, "
        "or content projects — where the assistant works more autonomously "
        "and you check in periodically rather than every message.",
    ),
    "code": (
        "Code",
        "Best for anything touching an actual codebase: reading, writing, "
        "running, testing, or debugging code, or tasks needing a shell "
        "and filesystem access.",
    ),
}


def ask_yes_no(prompt: str) -> bool:
    while True:
        answer = input(f"{prompt} [y/n]: ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  Please answer y or n.")


def score(answers: dict[str, bool]) -> dict[str, int]:
    totals = {"chat": 0, "cowork": 0, "code": 0}
    for q in QUESTIONS:
        if answers.get(q.flag):
            for mode, points in q.weights.items():
                totals[mode] += points
    return totals


def recommend(totals: dict[str, int]) -> str:
    return max(totals, key=lambda m: totals[m])


def print_report(totals: dict[str, int]) -> None:
    print("\nScores:")
    for mode in ("chat", "cowork", "code"):
        name, _ = MODE_INFO[mode]
        bar = "#" * totals[mode]
        print(f"  {name:<7} {totals[mode]:>2}  {bar}")

    winner = recommend(totals)
    name, why = MODE_INFO[winner]

    # Detect ties
    top_score = totals[winner]
    tied = [m for m, s in totals.items() if s == top_score]
    print()
    if len(tied) > 1:
        names = " / ".join(MODE_INFO[m][0] for m in tied)
        print(f"It's close — this task fits {names} about equally.")
        print("Consider starting with whichever is less friction to switch out of later.")
    else:
        print(f"Recommendation: {name}")
        print(f"  {why}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Decide whether Chat, Cowork, or Code fits your task best.",
    )
    for q in QUESTIONS:
        parser.add_argument(
            f"--{q.flag.replace('_', '-')}",
            dest=q.flag,
            choices=["y", "n"],
            default=None,
            help=q.prompt,
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    provided = {q.flag: getattr(args, q.flag) for q in QUESTIONS}
    interactive = all(v is None for v in provided.values())

    answers: dict[str, bool] = {}
    if interactive:
        print("Chat vs. Cowork vs. Code — quick picker")
        print("Answer a few questions about your task.\n")
        for q in QUESTIONS:
            answers[q.flag] = ask_yes_no(q.prompt)
    else:
        # Non-interactive: any unset flag defaults to "n" (no).
        for q in QUESTIONS:
            val = provided[q.flag]
            answers[q.flag] = (val == "y")

    totals = score(answers)
    print_report(totals)
    return 0


if __name__ == "__main__":
    sys.exit(main())
