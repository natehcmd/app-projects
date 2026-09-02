# DESIGN.md scaffolder

## What this actually is

The source reel was pure engagement bait: "Google dropped a repo called
DESIGN.md" / "comment DESIGN and I'll DM you the repo" — no technique, no
file contents, no structure was ever shown. There's no real "Google repo" to
reproduce and nothing concrete to copy from the reel itself.

What *is* real and useful is the underlying idea the reel is gesturing at:
coding agents like Claude Code produce inconsistent, generic-looking UI when
they aren't given a written design system to follow, and putting that system
in one file the agent reads before touching UI code measurably helps. So
that's what this tool builds — a solid, from-scratch `DESIGN.md` starter and
a small script to drop it into any repo and make sure Claude Code (or any
agent reading `CLAUDE.md`) actually picks it up.

This is **not** a copy of any specific product's file — it's an original
template covering the sections a design-system file needs (colors, spacing,
typography, components, motion, accessibility, and explicit rules for the
agent), plus best-effort auto-fill from your existing Tailwind config if you
have one.

## Files

- `DESIGN.template.md` — the starter template with `{{PLACEHOLDER}}` tokens
  for colors, spacing, typography, components, motion, and a "rules for the
  agent" section that's the actual behavior-changing part.
- `init_design_system.py` — CLI that copies the template into a target repo
  as `DESIGN.md`, tries to pre-fill color tokens from `tailwind.config.{js,ts,cjs}`
  if one exists, and adds/creates a `CLAUDE.md` pointer so Claude Code reads
  `DESIGN.md` before doing UI work.

## How to run it

Requires Python 3 (no external dependencies — standard library only).

```bash
# Scaffold DESIGN.md + CLAUDE.md pointer into a target project
python3 init_design_system.py /path/to/your/repo

# Or scaffold into the current directory
python3 init_design_system.py .
```

Then:

1. Open the generated `DESIGN.md` and fill in the remaining
   `{{PLACEHOLDER}}` values (colors, spacing scale, fonts, component list,
   etc.) with your project's actual choices.
2. Commit it to the repo.
3. When you prompt Claude Code (or another coding agent whose instructions
   file it reads) to build or edit UI, it will see the pointer in
   `CLAUDE.md`, read `DESIGN.md` first, and use your tokens/components
   instead of inventing new ones each time.

If a `tailwind.config.js`/`.ts`/`.cjs` already exists in the target repo,
the script does a best-effort regex scan for `key: '#hex'` color entries and
pre-fills matching tokens (e.g. a `primary` color maps to `color-accent`).
This is a convenience heuristic, not a JS/TS parser — always sanity-check
the filled-in values before committing.

## Setup / API-key notes

None. This is a static templating tool — no API keys, no network calls, no
external services. It only reads/writes files on disk in the directory you
point it at.

## Re-running

The script refuses to overwrite an existing `DESIGN.md` (it exits with an
error) so you don't accidentally clobber one you've already customized.
Delete or rename the existing file first if you want to regenerate from
scratch. It's safe to re-run against a repo that already has a `CLAUDE.md`
— if that file already mentions `DESIGN.md` it leaves it untouched;
otherwise it appends a short pointer section.
