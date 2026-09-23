# Skill Scanner

## Where this came from

Reel `DactwNnswpk` ("I check skills for danger by pasting them into Claude")
is mostly engagement bait — the caption withholds the actual prompts behind a
"comment 'secure' and I'll DM you" hook, and the video itself only describes
the workflow in one loose sentence:

> "A downloaded skill can run code on your computer, so before I install
> anything I paste it into a Claude chat and have Claude flag anything
> sketchy first. Then customize and save."

There's no concrete prompt, method, or checklist given in the source
material. Rather than decline (this isn't unsafe or hype-with-nothing-under-
it — it's a genuinely reasonable security habit, just described vaguely),
this build implements the most useful standalone version of that workflow:
**a script that automates "paste it into Claude and have it flag anything
sketchy" so you don't have to do it by hand for every download.**

## What it does

`skill_scanner.py` takes a path to a downloaded "skill" (a folder or a
single script — works for Claude Agent Skills, shell installers, small
Python/Node packages, etc.) that you're about to install, and:

1. **Local static heuristics (offline, no API key needed).** Scans every
   text/code file for common red-flag patterns: curl-pipe-to-shell,
   reverse-shell patterns, reads of SSH keys / AWS credentials / browser
   credential stores, exfil to pastebin/webhook-style endpoints, raw-IP
   network calls, suspicious base64 blobs, `eval`/`exec` of remote content,
   persistence via cron/shell-rc files, and more. Each hit is scored
   high/medium/low with the exact file and line.
2. **Optional Claude second opinion.** If `ANTHROPIC_API_KEY` is set (and
   the `anthropic` package is installed), it bundles up the skill's source
   and sends it to Claude with a security-reviewer system prompt — the
   scripted version of "paste it into a Claude chat and have it flag
   anything sketchy." Claude returns a verdict (SAFE / CAUTION /
   DANGEROUS), a plain-English summary of what the code actually does, and
   a list of concrete concerns. This step also explicitly checks for
   prompt-injection attempts aimed at an AI agent reading the file.
3. **A combined report**, and a non-zero exit code if anything high-severity
   turned up — so you can wire it into a pre-install check.

It **never executes, installs, or modifies** the skill. It only reads files
and reports on them — a read-only review tool, exactly like the manual
"paste it into Claude" habit described in the reel.

## How to run it

```bash
cd /Users/natehoward/Projects/mission-control/reels-build/DactwNnswpk

# Optional but recommended, for the Claude second opinion:
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

# Scan a downloaded skill folder or single script before installing it:
python3 skill_scanner.py ~/Downloads/some-new-skill/

# Local heuristics only (no API calls, no key needed):
python3 skill_scanner.py ~/Downloads/some-new-skill/ --no-claude

# Pick a different Claude model:
python3 skill_scanner.py ~/Downloads/some-new-skill/ --model claude-opus-4-1-20250805
```

A deliberately sketchy `example_skill/install.sh` is included so you can see
the scanner in action immediately:

```bash
python3 skill_scanner.py example_skill --no-claude
```

That should print several HIGH-severity findings (curl-pipe-to-shell,
SSH-key read + exfil to a webhook, etc.) and exit with a non-zero status.

## Setup / API key notes

- **No API key required** for the local heuristics pass (`--no-claude`) —
  it's pure regex-based static analysis, works fully offline.
- **For the Claude review**, you need:
  - `pip install anthropic` (already in `requirements.txt`)
  - an Anthropic API key from https://console.anthropic.com/, exported as
    `ANTHROPIC_API_KEY`
  - this will make a real API call per scan and will incur normal API
    usage costs; the script caps the bundled source at ~1.5MB to keep
    requests reasonable.
- If the key or package is missing, the script still runs — it just skips
  the Claude section and tells you why, so the local heuristics report is
  always available.

## Limitations (read before trusting the output blindly)

- Static heuristics are pattern-based and will have both false positives
  (e.g. legitimate `sudo` usage) and false negatives (heavily obfuscated or
  multi-stage malicious code can slip through).
- The Claude review is a second opinion, not a guarantee — treat CAUTION/
  DANGEROUS verdicts as a strong signal to dig further by hand, and treat a
  clean SAFE verdict as "nothing obvious jumped out," not a formal audit.
- This tool only reads and reports; it doesn't sandbox or actually run the
  skill, so it can't catch behavior that only manifests at runtime (e.g.
  logic that only turns malicious under specific conditions).
