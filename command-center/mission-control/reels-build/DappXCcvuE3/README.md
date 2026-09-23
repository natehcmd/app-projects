# Animated UI Component Finder

## Source material / why this exists

The source reel (`DappXCcvuE3`) is a one-line caption:

> "Powerful websites you should know (part 1082) find almost any animated UI component #animation #component #development"

This is a generic "part N" listicle-style Instagram post. It doesn't name any
actual websites, URLs, or techniques in the extractable text/caption — the
specific site names presumably only appear as on-screen text in the video
itself, which wasn't available to build from. Rather than treat that as
"nothing here," the caption does give a clear **topic**: sites for finding
animated UI components for web development.

So instead of fabricating fake sites or declining outright, this tool builds
the thing the reel is gesturing at: **a small curated directory of real,
well-known websites/tools that developers actually use to find animated UI
components** (buttons, cards, loaders, hero sections, background effects,
etc.), with a CLI to search and filter it. Every entry in `sites.json` is a
genuine, real, publicly known site/tool in this space (Aceternity UI, Magic
UI, UIverse, Animista, HyperUI, Motion.dev, React Bits, shadcn/ui, Codrops,
LottieFiles, Tailwind CSS Buttons, Cuberto) — nothing was invented.

## What it does

`finder.py` is an offline CLI over `sites.json`, a small curated database of
12 real animated-UI-component resources. You can:

- List everything
- Filter by tag (e.g. `react`, `tailwind`, `free`, `css-animation`)
- Keyword-search names/descriptions/tags (e.g. `"hero"`, `"button"`)
- List all available tags
- Get a random pick (handy when you just want inspiration)
- Get JSON output for piping into other tools/scripts

No network calls, no scraping, no API keys — it's just a local lookup table
plus a search interface, meant as a quick personal reference the same way the
reel promises ("find almost any animated UI component").

## How to run it

Requires Python 3 (stdlib only, no dependencies to install).

```bash
cd /Users/natehoward/Projects/mission-control/reels-build/DappXCcvuE3/

# list every curated site
python3 finder.py

# filter by tag (repeatable — AND logic)
python3 finder.py --tag react --tag free

# keyword search across name/description/tags
python3 finder.py --search "button"

# see all tags you can filter on
python3 finder.py --tags

# grab one at random for inspiration
python3 finder.py --random

# machine-readable output
python3 finder.py --json
```

## Extending it

To add more sites, just append entries to `sites.json` following the existing
shape:

```json
{
  "name": "Site Name",
  "url": "https://example.com",
  "tags": ["react", "css"],
  "description": "What it's good for."
}
```

## Setup / API-key notes

None. No API keys, accounts, or network access are required — this is a fully
self-contained local tool.
