# Student Software Perks Directory

## What this is

The source reel ([DYaA7dnxfUi](https://www.instagram.com/reel/DYaA7dnxfUi)) is a
"comment STUDENT for the full list" engagement-bait post. The caption itself
contains no technique or method — it just teases five well-known,
legitimately free-for-students software offers (GitHub Student Developer
Pack, Cursor Pro, Notion, Figma, Perplexity Pro) and gates the "full list"
behind a comment/DM funnel.

Rather than build nothing, this turns the *underlying, legitimate idea*
("here's software that's free/discounted for students") into a small,
standalone, offline reference tool — a local directory of these offers with
links to each vendor's **official** sign-up/verification page. It replaces
the comment-for-DM funnel with a script you can run yourself, anytime,
without needing to comment on anything or hand over contact info to a
stranger's bot.

This tool does **not**:
- scrape any website or platform
- automate or fake student-status verification
- collect or transmit your email/credentials anywhere
- guarantee current pricing/eligibility (vendor terms change — always
  confirm on the vendor's own site before assuming a price or eligibility
  rule is still accurate)

It's a static, curated data file (`perks.json`) plus a tiny CLI
(`student_perks.py`) to browse it.

## Files

- `perks.json` — curated list of 5 known official student software offers
  (name, category, normal price, student price, requirements, official
  sign-up URL, notes).
- `student_perks.py` — CLI to list, search, and do a very light "does this
  email look academic" heuristic check (a pattern check only — it does not
  verify anything with any vendor or school).

## How to run

Requires only Python 3 (no dependencies, no API keys).

```bash
cd reels-build/DYaA7dnxfUi

# List every known perk with full details
python3 student_perks.py list

# Search by keyword (name, category, or notes)
python3 student_perks.py search cursor
python3 student_perks.py search design

# Sanity-check whether an email address looks like a typical academic address
python3 student_perks.py check jane.doe@some-university.edu
```

## Setup / API-key notes

None needed. This is fully offline and self-contained — it only reads the
bundled `perks.json` file. There is no network access, no scraping, and no
account credentials involved anywhere in this tool.

## Keeping it current

Vendor pricing and eligibility rules change over time. `perks.json` is a
plain JSON file — edit it directly to add new offers, update prices, or
correct a sign-up URL. Each entry links to the vendor's own official
program page so you can always double-check current terms there before
signing up.

## Why it stops here

The reel's "full list" behind the comment funnel is presumably a longer
version of the same kind of list (more free-for-student tools). Nothing in
the source material discloses any actual method, workflow, or technique
beyond "here are some products students can get for free/cheap" — so this
tool implements exactly that idea (a lookup directory) rather than
fabricating a fake "full list" or trying to replicate whatever lead-gen
funnel sits behind the original comment gate.
