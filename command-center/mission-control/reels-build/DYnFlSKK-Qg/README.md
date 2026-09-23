# Chat vs. Cowork vs. Code — Mode Picker

## Source material note

The saved reel for this build (`DYnFlSKK-Qg`) contained no transcript and no
technique description — just a caption line:

> "Chat vs. Cowork vs. Code - Which Should You Use?"

There was nothing concrete to extract a "how-to" from. But the title itself
names a real, recognizable comparison — the three different modes many AI
assistants (including Claude) offer for working with them — so this build is
a reasonable, standalone interpretation of that topic rather than a literal
implementation of "the reel's technique."

## What it does

`pick_mode.py` is a small, offline decision tool. You answer a handful of
yes/no questions about a task, and it scores and recommends which mode fits
best:

- **Chat** — quick questions, brainstorming, short back-and-forth exchanges.
- **Cowork** — longer, multi-step, more autonomous collaboration where you
  check in periodically rather than every turn (research, planning,
  multi-part content projects).
- **Code** — anything touching an actual codebase or needing a shell/file
  access — reading, writing, running, or debugging code.

It's a heuristic scorer, not an AI call — no model, no network request, no
API key. Just a weighted checklist turned into a recommendation.

## How to run it

Requires Python 3.9+ (uses only the standard library — no `pip install`
needed).

**Interactive mode** (it asks you the questions):

```bash
python3 pick_mode.py
```

**Non-interactive / scriptable mode** (pass answers as flags, useful for
automation or quick one-liners):

```bash
python3 pick_mode.py \
  --touches-code n \
  --needs-files-or-shell n \
  --single-quick-question y \
  --multi-step n \
  --long-running-project n \
  --wants-tool-use n \
  --just-thinking-out-loud y
```

See all available questions/flags:

```bash
python3 pick_mode.py --help
```

Any flag you omit in non-interactive mode defaults to "no."

## Setup / API-key notes

None. This tool makes no network calls and requires no API keys, accounts,
or third-party packages — it's a pure Python standard-library script you can
read top to bottom in a couple of minutes.

## Files

- `pick_mode.py` — the tool (CLI, interactive + flag-driven modes).
- `README.md` — this file.
