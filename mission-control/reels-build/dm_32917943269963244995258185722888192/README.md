# Idea Council

A small CLI that puts your business/product idea in front of four AI personas
who argue it out and hand you a verdict — before you spend six months
building the wrong thing.

## Source note

The reel's caption/transcript sidecar file was empty (0 bytes), so this build
is based on directly transcribing the reel's audio track (via whisper.cpp),
not the sidecar. The reel pitches an "idea council" that splits a one-paragraph
idea into four fighting personas — Believer, Skeptic, Investor, and a Judge
that hands down one verdict and remembers the idea so you can revise later
and ask "what changed." This tool implements exactly that, for real, using
the Claude API.

## What it does

You give it your idea in one paragraph. It runs three personas in sequence:

- **The Believer** — makes the strongest case *for* the idea and who needs it.
- **The Skeptic** — attacks the weak points: why people won't pay, the
  competitor you forgot, what you're lying to yourself about.
- **The Investor** — cares about one thing only: would real money show up,
  and how fast.

Then **The Judge** reads the whole debate and hands down one structured
verdict: BUILD IT / KILL IT / VALIDATE FIRST, the reasoning, the single
biggest fatal-flaw risk, and one concrete next step.

Every run is saved locally to `council_history.json` (in this folder, or
wherever `COUNCIL_STORE` points). If you revise an idea and re-run it, the
Judge is shown your *previous* verdict and asked to explicitly compare —
so you can track whether your changes actually helped.

This is a straightforward wrapper around the Claude API and local JSON
storage. It does not scrape anything, evade any detection, or touch anyone
else's data — it only processes text you type in.

## Setup

1. Python 3.10+
2. Install the one dependency **in a venv** — this machine's global `pydantic`
   (pip-installed) and `pydantic-core` (brew-installed) versions conflict, which
   breaks the `anthropic` SDK import if you install system-wide:
   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
   Then run the tool with `.venv/bin/python council.py ...` instead of `python3 council.py ...`.
3. Get an Anthropic API key from https://console.anthropic.com/ and export it:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
   (This is your own API key, billed per Anthropic's normal usage pricing —
   no credentials of any other service are collected or required.)

## Run it

Evaluate a new idea:
```bash
python3 council.py "A subscription box that ships one artisanal dog treat flavor per month, sourced from small US bakeries."
```

List everything you've evaluated so far:
```bash
python3 council.py --history
```

Replay all past verdicts for a saved idea:
```bash
python3 council.py --show <idea_id>
```

Revise an idea and see if the verdict improves (the Judge is shown the prior
verdict and asked to compare):
```bash
python3 council.py --revise <idea_id> "Same box, but now positioned as a vet-recommended allergy-friendly subscription."
```

## Notes / customization

- Model defaults to `claude-sonnet-4-5`; override with `COUNCIL_MODEL`.
- Storage file defaults to `council_history.json` next to the script;
  override with `COUNCIL_STORE` if you want it elsewhere.
- Everything is plain JSON on disk — no database, no server, easy to inspect
  or delete.
