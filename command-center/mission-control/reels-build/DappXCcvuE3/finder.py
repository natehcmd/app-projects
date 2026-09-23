#!/usr/bin/env python3
"""
finder.py — Animated UI Component Site Finder

A tiny offline CLI over a curated list of real, well-known websites/tools for
finding animated UI components (buttons, cards, loaders, hero sections, etc.)
to use in web projects.

No network calls, no API keys, no scraping — just a small local database
(sites.json) and a search/filter CLI on top of it.

Usage:
    python3 finder.py                     # list everything
    python3 finder.py --tag react         # filter by tag
    python3 finder.py --search "hero"     # keyword search (name/description/tags)
    python3 finder.py --tags              # list all available tags
    python3 finder.py --random            # show one random pick
    python3 finder.py --json              # machine-readable output

Examples:
    python3 finder.py --search "button"
    python3 finder.py --tag tailwind --tag free
"""

import argparse
import json
import random
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent / "sites.json"


def load_sites():
    if not DATA_FILE.exists():
        print(f"Error: could not find {DATA_FILE}", file=sys.stderr)
        sys.exit(1)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def matches_search(site, query):
    query = query.lower()
    haystack = " ".join(
        [site["name"], site["description"], " ".join(site["tags"])]
    ).lower()
    return query in haystack


def filter_sites(sites, tags=None, search=None):
    result = sites
    if tags:
        wanted = {t.lower() for t in tags}
        result = [s for s in result if wanted.issubset({t.lower() for t in s["tags"]})]
    if search:
        result = [s for s in result if matches_search(s, search)]
    return result


def print_sites(sites):
    if not sites:
        print("No matches. Try --tags to see available filters.")
        return
    for s in sites:
        print(f"\n{s['name']}")
        print(f"  {s['url']}")
        print(f"  {s['description']}")
        print(f"  tags: {', '.join(s['tags'])}")


def all_tags(sites):
    tags = sorted({t for s in sites for t in s["tags"]})
    return tags


def main():
    parser = argparse.ArgumentParser(description="Find animated UI component websites.")
    parser.add_argument("--tag", action="append", help="Filter by tag (repeatable, AND logic).")
    parser.add_argument("--search", help="Keyword search across name/description/tags.")
    parser.add_argument("--tags", action="store_true", help="List all available tags and exit.")
    parser.add_argument("--random", action="store_true", help="Show one random site.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text.")
    args = parser.parse_args()

    sites = load_sites()

    if args.tags:
        for t in all_tags(sites):
            print(t)
        return

    if args.random:
        pick = [random.choice(sites)]
        if args.json:
            print(json.dumps(pick, indent=2))
        else:
            print_sites(pick)
        return

    result = filter_sites(sites, tags=args.tag, search=args.search)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_sites(result)
        print(f"\n{len(result)} site(s) shown out of {len(sites)} total.")


if __name__ == "__main__":
    main()
