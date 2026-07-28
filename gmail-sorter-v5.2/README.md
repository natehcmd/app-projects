# Gmail Sorter v5.2

Smart Gmail inbox classifier that sorts unread email into 4 labeled categories (`AI/Important`, `AI/Updates`, `AI/Shared-Docs`, `AI/Spam`). Works as a Claude Code skill or standalone via the Node.js CLI. All rules live in `preferences.json` — nothing is hardcoded, and it learns from your corrections over time.

## Requirements

- **Node.js >= 18**
- A **Gmail account** and a Google Cloud project with the Gmail API enabled (free tier is fine)
- **Claude Code** (optional — only needed for the skill/conversational interface)

## Quick Start

```bash
git clone https://github.com/natehcmd/gmail-sorter-v5.2.git
cd gmail-sorter-v5.2
npm install
npm run setup        # OAuth flow — opens a browser, creates token.json
npm run test-batch   # Preview: classify 10 unread emails, no changes made
npm run sort         # Classify all unread emails and apply Gmail labels
```

Before `npm run setup`, you need a `credentials.json` OAuth client file in the project root — follow [docs/google-cloud-setup.md](docs/google-cloud-setup.md) (one-time, ~5 minutes).

## Install the Claude Code Skill (optional)

The canonical skill definition is **`SKILL.md`**. Install it as a skill directory:

```bash
mkdir -p ~/.claude/skills/gmail-sorter
cp SKILL.md ~/.claude/skills/gmail-sorter/SKILL.md
```

> `gmail-sorter.md` is a legacy pointer kept for older installs — always install from `SKILL.md`.

Then tell Claude: **"sort my inbox"**

On first run (`onboardingComplete: false` in `preferences.json`), the skill walks you through onboarding:

- What's your work domain?
- Who are your important contacts?
- Any known spam senders?
- Review 10 test emails and correct any mistakes

After onboarding, your preferences are saved and future sorts are automatic.

## Daily Use (with Claude)

```
"sort my inbox"           — classify and sort all unread emails
"sort my inbox, max 20"   — limit to 20 emails
"test batch"              — preview 10 emails without applying labels
"add acme.com to trusted" — mark a domain as always-important
"mark deals@store.com as spam" — block a sender
"show my stats"           — see sorting history
```

Note: Claude classifies via Gmail MCP tools but cannot apply labels directly — run `npm run sort` to apply them.

## Node.js CLI (Standalone)

Sort without Claude, or apply Gmail labels directly:

```bash
npm run sort                        # Sort all unread (applies labels)
npm run test-batch                  # Preview 10, no label changes
node src/sort-now.mjs --max 20      # Limit to 20
```

## Categories

| Category | What Goes Here | Action |
|----------|---------------|--------|
| **AI/Important** | Emails from your trusted senders | Keep unread in inbox |
| **AI/Updates** | Automated notifications, receipts, security alerts | Mark read, archive |
| **AI/Shared-Docs** | Google Drive/Docs share notifications | Mark read, archive |
| **AI/Spam** | Marketing, promotions, newsletters | Mark read, archive |

Per-category `markRead`/`archive` behavior is configurable in `preferences.json → categories`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Missing credentials.json — run: node src/setup.js` | You haven't downloaded the OAuth client file. Follow [docs/google-cloud-setup.md](docs/google-cloud-setup.md) and put `credentials.json` in the project root. |
| `Missing token.json — run: node src/setup.js` | Run `npm run setup` and complete the browser sign-in. |
| `invalid_grant` / auth errors after some time | Your token expired or was revoked. Delete `token.json` and run `npm run setup` again. |
| Gmail API `429` / quota errors | The Gmail API free quota is generous but rate-limited. Wait a minute and retry, or use `--max 20` to sort in smaller batches. |
| `preferences.json not found` | Run from the project root, or restore `preferences.json` from this repo (it ships as a blank template). |

`credentials.json` and `token.json` are gitignored — never commit them.

## Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Canonical Claude Code skill (the brain) |
| `gmail-sorter.md` | Legacy pointer to SKILL.md (backwards compatibility) |
| `preferences.json` | Your personalized sorting rules (ships as a blank template) |
| `src/sort-now.mjs` | Node.js sorter (applies Gmail labels) |
| `src/scoring.mjs` | Shared scoring engine |
| `src/preferences-io.mjs` | Preferences read/write utilities |
| `src/setup.js` | OAuth authentication wizard |
| `docs/` | Setup guides and reference docs |

## How It Works

1. **preferences.json** stores your trusted senders, spam patterns, and scoring weights
2. **scoring.mjs** evaluates each email against your preferences using a multi-dimensional scoring system
3. The highest-scoring category wins (with safety overrides — e.g., no-reply senders are never "important", marketing from trusted senders is still spam)
4. Corrections you make feed back into preferences, improving accuracy over time

## Customization

Edit `preferences.json` directly or use natural language with Claude:

- `trustedSenders.domains` — domains always classified as important
- `trustedSenders.emails` — specific emails always classified as important
- `spamPatterns.domains` — domains always classified as spam
- `scoring.*Weight` — adjust how heavily different signals are weighted
- `categories.*.markRead` / `archive` — control what happens after classification

## Documentation

- [docs/google-cloud-setup.md](docs/google-cloud-setup.md) — OAuth setup walkthrough
- [docs/classification-rules.md](docs/classification-rules.md) — Detailed category definitions and examples

## License

[MIT](LICENSE)
