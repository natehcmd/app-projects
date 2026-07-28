#!/usr/bin/env python3
"""
Forge Loop — a self-critique/revise loop for Claude.

The reel this is built from ("Forge Loop") describes a technique, not a
concrete prompt: tell the model to draft something, then switch roles and
attack its own draft like a stranger wrote it, score it against a rubric,
fix exactly the issues it found, and repeat until the score clears a bar
with zero open issues. The reel withheld its actual prompt text behind a
"comment EVOLVE for the DM" gate, so this script is an independent,
runnable implementation of that idea — not a transcription of anything
that was sent out via DM.

What it does, concretely:
  1. Ask Claude to produce a first-draft response to a task.
  2. Ask Claude to grade its OWN draft against a 5-part rubric (correct,
     complete, clear, consistent, tested), list every issue it finds, and
     produce a revised draft that fixes exactly those issues.
  3. Repeat step 2 on the revised draft until either:
       - the overall score is >= --pass-score (default 90) AND there are
         zero open issues, or
       - --max-iterations is reached (default 6) — a hard stop so a
         model that can't converge doesn't loop (and bill) forever.
  4. Print the score trajectory (e.g. 61, 74, 85, 92) and write the final
     draft to a file.

Usage:
    python forge_loop.py --task "Write a cancellation email for a SaaS
        customer who churned after 3 months" --output final.md

    # Refine an existing draft instead of generating a fresh one:
    python forge_loop.py --task "Tighten this onboarding doc" \
        --input-file draft.md --output final.md

    # Tune the loop:
    python forge_loop.py --task "..." --pass-score 95 --max-iterations 10

See README.md for setup, API key notes, and cost/behavior caveats.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic

MODEL = "claude-opus-4-8"

RUBRIC_CATEGORIES = ["correct", "complete", "clear", "consistent", "tested"]

RUBRIC_DESCRIPTION = """\
Grade the draft on a 0-100 scale in each of these five categories, then an
overall 0-100 score. Be an honest, skeptical grader — you are not trying to
make the author (yourself) feel good, you are trying to find what is
actually wrong. A polite 90+ with no issues listed is only acceptable if
you truly cannot find a single real problem after actively looking for one.

- correct: Are the facts, logic, code, and claims in the draft actually
  right? Would a subject-matter expert find an error?
- complete: Does it fully address what was asked, with no missing pieces,
  unhandled edge cases, or unanswered parts of the task?
- clear: Is it unambiguous and easy to follow for its actual audience?
  Would a reader be confused or have to re-read anything?
- consistent: Does it avoid self-contradiction — consistent terminology,
  consistent formatting, consistent claims that don't undercut each other?
- tested: For anything checkable (code, math, instructions, claims that
  can be verified), has it actually been verified rather than assumed?
  For prose/creative work, treat this as: were the claims fact-checked?
"""

REVISE_INSTRUCTIONS = """\
You are switching roles: you are no longer the author of this draft, you
are an independent, skeptical reviewer seeing it for the first time — as
if a stranger wrote it and you have no attachment to it. Your job is to
find every real problem, not to rubber-stamp it.

Then, as a separate step, fix EXACTLY the issues you listed — no more, no
less. Do not do unrelated rewrites, do not add scope that wasn't asked
for, and do not "polish" things that weren't flagged as issues. If you
list zero issues, the revised draft should be identical to the input
draft.
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_score": {
            "type": "integer",
            "description": "Overall 0-100 score for the draft, after weighing all five categories.",
        },
        "category_scores": {
            "type": "object",
            "properties": {c: {"type": "integer"} for c in RUBRIC_CATEGORIES},
            "required": RUBRIC_CATEGORIES,
            "additionalProperties": False,
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Every concrete issue found, one per entry. Empty array only if truly none found.",
        },
        "revised_draft": {
            "type": "string",
            "description": "The draft with exactly the listed issues fixed (identical to input if issues is empty).",
        },
    },
    "required": ["overall_score", "category_scores", "issues", "revised_draft"],
    "additionalProperties": False,
}


@dataclass
class IterationResult:
    iteration: int
    overall_score: int
    category_scores: dict[str, int]
    issues: list[str]
    draft: str


@dataclass
class ForgeLoopResult:
    task: str
    final_draft: str
    iterations: list[IterationResult] = field(default_factory=list)
    stopped_reason: str = ""

    @property
    def score_trajectory(self) -> list[int]:
        return [it.overall_score for it in self.iterations]


