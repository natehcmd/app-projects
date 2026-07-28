#!/usr/bin/env python3
"""
student_perks.py

A tiny, self-contained directory/CLI for the "free software for students"
offers that get passed around in social-media posts (GitHub Student Pack,
Cursor, Notion, Figma, Perplexity, etc).

This does NOT scrape anything, does NOT automate sign-up or verification,
and does NOT try to fake/bypass student-status checks. It's just a curated,
locally-stored reference list with links to each vendor's *official*
sign-up/verification page, plus a couple of small convenience commands:

  - list all known perks
  - search perks by keyword/category
  - sanity-check whether an email address looks like a plausible .edu-style
    academic address (a simple heuristic, NOT a verification -- vendors do
    their own real verification, e.g. via SheerID or a school email domain
    check, when you actually sign up)

Usage:
    python3 student_perks.py list
    python3 student_perks.py search cursor
    python3 student_perks.py check your.name@some-university.edu
"""

import json
import re
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent / "perks.json"


def load_perks():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def print_perk(p, idx=None):
    prefix = f"{idx}. " if idx is not None else ""
    print(f"{prefix}{p['name']}  [{p['category']}]")
    print(f"   Normal price : {p['normal_price']}")
    print(f"   Student price: {p['student_price']}")
    print(f"   Requirements : {p['requirements']}")
    print(f"   Sign up here : {p['signup_url']}")
    if p.get("notes"):
        print(f"   Note         : {p['notes']}")
    print()


def cmd_list(perks):
    print(f"Found {len(perks)} known student software perks:\n")
    for i, p in enumerate(perks, 1):
        print_perk(p, i)


def cmd_search(perks, term):
    term_l = term.lower()
    matches = [
        p for p in perks
        if term_l in p["name"].lower()
        or term_l in p["category"].lower()
        or term_l in p.get("notes", "").lower()
    ]
    if not matches:
        print(f"No perks matched '{term}'.")
        return
    print(f"{len(matches)} match(es) for '{term}':\n")
    for i, p in enumerate(matches, 1):
        print_perk(p, i)


EDU_LIKE_RE = re.compile(r"^[^@\s]+@[^@\s]+\.(edu|ac\.[a-z]{2}|edu\.[a-z]{2})$", re.IGNORECASE)


def cmd_check(email):
    """
    Heuristic only. This is NOT a verification service and does not talk to
    any vendor or school. It just flags whether an email address *looks*
    like a typical academic address pattern, so you know whether it's worth
    trying a vendor's real (official) student-verification flow.
    """
    looks_academic = bool(EDU_LIKE_RE.match(email.strip()))
    print(f"Email: {email}")
    if looks_academic:
        print("Looks like an academic-style address (.edu / ac.xx / edu.xx).")
        print("This is only a pattern check -- actual eligibility is decided")
        print("by each vendor's own verification process (e.g. SheerID),")
        print("not by this script.")
    else:
        print("Doesn't match a typical academic email pattern.")
        print("You may still be eligible -- many programs accept alternate")
        print("proof of enrollment (student ID, transcript, etc). Check each")
        print("vendor's official sign-up page for accepted proof types.")


def main():
    perks = load_perks()
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "list":
        cmd_list(perks)
    elif cmd == "search":
        if len(args) < 2:
            print("Usage: python3 student_perks.py search <term>")
            sys.exit(1)
        cmd_search(perks, " ".join(args[1:]))
    elif cmd == "check":
        if len(args) < 2:
            print("Usage: python3 student_perks.py check <email>")
            sys.exit(1)
        cmd_check(args[1])
    else:
        print(f"Unknown command: {cmd}\n")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
