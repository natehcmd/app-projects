# skillkit — scaffold & lint Claude Code Skills

## Where this came from

The source reel (`DaSwegFCZO7`) is hype content: it claims "a few
well-made skills" give Claude Code better planning, memory, frontend
design, and "automatic skill discovery," but it never explains what a
skill actually contains or how to build one — there's no concrete
technique in the transcript.

Rather than fabricate a fake mechanism, this tool implements the one
real, well-documented thing the reel is vaguely gesturing at: Claude
Code's actual **Skills** feature. A skill is a directory with a
`SKILL.md` file (YAML frontmatter + instructions) that Claude reads and
follows when its `description` matches what you're asking for. The
single biggest, checkable factor in whether a skill "auto-discovers"
correctly — the exact thing the reel name-drops — is whether that
description is written well (specific, third-person, states *when* to
trigger). So this tool scaffolds and lints for that.

## What it does

`skillkit.py` is a single-file, dependency-free Python CLI with three
commands:

- **`new <name>`** — scaffolds a new skill directory with a
  `SKILL.md` template (correct frontmatter shape, a `resources/`
  folder for reference files/scripts) so you start from a good
  structure instead of a blank page.
- **`lint <path>`** — checks an existing `SKILL.md` (or a directory
  containing one) against known good/bad patterns: missing
  frontmatter, missing/too-short/too-long description, vague phrases
  ("helps with", "various tasks", "general purpose"), first-person
  phrasing, and description text that doesn't state *when* to use the
  skill. Exits non-zero if issues are found, so you can wire it into a
  pre-commit hook or CI check on a skills repo.
- **`list <dir>`** — walks a directory of skills (e.g.
  `~/.claude/skills`) and prints a one-line summary of each, flagging
  the ones with lint issues.

## How to run it

Requires only Python 3.9+ (standard library, no installs).

```bash
# Scaffold a new skill
python3 skillkit.py new pdf-report-builder --dir ./skills

# Edit skills/pdf-report-builder/SKILL.md, then lint it
python3 skillkit.py lint ./skills/pdf-report-builder/SKILL.md

# Summarize everything in your real Claude Code skills directory
python3 skillkit.py list ~/.claude/skills
```

Run the smoke tests:

```bash
python3 -m unittest test_skillkit -v
# or: python3 test_skillkit.py
```

## Setup / API-key notes

None. This tool does no network calls and needs no API key — it only
reads/writes local files. It doesn't call the Claude API and isn't
required to use Claude Code's skills feature; it's just a helper for
authoring good `SKILL.md` files by hand, faster and more consistently.

## Files

- `skillkit.py` — the CLI (scaffold + lint + list)
- `test_skillkit.py` — unittest smoke tests covering all three commands
