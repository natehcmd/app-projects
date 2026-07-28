# Behavioral Skills CLAUDE.md

## Source material and what this actually is

The reel this was built from ("Comment KARPATHY and I'll send you the repo") is
comment-for-DM engagement bait. It names four complaints ("over-engineering simple
tasks. Ignoring your instructions. Marking things complete when they're not.
Hallucinating fake APIs.") but never discloses the actual contents of the file it's
promoting — the "170k-star repo" claim isn't independently verifiable from the reel
either, and the whole point of the post is to gate the file behind a comment+DM funnel
rather than describe it.

Rather than fabricate a copy of an unseen repo, this directory implements the concept
the reel is gesturing at from scratch: a small `CLAUDE.md`-style instructions file that
targets exactly the four named complaints, plus a one-shot installer to drop it into
any project.

## What it does

`BEHAVIORAL_SKILLS.CLAUDE.md` is a project-instructions file (the same kind of file
Claude Code reads automatically from a repo root) with four sections of concrete,
checkable rules:

1. **Do not over-engineer** — smallest correct diff, no speculative abstractions.
2. **Do not ignore instructions** — re-check every stated constraint before finishing.
3. **Do not mark things complete when they're not** — no "done" without actually
   running/verifying it.
4. **Do not hallucinate APIs** — don't invent methods/flags/config keys; verify
   against real docs/source or say you couldn't.

`install.py` copies (or merges) that file into a target project as `CLAUDE.md`,
wrapped in `<!-- BEGIN/END behavioral-skills-claude-md -->` markers so re-running it
updates the block in place instead of duplicating it.

## How to run it

No dependencies — just Python 3 (standard library only).

```bash
# Install into the current directory's CLAUDE.md
python3 install.py

# Install into a specific project
python3 install.py /path/to/your/project
```

If the target has no `CLAUDE.md`, one is created. If it already has one, the
behavioral-skills block is appended (or updated in place on re-run) rather than
overwriting the rest of the file.

You can also just copy/paste the contents of `BEHAVIORAL_SKILLS.CLAUDE.md` into an
existing `CLAUDE.md` by hand — the installer is a convenience, not a requirement.

## Setup / API-key notes

None. This is a static instructions file plus a filesystem script — no network calls,
no accounts, no API keys, nothing to authenticate.
