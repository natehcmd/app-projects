#!/usr/bin/env node
/**
 * MyAgent — Personal AI Gateway
 * Powered by Claude, ChatGPT, Gemini
 * Communicates via iMessage · Memory stored locally
 * 
 * Usage: node agent.mjs
 * Commands in iMessage:
 *   @claude <msg>   — force Claude
 *   @gpt <msg>      — force ChatGPT
 *   @gemini <msg>   — force Gemini
 *   /memory         — show current memory
 *   /remember <fact>— save a fact to memory
 *   /forget <fact>  — remove a fact from memory
 *   /model <name>   — switch default model
 *   /skills         — list available skills
 *   /status         — show agent status
 *   /help           — show commands
 */

import { execSync, spawn } from 'child_process';
import { readFileSync, writeFileSync, existsSync, readdirSync, appendFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ── Config ──────────────────────────────────────────────────────
const config = JSON.parse(readFileSync(join(__dirname, 'config.json'), 'utf8'));
const MEMORY_FILE = join(__dirname, 'memory/core.md');
const SKILLS_DIR  = join(__dirname, 'skills');
const LOG_FILE    = join(__dirname, 'logs/agent.log');

let defaultModel = config.agent.defaultModel;
let conversationHistory = [];
let pendingConfirmation = null;
let lastSeenMessage = null;

// ── Logging ─────────────────────────────────────────────────────
function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}`;
  console.log(line);
  try { appendFileSync(LOG_FILE, line + '\n'); } catch {}
}

// ── iMessage ─────────────────────────────────────────────────────
function getLastiMessage() {
  try {
    const script = `
      tell application "Messages"
        set theChats to chats
        repeat with aChat in theChats
          if (get class of aChat) is iMessage and (count of messages of aChat) > 0 then
            set lastMsg to last message of aChat
            if sender of lastMsg is not me then
              return {text:(text of lastMsg), id:(id of lastMsg)}
            end if
          end if
        end repeat
      end tell
    `;
    const result = execSync(`osascript -e '${script.replace(/'/g, "'\\''")}'`, { timeout: 5000 }).toString().trim();
    return result;
  } catch { return null; }
}

function sendIMessage(number, message) {
  try {
    // Chunk long messages
    const chunks = chunkMessage(message, 1500);
    for (const chunk of chunks) {
      const safe = chunk.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
      execSync(`osascript -e 'tell application "Messages" to send "${safe}" to buddy "${number}" of (service 1 whose service type is iMessage)'`, { timeout: 8000 });
      if (chunks.length > 1) sleep(500);
    }
    return true;
  } catch(e) {
    log(`iMessage send error: ${e.message}`);
    return false;
  }
}

function chunkMessage(text, maxLen) {
  if (text.length <= maxLen) return [text];
  const chunks = [];
  let i = 0;
  while (i < text.length) {
    let end = i + maxLen;
    if (end < text.length) {
      const lastNewline = text.lastIndexOf('\n', end);
      if (lastNewline > i) end = lastNewline;
    }
    chunks.push(text.slice(i, end));
    i = end;
  }
  return chunks;
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Memory ───────────────────────────────────────────────────────
function readMemory() {
  try { return readFileSync(MEMORY_FILE, 'utf8'); } catch { return ''; }
}

function appendMemory(fact) {
  const mem = readMemory();
  const updated = mem + `\n- ${fact} _(added ${new Date().toLocaleDateString()})_`;
  writeFileSync(MEMORY_FILE, updated);
}

function forgetMemory(keyword) {
  const lines = readMemory().split('\n');
  const filtered = lines.filter(l => !l.toLowerCase().includes(keyword.toLowerCase()));
  writeFileSync(MEMORY_FILE, filtered.join('\n'));
}

// ── Skills ───────────────────────────────────────────────────────
function listSkills() {
  try {
    const skills = readdirSync(SKILLS_DIR).filter(f => {
      return existsSync(join(SKILLS_DIR, f, 'SKILL.md'));
    });
    return skills.length ? skills.join(', ') : 'No skills installed';
  } catch { return 'Skills directory empty'; }
}

function loadSkill(name) {
  const path = join(SKILLS_DIR, name, 'SKILL.md');
  if (existsSync(path)) return readFileSync(path, 'utf8');
  // Also check ~/.claude/skills
  const globalPath = join(process.env.HOME, '.claude/skills', name, 'SKILL.md');
  if (existsSync(globalPath)) return readFileSync(globalPath, 'utf8');
  return null;
}

// ── Safety ───────────────────────────────────────────────────────
function requiresConfirmation(message) {
  const lower = message.toLowerCase();
  return config.safety.requireConfirmation.some(word => lower.includes(word));
}

// ── AI Models ────────────────────────────────────────────────────
async function askClaude(messages, systemPrompt) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: config.models.claude.model,
      max_tokens: 1500,
      system: systemPrompt,
      messages
    })
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.message);
  return data.content?.[0]?.text || '(no response)';
}

