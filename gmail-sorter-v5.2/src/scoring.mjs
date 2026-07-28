import { isTrustedSender, isSpamPattern } from './preferences-io.mjs';

/**
 * Extract the bare email address from a "Name <email>" format string.
 */
function extractEmail(from) {
  const match = from.match(/<([^>]+)>/);
  return match ? match[1].toLowerCase() : from.toLowerCase();
}

/**
 * Score an email against preferences and return classification.
 *
 * @param {string} subject - Email subject line
 * @param {string} snippet - Gmail snippet (preview text)
 * @param {string} from - From header (may include display name)
 * @param {string} body - Plain text body (first ~800 chars)
 * @param {object} preferences - Parsed preferences.json object
 * @returns {{ category: string, scores: object, confidence: number }}
 */
export function scoreEmail(subject, snippet, from, body, preferences) {
  const text = `${from}\n${subject}\n${snippet}\n${body}`.toLowerCase();
  const fromLower = from.toLowerCase();
  const email = extractEmail(from);
  const domain = email.split('@')[1] || '';

  const weights = preferences.scoring;

  let importantScore = 0;
  let updatesScore = 0;
  let spamScore = 0;
  let sharedDocsScore = 0;

  // ===== SHARED DOCS =====
  const isDriveShare = /drive-shares.*noreply@google\.com|via google (docs|drive|sheets|slides)/i.test(from);
  if (isDriveShare) {
    sharedDocsScore += 200;
  } else {
    if (/docs\.google\.com|drive\.google\.com/.test(text) && /share.*request|invited.*edit|invited.*view/.test(text)) sharedDocsScore += 100;
    if (/you.*were.*added.*shared.*drive|access.*granted.*document/.test(text)) sharedDocsScore += 80;
  }

  // ===== IMPORTANT: Trusted Senders =====
  const isTrustedDomain = preferences.trustedSenders.domains.some(d => d.toLowerCase() === domain);
  const isTrustedEmail = isTrustedSender(email, preferences);

  // Google Chat forwarded messages from trusted domains
  const isGoogleChatFromTrusted = /chat-noreply@google\.com/i.test(email)
    && preferences.trustedSenders.domains.some(d => new RegExp(`@${d.replace('.', '\\.')}`, 'i').test(text));

  const isKnownPerson = isTrustedDomain || isTrustedEmail || isGoogleChatFromTrusted;

  // Marketing detection — strong signals that this is promotional even from known senders
  const hasMarketingSignals = /unsubscribe|email.?preference|view.*in.*browser|hubspot|mailchimp|sendgrid/i.test(body || '');
  const hasPromoSubject = /masterclass|hackathon|webinar|\blead[s]?\b|credits|unlimited|100\+.*leads|\$\d+.*(?:free|credit|off)/i.test(subject);

  // Fwd: from trusted domain = always important (configurable)
  const isFwdFromTrusted = isTrustedDomain && /\bfwd:/i.test(subject) && weights.fwdFromTrustedAlwaysImportant;
  const isMarketingFromKnown = isKnownPerson && !isFwdFromTrusted && (hasMarketingSignals || hasPromoSubject);

  if (isKnownPerson && !isMarketingFromKnown) {
    importantScore += isTrustedDomain ? weights.trustedDomainWeight : weights.trustedEmailWeight;
    // Domain senders (coworkers) get extra weight
    if (isTrustedDomain || isGoogleChatFromTrusted) importantScore += 50;
  } else if (isMarketingFromKnown) {
    spamScore += weights.marketingOverrideWeight;
    importantScore = 0;
  } else {
    importantScore = 0;
  }

  // Bonus scoring only for confirmed important known people
  if (isKnownPerson && !isMarketingFromKnown) {
    if (/\bfwd:|re:|forward/i.test(subject)) importantScore += 40;
    if (/question|help|review|feedback|thoughts|input|opinion|advice/.test(text)) importantScore += 70;
    if (/meeting|call|timezone|schedule|available|lunch|coffee|catch.up/.test(text)) importantScore += 80;
    if (/project|contract|proposal|opportunity|partnership|collaboration|investment|fund/.test(text)) importantScore += 85;
    if (/attached|deliverable|document|report|analysis|findings/.test(text)) importantScore += 60;
  }

  // ===== SPAM: User-defined patterns take priority =====
  if (isSpamPattern(from, subject, body, preferences)) {
    spamScore += weights.marketingOverrideWeight;
  }

  // ===== SPAM: Generic Marketing/Promotional Signals =====
  if (/unsubscribe|newsletter|email.?list|mailing.?list|subscribe/.test(text)) spamScore += 100;
  if (/free.?trial|try.?free|early.?access|beta.?access|exclusive.?access|sign.?up/.test(text)) spamScore += 90;
  if (/promo|promotion|offer|deal|sale|discount|limited.?time|save.*%|exclusive|act.?now/.test(text)) spamScore += 110;
  if (/50.*off|60.*off|exclusive.?deal|flash.?sale|this.?week.*only|hurry|before.*ends/.test(text)) spamScore += 120;
  if (/learn.?more|shop.?now|claim.?offer|get.?yours|don.?t.?miss|start.?now/.test(text)) spamScore += 85;
  if (/webinar|conference|summit|expo|workshop|training.?course|certification|academy/.test(text)) spamScore += 80;
  if (/marketing@|sales@|hello@|noreply@.*marketing|careers@.*team/.test(fromLower)) spamScore += 120;
  if (/onboarding|getting.?started|quick.?start|welcome.*aboard|your.?first/.test(text)) spamScore += 60;

  // Marketing disguised as helpful content
  if (/your.*complete.*guide|the.*ultimate.*guide|how.?to.*guide|best.*practices/.test(text)) spamScore += 40;
  if (/resources|templates|toolkit|playbook|checklist/.test(text) && /free|download|grab/.test(text)) spamScore += 50;

  // ===== UPDATES: Automated/Transactional =====
  if (/noreply|no.?reply|donotreply|notifications?@|automated|system.*message/.test(fromLower)) updatesScore += weights.noreplyUpdateWeight;
  if (/verify.*email|confirm.*email|verification.?code|two.?factor|security.?code/.test(text)) updatesScore += 100;
  if (/receipt|invoice|order|transaction|payment|billing|statement|charge/.test(text)) updatesScore += 95;
  if (/your.*account|login|password|reset.*password|suspicious.*activity|security.?alert/.test(text)) updatesScore += 85;
  if (/github|gitlab|bitbucket|jira|asana|monday|notion|slack|discord|teams/.test(text)) updatesScore += 80;
  if (/build.*success|test.*pass|deployment|pipeline|ci.?cd|branch|pull.?request/.test(text)) updatesScore += 75;
  if (/scheduled|digest|report|summary|alert|notification/.test(text)) updatesScore += 70;
  if (/welcome.*to|getting.?started.*your.*account|account.*created|registration.?confirmation/.test(text)) updatesScore += 65;

  // Service announcements (not marketing)
  if (/maintenance|update|new.?feature|improvement|bug.?fix|downtime/.test(text) && !/free|trial|offer/.test(text)) {
    updatesScore += 60;
  }

  // Cloud storage notifications — service alerts vs marketing
  if (/dropbox|onedrive|google.?drive/.test(fromLower)) {
    if (/new.?sign.?in|suspicious|access|security|activity/.test(text)) {
      updatesScore += 90;
    } else if (/unlock|features|ready|explore|start.?here|upgrade/.test(text)) {
      spamScore += 100;
    }
  }

  // ===== DETERMINE CATEGORY =====
  const scores = {
    important: importantScore,
    updates: updatesScore,
    'shared-docs': sharedDocsScore,
    spam: spamScore,
  };

  let maxScore = 0;
  let category = weights.defaultCategory || 'updates';

  for (const [cat, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      category = cat;
    }
  }

  // If all scores are very low, default safely
  if (maxScore < (weights.minimumScoreThreshold || 30)) {
    category = weights.defaultCategory || 'updates';
  }

  // SAFETY: no-reply addresses should never be classified as Important
  // Exception: Google Chat forwarded from trusted domains
  const isChatNoreply = /chat-noreply@google\.com/i.test(fromLower);
  if (/noreply|no.?reply|donotreply|notifications?@/.test(fromLower) && category === 'important' && !isChatNoreply) {
    category = 'updates';
  }

  // Confidence: how dominant is the winning score
  const totalScore = Object.values(scores).reduce((a, b) => a + b, 0);
  const confidence = totalScore > 0 ? Math.round((maxScore / totalScore) * 100) : 0;

  return { category, scores, confidence };
}
