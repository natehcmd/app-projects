# Audit — gmail-sorter-np — 2026-05-05

Source: `~/audits/audit-report-2026-05-05.json` (machine-wide Codex scan)

**2 issue(s)** — CRITICAL: 0, HIGH: 2, MEDIUM: 0, LOW: 0

## ISS-002 — HIGH — SECURITY
**File:** `credentials.json` (lines 1-10)

**Problem:** This OAuth client credential bundle contains a live client secret in plaintext.

**Fix:** Rotate the OAuth client secret, delete the file from tracked storage, and load the credential from a secret manager or user-specific config path.

- auto_fixable: `False`  ·  requires_human_review: `True`

## ISS-003 — HIGH — SECURITY
**File:** `REDACTED_CLIENT_ID.apps.googleusercontent.com.json` (lines 1-12)

**Problem:** This is a second plaintext copy of the same OAuth client secret bundle, which increases the chance of accidental exposure and makes rotation harder.

**Fix:** Rotate the OAuth client secret, consolidate the credential into one secured location, and delete every plaintext duplicate.

- auto_fixable: `False`  ·  requires_human_review: `True`
