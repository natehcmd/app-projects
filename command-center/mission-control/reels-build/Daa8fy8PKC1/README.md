# Resources I Wish I Knew in College — CLI

## About the source material

The reel this was built from (`@jackk_flick`) is engagement bait: it promises
"resources I wish I knew in college when I started programming" but the
actual list is gated behind "follow + comment 'resource' and I'll DM you."
No concrete resource, tool, or technique is named anywhere in the caption.

Rather than decline outright, this tool implements the most reasonable
standalone interpretation of the topic the reel is gesturing at: a small,
honest, curated collection of genuinely well-known free/cheap resources that
CS students commonly recommend after the fact, wrapped in a simple CLI so
it's actually useful instead of just another list in a README.

None of this data was scraped from the creator or Instagram — it's a
hand-picked list of widely known, legitimate, public resources (CS50,
freeCodeCamp, The Odin Project, LeetCode, MIT's Missing Semester, etc.).

## What it does

- Stores a small curated database (`resources.json`) of learning resources
  for CS/programming students, tagged by category (fundamentals, web-dev,
  interview-prep, tools, career) with cost and a one-line note on each.
- `resources_cli.py` lets you browse, search, filter by category, or get a
  random pick — entirely offline, no network calls, no API keys.

## How to run

Requires Python 3.7+, no third-party dependencies.

```bash
cd reels-build/Daa8fy8PKC1

# List everything, grouped by category
python3 resources_cli.py

# List available categories
python3 resources_cli.py --categories

# Filter to one category
python3 resources_cli.py --category interview-prep

# Search by keyword (matches name or note)
python3 resources_cli.py --search git

# Get N random picks (good for "what should I look at today")
python3 resources_cli.py --random 3
```

## Setup / API-key notes

None. This tool is fully self-contained and offline — it reads only from
the local `resources.json` file. No API keys, accounts, or network access
required.

## Extending it

To add your own resources, edit `resources.json` — each entry is:

```json
{
  "name": "...",
  "url": "...",
  "category": "...",
  "cost": "free | free tier | paid | ...",
  "note": "..."
}
```
