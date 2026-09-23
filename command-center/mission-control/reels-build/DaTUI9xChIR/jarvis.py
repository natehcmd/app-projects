#!/usr/bin/env python3
"""
Jarvis Command Assistant
========================

A small, pluggable "command assistant" you can talk to in plain English.
It parses a natural-language instruction, decides which *skill* it maps to,
and dispatches it. Ships with two skills, inspired by the reel this repo
was built for:

  1. instagram_post  -> publish a video to Instagram, using Meta's official
                         Instagram Graph API (requires your own app + token).
  2. hardware_trigger -> send an "open"/"close"/"fire" style command to a
                          local hardware gadget over a serial connection
                          (e.g. an Arduino-driven servo/solenoid rig).
                          Ships with a --dry-run simulator so it's runnable
                          with zero hardware attached.

Nothing here scrapes Instagram, automates a logged-in browser session, or
evades any platform's bot/fraud detection. Posting uses the official,
documented Graph API and your own developer credentials. Hardware control
talks to a device *you* own over a serial cable — it does not touch anyone
else's systems.

Usage
-----
    python jarvis.py "post video clip.mp4 with caption 'launch day!'"
    python jarvis.py "fire the web shooter" --dry-run
    python jarvis.py --interactive

See README.md for full setup instructions.
"""

from __future__ import annotations

import argparse
import re
import shlex
import sys
from dataclasses import dataclass
from typing import Optional

from skills.instagram_post import post_video_to_instagram, InstagramConfigError
from skills.hardware_trigger import send_hardware_command, HardwareError


@dataclass
class ParsedCommand:
    skill: str
    args: dict


class UnknownCommand(Exception):
    pass


# --- very small rule-based NLU -------------------------------------------
# Real "Jarvis" style assistants can swap this out for an LLM call; keeping
# it regex-based here keeps the project runnable offline with no API key
# required just to try it out.

POST_RE = re.compile(
    r"post\s+(?:a\s+)?video\s+(?P<path>\S+)"
    r"(?:\s+(?:with\s+)?caption\s+(?P<caption>.+))?",
    re.IGNORECASE,
)

HARDWARE_RE = re.compile(
    r"(?:fire|trigger|activate|open|close)\s+(?:the\s+)?(?P<device>[\w\- ]+)",
    re.IGNORECASE,
)


def parse_command(text: str) -> ParsedCommand:
    text = text.strip()

    m = POST_RE.search(text)
    if m:
        caption = m.group("caption") or ""
        caption = caption.strip().strip("'\"")
        return ParsedCommand(skill="instagram_post", args={
            "path": m.group("path"),
            "caption": caption,
        })

    m = HARDWARE_RE.search(text)
    if m:
        action_word = text.split()[0].lower()
        return ParsedCommand(skill="hardware_trigger", args={
            "device": m.group("device").strip(),
            "action": action_word,
        })

    raise UnknownCommand(f"Couldn't map this to a known skill: {text!r}")


def dispatch(cmd: ParsedCommand, dry_run: bool) -> str:
    if cmd.skill == "instagram_post":
        return post_video_to_instagram(
            video_path=cmd.args["path"],
            caption=cmd.args["caption"],
            dry_run=dry_run,
        )
    if cmd.skill == "hardware_trigger":
        return send_hardware_command(
            device=cmd.args["device"],
            action=cmd.args["action"],
            dry_run=dry_run,
        )
    raise UnknownCommand(f"No handler registered for skill {cmd.skill!r}")


def run_once(text: str, dry_run: bool) -> None:
    try:
        cmd = parse_command(text)
        result = dispatch(cmd, dry_run=dry_run)
        print(f"[jarvis] {result}")
    except UnknownCommand as e:
        print(f"[jarvis] Sorry, I don't understand that yet: {e}")
    except (InstagramConfigError, HardwareError) as e:
        print(f"[jarvis] Skill error: {e}")


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Jarvis command assistant")
    parser.add_argument("command", nargs="?", help="Natural-language command to run")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate the action instead of calling the real API/hardware",
    )
    parser.add_argument(
        "--interactive", action="store_true",
        help="Drop into a REPL and keep accepting commands",
    )
    args = parser.parse_args(argv)

    if args.interactive:
        print("Jarvis ready. Type a command, or 'quit' to exit.")
        while True:
            try:
                line = input("jarvis> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if line.lower() in {"quit", "exit"}:
                break
            if not line:
                continue
            run_once(line, dry_run=args.dry_run)
        return 0

    if not args.command:
        parser.print_help()
        return 1

    run_once(args.command, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
