# AI Assembly Line (spec → draft → mass-produce → QA gate)

## Source material and what I actually built

The source reel (`Dalkk16Sy81.txt`) is mostly a comment-to-DM engagement-bait
funnel ("comment FACTORY and I'll DM you the guide") — the four "exact
prompts" it dangles are withheld behind an Instagram DM automation, not given
in the text. I'm not going to build anything that depends on triggering
someone else's DM-automation funnel, and I'm not reproducing prompts I don't
actually have.

However, underneath the bait there's a real, well-known, and genuinely useful
LLM pattern described in enough detail to implement honestly: a **3-tier
model assembly line** for batch content generation —

1. **Spec station** (expensive/smart model, called once): writes a master
   spec for the whole batch *and* an explicit, checkable quality bar. It
   never writes any of the actual output units.
2. **Draft station** (mid-tier model, called once): turns the spec into a
   reusable template/pattern.
3. **Production station** (cheap/fast model, called N times): mass-produces
   the N final units, personalized from a data source.
4. **QA gate** (same expensive model as step 1, called once per batch):
   grades every produced unit against the *exact* quality bar written in
   step 1, and separates passes from fails.

The payoff is real: the expensive model only ever touches the job twice (spec
+ QA) no matter how large the batch is, while the bulk of the token volume
runs on a cheap model — which is the actual mechanism behind the reel's
"pay Luna prices for the labor" claim. I implemented this as a small,
runnable CLI tool using the Claude model family (since that's what's
available here), with Opus as the spec/QA tier, Sonnet as the draft tier,
and Haiku as the production tier — the direct analog of the reel's
Sol/Terra/Luna framing.

## What it does

`assembly_line.py` is a single-file Python CLI that:

- Takes a plain-English description of a batch content job (`--task`) and an
  optional CSV of per-unit personalization data (`--data`, e.g.
  `name,company,pain_point`).
- Runs the 4-station pipeline described above against the Anthropic API.
- Writes every unit (pass or fail) to a JSONL file, along with the QA verdict
  and notes, so you can inspect and re-run just the failures.

It works for anything "write N personalized things from one spec": cold
emails, LinkedIn posts, product descriptions, review responses, etc.

## Setup

1. Python 3.10+.
2. Install the one dependency:
   ```bash
   pip install -r requirements.txt
   ```
3. Get an Anthropic API key from https://console.anthropic.com/settings/keys
   and export it:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   ```
   **This is a paid API** — each run costs real tokens across three model
   tiers. There is no free/local mode. Start with a small `--count` (e.g. 3-5)
   to see costs before running a big batch.

## Running it

Generic batch, no personalization data (produces N generic variants):

```bash
python assembly_line.py \
  --task "10 short LinkedIn posts announcing our new analytics dashboard feature" \
  --count 10 \
  --out posts.jsonl
```

Personalized batch, driven by a CSV (one row = one unit; `--count` is ignored
and the row count is used instead) — a sample CSV is included:

```bash
python assembly_line.py \
  --task "Cold outreach email introducing our analytics tool, referencing the prospect's specific pain point" \
  --data sample_data.csv \
  --out emails.jsonl
```

Useful flags:

- `--spec-model`, `--draft-model`, `--produce-model` — override the model
  used at each station (defaults are Opus / Sonnet / Haiku; point these at
  whatever models your key has access to).
- `--skip-qa` — skip the Station 4 QA gate entirely (cheaper/faster, no
  pass/fail filtering — everything is marked passed).
- `--sleep N` — pause N seconds between production calls if you hit rate
  limits on a large batch.

## Output

`assembly_line_output.jsonl` (or your `--out` path), one JSON object per
line:

```json
{"index": 1, "personalization": {"name": "Alex Rivera", ...}, "output": "...", "passed": true, "qa_notes": "VERDICT: PASS\nNOTES: Meets length and tone requirements."}
```

Failed units keep their `qa_notes` explaining why, so you can tweak the spec
or re-run just those rows.

## Notes / limitations

- This is a straightforward sequential implementation (no concurrency) to
  keep it small and easy to read — for large batches you may want to
  parallelize Station 3 calls yourself.
- The "quality bar" is only as good as what the spec model writes — for
  high-stakes use, read Station 1's spec output before letting Station 3 burn
  through a large batch.
- No scraping, no bot/fraud-evasion, no credential harvesting — this only
  calls the documented Anthropic Messages API with your own key.
