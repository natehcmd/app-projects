#!/usr/bin/env python3
"""
assembly_line.py — a 3-station "model assembly line" for batch content generation.

The idea (this is the real technique behind the "AI Factory / Sol-Terra-Luna"
reel, translated into an actually-runnable tool using the Claude model family):

  Station 1 — SPEC   (expensive/smart model, called ONCE)
      Writes a master spec + an explicit quality bar for the whole batch.
      It never writes any of the actual output units.

  Station 2 — DRAFT  (mid-tier model, called ONCE)
      Turns the spec into a structured template/pattern that Station 3 can
      stamp out repeatedly (tone, structure, placeholders for personalization).

  Station 3 — PRODUCE (cheap/fast model, called N times)
      Mass-produces the N final units (one per row of input personalization
      data, or N generic variants if no input data is given).

  Station 4 — QA GATE (expensive/smart model, called ONCE per batch pass)
      Grades every produced unit against the EXACT quality bar written in
      Station 1. Passing units go to the output file; failing units are
      logged with the reason so you can re-run just those.

Net effect: the expensive model only ever touches the job twice (spec + QA),
no matter how large N is. Everything in the middle runs on the cheap model.

This is a generic, provider-agnostic pattern. It ships wired up to the
Anthropic API (Claude) since that's what's available here, using three tiers
that map directly onto the reel's Sol/Terra/Luna idea:

    STATION            DEFAULT MODEL
    spec / qa    ->    claude-opus-4-8           (or override with --spec-model)
    draft        ->    claude-sonnet-5           (or override with --draft-model)
    produce      ->    claude-haiku-4-5          (or override with --produce-model)

Swap --spec-model / --draft-model / --produce-model to point at any models
your ANTHROPIC_API_KEY has access to (or edit DEFAULT_* below).
"""

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SPEC_MODEL = "claude-opus-4-8"
DEFAULT_DRAFT_MODEL = "claude-sonnet-5"
DEFAULT_PRODUCE_MODEL = "claude-haiku-4-5-20251001"

MAX_TOKENS = 2000


def _client():
    try:
        import anthropic
    except ImportError:
        sys.exit(
            "Missing dependency 'anthropic'. Install with:\n"
            "    pip install anthropic\n"
        )
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "ANTHROPIC_API_KEY is not set.\n"
            "Get a key at https://console.anthropic.com/settings/keys and run:\n"
            "    export ANTHROPIC_API_KEY=sk-ant-...\n"
        )
    return anthropic.Anthropic(api_key=api_key)


def call_model(client, model: str, system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    ).strip()


@dataclass
class Unit:
    index: int
    personalization: dict = field(default_factory=dict)
    draft_input: str = ""
    output: str = ""
    passed: bool = False
    qa_notes: str = ""


def load_personalization(csv_path: str | None, count: int) -> list[dict]:
    """Load per-unit personalization rows from a CSV, or fall back to N empty rows."""
    if not csv_path:
        return [{} for _ in range(count)]
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    if not rows:
        sys.exit(f"No rows found in {csv_path}")
    return rows


def station1_spec(client, model: str, task: str) -> str:
    system = (
        "You are the lead planner on a content assembly line. You write ONE "
        "master spec for a batch job — you never write individual output units "
        "yourself. Your spec must include:\n"
        "1) A clear description of the unit to be produced.\n"
        "2) Structure/format requirements (length, sections, placeholders for "
        "personalization fields if any).\n"
        "3) Tone and voice.\n"
        "4) An explicit, checkable QUALITY BAR: a short numbered rubric "
        "(3-6 criteria) that a reviewer can use to pass/fail any single unit. "
        "Be concrete and objective — avoid vague criteria like 'good writing'.\n"
        "Output the spec as plain text with a '## Quality Bar' section at the end."
    )
    return call_model(client, model, system, f"Batch task:\n{task}", max_tokens=1200)


def station2_draft(client, model: str, spec: str, sample_fields: list[str]) -> str:
    fields_note = (
        f"Personalization fields available per unit: {', '.join(sample_fields)}. "
        "Use {{field_name}} placeholders for these in the template."
        if sample_fields
        else "No personalization fields provided; produce a reusable generic template."
    )
    system = (
        "You are the drafter on a content assembly line. Given the master spec, "
        "produce ONE reusable template/pattern that a fast production model can "
        "stamp out repeatedly with light personalization. Do not write final "
        "copies — write the reusable structure/skeleton with clear placeholders "
        "and brief instructions for how to fill them in."
    )
    user = f"Master spec:\n{spec}\n\n{fields_note}"
    return call_model(client, model, system, user, max_tokens=1200)


