# find_skills.py — search GitHub for real Claude Code skills

## Source

> @abhishek.devini: Comment SKILL and I'll send you the exact command + full
> step-by-step setup. This is the last Claude Code skill you'll ever install
> by hand. Right now there are 2,000+ skills scattered across GitHub... So
> you install just one skill: find-skills. It runs on Vercel's open skills
> CLI and plugs straight into Claude Code with a single command.

The reel names a specific product ("Vercel's open skills CLI") but gates
the actual install command behind a comment-for-DM funnel. Rather than
guess at an unverified third-party CLI, this builds the same idea
transparently and standalone: search GitHub for skills matching a task,
rank by stars, and show (not auto-run) the install command.

## What it does

Queries GitHub's public Code Search API for `SKILL.md` files matching your
query; falls back to Repository Search (by name/description/topics) if code
search is unavailable. Sorts by star count, prints candidates with
descriptions, and prints (never runs) the clone + copy commands to install
the top match into `~/.claude/skills/`.

## Verified working (2026-07-20)

Ran live against `python3 find_skills.py "summarize a pdf"`. Found two real
issues during QA, both fixed:
1. GitHub's `/search/code` endpoint now requires authentication even for
   public repos (returns 401 without `GITHUB_TOKEN`) — the fallback to
   Repository Search already handled this gracefully, but the docstring
   didn't explain why the fallback triggers. Documented.
2. The repo-search fallback path produced a nonsensical install path
   (`~/.claude/skills/./`) because it doesn't know the skill's exact
   subfolder within the repo. Fixed to clone the whole repo and tell you to
   locate `SKILL.md` yourself in that case, instead of fabricating a path.

## Usage

```bash
python3 find_skills.py "summarize a pdf"
python3 find_skills.py "convert csv to json" --limit 5
python3 find_skills.py "web scraping" --min-stars 10
```

Set `GITHUB_TOKEN` for higher rate limits and the more precise code-search path.

## Status

**built = true**, verified working live against GitHub's API, two real bugs found and fixed during QA.

## Update (2026-07-20) — the real thing now exists

The reel's "Vercel's open skills CLI" is real: the npm package `skills`
(github.com/vercel-labs/skills, maintainer `rauchg`). Verified legitimate and
installed globally: `npm install -g skills`. It does everything this script
approximates, with a real skills.sh registry and install counts, e.g.:

```bash
skills find "summarize a pdf"
skills add <owner/repo@skill>
```

Prefer the real `skills` CLI for actual use; this script remains as a
standalone fallback that needs no npm install, useful in a sandboxed/offline
context.
