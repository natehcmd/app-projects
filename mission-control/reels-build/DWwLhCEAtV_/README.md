# vibecheck

A small, offline, dependency-free static scanner that turns the "5 prompts to
run before shipping a vibe-coded app" listicle into something you can
actually execute against a codebase, instead of just pasting into a chatbot.

## Source material and why it was interpreted this way

The source reel (`DWwLhCEAtV_`) is a generic engagement-bait listicle: five
one-line AI-prompt suggestions (rate limiting, secret scanning, env vars,
input sanitization, "run a security audit") with no concrete algorithm or
technique disclosed, ending in "Save this / Follow for more." There's no
single named tool to reproduce. Rather than build nothing, this project takes
the five checklist items themselves — which are legitimate, common security
concerns — and implements them as five real, local, static-analysis checks
you can run with one command. Nothing here evades any protection, scrapes
anything, or touches the network; it only reads files on your own disk.

## What it checks

Given a directory, `vibecheck.py` walks all text/source files (skipping
`node_modules`, `.git`, `venv`, build output, etc.) and runs:

1. **Hardcoded secrets** — regex signatures for AWS keys, Stripe keys,
   OpenAI/Anthropic keys, Slack tokens, GitHub tokens, PEM private key
   blocks, JWT-looking literals, and generic
   `password/secret/api_key = "..."` assignments (placeholder values like
   `"your_api_key"` or `process.env.X` are filtered out to cut noise).
2. **Env var exposure** — flags `.env`-style files that exist but aren't
   covered by `.gitignore`, and flags frontend code (`src/`, `client/`,
   `.jsx/.tsx/.vue/.svelte/.html` files) that references a
   secret-looking env var (`*_SECRET`, `*_PRIVATE`, `*_API_KEY`,
   `*_TOKEN`, `*_PASSWORD`) without a public-safe prefix like
   `NEXT_PUBLIC_`, `VITE_`, or `REACT_APP_`.
3. **Rate limiting** — finds auth-ish route definitions (`/login`,
   `/signup`, `/reset-password`, etc.) in common Express/Flask/FastAPI
   patterns, and flags them if no rate-limiting library or middleware
   (e.g. `express-rate-limit`, `Flask-Limiter`, `slowapi`,
   `django-ratelimit`) is detected anywhere in the project.
4. **Dangerous / unsanitized input handling** — flags `eval()`/`exec()`,
   `os.system()`, `subprocess(..., shell=True)`, `child_process.exec()`
   with string concatenation, string-built/concatenated SQL, `innerHTML =`,
   and `dangerouslySetInnerHTML`, with higher severity if the file has no
   sign of any validation/sanitization library (`zod`, `joi`, `yup`,
   `pydantic`, `express-validator`, parameterized queries, etc.).
5. **Summary** — a rolled-up pass/fail scorecard across the four checks
   above, printed to the console (and optionally written to JSON) so you can
   paste it into a PR description or commit message before you ship.

This is a **heuristic** scanner (regexes and keyword matching over source
text). It does not execute, import, or send anywhere the code it scans. It
will produce false positives and false negatives — it's a fast first pass to
catch the obvious stuff, not a replacement for a real SAST tool, dependency
scanner, or a human security review.

## Requirements

- Python 3.8+ (standard library only — no `pip install` needed)

## How to run it

```bash
# Scan the current directory
python3 vibecheck.py

# Scan a specific project
python3 vibecheck.py /path/to/your/app

# Also write a machine-readable JSON report
python3 vibecheck.py /path/to/your/app --json report.json

# Exit with a non-zero code if anything was flagged (handy in CI)
python3 vibecheck.py /path/to/your/app --fail-on-warn
```

Example output:

```
vibecheck — scanned 2 files under /path/to/your/app

[FAIL] Hardcoded API keys / tokens / passwords (2 finding(s))
    - HIGH   src/app.py:5  Possible Anthropic API Key found in source
             API_KEY = "sk-ant-abcdefghijklmnopqrstuvwx"

[FAIL] Sensitive data exposed via env vars / git / frontend (1 finding(s))
    - HIGH   .env:1  .env exists but doesn't appear to be excluded by .gitignore

[FAIL] Rate limiting on auth routes (1 finding(s))
    - MEDIUM src/app.py:7  Auth-related route '/login' found, but no rate-limiting
             library/middleware was detected anywhere in the project.

[FAIL] Input sanitization / dangerous execution patterns (2 finding(s))
    - HIGH   src/app.py:10  Possible raw SQL string concatenation found ...
    - HIGH   src/app.py:11  Python os.system() found ...

5. Summary
    6 total finding(s) — 5 high, 1 medium, 0 low. See details above.
```

## Setup / API-key notes

None. This tool makes zero network calls and needs zero API keys or
credentials — it only reads files under the path you give it. It's safe to
run against private/proprietary code since nothing leaves your machine.

## Known limitations

- Regex-based, so it can miss obfuscated secrets or flag false positives
  (e.g. a long random-looking test fixture string).
- Route/rate-limit detection is heuristic and framework-pattern based; it
  won't understand custom routing layers, gateways, or rate limiting
  enforced upstream (e.g. at a CDN/API gateway/load balancer level) rather
  than in application code.
- Not a substitute for dependency vulnerability scanning (`npm audit`,
  `pip-audit`), a real SAST tool, or a professional security review before
  shipping anything that handles real user data or money.
