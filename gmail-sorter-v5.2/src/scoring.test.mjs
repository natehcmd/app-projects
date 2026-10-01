// Minimal regression test for the fwd/re/forward word-boundary bug.
//
// Bug: `/\bfwd:|re:|forward/i` only binds `\b` to the first alternative
// ("fwd:"). The second alternative ("re:") has no boundary, so it matches
// *anywhere* the substring "re:" occurs — including inside words like
// "Architecture:" (…tu|re:). That falsely added +40 "reply/forward" points
// to importantScore for subjects that were never a reply or forward.
//
// Fix: group the alternation — `/\b(?:fwd:|re:|forward)/i` — so the word
// boundary applies to every alternative.
//
// Run with: node --test src/scoring.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { scoreEmail } from './scoring.mjs';

const prefs = {
  trustedSenders: { domains: ['example.com'], emails: [] },
  spamPatterns: { domains: [], emails: [], subjectPatterns: [], bodyPatterns: [] },
  scoring: {
    trustedDomainWeight: 200,
    trustedEmailWeight: 150,
    noreplyUpdateWeight: 110,
    marketingOverrideWeight: 130,
    fwdFromTrustedAlwaysImportant: true,
    defaultCategory: 'updates',
    minimumScoreThreshold: 30,
  },
};

const from = 'Colleague <person@example.com>';
const snippet = 'no special keywords here';
const body = 'no special keywords here either';

test('"Architecture:" subject does not falsely trigger the reply/forward bonus', () => {
  const result = scoreEmail('Architecture: new service diagram', snippet, from, body, prefs);
  // Base trusted-domain score only (200 + 50 domain bonus) — no +40 bonus.
  assert.equal(result.scores.important, 250);
});

test('a real "Re:" subject still gets the reply/forward bonus', () => {
  const result = scoreEmail('Re: Architecture diagram', snippet, from, body, prefs);
  assert.equal(result.scores.important, 290);
});

test('a real "Fwd:" subject still gets the reply/forward bonus', () => {
  const result = scoreEmail('Fwd: Architecture diagram', snippet, from, body, prefs);
  assert.equal(result.scores.important, 290);
});
