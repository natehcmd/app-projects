#!/usr/bin/env python3
"""
resources_cli.py — "Resources I wish I knew in college"

The source reel this tool was built from was pure engagement bait: a creator
promising to DM a link if you follow + comment "resource", with zero actual
resources named. Rather than build nothing, this tool implements the most
reasonable standalone version of what the reel gestures at: a small, local,
curated database of well-known, legitimate, free/cheap resources that CS
students commonly wish they'd found earlier (CS50, freeCodeCamp, LeetCode,
Missing Semester, etc.), plus a CLI to browse/search/filter it.

No scraping, no API calls, no external services — the data lives in
resources.json next to this script and everything runs offline.

Usage:
    python3 resources_cli.py                # list everything, grouped by category
    python3 resources_cli.py --category interview-prep
    python3 resources_cli.py --search git
    python3 resources_cli.py --random 3      # print 3 random picks
    python3 resources_cli.py --categories    # list available categories
"""

import argparse
import json
import random
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent / "resources.json"


def load_resources():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def print_resource(r):
    print(f"  * {r['name']}")
    print(f"    {r['url']}")
    print(f"    cost: {r['cost']}")
    print(f"    {r['note']}")
    print()


def group_by_category(items):
    groups = {}
    for r in items:
        groups.setdefault(r["category"], []).append(r)
    return groups


def main():
    parser = argparse.ArgumentParser(
        description='Browse a curated list of "resources I wish I knew in college" for CS students.'
    )
    parser.add_argument("--category", help="Only show resources in this category")
    parser.add_argument("--search", help="Case-insensitive search across name/note")
    parser.add_argument(
        "--random", type=int, metavar="N", help="Print N random resources"
    )
    parser.add_argument(
        "--categories", action="store_true", help="List available categories and exit"
    )
    args = parser.parse_args()

    resources = load_resources()

    if args.categories:
        cats = sorted({r["category"] for r in resources})
        print("Categories:")
        for c in cats:
            print(f"  - {c}")
        return

    if args.search:
        q = args.search.lower()
        resources = [
            r for r in resources
            if q in r["name"].lower() or q in r["note"].lower()
        ]
        if not resources:
            print(f'No resources matched "{args.search}".')
            sys.exit(0)

    if args.category:
        resources = [r for r in resources if r["category"] == args.category]
        if not resources:
            print(f'No resources found in category "{args.category}". '
                  f"Run with --categories to see valid options.")
            sys.exit(1)

    if args.random:
        pool = resources
        n = min(args.random, len(pool))
        print(f"Random pick of {n}:\n")
        for r in random.sample(pool, n):
            print_resource(r)
        return

    groups = group_by_category(resources)
    for category in sorted(groups):
        print(f"== {category} ==")
        for r in groups[category]:
            print_resource(r)


if __name__ == "__main__":
    main()