def _client() -> anthropic.Anthropic:
    # Resolves ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / `ant auth login`
    # profile from the environment automatically.
    return anthropic.Anthropic()


def generate_first_draft(client: anthropic.Anthropic, task: str, model: str, max_tokens: int) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Produce a first draft for the following task. Do not "
                    "self-critique yet — just write the best draft you can "
                    "in one pass.\n\nTASK:\n" + task
                ),
            }
        ],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def critique_and_revise(
    client: anthropic.Anthropic,
    task: str,
    draft: str,
    model: str,
    max_tokens: int,
    extra_rubric_notes: list[str],
) -> dict[str, Any]:
    rubric = RUBRIC_DESCRIPTION
    if extra_rubric_notes:
        rubric += "\n\nAdditional rubric notes from the user (apply these too):\n"
        rubric += "\n".join(f"- {note}" for note in extra_rubric_notes)

    prompt = (
        f"{REVISE_INSTRUCTIONS}\n\nRUBRIC:\n{rubric}\n\n"
        f"ORIGINAL TASK:\n{task}\n\nCURRENT DRAFT:\n{draft}"
    )

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {
                "type": "json_schema",
                "schema": OUTPUT_SCHEMA,
            },
        },
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def run_forge_loop(
    task: str,
    starting_draft: str | None = None,
    model: str = MODEL,
    max_tokens: int = 4096,
    max_iterations: int = 6,
    pass_score: int = 90,
    extra_rubric_notes: list[str] | None = None,
    on_iteration=None,
) -> ForgeLoopResult:
    extra_rubric_notes = extra_rubric_notes or []
    client = _client()

    draft = starting_draft or generate_first_draft(client, task, model, max_tokens)
    result = ForgeLoopResult(task=task, final_draft=draft)

    for i in range(1, max_iterations + 1):
        graded = critique_and_revise(client, task, draft, model, max_tokens, extra_rubric_notes)
        iteration = IterationResult(
            iteration=i,
            overall_score=graded["overall_score"],
            category_scores=graded["category_scores"],
            issues=graded["issues"],
            draft=graded["revised_draft"],
        )
        result.iterations.append(iteration)
        if on_iteration:
            on_iteration(iteration)

        draft = iteration.draft
        result.final_draft = draft

        if iteration.overall_score >= pass_score and not iteration.issues:
            result.stopped_reason = f"passed: score {iteration.overall_score} >= {pass_score} with zero open issues"
            return result

    result.stopped_reason = f"stopped: reached max_iterations={max_iterations} without clearing the bar"
    return result


def _print_iteration(it: IterationResult) -> None:
    cats = ", ".join(f"{k}={v}" for k, v in it.category_scores.items())
    print(f"[iteration {it.iteration}] overall={it.overall_score}  ({cats})", file=sys.stderr)
    if it.issues:
        for issue in it.issues:
            print(f"    - {issue}", file=sys.stderr)
    else:
        print("    - no open issues", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Forge Loop: make Claude draft, self-critique against a rubric, and fix its own work before you see it.",
    )
    parser.add_argument("--task", required=True, help="What you want produced or improved.")
    parser.add_argument("--input-file", help="Optional starting draft to refine instead of generating a fresh one.")
    parser.add_argument("--output", default="forge_loop_output.md", help="Where to write the final draft.")
    parser.add_argument("--model", default=MODEL, help=f"Claude model ID (default: {MODEL}).")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max output tokens per API call.")
    parser.add_argument("--max-iterations", type=int, default=6, help="Hard cap on critique/revise loops.")
    parser.add_argument("--pass-score", type=int, default=90, help="Overall score required to stop early.")
    parser.add_argument(
        "--rubric-note",
        action="append",
        default=[],
        dest="rubric_notes",
        help='Extra grading rule, e.g. --rubric-note "Must stay under 200 words". Repeatable.',
    )
    args = parser.parse_args()

    starting_draft = None
    if args.input_file:
        starting_draft = Path(args.input_file).read_text()

    print(f"Forge Loop starting — task: {args.task}", file=sys.stderr)

    result = run_forge_loop(
        task=args.task,
        starting_draft=starting_draft,
        model=args.model,
        max_tokens=args.max_tokens,
        max_iterations=args.max_iterations,
        pass_score=args.pass_score,
        extra_rubric_notes=args.rubric_notes,
        on_iteration=_print_iteration,
    )

    print(f"\n{result.stopped_reason}", file=sys.stderr)
    print(f"Score trajectory: {result.score_trajectory}", file=sys.stderr)

    Path(args.output).write_text(result.final_draft)
    print(f"Final draft written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
