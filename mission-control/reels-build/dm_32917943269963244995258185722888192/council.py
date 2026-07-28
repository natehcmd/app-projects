#!/usr/bin/env python3
"""
Idea Council — four AI personas argue out whether your idea is worth building.

Personas:
  1. The Believer  — makes the strongest possible case FOR the idea.
  2. The Skeptic    — attacks every weak point (who won't pay, who's already
                       doing this, what you're lying to yourself about).
  3. The Investor   — cares about exactly one thing: would real money show up,
                       and how fast.
  4. The Judge      — reads the whole exchange and hands down ONE verdict.

Ideas (and their verdicts) are saved locally, so you can come back later,
tweak the idea, and ask "what changed?" — the Judge is shown the prior
verdict and explicitly told to compare.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 council.py "A subscription box for artisanal dog treats"
    python3 council.py --history                 # list saved ideas
    python3 council.py --show <idea_id>           # replay a past verdict
    python3 council.py --revise <idea_id> "new pitch text"

Requires: pip install anthropic
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Missing dependency. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

MODEL = os.environ.get("COUNCIL_MODEL", "claude-sonnet-5")
STORE_PATH = Path(os.environ.get("COUNCIL_STORE", str(Path(__file__).parent / "council_history.json")))

PERSONAS = {
    "believer": (
        "You are THE BELIEVER on an idea-evaluation council. Make the strongest, "
        "most concrete case FOR this idea. Name who desperately needs it and why "
        "now. No generic cheerleading — specifics only. 3-5 sentences."
    ),
    "skeptic": (
        "You are THE SKEPTIC on an idea-evaluation council. Attack the idea's "
        "weakest points as hard as honesty allows: why people won't actually pay, "
        "the competitor the founder is forgetting, and the thing the founder is "
        "probably lying to themselves about. Be specific, not just cynical. "
        "3-5 sentences."
    ),
    "investor": (
        "You are THE INVESTOR on an idea-evaluation council. You care about "
        "exactly one thing: would real money show up, and how fast? Estimate "
        "willingness to pay, likely price point, and time-to-first-revenue. "
        "Be blunt about whether this is fundable or a hobby. 3-5 sentences."
    ),
}

JUDGE_PROMPT = (
    "You are THE JUDGE on an idea-evaluation council. You have just read arguments "
    "from the Believer, the Skeptic, and the Investor about a business idea. "
    "Hand down ONE verdict in this exact structure:\n\n"
    "VERDICT: [BUILD IT / KILL IT / VALIDATE FIRST]\n"
    "WHY: one tight paragraph synthesizing the strongest points from all three.\n"
    "FATAL FLAW (if any): the single biggest risk that must be resolved first.\n"
    "NEXT STEP: one concrete, doable-this-week action.\n\n"
    "{compare_clause}"
)


def idea_id(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode("utf-8")).hexdigest()[:10]


def load_store() -> dict:
    if STORE_PATH.exists():
        return json.loads(STORE_PATH.read_text())
    return {}


def save_store(store: dict) -> None:
    STORE_PATH.write_text(json.dumps(store, indent=2))


def call(client: "anthropic.Anthropic", system: str, user: str) -> str:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


def run_council(idea_text: str, prior_verdict: str | None = None) -> dict:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    transcript = {}
    for name, system in PERSONAS.items():
        transcript[name] = call(client, system, f"THE IDEA:\n{idea_text}")

    debate = "\n\n".join(
        f"{name.upper()}: {text}" for name, text in transcript.items()
    )

    compare_clause = ""
    if prior_verdict:
        compare_clause = (
            "The founder revised their idea after a previous verdict. Here is "
            f"that previous verdict for comparison:\n\n{prior_verdict}\n\n"
            "In WHY, explicitly note what changed and whether the revision helped."
        )

    verdict = call(
        client,
        JUDGE_PROMPT.format(compare_clause=compare_clause),
        f"THE IDEA:\n{idea_text}\n\nTHE DEBATE:\n{debate}",
    )

    return {"transcript": transcript, "verdict": verdict}


def cmd_evaluate(idea_text: str, revise_of: str | None = None) -> None:
    store = load_store()
    iid = revise_of or idea_id(idea_text)

    prior_verdict = None
    if revise_of and revise_of in store and store[revise_of]["runs"]:
        prior_verdict = store[revise_of]["runs"][-1]["verdict"]

    print(f"Idea ID: {iid}")
    print("Convening the council...\n")

    result = run_council(idea_text, prior_verdict=prior_verdict)

    for name in ("believer", "skeptic", "investor"):
        print(f"--- {name.upper()} ---")
        print(result["transcript"][name])
        print()

    print("=== JUDGE'S VERDICT ===")
    print(result["verdict"])

    entry = store.setdefault(iid, {"idea_text": idea_text, "runs": []})
    entry["idea_text"] = idea_text  # keep latest wording
    entry["runs"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "transcript": result["transcript"],
            "verdict": result["verdict"],
        }
    )
    save_store(store)
    print(f"\nSaved to {STORE_PATH} under id '{iid}'.")
    print(f"Tip: revise later with --revise {iid} \"updated pitch\"")


def cmd_history() -> None:
    store = load_store()
    if not store:
        print("No ideas evaluated yet.")
        return
    for iid, entry in store.items():
        latest = entry["runs"][-1]
        first_line = latest["verdict"].splitlines()[0] if latest["verdict"] else ""
        print(f"{iid}  ({len(entry['runs'])} run(s))  {first_line}")
        print(f"    idea: {entry['idea_text'][:80]}")


def cmd_show(iid: str) -> None:
    store = load_store()
    if iid not in store:
        print(f"No saved idea with id '{iid}'. Run --history to list ids.", file=sys.stderr)
        sys.exit(1)
    entry = store[iid]
    print(f"Idea: {entry['idea_text']}\n")
    for i, run in enumerate(entry["runs"], 1):
        print(f"--- Run {i} ({run['timestamp']}) ---")
        print(run["verdict"])
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Idea Council: four AI personas debate your idea.")
    parser.add_argument("idea", nargs="?", help="Your idea, in one paragraph.")
    parser.add_argument("--history", action="store_true", help="List all saved ideas.")
    parser.add_argument("--show", metavar="ID", help="Replay all verdicts for a saved idea id.")
    parser.add_argument("--revise", metavar="ID", help="Re-run council for an existing idea id with new text.")
    args = parser.parse_args()

    if args.history:
        cmd_history()
        return

    if args.show:
        cmd_show(args.show)
        return

    if args.revise:
        if not args.idea:
            print("Provide the revised idea text as the positional argument.", file=sys.stderr)
            sys.exit(1)
        cmd_evaluate(args.idea, revise_of=args.revise)
        return

    if not args.idea:
        parser.print_help()
        sys.exit(1)

    cmd_evaluate(args.idea)


if __name__ == "__main__":
    main()
