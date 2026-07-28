# DZqg7QoMKI4 — Prompt Macro Expander

## Original verdict (text-only)

Cached caption was just "My most kept secret" — declined as nothing buildable.

## Re-reviewed via video (2026-07-20)

Watching the actual clip found real content the caption didn't capture: an
on-screen list titled "Claude Command Secret Codes" — 13 named prompt-prefix
shortcuts (`/godmode`, `/devil`, `/10x`, `/pitch`, `/ghost`, `/compare`,
`/scout`, `/artifacts`, `/ooda`, `/critique`, `/explainlikeim5`, `/brief`,
`/teacher`), each with a one-line description. These are the creator's own
prompt macros, not real Claude Code slash commands — gated behind "comment
'all' to get 90+ detailed commands," but the visible 13 were fully legible.

## What was built

`prompt_macros.py` — implements all 13 macros as real expandable prefixes:

```bash
python3 prompt_macros.py list
python3 prompt_macros.py expand /critique "review this function for bugs"
```

## Status

**built = true**, tested — `list` and `expand` both verified working.
