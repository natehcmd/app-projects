#!/usr/bin/env python3
"""
install.py — drop BEHAVIORAL_SKILLS.CLAUDE.md into a target project's CLAUDE.md.

Usage:
    python3 install.py [TARGET_DIR]

If TARGET_DIR is omitted, defaults to the current directory.

Behavior:
    - If TARGET_DIR/CLAUDE.md does not exist, it is created from
      BEHAVIORAL_SKILLS.CLAUDE.md.
    - If TARGET_DIR/CLAUDE.md already exists, the behavioral skills block is
      appended under a clearly marked heading (idempotent — running it twice
      won't duplicate the block).
"""
import argparse
import sys
from pathlib import Path

MARKER = "<!-- BEGIN behavioral-skills-claude-md -->"
END_MARKER = "<!-- END behavioral-skills-claude-md -->"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Drop BEHAVIORAL_SKILLS.CLAUDE.md into a target project's CLAUDE.md (idempotent).")
    parser.add_argument("target_dir", nargs="?", default=".",
                         help="Target project directory (defaults to the current directory)")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    source = script_dir / "BEHAVIORAL_SKILLS.CLAUDE.md"
    if not source.exists():
        print(f"error: {source} not found", file=sys.stderr)
        return 1

    target_dir = Path(args.target_dir)
    if not target_dir.is_dir():
        print(f"error: {target_dir} is not a directory", file=sys.stderr)
        return 1

    target = target_dir / "CLAUDE.md"
    block = f"{MARKER}\n{source.read_text()}\n{END_MARKER}\n"

    if not target.exists():
        target.write_text(block)
        print(f"created {target}")
        return 0

    existing = target.read_text()
    if MARKER in existing:
        # Replace the existing block in place so re-running updates it.
        start = existing.index(MARKER)
        end = existing.index(END_MARKER) + len(END_MARKER)
        updated = existing[:start] + block.rstrip("\n") + existing[end:]
        target.write_text(updated)
        print(f"updated behavioral skills block in {target}")
    else:
        with target.open("a") as f:
            if not existing.endswith("\n"):
                f.write("\n")
            f.write("\n" + block)
        print(f"appended behavioral skills block to {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
