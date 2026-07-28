#!/usr/bin/env node

import { google } from 'googleapis';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { OAuth2Client } from 'google-auth-library';
import { scoreEmail } from './scoring.mjs';
import { loadPreferences, savePreferences } from './preferences-io.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..');
const CREDENTIALS_PATH = path.join(PROJECT_ROOT, 'credentials.json');
const TOKEN_PATH = path.join(PROJECT_ROOT, 'token.json');

const args = process.argv.slice(2);
const testBatch = args.includes('--test-batch');
const draftReplies = args.includes('--draft-replies');
const maxFlag = args.indexOf('--max');
const maxEmails = maxFlag !== -1 ? parseInt(args[maxFlag + 1], 10) : (testBatch ? 10 : 50);

function getAuth() {
  if (!fs.existsSync(CREDENTIALS_PATH)) { console.error('Missing credentials.json'); process.exit(1); }
  if (!fs.existsSync(TOKEN_PATH)) { console.error('Missing token.json — run: node src/setup.js'); process.exit(1); }
  const creds = JSON.parse(fs.readFileSync(CREDENTIALS_PATH));
  const { client_id, client_secret, redirect_uris } = creds.installed;
  const auth = new OAuth2Client(client_id, client_secret, redirect_uris[0]);
  const token = JSON.parse(fs.readFileSync(TOKEN_PATH));
  auth.setCredentials(token);
  return auth;
}

async function ensureLabels(gmail, prefs) {
  const labelMap = {};
  const res = await gmail.users.labels.list({ userId: 'me' });
  const existing = res.data.labels || [];
  for (const cat of Object.values(prefs.categories)) {
    let label = existing.find(l => l.name === cat.label);
    if (!label) {
      const created = await gmail.users.labels.create({ userId: 'me', requestBody: { name: cat.label, labelListVisibility: 'labelShow', messageListVisibility: 'show' } });
      label = created.data;
    }
    labelMap[cat.label] = label.id;
  }
  if (prefs.draftReplies?.label) {
    const draftLabelName = prefs.draftReplies.label;
    let draftLabel = existing.find(l => l.name === draftLabelName);
    if (!draftLabel) {
      const created = await gmail.users.labels.create({ userId: 'me', requestBody: { name: draftLabelName, labelListVisibility: 'labelShow', messageListVisibility: 'show' } });
      draftLabel = created.data;
    }
    labelMap[draftLabelName] = draftLabel.id;
  }
  return labelMap;
}

function extractBody(payload) {
  if (payload.parts) {
    const textPart = payload.parts.find(p => p.mimeType === 'text/plain');
    if (textPart?.body?.data) return Buffer.from(textPart.body.data, 'base64').toString('utf-8').substring(0, 800);
  } else if (payload.body?.data) {
    return Buffer.from(payload.body.data, 'base64').toString('utf-8').substring(0, 800);
  }
  return '';
}

async function main() {
  const prefs = loadPreferences(PROJECT_ROOT);
  const auth = getAuth();
  const gmail = google.gmail({ version: 'v1', auth });
  const labelMap = await ensureLabels(gmail, prefs);

  const res = await gmail.users.messages.list({ userId: 'me', labelIds: ['INBOX', 'UNREAD'], maxResults: maxEmails });
  const messages = res.data.messages || [];
  console.log(`\n📧 Found ${messages.length} unread messages\n`);
  if (messages.length === 0) { console.log('Nothing to sort.'); return; }

  const results = {};
  for (const cat of Object.keys(prefs.categories)) results[cat] = [];

  for (const msg of messages) {
    try {
      const full = await gmail.users.messages.get({ userId: 'me', id: msg.id, format: 'full' });
      const headers = full.data.payload.headers;
      const subject = headers.find(h => h.name === 'Subject')?.value || '(no subject)';
      const from = headers.find(h => h.name === 'From')?.value || '(unknown)';
      const snippet = full.data.snippet || '';
      const body = extractBody(full.data.payload);
      const { category, scores, confidence } = scoreEmail(subject, snippet, from, body, prefs);
      results[category].push({ id: msg.id, from, subject, scores, confidence });
      if (!testBatch) {
        const catConfig = prefs.categories[category];
        const labelId = labelMap[catConfig.label];
        if (labelId) {
          const removeLabels = [];
          if (catConfig.markRead) removeLabels.push('UNREAD');
          if (catConfig.archive) removeLabels.push('INBOX');
          await gmail.users.messages.modify({ userId: 'me', id: msg.id, requestBody: { addLabelIds: [labelId], removeLabelIds: removeLabels } });
        }
      }
    } catch (e) { console.error(`Error processing message ${msg.id}: ${e.message}`); }
  }

  const catDisplay = {
    important: { icon: '📌', label: 'IMPORTANT', suffix: 'kept unread' },
    updates: { icon: '🔔', label: 'UPDATES', suffix: 'marked read' },
    'shared-docs': { icon: '📄', label: 'SHARED-DOCS', suffix: 'marked read' },
    spam: { icon: '🚫', label: 'SPAM', suffix: 'marked read' },
  };
  console.log('✅ INBOX SORTED\n');
  for (const [cat, emails] of Object.entries(results)) {
    const d = catDisplay[cat] || { icon: '•', label: cat, suffix: '' };
    console.log(`${d.icon} ${d.label} (${emails.length} emails) — ${d.suffix}`);
    emails.forEach(e => console.log(`   • ${e.from.substring(0, 45)} | ${e.subject.substring(0, 55)}`));
    console.log('');
  }

  const totalProcessed = Object.values(results).reduce((sum, arr) => sum + arr.length, 0);
  prefs.stats.totalProcessed += totalProcessed;
  prefs.stats.lastRunDate = new Date().toISOString();
  prefs.stats.runsCompleted++;
  savePreferences(PROJECT_ROOT, prefs);
  console.log(`Stats: ${totalProcessed} emails processed (run #${prefs.stats.runsCompleted})`);
}

main().catch(err => { console.error('Fatal error:', err.message); process.exit(1); });
