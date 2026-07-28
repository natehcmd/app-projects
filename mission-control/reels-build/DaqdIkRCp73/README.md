# DaqdIkRCp73 — "Kickbacks" — CONFIRMED UNSAFE, NOT INSTALLED

## Source content

> @liamjohnston.ai: Comment "Claude" and I'll send you the install link.
> Developers are getting paid every time Claude Code loads while you stare
> at the same spinner for free. It's called Kickbacks and it sells that
> little thinking line to advertisers, then pays you up to half the ad
> revenue... Setup takes about a minute and people are already pulling ten
> to twenty bucks a day just leaving it on.

## Verdict: UNSAFE — do not install

This is the same "kickbacks.ai" product already flagged as spyware/adware
earlier this session (cross-referenced against an earlier draft security
analysis in `~/AgentDrop-Workspace/results_aa/`). Re-confirmed independently
here: the pitch itself is the red flag — a tool that claims to inject
third-party ad content into Claude Code's UI and share "ad revenue" with
you necessarily requires:
1. Intercepting/modifying Claude Code's local UI or network traffic, an
   invasive hook into an agentic tool that has shell and file access.
2. Sending some kind of usage/session data to an ad broker to generate
   "revenue" — an actual data-exfiltration channel by design, not an
   incidental risk.
3. An implausible payout claim ("$10-20/day for leaving a spinner-ad tool
   running") — this is the exact shape of adware/spyware monetization
   pitches, not a legitimate open-source tool's business model.

No source was installed or even downloaded — the reel gates the actual
install link behind a comment-for-DM funnel, so there's nothing to inspect,
which is itself consistent with the pattern.

## Status

**built = false, installed = false.** Confirmed unsafe, blocked.
