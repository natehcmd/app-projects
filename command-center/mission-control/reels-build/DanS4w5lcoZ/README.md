# DanS4w5lcoZ — "5 free repos that should be illegal"

## Source content

> @dubibubiii: Comment 'skill' and I'll send you the link! Five free repos
> that should be illegal. Camofox Browser... Claude Ads... Agentic Inbox...
> Open-LLM-VTuber... Hyperframes...

Unusually, this reel names 5 specific real products (most reels in this
archive name nothing verifiable). Re-reviewed via video+audio on 2026-07-20;
the cached caption already had the names, video added no further detail.
All 5 were researched (GitHub star-growth sanity check + source inspection
for malware) before touching anything, per this session's safety process.

## Findings & actions

### 1. Camoufox — `daijro/camoufox` — INSTALLED & VERIFIED
Anti-fingerprinting Firefox fork for stealth browser automation (Playwright).
Real project since 2024, 10,294 stars over ~2 years — organic, plausible
growth curve. Installed in `.venv/`, downloaded the real ~312MB browser
binary from GitHub releases, and verified end-to-end:
```
from camoufox.sync_api import Camoufox
with Camoufox(headless=True) as browser:
    page = browser.new_page(); page.goto('https://example.com')
```
Launched, navigated, returned the correct page title. Works.

### 2. Hyperframes — `heygen-com/hyperframes` — INSTALLED & VERIFIED
"Write HTML, render video" CLI from HeyGen (real company, official GitHub
org). Apache 2.0, real npm package, real docs/Discord/showcase.
`npm install -g hyperframes` — confirmed `hyperframes --version` → 0.7.64
and the CLI's real command list (init/add/capture/render/etc.) matches docs.

### 3. Agentic Inbox — `cloudflare/agentic-inbox` — SOURCE CLONED, not deployed
Real, official Cloudflare repo (linked from an official Cloudflare blog
post). It's a self-deploy-to-your-own-Cloudflare-account email client
template — deploying it live requires binding your own domain, email
routing, and Cloudflare Access. That's account/infra configuration on
Nate's actual Cloudflare account, which I won't do autonomously. Source is
cloned at `agentic_inbox_src/` and verified legitimate; deploy it yourself
via the "Deploy to Cloudflare" button in that repo's README if you want it live.

### 4. Claude Ads — `AgriciDaniel/claude-ads` — INSTALLED (deps only), not credentialed
The most scrutinized of the 5: solo-dev-owned repo, 7,246 stars in ~5
months — a faster-than-typical growth curve, though not in the same
extreme range as the two repos declined earlier this session (ECC/free-claude-code
were 41k-231k stars). Source-inspected: no credential harvesting, no
obfuscation, no curl-pipe-to-shell; the alarming-looking internal-IP URLs
(169.254.169.254, etc.) are SSRF-protection *test fixtures*, same pattern
already seen in the other legitimate repos this session. Read-only by
default, live account changes gated behind explicit approval per its own
docs. Python deps installed in `.venv/`. **Not connected to any real ad
account** — doing so requires Nate's own Google/Meta/YouTube/LinkedIn/TikTok
credentials, which I won't provision myself. Structurally ready if he wants
to connect his own accounts.

### 5. Open-LLM-VTuber — `Open-LLM-VTuber/Open-LLM-VTuber` — verified legit, not installed
Real project since Nov 2023, 12,669 stars over ~2.5 years — organic growth,
legitimate org. It's a heavy local install (Live2D avatar rendering + local
LLM/TTS/ASR stack, GPU-recommended) — verified legitimate but not installed
in this pass given the size; safe to install later if wanted
(`git clone https://github.com/Open-LLM-VTuber/Open-LLM-VTuber`).

## Status

**4 of 5 verified real and safe. 2 fully installed and tested (Camoufox,
Hyperframes). 2 have deps/source staged but intentionally not connected to
live accounts (Agentic Inbox, Claude Ads) since that requires Nate's own
credentials. 1 verified-safe but not installed due to size (Open-LLM-VTuber).**
Zero malware found across any of the 5, despite each having marketing-driven
star counts worth some skepticism.