async function askGPT(messages, systemPrompt) {
  const key = config.models.gpt.apiKey;
  if (!key || key.includes('YOUR_')) throw new Error('OpenAI API key not configured. Edit config.json');
  const res = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${key}` },
    body: JSON.stringify({
      model: config.models.gpt.model,
      max_tokens: 1500,
      messages: [{ role: 'system', content: systemPrompt }, ...messages]
    })
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.message);
  return data.choices?.[0]?.message?.content || '(no response)';
}

async function askGemini(messages, systemPrompt) {
  const key = config.models.gemini.apiKey;
  if (!key || key.includes('YOUR_')) throw new Error('Gemini API key not configured. Edit config.json');
  const contents = messages.map(m => ({
    role: m.role === 'assistant' ? 'model' : 'user',
    parts: [{ text: m.content }]
  }));
  const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${config.models.gemini.model}:generateContent?key=${key}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: systemPrompt }] },
      contents
    })
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.message);
  return data.candidates?.[0]?.content?.parts?.[0]?.text || '(no response)';
}

async function queryModel(model, messages, systemPrompt) {
  switch(model) {
    case 'claude':  return await askClaude(messages, systemPrompt);
    case 'gpt':     return await askGPT(messages, systemPrompt);
    case 'gemini':  return await askGemini(messages, systemPrompt);
    default: throw new Error(`Unknown model: ${model}`);
  }
}

// ── Command Handler ───────────────────────────────────────────────
async function handleCommand(text) {
  const cmd = text.trim().toLowerCase();

  if (cmd === '/help') {
    return `🦞 Jax Commands:
@claude / @gpt / @gemini — route to specific AI
/memory — show what I remember
/remember <fact> — save something
/forget <word> — remove memories with that word
/model <claude|gpt|gemini> — switch default
/skills — list installed skills
/status — agent status
/clear — clear conversation history
/help — this message`;
  }

  if (cmd === '/memory') {
    return `📝 Memory:\n${readMemory()}`;
  }

  if (cmd.startsWith('/remember ')) {
    const fact = text.slice(10).trim();
    appendMemory(fact);
    return `✓ Remembered: "${fact}"`;
  }

  if (cmd.startsWith('/forget ')) {
    const keyword = text.slice(8).trim();
    forgetMemory(keyword);
    return `✓ Removed entries containing "${keyword}" from memory`;
  }

  if (cmd.startsWith('/model ')) {
    const m = cmd.slice(7).trim();
    if (!['claude', 'gpt', 'gemini'].includes(m)) return `Unknown model. Use: claude, gpt, gemini`;
    defaultModel = m;
    return `✓ Default model set to ${m}`;
  }

  if (cmd === '/skills') {
    return `🛠 Skills: ${listSkills()}`;
  }

  if (cmd === '/status') {
    return `🟢 Jax is running
Default model: ${defaultModel}
Messages in history: ${conversationHistory.length}
Memory: ${readMemory().split('\n').length} lines
Skills: ${listSkills()}`;
  }

  if (cmd === '/clear') {
    conversationHistory = [];
    return `✓ Conversation history cleared`;
  }

  return null; // not a command
}

// ── Main message processor ────────────────────────────────────────
async function processMessage(text) {
  log(`Received: ${text}`);

  // Handle confirmation responses
  if (pendingConfirmation) {
    const lower = text.toLowerCase().trim();
    if (['yes', 'y', 'confirm', 'ok', 'go ahead', 'do it'].includes(lower)) {
      const action = pendingConfirmation;
      pendingConfirmation = null;
      return await executeWithModel(action.model, action.message, action.history);
    } else {
      pendingConfirmation = null;
      return '✓ Cancelled.';
    }
  }

  // Commands
  const cmdResponse = await handleCommand(text);
  if (cmdResponse !== null) return cmdResponse;

  // Detect model routing
  let model = defaultModel;
  let cleanText = text;

  if (text.toLowerCase().startsWith('@claude ')) { model = 'claude'; cleanText = text.slice(8); }
  else if (text.toLowerCase().startsWith('@gpt ')) { model = 'gpt'; cleanText = text.slice(5); }
  else if (text.toLowerCase().startsWith('@gemini ')) { model = 'gemini'; cleanText = text.slice(8); }

  // Safety check
  if (requiresConfirmation(cleanText)) {
    pendingConfirmation = { model, message: cleanText, history: [...conversationHistory] };
    return `⚠️ This seems like it could take an important action. Confirm? (yes/no)\n"${cleanText}"`;
  }

  return await executeWithModel(model, cleanText, conversationHistory);
}

async function executeWithModel(model, text, history) {
  const memory = readMemory();
  const systemPrompt = `You are Jax, ${config.agent.owner}'s personal AI assistant running locally on their Mac.
Be direct, concise, and genuinely helpful. No padding.

Your memory about ${config.agent.owner}:
${memory}

You are running as model: ${model}. 
Current time: ${new Date().toLocaleString('en-US', { timeZone: 'America/Chicago' })}`;

  const messages = [
    ...history,
    { role: 'user', content: text }
  ];

  try {
    const response = await queryModel(model, messages, systemPrompt);
    
    // Update history
    conversationHistory.push({ role: 'user', content: text });
    conversationHistory.push({ role: 'assistant', content: response });
    
    // Keep history bounded
    if (conversationHistory.length > 40) {
      conversationHistory = conversationHistory.slice(-30);
    }

    const modelTag = model !== defaultModel ? ` [${model}]` : '';
    return response + modelTag;
  } catch(e) {
    log(`Model error (${model}): ${e.message}`);
    return `⚠️ Error from ${model}: ${e.message}`;
  }
}

// ── iMessage Poll Loop ────────────────────────────────────────────
async function startIMessageLoop() {
  const myNumber = config.iMessage.yourNumber;
  if (myNumber.includes('YOUR_')) {
    log('⚠️  iMessage number not configured. Edit config.json → iMessage.yourNumber');
    log('   Example: "+19725550000"');
  }

  log(`🦞 Jax is running — default model: ${defaultModel}`);
  log(`   iMessage polling every ${config.iMessage.pollIntervalMs}ms`);
  log(`   Send a message to yourself to test`);
  log(`   Type Ctrl+C to stop`);

  // For testing without iMessage — also accept stdin
  if (process.stdin.isTTY) {
    process.stdin.setRawMode(false);
  }
  process.stdin.setEncoding('utf8');
  let stdinBuffer = '';
  process.stdin.on('data', async (chunk) => {
    stdinBuffer += chunk;
    const lines = stdinBuffer.split('\n');
    stdinBuffer = lines.pop();
    for (const line of lines) {
      if (!line.trim()) continue;
      const response = await processMessage(line.trim());
      console.log(`\nJax: ${response}\n`);
    }
  });

  // Poll iMessage
  setInterval(async () => {
    try {
      const script = `
        tell application "Messages"
          if (count of chats) > 0 then
            set recentChat to item 1 of chats
            if (count of messages of recentChat) > 0 then
              set lastMsg to last message of recentChat
              return (get text of lastMsg) & "|||" & (get id of lastMsg) & "|||" & (get sender of lastMsg)
            end if
          end if
        end tell
      `;
      const result = execSync(`osascript -e '${script.replace(/'/g, "'\\''")}'`, { timeout: 4000 }).toString().trim();
      if (!result) return;

      const [msgText, msgId, sender] = result.split('|||');
      if (!msgText || msgId === lastSeenMessage) return;
      if (sender === 'undefined' || !sender || sender === config.iMessage.yourNumber) {
        // Only respond to messages from yourself (owner)
        lastSeenMessage = msgId;
        const response = await processMessage(msgText.trim());
        log(`Response: ${response.slice(0, 100)}...`);
        sendIMessage(myNumber, response);
      }
    } catch(e) {
      // Silent — iMessage access errors are common on first run
    }
  }, config.iMessage.pollIntervalMs);
}

// ── Entry point ───────────────────────────────────────────────────
console.log(`
  ╔══════════════════════════════╗
  ║   🦞 Jax — Personal Agent   ║
  ║   Claude · GPT · Gemini     ║
  ╚══════════════════════════════╝
  
  Type messages below to test, or configure iMessage in config.json
  Commands: /help · /memory · /status · /skills
`);

startIMessageLoop().catch(console.error);
