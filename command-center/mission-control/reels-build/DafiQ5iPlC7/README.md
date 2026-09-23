# Design System Extractor

## Where this came from

The source reel (`@nick_saraev`) is a "comment DESIGN to get the link"
lead-gen post advertising four pre-made Claude Code skills (Skill UI,
Impeccable, UI/UX Pro Max, Playwright CLI). It's marketing copy, not a spec —
no prompts, file formats, or code are shown for any of the four.

Of the four, exactly one ("Skill UI") describes an actual, buildable
technique in plain terms: *"point it at any site, and it reverse engineers
the entire design system into a markdown file"* so an LLM can copy the
colors/fonts/spacing instead of guessing. That's concrete enough to
reimplement from scratch, so this directory contains a small, original,
standalone tool that does exactly that. The other three ("gives Claude
taste," "pulls the best palette," "screenshots what it built") are pure
marketing description with no mechanism disclosed — nothing to build from
there, so they're left out rather than invented wholesale.

## What it does

`design_extract.py` points at **one public URL** you give it, fetches the
page's HTML and linked CSS with a single plain HTTP request, and statically
analyzes the text to produce a markdown "design system cheat sheet"
(`design-system.md` by default) containing:

- **Colors** — every hex/rgb/hsl value found, ranked by how often it's used
- **Fonts** — `font-family` declarations, ranked by frequency
- **Font size scale** — the distinct `font-size` values in use
- **Spacing scale** — numeric tokens pulled from `margin`/`padding`/`gap`
- **Border radius** — corner-rounding values in use
- **Shadows** — `box-shadow` values in use

The idea: paste the resulting markdown into a prompt ("build this landing
page using the design system in design-system.md") so Claude Code (or any
assistant) matches an existing site's look instead of defaulting to generic
Tailwind/Bootstrap styling.

## How to run it

Requires only Python 3 (standard library — no dependencies to install).

```bash
python3 design_extract.py https://example.com
# -> writes design-system.md in the current directory

python3 design_extract.py https://example.com -o my-notes/example-style.md
```

Options:

- `-o, --output PATH` — where to write the markdown (default `design-system.md`)
- `--max-stylesheets N` — cap on how many linked `<link rel="stylesheet">`
  files to fetch (default 8)
- `--ignore-robots` — skip the robots.txt check (see below; only use this on
  sites you own or have explicit permission to inspect)

No API keys or accounts needed — it's a plain `urllib` HTTP client.

## Setup / API-key notes

None. It uses only the Python standard library (`urllib`, `html.parser`,
`re`, `argparse`) — no `pip install`, no keys, no accounts.

## Scope, limits, and why it's built this way

This tool is intentionally narrow and honest about what it is:

- **One page, one request.** It fetches exactly the URL you give it (plus,
  best-effort, that page's linked stylesheets) — it does not crawl a site.
- **Respects `robots.txt` by default.** It checks the target's robots.txt
  before fetching and refuses if disallowed, unless you pass
  `--ignore-robots` (intended only for sites you own/control).
- **Plain, honest User-Agent.** It identifies itself as
  `design-extract/1.0` — no attempt to impersonate a browser, rotate
  identities, or otherwise evade bot detection.
- **No auth, no credentials, no login flows.** It only ever reads what an
  anonymous browser visitor would already receive.
- **Static analysis only.** It reads HTML/CSS text with regex, the same
  information visible in a browser's "View Source" or DevTools Styles
  panel — it does not execute JavaScript. Sites that generate all their
  styling via client-side JS (some CSS-in-JS setups) won't yield much;
  that's a known limitation, not a workaround for anything.

If you need to point this at a site you don't own, check that site's terms
of service first — this tool doesn't make that judgment for you.
