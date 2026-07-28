#!/usr/bin/env python3
"""
skillkit.py — a small, self-contained CLI for scaffolding and linting
Claude Code "Skills" (SKILL.md files).

Why this exists
----------------
The source reel is hype-y and doesn't describe any concrete technique
("a few well-made skills" improve planning/memory/design — no mechanism
given). What IS real and well-documented is Claude Code's actual Skills
feature: a skill is a directory containing a SKILL.md file with YAML
frontmatter (name + description) plus instructions Claude reads and
follows when the description matches the user's request. The single
biggest lever for whether a skill actually "auto-discovers" correctly
is whether that description is written well.

So instead of inventing a fake magic technique, this tool implements the
one concrete, checkable practice that actually matters for skills: a
good SKILL.md. It gives you:

  1. `new`  — scaffold a well-formed skill directory from a template
  2. `lint` — check an existing SKILL.md against known good/bad patterns
  3. `list` — summarize all skills in a directory (e.g. ~/.claude/skills)

No API key, no network access, no dependencies beyond the Python
standard library.

Usage
-----
    python3 skillkit.py new my-skill-name --dir ./skills
    python3 skillkit.py lint ./skills/my-skill-name/SKILL.md
    python3 skillkit.py list ~/.claude/skills

Run `python3 skillkit.py --help` for full options.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TEMPLATE = """---
name: {name}
description: >
  {description}
---

# {title}

## When to use this skill
Describe the concrete situation that should trigger this skill. Be specific
about trigger phrases/tasks — this text (plus the frontmatter description)
is what Claude matches against, so vague descriptions mean the skill never
fires and specific ones mean it fires at the wrong time.

## Steps
1. First concrete step.
2. Second concrete step.
3. ...

## Notes / gotchas
- Anything a future run of this skill should know to avoid repeating a
  mistake.
