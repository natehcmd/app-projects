# agent-guard

A small, standalone toolkit of real prompt-injection defenses for AI agents
that ingest untrusted text (web pages, scraped content, documents, tool
output, email bodies, etc.) and call tools.

## Why this exists / a note on the source reel

This reel (`@kevinfremon`, shortcode `DYNm5GcSswI`) claimed to show "the
prompt" used to harden an AI agent called Trillion against prompt injection —
but the actual prompt/technique is never given in the caption or transcript.
It ends with "Prompt is in the video" and a comment-emoji engagement hook
(🔒 / 👀), which is a classic engagement-bait pattern, not a disclosed
method.

Rather than fabricate a fake "secret prompt" to match the video's claim, this
implements the well-documented, real defenses that security-conscious agent
builders actually use against prompt injection. It's a genuinely useful,
honest standalone tool inspired by the topic the reel gestures at, built from
first principles instead of invented content.

## What it does

`guard.py` provides six independent, composable defenses:

1. **Quarantine untrusted content** (`quarantine()`) — wraps any
   externally-sourced text in explicit delimiters and labels it as inert
   data, not instructions.
2. **Canary tokens** (`make_canary()`, `canary_leaked()`) — a random
   per-request token embedded in the system prompt that the model is told
   never to repeat. If it shows up in the output, untrusted content likely
   hijacked the model.
3. **Hardened system prompt** (`build_hardened_system_prompt()`) — states
   the instruction hierarchy explicitly: only the operator's instructions
   are authoritative, content encountered while working is never a source
   of new instructions.
4. **Heuristic injection scanner** (`scan_for_injection()`) — flags
   untrusted text containing classic injection phrasing ("ignore previous
   instructions", "you are now", fake `system:`/`assistant:` role markers,
   jailbreak language, etc.) *before* it reaches the model.
5. **Tool-call allowlisting** (`ToolGuard`) — a small wrapper that only
   permits calling tools from an explicit allowlist, so even a successful
   injection can't make the agent invoke something it was never authorized
   to call.
6. **Output leak check** (`check_output_for_leaks()`) — after the model
   replies, checks the reply for a leaked canary token or secret-shaped
   strings (API key patterns) before it's shown to a user or sent
   anywhere.

`prepare_guarded_turn()` ties 1–3 together into a one-call pipeline for a
single agent turn.

This is a defensive library only. It does not evade bot/fraud detection,
does not scrape anything, and only touches "secrets" in the sense of
checking that they are *not* leaking back out in model output.

## Files

- `guard.py` — the library (stdlib only, no dependencies).
- `example.py` — runnable demo: an offline mock-model walkthrough of all
  six defenses, plus an optional live call against Claude if you set an API
  key.
- `test_guard.py` — lightweight sanity tests (no pytest needed).
- `requirements.txt` — documents the one optional dependency (`anthropic`,
  only needed for the live-Claude portion of the demo).

## How to run

Requires Python 3.10+ (uses `X | None` union syntax). No install needed for
the core library or tests:

```bash
cd DYNm5GcSswI
python3 test_guard.py      # run the sanity test suite
python3 example.py         # run the offline demo (mock model)
```

Expected: all tests print `PASS` and the demo shows the scanner catching an
injected review, the mock model "leaking" its canary + a fake key, and the
leak checker + tool allowlist both catching it.

### Optional: live Claude demo

To also see the same pipeline wired to a real model call:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # your own key, from console.anthropic.com
python3 example.py
```

No key, no problem — the offline demo runs regardless and needs nothing.

## Using it in your own agent

```python
from guard import prepare_guarded_turn, check_output_for_leaks

turn = prepare_guarded_turn(
    base_instructions="You are a helpful research assistant.",
    operator_message="Summarize this page for me.",
    untrusted_context=scraped_page_text,   # anything from outside your control
    untrusted_source="scraped web page",
)

# send turn.system_prompt as your system message and turn.user_message as
# the user turn to whatever model you're using

reply = call_your_model(turn.system_prompt, turn.user_message)

leak_check = check_output_for_leaks(reply, canary=turn.canary)
if leak_check.flagged:
    # don't show this reply as-is; log it, sanitize it, or ask again
    ...
```

Wrap any tool-calling with `ToolGuard` so the agent can only call tools you
explicitly listed, independent of anything a prompt injection tries to get
it to do.

## Limitations (be honest with yourself about this)

- The heuristic scanner (`scan_for_injection`) is a first-pass filter based
  on known phrasing, not a guarantee — sophisticated injections can be
  worded around it. Use it alongside quarantining and canaries, not instead
  of them.
- Canary tokens catch *leaks*, not all forms of hijacking — a well-crafted
  injection could change agent behavior without ever repeating the canary.
  Combine with tool allowlisting for actions that matter.
- None of this replaces validating and constraining what your agent's tools
  are actually capable of doing (least privilege). The strongest defense is
  still: don't give an agent a tool it doesn't need.
