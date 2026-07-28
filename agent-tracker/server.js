#!/usr/bin/env node
/* Agent Deck server — serves the UI and hosts one real PTY per agent.
   WebSocket protocol (JSON):
     client → server: {type:'attach', agent, cols, rows}
                      {type:'input', data}
                      {type:'resize', cols, rows}
                      {type:'relay', to, data}          // write into a linked agent's pty
                      {type:'kill', agent}
     server → client: {type:'output', data}             // pty output for attached agent
                      {type:'scrollback', data}
                      {type:'exit', code}
                      {type:'live', agents:[ids]}       // broadcast: which agents have live ptys
                      {type:'relayed', from, to}        // broadcast: a relay happened
*/
'use strict';
const http = require('http');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFile } = require('child_process');
const { WebSocketServer } = require('ws');
const pty = require('node-pty');

const PORT = process.env.PORT || 8444;
const ROOT = __dirname;
const SCROLLBACK_LIMIT = 200 * 1024; // bytes kept per agent for reattach
const WORKFLOWS_DIR = path.join(ROOT, 'workflows');
if (!fs.existsSync(WORKFLOWS_DIR)) fs.mkdirSync(WORKFLOWS_DIR);

/* ---------- workflow mode: one-shot agent turns (persona from deck notes) ---------- */
function claudeEnv() {
  return { ...process.env, PATH: `${os.homedir()}/.npm-global/bin:${os.homedir()}/.local/bin:/opt/homebrew/bin:${process.env.PATH || ''}` };
}

function runAgentTurn(persona, goal, transcript, cb) {
  const convo = (transcript || []).map(t => `${t.agentName}: ${t.content}`).join('\n\n');
  const prompt = `${persona || 'You are a helpful assistant.'}\n\nGOAL: ${goal}\n\n` +
    (convo ? `CONVERSATION SO FAR:\n${convo}\n\n` : '') +
    `Respond as yourself, continuing the work. Be concise and concrete.`;
  execFile('claude', ['-p', prompt, '--permission-mode', 'acceptEdits'],
    { cwd: os.homedir(), env: claudeEnv(), timeout: 180000, maxBuffer: 10 * 1024 * 1024 },
    (err, stdout, stderr) => {
      const out = (stdout || '').trim() || (stderr || '').trim();
      cb(out || (err ? `error: ${err.message}` : '(no response)'));
    });
}

const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.map': 'application/json',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2',
};

/* ---------- state persistence (agents/links/view live server-side) ---------- */
const STATE_FILE = path.join(ROOT, 'deck-state.json');

/* ---------- static files ---------- */
const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/') urlPath = '/index.html';

  if (urlPath === '/state') {
    if (req.method === 'GET') {
      fs.readFile(STATE_FILE, (err, data) => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(err ? '{}' : data);
      });
    } else if (req.method === 'POST') {
      let body = '';
      req.on('data', c => { body += c; if (body.length > 5e6) req.destroy(); });
      req.on('end', () => {
        try {
          JSON.parse(body); // validate before persisting
          fs.writeFile(STATE_FILE, body, () => { res.writeHead(204); res.end(); });
        } catch { res.writeHead(400); res.end(); }
      });
    } else { res.writeHead(405); res.end(); }
    return;
  }

  if (urlPath === '/api/agent-turn' && req.method === 'POST') {
    let body = '';
    req.on('data', c => { body += c; if (body.length > 2e6) req.destroy(); });
    req.on('end', () => {
      let m;
      try { m = JSON.parse(body); } catch { res.writeHead(400); return res.end(); }
      runAgentTurn(m.persona, m.goal, m.transcript, reply => {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ reply }));
      });
    });
    return;
  }

  if (urlPath === '/api/sessions' && req.method === 'GET') {
    const list = [...sessions.entries()].map(([agent, s]) =>
      ({ agent, startedAt: s.startedAt, lastActivity: s.lastActivity }));
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify(list));
  }

  if (urlPath === '/api/workflows') {
    if (req.method === 'GET') {
      fs.readdir(WORKFLOWS_DIR, (err, files) => {
        if (err) { res.writeHead(200, { 'Content-Type': 'application/json' }); return res.end('[]'); }
        const runs = (files || []).filter(f => f.endsWith('.json')).sort().reverse().slice(0, 30)
          .map(f => { try { return JSON.parse(fs.readFileSync(path.join(WORKFLOWS_DIR, f))); } catch { return null; } })
          .filter(Boolean);
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(runs));
      });
    } else if (req.method === 'POST') {
      let body = '';
      req.on('data', c => { body += c; if (body.length > 5e6) req.destroy(); });
      req.on('end', () => {
        let m;
        try { m = JSON.parse(body); } catch { res.writeHead(400); return res.end(); }
        const id = m.id || ('wf' + Date.now());
        fs.writeFile(path.join(WORKFLOWS_DIR, `${id}.json`), JSON.stringify({ ...m, id }), () => {
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ id }));
        });
      });
    } else { res.writeHead(405); res.end(); }
    return;
  }

  // map /vendor/* to node_modules
  let file;
  if (urlPath.startsWith('/vendor/')) {
    file = path.join(ROOT, 'node_modules', urlPath.slice('/vendor/'.length));
  } else {
    file = path.join(ROOT, urlPath);
  }
  const resolved = path.resolve(file);
  if (!resolved.startsWith(ROOT)) { res.writeHead(403); return res.end(); }
  fs.readFile(resolved, (err, data) => {
    if (err) { res.writeHead(404); return res.end('not found'); }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(resolved)] || 'application/octet-stream' });
    res.end(data);
  });
});