def station3_produce(client, model: str, spec: str, draft_template: str, personalization: dict) -> str:
    system = (
        "You are the production worker on a content assembly line. Using the "
        "spec and the reusable template, produce exactly ONE final unit, fully "
        "personalized with the fields given. Output only the final unit text, "
        "no commentary, no markdown fences."
    )
    user = (
        f"Master spec:\n{spec}\n\n"
        f"Template:\n{draft_template}\n\n"
        f"Personalization fields for this unit:\n{json.dumps(personalization, indent=2)}\n\n"
        "Produce the final unit now."
    )
    return call_model(client, model, system, user, max_tokens=MAX_TOKENS)


def station4_qa(client, model: str, spec: str, unit_output: str) -> tuple[bool, str]:
    system = (
        "You are the QA inspector on a content assembly line. Grade the given "
        "unit STRICTLY against the '## Quality Bar' section of the spec. "
        "Respond with exactly two lines:\n"
        "VERDICT: PASS or FAIL\n"
        "NOTES: one sentence explaining why."
    )
    user = f"Spec:\n{spec}\n\nUnit to grade:\n{unit_output}"
    result = call_model(client, model, system, user, max_tokens=200)
    passed = "PASS" in result.splitlines()[0].upper() if result else False
    notes = result
    return passed, notes


def run(args):
    client = _client()
    rows = load_personalization(args.data, args.count)
    count = len(rows) if args.data else args.count
    sample_fields = list(rows[0].keys()) if args.data and rows else []

    print(f"[Station 1] SPEC ({args.spec_model}) — writing master spec + quality bar...")
    spec = station1_spec(client, args.spec_model, args.task)
    print("--- SPEC ---\n" + spec + "\n")

    print(f"[Station 2] DRAFT ({args.draft_model}) — building reusable template...")
    draft_template = station2_draft(client, args.draft_model, spec, sample_fields)
    print("--- TEMPLATE ---\n" + draft_template + "\n")

    units: list[Unit] = []
    print(f"[Station 3] PRODUCE ({args.produce_model}) — mass-producing {count} units...")
    for i, personalization in enumerate(rows[:count], start=1):
        out = station3_produce(client, args.produce_model, spec, draft_template, personalization)
        units.append(Unit(index=i, personalization=personalization, output=out))
        print(f"  produced {i}/{count}")
        if args.sleep:
            time.sleep(args.sleep)

    if args.skip_qa:
        for u in units:
            u.passed = True
            u.qa_notes = "QA skipped (--skip-qa)"
    else:
        print(f"[Station 4] QA GATE ({args.spec_model}) — grading {count} units against the quality bar...")
        for u in units:
            passed, notes = station4_qa(client, args.spec_model, spec, u.output)
            u.passed, u.qa_notes = passed, notes
            print(f"  unit {u.index}: {'PASS' if passed else 'FAIL'} — {notes.splitlines()[-1] if notes else ''}")

    out_path = Path(args.out)
    passed_units = [u for u in units if u.passed]
    failed_units = [u for u in units if not u.passed]

    with out_path.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps({
                "index": u.index,
                "personalization": u.personalization,
                "output": u.output,
                "passed": u.passed,
                "qa_notes": u.qa_notes,
            }) + "\n")

    print(f"\nDone. {len(passed_units)}/{count} passed QA, {len(failed_units)} failed.")
    print(f"All results (pass + fail) written to: {out_path}")
    if failed_units:
        print(f"Failed indices: {[u.index for u in failed_units]} — inspect qa_notes in the output file and re-run just those.")


def main():
    p = argparse.ArgumentParser(
        description="3-station AI assembly line: spec (expensive) -> draft (mid) -> "
                     "mass-produce (cheap, xN) -> QA gate (expensive)."
    )
    p.add_argument("--task", required=True, help="Description of the batch job, e.g. "
                   "'50 cold outreach emails to SaaS founders about our analytics tool'.")
    p.add_argument("--count", type=int, default=10, help="How many units to produce "
                   "(ignored if --data is given; then count = number of CSV rows).")
    p.add_argument("--data", help="Optional CSV of per-unit personalization fields "
                   "(e.g. name,company,pain_point). One row = one unit.")
    p.add_argument("--out", default="assembly_line_output.jsonl", help="Output JSONL path.")
    p.add_argument("--spec-model", default=DEFAULT_SPEC_MODEL, help="Model for spec + QA stations.")
    p.add_argument("--draft-model", default=DEFAULT_DRAFT_MODEL, help="Model for the draft/template station.")
    p.add_argument("--produce-model", default=DEFAULT_PRODUCE_MODEL, help="Model for the mass-production station.")
    p.add_argument("--skip-qa", action="store_true", help="Skip Station 4 (QA gate) to save cost/time.")
    p.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between production calls (rate-limit friendliness).")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
