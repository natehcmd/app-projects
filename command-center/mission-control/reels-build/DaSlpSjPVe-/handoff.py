#!/usr/bin/env python3
"""
handoff.py — a tiny "session handoff" system for long Claude Code sessions.

Idea: instead of letting a coding agent's context window fill up with a full
session transcript (context rot -> repeated mistakes, forgotten decisions),
keep a single living HANDOFF.md file that captures just the state a *new*
session needs: current task, decisions made, gotchas hit, and next steps.

When context gets long / a session wraps up, run `snapshot` to pull in a
git-based summary of what changed, then start a fresh Claude Code session
and tell it: "Read HANDOFF.md before doing anything else." That's the whole
trick — cheap, no API keys, no dependencies beyond git (optional).

Usage:
    python3 handoff.py init
    python3 handoff.py task "Refactor auth module to use JWT"
    python3 handoff.py decision "Using PyJWT, not python-jose (fewer deps)"
    python3 handoff.py gotcha "Tests fail if TZ != UTC, set env var in CI"
    python3 handoff.py next "Wire up refresh-token endpoint"
    python3 handoff.py snapshot        # auto-append git status/diff summary
    python3 handoff.py show            # print current HANDOFF.md
    python3 handoff.py clear           # start a fresh handoff (archives old one)
"""

import argparse
import datetime
import shutil
import subprocess
import sys
from pathlib import Path

HANDOFF_FILE = Path("HANDOFF.md")
ARCHIVE_DIR = Path(".handoff_archive")

SECTIONS = ["Current Task", "Key Decisions", "Gotchas / Things That Bit Us", "Next Steps"]

TEMPLATE = """# Handoff Notes

> Read this file first, before doing anything else. It's the compressed
> memory of prior sessions on this project — trust it over guessing.

## Current Task
_(what we're actively working on right now)_

## Key Decisions
_(choices made and why, so they aren't re-litigated or reversed by accident)_

## Gotchas / Things That Bit Us
_(traps, weird behavior, things that wasted time — don't repeat them)_

## Next Steps
_(the immediate next actions for whoever/whatever picks this up)_

## Session Snapshots
_(auto-generated `snapshot` entries — recent git activity at handoff time)_
"""


def ensure_file():
    if not HANDOFF_FILE.exists():
        HANDOFF_FILE.write_text(TEMPLATE)
        print(f"Created {HANDOFF_FILE}")


def append_to_section(section: str, line: str):
    ensure_file()
    text = HANDOFF_FILE.read_text()
    marker = f"## {section}"
    if marker not in text:
        print(f"Section '{section}' not found in {HANDOFF_FILE}; appending at end instead.")
        text += f"\n\n{marker}\n"
        marker_idx = len(text)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"- [{stamp}] {line}\n"

    lines = text.splitlines(keepends=True)
    out = []
    inserted = False
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == marker.strip() and not inserted:
            # skip the italic hint line if present
            j = i + 1
            if j < len(lines) and lines[j].strip().startswith("_("):
                out.append(lines[j])
                i = j
            out.append(entry)
            inserted = True
        i += 1

    if not inserted:
        out.append(f"\n{marker}\n{entry}")

    HANDOFF_FILE.write_text("".join(out))
    print(f"Added to '{section}': {line}")


def cmd_init(_args):
    if HANDOFF_FILE.exists():
        print(f"{HANDOFF_FILE} already exists. Use 'clear' to archive and start fresh.")
        return
    ensure_file()


def cmd_task(args):
    append_to_section("Current Task", args.text)


def cmd_decision(args):
    append_to_section("Key Decisions", args.text)


def cmd_gotcha(args):
    append_to_section("Gotchas / Things That Bit Us", args.text)


def cmd_next(args):
    append_to_section("Next Steps", args.text)


def _git(*cmd):
    try:
        out = subprocess.run(
            ["git", *cmd], capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""


def cmd_snapshot(_args):
    ensure_file()
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    is_git = shutil.which("git") and _git("rev-parse", "--is-inside-work-tree") == "true"
    lines = [f"\n### Snapshot @ {stamp}\n"]

    if is_git:
        branch = _git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
        status = _git("status", "--porcelain")
        last_commit = _git("log", "-1", "--pretty=%h %s")
        changed_files = [l for l in status.splitlines() if l.strip()]

        lines.append(f"- Branch: `{branch}`\n")
        lines.append(f"- Last commit: `{last_commit}`\n" if last_commit else "- Last commit: (none yet)\n")
        if changed_files:
            lines.append(f"- Uncommitted changes ({len(changed_files)} files):\n")
            for f in changed_files[:25]:
                lines.append(f"  - `{f}`\n")
            if len(changed_files) > 25:
                lines.append(f"  - ...and {len(changed_files) - 25} more\n")
        else:
            lines.append("- Working tree clean\n")
    else:
        lines.append("- (not a git repo, or git unavailable — no auto-diff captured)\n")

    with HANDOFF_FILE.open("a") as f:
        f.writelines(lines)
    print(f"Snapshot appended to {HANDOFF_FILE}")


def cmd_show(_args):
    if not HANDOFF_FILE.exists():
        print("No HANDOFF.md yet. Run 'init' first.")
        return
    print(HANDOFF_FILE.read_text())


def cmd_clear(_args):
    if not HANDOFF_FILE.exists():
        print("No HANDOFF.md to archive.")
        ensure_file()
        return
    ARCHIVE_DIR.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = ARCHIVE_DIR / f"HANDOFF-{stamp}.md"
    HANDOFF_FILE.rename(dest)
    print(f"Archived old handoff to {dest}")
    ensure_file()


def main():
    parser = argparse.ArgumentParser(description="Maintain a HANDOFF.md to fight context rot across coding sessions.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create HANDOFF.md from template").set_defaults(func=cmd_init)

    for name, fn, help_text in [
        ("task", cmd_task, "Set/append the current task"),
        ("decision", cmd_decision, "Log a decision and its rationale"),
        ("gotcha", cmd_gotcha, "Log a trap or weird behavior to avoid repeating"),
        ("next", cmd_next, "Add a next step for the next session"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("text", help="The note text")
        p.set_defaults(func=fn)

    sub.add_parser("snapshot", help="Append an auto-generated git status snapshot").set_defaults(func=cmd_snapshot)
    sub.add_parser("show", help="Print the current HANDOFF.md").set_defaults(func=cmd_show)
    sub.add_parser("clear", help="Archive the current HANDOFF.md and start fresh").set_defaults(func=cmd_clear)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
