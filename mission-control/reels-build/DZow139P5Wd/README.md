# slop_check.py — offline "fix your slop" linter

## Source

> @leon.commits.code: Fix your slop bro 😭 Comment "Slop" for the link.

Pure comment-for-DM engagement bait — no tool was ever named or linked. The
one real, buildable idea is the concept itself: a local static-analysis pass
that flags common signs of rushed/AI-generated code ("slop").

## What it does

Dependency-free scanner (stdlib only) for placeholders, swallowed
exceptions, copy-pasted lines, giant functions, deep nesting, generic
variable names, debug leftovers, and possible hardcoded secrets.

## Verified working (2026-07-20)

Ran against a real file (`../DZdkrPthOoM/scan.py`) and a synthetic
deeply-nested test file. Found and fixed a real bug: `check_deep_nesting`
used raw indentation depth with no awareness of multi-line function-call
continuation lines (e.g. keyword args each on their own indented line),
producing 16 false positives on one well-formatted 377-line file. Fixed by
tracking open-bracket depth across lines and only flagging nesting when not
inside a continued call — false positives dropped from 16 to 0, and it still
correctly catches real deep nesting (verified on a synthetic 6-level-deep
`if` chain).

## Usage

```bash
python3 slop_check.py [PATH] [--ext .py,.js,.ts] [--json out.json] [--top N]
```

## Status

**built = true**, verified working, one real false-positive bug found and fixed during QA.