/* ---------- pty registry ---------- */
const sessions = new Map(); // agentId -> {pty, scrollback:Buffer[], size, watchers:Set<ws>}

function getSession(agentId, cols = 80, rows = 24) {
  let s = sessions.get(agentId);
  if (s) return s;
  const shell = process.env.SHELL || '/bin/zsh';
  const term = pty.spawn(shell, ['-l'], {
    name: 'xterm-256color',
    cols, rows,
    cwd: os.homedir(),
    env: { ...process.env, AGENT_DECK: agentId },
  });
  s = { pty: term, chunks: [], bytes: 0, watchers: new Set(), startedAt: Date.now(), lastActivity: Date.now() };
  term.onData(data => {
    s.lastActivity = Date.now();
    s.chunks.push(data);
    s.bytes += data.length;
    while (s.bytes > SCROLLBACK_LIMIT && s.chunks.length > 1) s.bytes -= s.chunks.shift().length;
    for (const ws of s.watchers) send(ws, { type: 'output', data });
  });
  term.onExit(({ exitCode }) => {
    for (const ws of s.watchers) send(ws, { type: 'exit', code: exitCode });
    sessions.delete(agentId);
    broadcastLive();
  });
  sessions.set(agentId, s);
  broadcastLive();
  return s;
}

function send(ws, obj) { if (ws.readyState === 1) ws.send(JSON.stringify(obj)); }

/* ---------- websocket ---------- */
const wss = new WebSocketServer({ server });
const allClients = new Set();

function broadcastLive() {
  const msg = { type: 'live', agents: [...sessions.keys()] };
  for (const ws of allClients) send(ws, msg);
}

wss.on('connection', ws => {
  allClients.add(ws);
  let attached = null; // agentId
  send(ws, { type: 'live', agents: [...sessions.keys()] });

  ws.on('message', raw => {
    let m;
    try { m = JSON.parse(raw); } catch { return; }

    if (m.type === 'attach' && typeof m.agent === 'string') {
      if (attached) sessions.get(attached)?.watchers.delete(ws);
      attached = m.agent;
      const s = getSession(attached, m.cols, m.rows);
      s.watchers.add(ws);
      if (m.cols && m.rows) { try { s.pty.resize(m.cols, m.rows); } catch {} }
      send(ws, { type: 'scrollback', data: s.chunks.join('') });

    } else if (m.type === 'input' && attached) {
      sessions.get(attached)?.pty.write(m.data);

    } else if (m.type === 'resize' && attached && m.cols > 0 && m.rows > 0) {
      try { sessions.get(attached)?.pty.resize(m.cols, m.rows); } catch {}

    } else if (m.type === 'relay' && typeof m.to === 'string' && typeof m.data === 'string') {
      const s = getSession(m.to); // spawn target if needed so the message lands
      s.pty.write(m.data);
      for (const c of allClients) send(c, { type: 'relayed', from: m.from || attached, to: m.to });

    } else if (m.type === 'kill' && typeof m.agent === 'string') {
      const s = sessions.get(m.agent);
      if (s) { try { s.pty.kill(); } catch {} }
    }
  });

  ws.on('close', () => {
    allClients.delete(ws);
    if (attached) sessions.get(attached)?.watchers.delete(ws);
    // ptys stay alive on purpose — sessions survive tab switches and reloads
  });
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`Agent Deck running → http://localhost:${PORT}`);
});
