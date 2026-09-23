# App Stage Advisor

## Where this came from

The source reel (`DYkjSXcA45p`) is a short motivational hook, not a
tutorial:

> "Vibing an app is not hard. Growing an app ain't easy. Scaling one though,
> good luck. Stop thinking you can do this on your own, because you can't."

There's no method, workflow, or named tool in the transcript — it's an
engagement-bait lead-in (likely to a coaching/course pitch). But it does name
three real, distinct stages of building an app — **vibing** (prototyping),
**growing** (getting real usage), and **scaling** (surviving real load) — and
implies that each stage needs help you can't provide alone. That's a real,
useful idea even without a concrete technique attached to it, so this tool
builds the missing piece: a way to figure out which stage you're actually in
and what to do about it.

## What it does

`app_stage_advisor.py` is a CLI. You give it a few numbers about your app
(monthly active users, month-over-month growth, revenue, team size, a
self-rated "infra pain" score, and churn), and it:

1. Classifies you into **Vibing**, **Growing**, or **Scaling**, with a
   one-line explanation of why.
2. Lists the specific risks people hit at that stage.
3. Gives a concrete checklist of next moves for that stage.
4. Names what you likely can't do solo at that stage — the "you can't do
   this on your own" part of the reel, made concrete (e.g. "honest outside
   feedback" at the prototype stage vs. "a second on-call engineer" at the
   scaling stage).

It's a self-assessment/diagnostic tool, not a growth-hacking or scaling
automation tool — it just replaces the reel's vague hype with something you
can actually run and act on.

## How to run it

Requires Python 3.7+, no third-party packages.

**Interactive mode** (prompts for each value, with sane defaults):

```bash
python3 app_stage_advisor.py
```

**Flag mode** (scriptable, e.g. from a dashboard or cron job):

```bash
python3 app_stage_advisor.py \
  --mau 1200 \
  --growth 12 \
  --revenue 800 \
  --team 2 \
  --infra-pain 2 \
  --churn 5
```

**JSON output** (for piping into another tool):

```bash
python3 app_stage_advisor.py --mau 1200 --growth 12 --revenue 800 \
  --team 2 --infra-pain 2 --churn 5 --json
```

Run `python3 app_stage_advisor.py --help` for the full flag list.

## Setup / API-key notes

None. This is a pure-stdlib Python script — no dependencies, no network
calls, no API keys, no accounts. It only reads the numbers you give it and
applies a fixed set of thresholds/rules; nothing is sent anywhere.

## Files

- `app_stage_advisor.py` — the whole tool (single file, ~200 lines).
- `README.md` — this file.
