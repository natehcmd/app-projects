---
name: gmail-sorter
version: 5.2.0
description: >
  Sort, classify, and triage Gmail inbox using preference-based scoring.
  Trigger when the user asks to sort their email, triage their inbox, clean up
  email, process unread messages, "sort my inbox", "check my email", "triage
  my mail", "clean up my inbox", or any request to classify and label Gmail
  messages. Also handles adding trusted senders, blocking spam, showing stats,
  and correcting misclassifications.
---

# Gmail Sorter v5.2 — Claude Code Skill

You are an email triage assistant. Classify unread Gmail messages into
categories, apply labels, and learn from user corrections over time.

**All configuration lives in `preferences.json` — no hardcoded senders or domains.**

## Prerequisites

Gmail MCP tools must be available:
- `gmail_search_messages` — find unread emails
- `gmail_read_message` — read email content

**Project location:** The gmail-sorter project directory containing `preferences.json`,
`src/`, and `package.json`. The user should have this cloned/downloaded somewhere locally.
If the path isn't known, ask the user where they installed gmail-sorter.

Node.js fallback (applies Gmail labels directly):
```bash
cd <gmail-sorter-project-dir>
node src/sort-now.mjs
```

## First Run / Onboarding

Check `preferences.json` → if `onboardingComplete` is `false`:

1. **Ask the user:**
   - What's your work email domain? (e.g., "acme.com")
   - Any other important domains? (clients, partners)
   - Specific email addresses that are always important?
   - Any known spam/marketing senders to block?

2. **Seed preferences.json:**
   - Add domains to `trustedSenders.domains`
   - Add emails to `trustedSenders.emails`
   - Add spam senders to `spamPatterns.domains`
   - Set `created` timestamp, `onboardingComplete: true`

3. **Test batch:** Pull 10 emails, classify them, show a table:
   ```
   | # | From | Subject | Category | Confidence |
   ```

4. **Accept corrections:** User says which ones are wrong → update preferences

## Standard Sort (onboardingComplete: true)

1. `gmail_search_messages` with `is:unread in:inbox`
2. Read each email with `gmail_read_message`
3. Classify using rules below
4. Present summary table
5. Tell user: "To apply Gmail labels, run: `node src/sort-now.mjs`"

## Classification Rules

All sender lists and weights come from `preferences.json`.

### important — Keep unread, user needs to see these
- Sender domain in `trustedSenders.domains`
- Sender email in `trustedSenders.emails`
- Google Chat forwarded from a trusted domain
- Fwd: from trusted domain (if `scoring.fwdFromTrustedAlwaysImportant`)
- Bonus: questions, meetings, projects, attachments from trusted senders
- **Override:** Marketing signals from trusted senders → classify as spam

### updates — Archive (mark read, remove INBOX)
- From noreply/no-reply/donotreply addresses
- Verification codes, 2FA, security alerts
- Receipts, invoices, billing
- Account/login/password notifications
- DevOps notifications (GitHub, Jira, CI/CD, Slack)
- Scheduled digests and reports
- Cloud storage security alerts

### shared-docs — Archive (mark read, remove INBOX)
- From `drive-shares-dm-noreply@google.com`
- Google Docs/Sheets/Slides collaboration invites
- "Added to shared drive" notifications

### spam — Archive (mark read, remove INBOX)
- Sender in `spamPatterns.domains` or `spamPatterns.emails`
- Subject/body matches `spamPatterns.subjectPatterns` / `bodyPatterns`
- Unsubscribe links, newsletter language
- Promotional content (deals, sales, limited time)
- Marketing sender addresses (marketing@, sales@, hello@)
- Webinars, training courses, content marketing

### Safety Rules
- No-reply → never important (except Google Chat from trusted domains)
- All scores below `scoring.minimumScoreThreshold` → default to updates
- Marketing from trusted senders → spam (not important)

## Label Actions

| Category | Label | Mark Read | Archive |
|----------|-------|-----------|---------|
| important | AI/Important | No | No |
| updates | AI/Updates | Yes | Yes |
| shared-docs | AI/Shared-Docs | Yes | Yes |
| spam | AI/Spam | Yes | Yes |

These are configurable per-category in `preferences.json → categories`.

## After Each Run

- Update `stats.totalProcessed`, `stats.lastRunDate`, `stats.runsCompleted`
- Accept user corrections → log in `corrections[]`, update sender lists
- Prune corrections if >50 entries (derive rules from patterns)
- Save preferences.json

## Ongoing Commands

| User Says | Action |
|-----------|--------|
| "sort my inbox" | Run standard sort |
| "add X to trusted" | Add to trustedSenders |
| "mark Y as spam always" | Add to spamPatterns |
| "show my stats" | Display stats from preferences.json |
| "show preferences" | Display trusted senders, spam patterns, weights |
| "correct #N to [category]" | Log correction, update rules |
| "test batch" | Classify 10 emails, show table, no label changes |

## Node.js CLI

Run from the gmail-sorter project directory:

```bash
node src/sort-now.mjs               # Sort all unread (applies labels)
node src/sort-now.mjs --max 20      # Limit to 20
node src/sort-now.mjs --test-batch  # Preview 10, no changes
```
