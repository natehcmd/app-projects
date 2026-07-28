# Forge Loop

A small, self-contained implementation of the "Forge Loop" self-critique
technique described in reel `DarPBb4sxlg`.

## Why this exists / what was in the source material

The reel (`@nocodealex`) describes a technique at a high level — a
standing instruction that makes Claude critique and fix its own drafts
before you ever see them — but withholds the actual prompt text and
rubric behind a "comment EVOLVE and I'll DM it to you" gate. That's
classic comment-for-link engagement bait, and the reel itself contains no
runnable spec, only a description of the shape:

1. Claude drafts something.
2. Claude switches roles and attacks its own draft "like a stranger wrote
   it," scoring it 0-100 against a rubric covering **correct, complete,
   clear, consistent, tested**.
3. Claude fixes exactly the issues it found (not more, not less).
4. Repeat until the score clears ~90 with zero open issues, then stop.
5. The score is supposed to visibly climb loop by loop (e.g. 61, 74, 85,
   92).

Rather than fabricate a "leaked" version of whatever prompt the original
poster is DM-gating, this is an independent, working implementation of
that same idea, built as a runnable tool instead of a copy-pasted prompt
snippet.

## What it does

`forge_loop.py` is a CLI that:

- Takes a task description (and optionally an existing draft to refine).
- Generates a first draft via the Claude API.
- Loops: asks Claude to grade its own current draft against the 5-part
  rubric, list every concrete issue, and produce a revised draft that
  fixes exactly those issues (structured JSON output, not free text, so
  the loop can reliably parse the score and decide whether to continue).
- Stops when the score is `>= --pass-score` (default 90) **and** there
  are zero open issues, or after `--max-iterations` (default 6) — a hard
  cap so a model that can't converge doesn't loop (and bill) forever.
  This caps the "auto-rerun" idea from the reel with an actual safety
  limit, since "no cap, run until 90+" is a real cost/runaway risk for a
  script (a human watching a chat UI can just stop it; a script can't).
- Prints the score trajectory and every issue found at each iteration to
  stderr, and writes the final draft to a file.

## Setup

```bash
cd reels-build/DarPBb4sxlg
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### API key

This uses the official `anthropic` Python SDK, which resolves credentials
automatically. You need one of:

- `export ANTHROPIC_API_KEY=sk-ant-...` (get one at
  https://console.anthropic.com/), or
- Run `ant auth login` if you have the Anthropic CLI installed (stores a
  profile the SDK picks up automatically — no env var needed).

No key is hardcoded anywhere in the script.

## Run it

```bash
python forge_loop.py --task "Write a cancellation email for a SaaS customer who churned after 3 months" --output final.md
```

Refine an existing draft instead of generating a fresh one:

```bash
python forge_loop.py --task "Tighten this onboarding doc for clarity" --input-file draft.md --output final.md
```

Tune the loop:

```bash
python forge_loop.py --task "..." --pass-score 95 --max-iterations 10 --model claude-opus-4-8
```

Add your own grading rules on top of the base rubric (the reel's "add
this to your rubric, and that mistake stops showing up" idea):

```bash
python forge_loop.py --task "..." --rubric-note "Must stay under 200 words" --rubric-note "Never use the word 'leverage'"
```

## Notes / caveats

- **Cost**: each iteration is 1 API call at `effort: high` with adaptive
  thinking on `claude-opus-4-8`. A 4-iteration run on a short task is a
  handful of calls — cheap, but not free. Use `--model claude-sonnet-5`
  or lower `--max-iterations` if you're running this a lot.
- **This is self-grading**, same as the reel describes — Claude grades
  its own work, not an independent reviewer. That's a real limitation,
  not just a caveat: a model can be systematically blind to its own
  mistakes in ways a second, independent grading pass wouldn't be. If you
  want more rigor, the `--rubric-note` mechanism lets you feed back
  specific failure patterns you've observed, which is the reel's stated
  workaround ("say 'add this to your rubric' once, and that category of
  mistake stops showing up").
- **Structured output**: the critique/revise step uses
  `output_config.format` (JSON schema) rather than asking for free-form
  text and hoping to parse a score out of it — this is a Claude API
  feature ([Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)),
  not something invented for this script.