"""

DEFAULT_DESCRIPTION_PLACEHOLDER = (
    "One or two sentences: WHAT this skill does and WHEN to trigger it "
    "(name the exact task/phrases a user would say). Write it in third "
    "person, describing the skill rather than speaking as it."
)

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

# Words/phrases that signal a description is too vague to reliably
# trigger skill auto-discovery (the "automatic skill discovery" the
# source reel gestures at, but doesn't explain).
VAGUE_PHRASES = [
    "helps with",
    "useful for",
    "various tasks",
    "general purpose",
    "does stuff",
    "misc",
    "etc.",
]

FIRST_PERSON_RE = re.compile(r"\bI\s+(will|can|am|help)\b", re.IGNORECASE)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Very small YAML-frontmatter parser for the two fields we care
    about (name, description). Not a general YAML parser on purpose —
    this tool has zero dependencies."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw, body = parts[1], parts[2]

    fields: dict[str, str] = {}
    current_key = None
    for line in fm_raw.splitlines():
        if not line.strip():
            continue
        m = re.match(r"^(\w[\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val in (">", "|", ""):
                current_key = key
                fields[key] = ""
            else:
                fields[key] = val.strip('"').strip("'")
                current_key = None
        elif current_key and line.startswith((" ", "\t")):
            fields[current_key] = (fields[current_key] + " " + line.strip()).strip()
    return fields, body


def cmd_new(args: argparse.Namespace) -> int:
    name = args.name
    if not NAME_RE.match(name):
        print(
            f"error: '{name}' is not a good skill name. Use lowercase "
            "letters, digits, and hyphens only (e.g. 'pdf-report-builder').",
            file=sys.stderr,
        )
        return 1

    out_dir = Path(args.dir).expanduser() / name
    if out_dir.exists() and not args.force:
        print(f"error: {out_dir} already exists (use --force to overwrite)", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)

    title = name.replace("-", " ").title()
    content = TEMPLATE.format(
        name=name,
        description=DEFAULT_DESCRIPTION_PLACEHOLDER,
        title=title,
    )
    skill_file = out_dir / "SKILL.md"
    skill_file.write_text(content)

    (out_dir / "resources").mkdir(exist_ok=True)
    (out_dir / "resources" / ".gitkeep").write_text("")

    print(f"Created skill scaffold at {out_dir}")
    print(f"  - {skill_file}")
    print(f"  - {out_dir / 'resources'}/  (put reference files, scripts, templates here)")
    print("\nNext: edit the description in SKILL.md, then run:")
    print(f"  python3 {Path(__file__).name} lint {skill_file}")
    return 0


def lint_text(text: str, path_label: str) -> list[str]:
    issues: list[str] = []
    fields, body = parse_frontmatter(text)

    if not fields:
        issues.append("No YAML frontmatter found (must start with '---' ... '---').")
        return issues

    name = fields.get("name", "")
    desc = fields.get("description", "")

    if not name:
        issues.append("Missing 'name' field in frontmatter.")
    elif not NAME_RE.match(name):
        issues.append(
            f"'name: {name}' should be lowercase letters/digits/hyphens only, 2-64 chars."
        )

    if not desc:
        issues.append("Missing 'description' field in frontmatter — skill will never auto-trigger.")
    else:
        if len(desc) < 20:
            issues.append("Description is very short — too vague to trigger reliably.")
        if len(desc) > 500:
            issues.append("Description is very long — trim to the essential trigger conditions.")
        lowered = desc.lower()
        for phrase in VAGUE_PHRASES:
            if phrase in lowered:
                issues.append(f"Description contains vague phrase '{phrase}' — be concrete about WHEN to use this.")
        if FIRST_PERSON_RE.search(desc):
            issues.append("Description uses first person ('I will...') — write it in third person, describing what/when.")
        if "when" not in lowered and "use" not in lowered and "trigger" not in lowered:
            issues.append(
                "Description doesn't obviously state WHEN to use the skill "
                "(no 'when'/'use'/'trigger' language) — auto-discovery depends on this."
            )

    if len(body.strip()) < 30:
        issues.append("Skill body is nearly empty — add concrete steps, not just a title.")

    if not issues:
        return []
    return [f"[{path_label}] {msg}" for msg in issues]


def cmd_lint(args: argparse.Namespace) -> int:
    path = Path(args.path).expanduser()
    if path.is_dir():
        path = path / "SKILL.md"
    if not path.exists():
        print(f"error: {path} not found", file=sys.stderr)
        return 1

    text = path.read_text()
    issues = lint_text(text, str(path))

    if not issues:
        print(f"OK  {path} — looks good.")
        return 0

    print(f"{len(issues)} issue(s) found in {path}:\n")
    for issue in issues:
        print(f"  - {issue.split('] ', 1)[-1]}")
    return 1


def cmd_list(args: argparse.Namespace) -> int:
    root = Path(args.dir).expanduser()
    if not root.exists():
        print(f"error: {root} not found", file=sys.stderr)
        return 1

    skill_files = sorted(root.glob("*/SKILL.md"))
    if not skill_files:
        print(f"No SKILL.md files found under {root}")
        return 0

    total_issues = 0
    for sf in skill_files:
        text = sf.read_text()
        fields, _ = parse_frontmatter(text)
        issues = lint_text(text, sf.parent.name)
        total_issues += len(issues)
        flag = "!" if issues else " "
        name = fields.get("name", sf.parent.name)
        desc = fields.get("description", "(no description)")
        desc_short = (desc[:90] + "...") if len(desc) > 90 else desc
        print(f"[{flag}] {name:<28} {desc_short}")

    print(f"\n{len(skill_files)} skill(s), {total_issues} lint issue(s) total.")
    print("Run with 'lint <path>' on any flagged skill for details.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="skillkit.py",
        description="Scaffold and lint Claude Code Skills (SKILL.md files).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Scaffold a new skill directory.")
    p_new.add_argument("name", help="Skill name, e.g. 'pdf-report-builder'")
    p_new.add_argument("--dir", default="./skills", help="Parent directory to create the skill in (default: ./skills)")
    p_new.add_argument("--force", action="store_true", help="Overwrite if the skill directory already exists")
    p_new.set_defaults(func=cmd_new)

    p_lint = sub.add_parser("lint", help="Lint a SKILL.md file (or a directory containing one).")
    p_lint.add_argument("path", help="Path to SKILL.md or a skill directory")
    p_lint.set_defaults(func=cmd_lint)

    p_list = sub.add_parser("list", help="List and summarize all skills under a directory.")
    p_list.add_argument("dir", nargs="?", default="~/.claude/skills", help="Directory containing skill subfolders (default: ~/.claude/skills)")
    p_list.set_defaults(func=cmd_list)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
