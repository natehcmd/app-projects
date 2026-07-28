# DX5MzljR0n7 — Free student certifications directory

## Source

> @niknaglapur: 5 free certifications every student needs — Google AI Essentials,
> HubSpot Digital Marketing, IBM SkillsBuild, GitHub Foundations, "Claude
> Certified Architect" (claimed Deloitte pays employees for this).

## Re-reviewed 2026-07-20

Re-checked against each provider's real public program pages. 4 of 5 are
real, verifiable, free programs. The 5th ("Claude Certified Architect")
could not be verified as an actual Anthropic credential — likely marketing
embellishment. Substituted with Anthropic's real, official, free course repo
(`anthropics/courses`, cloned to `~/Learning/anthropic-courses`).

## What was built

`certs_directory.py` — offline CLI listing the 4 verified real certs plus
the real Anthropic course repo, with direct links and honest notes (e.g.
IBM SkillsBuild credit-transfer claims need school verification, not assumed).

```bash
python3 certs_directory.py
python3 certs_directory.py --json
```

## Status

**built = true**, verified against real provider URLs.
