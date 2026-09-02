#!/usr/bin/env python3
"""Resume optimizer — runs the exact 3-prompt sequence from the source reel
against your resume + a target job description, using the local `claude` CLI
so the whole thing stays on your own machine and your own Claude session
(no third-party service, no API key needed beyond what Claude Code already
uses).

Usage:
    python3 resume_optimizer.py --resume resume.txt --job job_description.txt
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROMPT_1 = """Act as a senior recruiter for this exact company. Analyze my resume against \
this job description and give me a match score out of 100, the top 5 missing \
keywords, and the 3 red flags a hiring manager would spot in under 10 seconds.

RESUME:
{resume}

JOB DESCRIPTION:
{job}"""

PROMPT_2 = """Rewrite my experience section to naturally include those keywords and remove \
the red flags. Use the Google XYZ formula: Accomplish X as measured by Y by doing Z."""

PROMPT_3 = """Now act as an ATS filter and a hiring manager reading 200 resumes in one \
sitting. Scan my new resume and tell me which sections would get skipped, then \
rewrite them so they actually stop the scroll."""


def find_claude():
    for candidate in [str(Path.home() / ".npm-global/bin/claude"),
                       "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    found = shutil.which("claude")
    if found:
        return found
    print("Couldn't find the claude CLI on PATH.", file=sys.stderr)
    sys.exit(1)


def run_claude(claude_path, prompt, session_id=None):
    cmd = [claude_path, "-p", prompt, "--permission-mode", "acceptEdits",
           "--output-format", "json"]
    if session_id:
        cmd += ["--resume", session_id]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        print(f"claude exited {result.returncode}: {result.stderr[:400]}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def extract_session_id(json_output):
    import json
    try:
        return json.loads(json_output).get("session_id")
    except Exception:
        return None


def extract_result(json_output):
    import json
    try:
        return json.loads(json_output).get("result", json_output)
    except Exception:
        return json_output


def main():
    parser = argparse.ArgumentParser(description="Run the reel's 3-prompt resume optimizer sequence.")
    parser.add_argument("--resume", required=True, help="Path to your resume (plain text or markdown)")
    parser.add_argument("--job", required=True, help="Path to the target job description")
    parser.add_argument("--out", default="resume_optimizer_output.md", help="Where to save the full transcript")
    args = parser.parse_args()

    resume_text = Path(args.resume).read_text()
    job_text = Path(args.job).read_text()
    claude_path = find_claude()

    transcript = []
    print("[1/3] Scoring resume against job description...")
    out1 = run_claude(claude_path, PROMPT_1.format(resume=resume_text, job=job_text))
    session_id = extract_session_id(out1)
    transcript.append("## Step 1 — Match score & gaps\n\n" + extract_result(out1))

    print("[2/3] Rewriting experience section...")
    out2 = run_claude(claude_path, PROMPT_2, session_id=session_id)
    transcript.append("## Step 2 — Rewritten experience section\n\n" + extract_result(out2))

    print("[3/3] ATS/hiring-manager scan pass...")
    out3 = run_claude(claude_path, PROMPT_3, session_id=session_id)
    transcript.append("## Step 3 — ATS scan & final polish\n\n" + extract_result(out3))

    Path(args.out).write_text("# Resume Optimizer Output\n\n" + "\n\n---\n\n".join(transcript))
    print(f"\nDone. Full transcript saved to {args.out}")


if __name__ == "__main__":
    main()
