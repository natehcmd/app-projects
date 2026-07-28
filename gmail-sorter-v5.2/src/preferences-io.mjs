import fs from 'fs';
import path from 'path';
import { randomUUID } from 'crypto';

const PREFS_FILE = 'preferences.json';

/**
 * Load preferences.json from a directory.
 * Returns parsed object or throws if missing/invalid.
 */
export function loadPreferences(dir) {
  const filePath = path.join(dir, PREFS_FILE);
  if (!fs.existsSync(filePath)) {
    throw new Error(`preferences.json not found in ${dir}. Run onboarding first.`);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

/**
 * Atomic write: write to .tmp then rename to prevent corruption.
 */
export function savePreferences(dir, prefs) {
  prefs.lastUpdated = new Date().toISOString();
  const filePath = path.join(dir, PREFS_FILE);
  const tmpPath = filePath + '.tmp';
  fs.writeFileSync(tmpPath, JSON.stringify(prefs, null, 2) + '\n', 'utf-8');
  fs.renameSync(tmpPath, filePath);
}

/**
 * Check if an email address belongs to a trusted sender.
 * Matches against both domains[] and emails[].
 */
export function isTrustedSender(email, prefs) {
  const lower = email.toLowerCase();
  const domain = lower.split('@')[1] || '';
  if (prefs.trustedSenders.domains.some(d => d.toLowerCase() === domain)) return true;
  if (prefs.trustedSenders.emails.some(e => e.toLowerCase() === lower)) return true;
  return false;
}

/**
 * Check if an email matches known spam patterns.
 */
export function isSpamPattern(from, subject, body, prefs) {
  const sp = prefs.spamPatterns;
  const fromLower = from.toLowerCase();
  const domain = (fromLower.match(/@([^>]+)/)?.[1] || '').replace('>', '');

  if (sp.domains.some(d => domain.includes(d.toLowerCase()))) return true;
  if (sp.emails.some(e => fromLower.includes(e.toLowerCase()))) return true;
  if (sp.subjectPatterns.some(p => new RegExp(p, 'i').test(subject))) return true;
  if (sp.bodyPatterns.some(p => new RegExp(p, 'i').test(body || ''))) return true;
  return false;
}

/**
 * Log a classification correction.
 */
export function addCorrection(prefs, { messageId, from, subject, proposed, corrected, reason }) {
  prefs.corrections.push({
    id: randomUUID(),
    date: new Date().toISOString(),
    messageId: messageId || null,
    from,
    subject,
    proposed,
    corrected,
    reason: reason || null,
  });
  prefs.stats.totalCorrected++;
}

/**
 * Add a trusted sender (domain or email).
 * type: 'domain' | 'email'
 */
export function addTrustedSender(prefs, type, value) {
  const lower = value.toLowerCase();
  if (type === 'domain') {
    if (!prefs.trustedSenders.domains.includes(lower)) {
      prefs.trustedSenders.domains.push(lower);
    }
  } else if (type === 'email') {
    if (!prefs.trustedSenders.emails.includes(lower)) {
      prefs.trustedSenders.emails.push(lower);
    }
  }
}

/**
 * Add a spam pattern.
 * type: 'domain' | 'email' | 'subjectPattern' | 'bodyPattern'
 */
export function addSpamPattern(prefs, type, value) {
  const map = {
    domain: 'domains',
    email: 'emails',
    subjectPattern: 'subjectPatterns',
    bodyPattern: 'bodyPatterns',
  };
  const key = map[type];
  if (!key) throw new Error(`Unknown spam pattern type: ${type}`);
  if (!prefs.spamPatterns[key].includes(value)) {
    prefs.spamPatterns[key].push(value);
  }
}

/**
 * Prune old corrections: keep the most recent maxKeep.
 * Derive rules from pruned corrections before discarding them.
 * Returns array of derived rules for logging.
 */
export function pruneCorrections(prefs, maxKeep = 50) {
  if (prefs.corrections.length <= maxKeep) return [];

  const sorted = prefs.corrections.sort((a, b) => new Date(b.date) - new Date(a.date));
  const keep = sorted.slice(0, maxKeep);
  const pruned = sorted.slice(maxKeep);

  const derived = [];

  // Derive rules from pruned corrections
  const correctionCounts = {};
  for (const c of pruned) {
    const emailMatch = c.from.match(/<([^>]+)>/);
    const email = emailMatch ? emailMatch[1].toLowerCase() : c.from.toLowerCase();
    const domain = email.split('@')[1] || '';
    const key = `${domain}|${c.corrected}`;
    correctionCounts[key] = (correctionCounts[key] || 0) + 1;
  }

  // If a domain was corrected to the same category 3+ times, add it as a rule
  for (const [key, count] of Object.entries(correctionCounts)) {
    if (count >= 3) {
      const [domain, corrected] = key.split('|');
      if (corrected === 'important' && domain) {
        addTrustedSender(prefs, 'domain', domain);
        derived.push({ type: 'trustedDomain', value: domain, count });
      } else if (corrected === 'spam' && domain) {
        addSpamPattern(prefs, 'domain', domain);
        derived.push({ type: 'spamDomain', value: domain, count });
      }
    }
  }

  prefs.corrections = keep;
  return derived;
}
