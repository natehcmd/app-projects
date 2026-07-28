#!/usr/bin/env python3
"""
Target Job Project Builder
===========================

Reel summary (dm_32917944601702137096864179318423552):
A skit where a candidate bombs a FAANG interview because his resume is all
talk. "One week later" he goes to learn.nextwork.org, pastes a target job
description into an AI chat box, gets back a custom hands-on project (with a
free step-by-step guide), builds it, and the platform generates polished
"hands-on documentation" he shares to LinkedIn/recruiters. The interviewer
comes back stunned: "you literally built everything."

This script is a small, standalone, self-contained reimplementation of that
core idea -- it does NOT scrape or depend on the nextwork.org product. It
uses your own Anthropic API key to:

  1. Read a target job description and generate a tailored, hands-on
     practice project (with a step-by-step guide) that would let you build
     real, demonstrable experience against that job's required skills.
  2. After you've done the project and jotted a few notes about what you
     actually built, generate a polished "recruiter-ready" write-up /
     LinkedIn blurb summarizing the work -- the same kind of artifact the
     video shows being generated and shared to LinkedIn.

No fraud, no scraping, no bot evasion -- just two ordinary LLM calls wrapping
a genuinely useful "practice for the job you want" workflow.
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print(
        "Missing dependency 'anthropic'. Install it with:\n"
        "    pip install anthropic\n",
        file=sys.stderr,
    )
    sys.exit(1)

MODEL = "claude-sonnet-5"

PROJECT_SYSTEM_PROMPT = """\
You are a senior hiring manager and technical mentor. Given a target job \
description, design ONE concrete, hands-on practice project a candidate \
could build in a few hours to a few days that directly demonstrates the \
skills that job description asks for. Favor real, buildable, verifiable \
work (code, infra, data pipelines, designs) over toy exercises.

Respond in this exact Markdown structure:

# Project: <short punchy title>

## Why this project
2-3 sentences tying it directly to specific requirements/keywords from the
job description.

## Skills you'll demonstrate
- bullet list, pulled from the job description's actual language

## Step-by-step guide
Numbered steps, concrete enough to follow with no extra research for the
first few steps (name specific tools/commands/services where relevant).

## What "done" looks like
A short checklist of concrete deliverables (e.g. a repo, a diagram, a
deployed endpoint, a written doc) that prove the work was completed.
"""

WRITEUP_SYSTEM_PROMPT = """\
You are helping a candidate turn a completed practice project into a short,
concrete, recruiter-ready write-up they can post on LinkedIn or paste into a
resume bullet / cover letter. Ground every claim strictly in the notes and
project plan you're given -- never invent tools, metrics, or outcomes the
candidate didn't mention. If the notes are thin, keep the write-up short
rather than padding it with fabricated detail.

Respond in this exact Markdown structure:

# LinkedIn-ready write-up

## One-line headline
A single sentence, resume-bullet style ("Built X to Y, using Z").

## Short post (3-6 sentences)
A LinkedIn-post-length narrative: what the job/skill gap was, what you
built, what you learned, phrased in first person.

## Resume bullets
2-4 bullets in standard resume format (action verb + what + tool + result).
"""


def read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        print(f"File is empty: {path}", file=sys.stderr)
        sys.exit(1)
    return text


def get_client() -> "anthropic.Anthropic":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "Set ANTHROPIC_API_KEY in your environment first, e.g.:\n"
            "    export ANTHROPIC_API_KEY=sk-ant-...\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return anthropic.Anthropic(api_key=api_key)


def call_claude(system_prompt: str, user_content: str) -> str:
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def cmd_generate_project(args: argparse.Namespace) -> None:
    job_description = read_text(args.job_description)
    print("Generating a custom hands-on project for this job... (calling Claude)")
    project_md = call_claude(
        PROJECT_SYSTEM_PROMPT,
        f"Target job description:\n\n{job_description}",
    )
    out_path = Path(args.out)
    out_path.write_text(project_md + "\n", encoding="utf-8")
    print(f"Wrote project plan to {out_path}")
    print("\nGo build it, take notes on what you actually did, then run:")
    print(f"    python3 {Path(__file__).name} generate-writeup "
          f"--project {out_path} --notes <your_notes.txt>")


def cmd_generate_writeup(args: argparse.Namespace) -> None:
    project_md = read_text(args.project)
    notes = read_text(args.notes)
    print("Generating a recruiter-ready write-up... (calling Claude)")
    writeup_md = call_claude(
        WRITEUP_SYSTEM_PROMPT,
        f"Project plan:\n\n{project_md}\n\n---\n\nMy notes on what I actually built:\n\n{notes}",
    )
    out_path = Path(args.out)
    out_path.write_text(writeup_md + "\n", encoding="utf-8")
    print(f"Wrote write-up to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Turn a target job posting into a hands-on practice project, "
        "then turn the finished project into a recruiter-ready write-up."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p1 = sub.add_parser(
        "generate-project",
        help="Read a job description and generate a custom hands-on project + guide",
    )
    p1.add_argument("--job-description", required=True, help="Path to a text file with the job posting")
    p1.add_argument("--out", default="project_plan.md", help="Where to write the project plan (default: project_plan.md)")
    p1.set_defaults(func=cmd_generate_project)

    p2 = sub.add_parser(
        "generate-writeup",
        help="Turn a completed project + your notes into a LinkedIn/resume write-up",
    )
    p2.add_argument("--project", required=True, help="Path to the project_plan.md from generate-project")
    p2.add_argument("--notes", required=True, help="Path to a text file with your notes on what you built")
    p2.add_argument("--out", default="writeup.md", help="Where to write the write-up (default: writeup.md)")
    p2.set_defaults(func=cmd_generate_writeup)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
