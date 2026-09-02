#!/usr/bin/env python3
"""
init_design_system.py — scaffold a DESIGN.md into a repo and wire it into
Claude Code so it actually gets read.

What this does (no network calls, no scraping, no external repo required):
  1. Copies DESIGN.template.md into the target repo as DESIGN.md.
  2. If a tailwind.config.js/ts is found, best-effort extracts any custom
     `theme.extend.colors` entries and pre-fills the color table so you're
     not starting from all-placeholders.
  3. Ensures the repo's CLAUDE.md (creating one if missing) has a short
     pointer telling Claude Code to read DESIGN.md before doing UI work.

Usage:
    python3 init_design_system.py /path/to/your/repo
    python3 init_design_system.py .                 # current directory

Nothing here is Google's actual repo — the reel that inspired this only
described the *idea* (one file holding your design tokens/components that
the agent reads before building UI) with zero technical detail, so this
generates a solid starting DESIGN.md from scratch rather than pretending to
reproduce something that was never shown.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(HERE, "DESIGN.template.md")

CLAUDE_MD_POINTER = """
## Design system

Before building or editing any UI (pages, components, styles), read
`DESIGN.md` in the repo root and follow it. It defines the color palette,
spacing scale, typography, and reusable components for this project. If a
request conflicts with it, say so instead of guessing.
"""


def find_tailwind_config(repo_dir):
    for name in ("tailwind.config.js", "tailwind.config.ts", "tailwind.config.cjs"):
        path = os.path.join(repo_dir, name)
        if os.path.isfile(path):
            return path
    return None


def extract_colors(tailwind_config_path):
    """Best-effort regex scrape of `key: '#hex'` pairs inside the file.
    Not a real JS parser — good enough to pre-fill placeholders, nothing more.
    """
    try:
        with open(tailwind_config_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return {}

    colors = {}
    for match in re.finditer(r"['\"]?([a-zA-Z0-9_-]+)['\"]?\s*:\s*['\"](#[0-9a-fA-F]{3,8})['\"]", content):
        key, hex_value = match.groups()
        colors[key.lower()] = hex_value
    return colors


def guess_placeholder_fill(colors):
    """Map whatever custom colors we found to the template's placeholder
    tokens on a best-effort basis. Anything unmatched stays a placeholder.
    """
    fill = {}
    keyword_map = {
        "BG": ["background", "bg"],
        "SURFACE": ["surface", "card", "panel"],
        "BORDER": ["border", "outline"],
        "TEXT_PRIMARY": ["text", "foreground", "ink"],
        "TEXT_SECONDARY": ["muted", "subtle", "secondary"],
        "ACCENT": ["accent", "primary", "brand"],
        "ACCENT_HOVER": ["accenthover", "primaryhover"],
        "SUCCESS": ["success", "green"],
        "WARNING": ["warning", "amber", "yellow"],
        "DANGER": ["danger", "error", "destructive", "red"],
    }
    for placeholder, keywords in keyword_map.items():
        for kw in keywords:
            if kw in colors:
                fill[placeholder] = colors[kw]
                break
    return fill


def render_template(fill):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    for key, value in fill.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def ensure_claude_md_pointer(repo_dir):
    claude_md_path = os.path.join(repo_dir, "CLAUDE.md")
    if os.path.isfile(claude_md_path):
        with open(claude_md_path, "r", encoding="utf-8") as f:
            existing = f.read()
        if "DESIGN.md" in existing:
            print("CLAUDE.md already references DESIGN.md — leaving it alone.")
            return
        with open(claude_md_path, "a", encoding="utf-8") as f:
            f.write("\n" + CLAUDE_MD_POINTER)
        print(f"Appended a DESIGN.md pointer to {claude_md_path}")
    else:
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write("# Project Instructions\n" + CLAUDE_MD_POINTER)
        print(f"Created {claude_md_path} with a DESIGN.md pointer")


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold a DESIGN.md into a repo and wire it into Claude Code.",
        epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo_dir", help="Path to the target repo (use '.' for the current directory)")
    args = parser.parse_args()

    repo_dir = os.path.abspath(args.repo_dir)
    if not os.path.isdir(repo_dir):
        print(f"Error: {repo_dir} is not a directory")
        sys.exit(1)

    design_md_path = os.path.join(repo_dir, "DESIGN.md")
    if os.path.exists(design_md_path):
        print(f"Error: {design_md_path} already exists. Remove it first if you want to regenerate.")
        sys.exit(1)

    tailwind_config = find_tailwind_config(repo_dir)
    fill = {}
    if tailwind_config:
        colors = extract_colors(tailwind_config)
        fill = guess_placeholder_fill(colors)
        if fill:
            print(f"Found {tailwind_config}, pre-filled {len(fill)} color token(s) from it.")
        else:
            print(f"Found {tailwind_config} but couldn't confidently map any colors — leaving placeholders.")
    else:
        print("No tailwind.config found — DESIGN.md will be all placeholders, fill them in by hand.")

    rendered = render_template(fill)
    with open(design_md_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"Wrote {design_md_path}")

    ensure_claude_md_pointer(repo_dir)

    print("\nDone. Next steps:")
    print(f"  1. Open {design_md_path} and fill in the remaining {{{{PLACEHOLDER}}}} values.")
    print("  2. Commit it. Claude Code will now read it before touching UI code.")


if __name__ == "__main__":
    main()
