const $ = s => document.querySelector(s);
let _cachedToken = localStorage.getItem("hands_token") || "";
async function getAuthToken() {
  if (_cachedToken) return _cachedToken;
  try {
    const res = await fetch("/api/hands/token");
    const d = await res.json();
    if (d && d.token) {
      _cachedToken = d.token;
      if (d.port && typeof state !== "undefined") state.handsPort = d.port;
      localStorage.setItem("hands_token", _cachedToken);
      return _cachedToken;
    }
  } catch (e) {}
  return "";
}
const api = async (p, body) => {
  const headers = {"Content-Type": "application/json"};
  const token = (typeof state !== "undefined" && state.handsToken) || (await getAuthToken());
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch("/api/" + p, body ? {method: "POST", headers, body: JSON.stringify(body)} : {headers});
  return res.json();
};
const esc = s => (s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const TOPIC_COLOR = {"claude-setup":"mint","skills":"mint","multi-agent":"lav","local-models":"sky",
  "design":"rose","security":"peach","career":"peach","jarvis":"lav","saves-organizer":"sky",
  "agent-team":"lav","memory-graph":"sky","learning":"mint","markitdown":"mint",
  "agents-marketplace":"mint","mega-repo":"lav","free-backends":"sky","claude-md":"mint"};
let state = {view:"chat", topic:null, verdict:null};

/* ---------- views ---------- */
const views = {
async chat() {
  // Chat IS the Hammond agent now — one engine, one conversation, shared
  // across Command Center, the Hammond menu bar app, and the iOS remote
  // (all three drive/observe the same AgentStore over this WebSocket).
  // There used to be a second, separate "spawn claude/codex/ollama CLI
  // fresh per message" implementation here — removed so there's exactly
  // one chat experience instead of two divergent ones.
  if (!state.handsMsgs) state.handsMsgs = [];
  if (!state.handsToolCalls) state.handsToolCalls = [];
  if (state.handsStatus === undefined) state.handsStatus = "disconnected";
  if (state.handsToken === undefined) state.handsToken = localStorage.getItem("hands_token") || "";
  if (!state.handsEngine) state.handsEngine = "ollama";
  // Auto-connect once per page load — both apps run on the same Mac, so
  // there's no real reason to make the user copy/paste a token manually.
  if (!state.handsAutoTried && state.handsStatus === "disconnected") {
    state.handsAutoTried = true;
    api("hands/token").then(t => {
      if (t.token) {
        state.handsToken = t.token;
        if (t.port) state.handsPort = t.port;
        localStorage.setItem("hands_token", t.token);
        const el = $("#handstoken"); if (el) el.value = t.token;
        connectHands();
      }
    });
  }
  const statusColor = {connected:"mint", connecting:"peach", disconnected:"sky", error:"rose"}[state.handsStatus] || "sky";
  const opts = await api("term/options");
  // Per-engine model lists — ollama is real installed tags (from Ollama
  // itself via /api/term/options); claude/claude-cli mirror the exact ids
  // ClaudeClient.swift / the CLI's --model flag actually accept.
  const HANDS_MODELS = {
    ollama: (opts.local && opts.local.length) ? opts.local : ["(profile default)"],
    claude: ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"],
    "claude-cli": ["default", "opus", "sonnet", "haiku"],
  };
  const models = HANDS_MODELS[state.handsEngine];
  if (!state.handsModel || !models.includes(state.handsModel)) state.handsModel = models[0];
  const HANDS_ENGINE_LABEL = {ollama: "Local", claude: "Claude API", "claude-cli": "Claude Code"};
  const HANDS_ENGINE_COLOR = {ollama: "sky", claude: "lav", "claude-cli": "mint"};
  return `
  <div class="card glass chat-card">
    <h2><span class="dot t-${statusColor}"></span>Chat — Hammond
      <div class="row" style="margin-left:auto;gap:6px;align-items:center">
        <span class="sub" id="handsstatus">${esc(state.handsStatusText || "not connected")}</span>
      </div>
    </h2>
    <div class="row" style="margin-bottom:10px;gap:8px">
      <input id="handstoken" placeholder="token from Hammond → Settings → Remote" value="${esc(state.handsToken)}"
        style="flex:1" oninput="state.handsToken=this.value">
      <button class="act ghost" onclick="connectHands()">Connect</button>
    </div>
    <div class="row" style="margin-bottom:10px;gap:6px;flex-wrap:wrap;align-items:center">
      ${Object.keys(HANDS_MODELS).map(e => `<span class="pill ${state.handsEngine===e?"on t-"+HANDS_ENGINE_COLOR[e]:""}"
        onclick="setHandsEngine('${e}')">${HANDS_ENGINE_LABEL[e]}</span>`).join("")}
      <select id="handsmodel" style="width:auto;min-width:170px" onchange="state.handsModel=this.value">
        ${models.map(m=>`<option ${m===state.handsModel?"selected":""}>${esc(m)}</option>`).join("")}</select>
      <span class="sub">picks the model for your <i>next</i> message only — doesn't change the Mac app's own default</span>
    </div>
    <div class="chat-log" id="handslog">${renderHandsLog()}</div>
    <div id="handstools" style="margin:8px 0"></div>
    <div class="row" style="margin-top:12px">
      <textarea id="handsinput" rows="1" placeholder="ask Hammond…"
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendHands();}"></textarea>
      <button class="act" id="handssend" onclick="sendHands()">Send</button>
    </div>
    <div class="sub" style="margin-top:8px">talks straight to the Hammond Mac app over a local WebSocket — same agent, same tools, same conversation as the native app and the iPhone app.</div>
  </div>`;
},

async home() {
  const [st, hq, vit, act] = await Promise.all([api("status"), api("lifehq"), api("vitals"), api("activity?limit=12")]);
  const loaded = st.ollama_loaded;
  $("#topstats").innerHTML = `<span><b>${st.ollama_models.length}</b> models</span>
    <span><b>${st.skills.length}</b> skills</span>
    <span>brief: <b>${st.latest_brief ? st.latest_brief.replace(".md","") : "none yet"}</b></span>
    <span class="ollama-chip" title="${loaded === null ? "ollama unreachable" : loaded.length ? "loaded: "+esc(loaded.join(", ")) : "ollama up, no model in memory"}">
      <i class="status-dot ${loaded === null ? "err" : loaded.length ? "ok" : "run"}"></i>
      ${loaded === null ? "ollama off" : loaded.length ? esc(loaded[0]) : "ollama idle"}</span>`;
  const score = hq.checkin ? hq.checkin.score : null;
  return `
  <div class="grid3">
    <div class="card glass"><h2><span class="dot t-mint"></span>Today</h2>
      <div class="stat">${hq.goals.length}</div><div class="sub">open goals · ${hq.done_today.length} done today</div></div>
    <div class="card glass" style="text-align:center"><h2 style="justify-content:center"><span class="dot t-lav"></span>Day Score</h2>
      ${score !== null ? `<div class="score-ring" style="--p:${score}"><b>${score}</b></div>`
        : `<div class="empty">no check-in yet — Life HQ</div>`}</div>
    <div class="card glass"><h2><span class="dot t-sky"></span>Systems</h2>
      <div class="sub">ollama ${loaded === null ? "○&nbsp;offline" : "●&nbsp;online"}${loaded && loaded.length ? ` · <b style="color:var(--ink)">${esc(loaded[0])}</b> in memory` : loaded ? " · idle" : ""}</div>
      ${Object.entries(st.links).map(([k,v]) => `<div class="sub"><a href="${v}" target="_blank" style="color:var(--sky)">${k} ↗</a></div>`).join("")}</div>
  </div>
  <div class="grid2">
    <div class="card glass"><h2><span class="dot t-sky"></span>System Vitals
      <span class="sub" style="margin-left:auto;text-transform:none;letter-spacing:0">up ${esc(vit.uptime)}</span></h2>
      ${vitalMeter("CPU load", vit.cpu.pct, `${vit.cpu.load1} / ${vit.cpu.cores} cores`, "mint")}
      ${vitalMeter("Memory", vit.mem.pct, `${gb(vit.mem.used)} of ${gb(vit.mem.total)}`, "lav")}
      ${vitalMeter("Disk /", vit.disk.pct, `${gb(vit.disk.used)} of ${gb(vit.disk.total)}`, "peach")}</div>
    <div class="card glass"><h2><span class="dot t-peach"></span>Recent Activity</h2>
      <div class="list actlist">${act.map(activityRow).join("") || '<div class="empty">nothing logged yet — actions across the dashboard land here</div>'}</div></div>
  </div>
  <div class="card glass"><h2><span class="dot t-lav"></span>The Overseer</h2>
    <div class="overseer" id="overseer">Ask the Overseer for a status read on your day.</div>
    <div style="margin-top:12px"><button class="act ghost" onclick="askOverseer(this)">Consult Overseer</button></div></div>
  <div class="card glass"><h2><span class="dot t-peach"></span>Urgent Goals</h2>
    <div class="list">${hq.goals.filter(g=>g.urgent).map(goalRow).join("") || '<div class="empty">nothing urgent 🎉</div>'}</div></div>`;
},

async agentdrop() {
  const d = await api("agentdrop");
  const lib = await api("agentdrop/library");
  const synced = await api("agentdrop/synced");
  window._agentdropLibrary = lib.reels || [];
  window._agentdropSynced = synced.reels || [];
  if (!state.agentdropFilter) state.agentdropFilter = null;
  if (!state.agentdropQuery) state.agentdropQuery = "";
  if (!state.syncedQuery) state.syncedQuery = "";
  const fmtSize = b => b < 1024 ? `${b} B` : b < 1048576 ? `${(b/1024).toFixed(1)} KB` : `${(b/1048576).toFixed(1)} MB`;
  const drop = d.current_drop;
  const fileRow = f => `<div class="item">
    <div class="grow">${esc(f.name)}</div>
    <div class="meta">${fmtSize(f.size)} · ${esc(f.modified.replace("T"," "))}</div>
    <button onclick="openAgentDropFile('${f.name.replace(/'/g,"\\'")}')">open</button>
  </div>`;
  return `
  <div class="card glass"><h2><span class="dot t-mint"></span>Synced Reels — live from Instagram (${window._agentdropSynced.length})
    <button class="act ghost" style="margin-left:auto" onclick="openAgentDropFile('reels')">Open Folder</button>
  </h2>
  <div class="sub" style="margin-bottom:10px">Auto-synced every 10 minutes from <b>tech.review.nate</b> — anything saved there,
    or DM'd there from natep.howard, lands here automatically (ig-curate.py via launchd).</div>
  <input id="synced_q" placeholder="search captions…" value="${esc(state.syncedQuery)}"
    style="width:100%;margin-bottom:10px" oninput="state.syncedQuery=this.value;renderSyncedOnly()">
  <div class="list" id="synced_reels" style="max-height:320px;overflow-y:auto">${syncedReelRows(window._agentdropSynced, state.syncedQuery)}</div>
  </div>
  <div class="card glass"><h2><span class="dot t-peach"></span>Agent Drop
    <button class="act ghost" style="margin-left:auto" onclick="openAgentDropFile(null)">Open Workspace</button>
  </h2>
  <div class="sub">Drag anything (a link, a video, a PDF) onto the AgentDrop app and it runs Claude Code on it,
    saving output into <code>~/AgentDrop-Workspace</code>. That's <b>one shared folder, not per-drop folders</b> —
    a new drop's same-named files (metadata.json, summary.md, dropped_item.json) overwrite the last drop's.
    So only the most recent structured drop shows below, plus any uniquely-named leftovers from earlier ones —
    nothing here is invented history.</div>
  </div>
  ${!d.exists ? '<div class="card glass empty">no ~/AgentDrop-Workspace folder yet — drop something onto AgentDrop first</div>' : `
  <div class="grid2">
    <div class="card glass"><h2><span class="dot t-mint"></span>Current Drop</h2>
      ${drop ? `
        <b>${esc(drop.title || "untitled")}</b>
        <div class="sub" style="margin-top:4px">${esc(drop.uploader || "")}${drop.featured_speaker ? " · " + esc(drop.featured_speaker) : ""}</div>
        ${drop.url ? `<div class="sub"><a href="${esc(drop.url)}" target="_blank" style="color:var(--sky)">${esc(drop.url)} ↗</a></div>` : ""}
        ${drop.duration_seconds ? `<div class="sub">${Math.round(drop.duration_seconds/60)} min</div>` : ""}
        <div class="sub" style="margin-top:6px">dropped ${esc((drop.dropped_at||"").replace("T"," "))}</div>
        ${drop.web_tools && drop.web_tools.length ? `<div class="tags" style="display:flex;gap:6px;flex-wrap:wrap;margin-top:8px">
          ${drop.web_tools.map(t=>`<span class="pill">${esc(t)}</span>`).join("")}</div>` : ""}
      ` : '<div class="empty">no dropped_item.json in the workspace right now</div>'}
    </div>
    <div class="card glass"><h2><span class="dot t-sky"></span>Workspace Files (${d.files.length})</h2>
      <div class="list">${d.files.map(fileRow).join("") || '<div class="empty">empty</div>'}</div>
    </div>
  </div>`}
  <div class="card glass">
    <h2><span class="dot t-lav"></span>Library — every reel you've saved/DM'd to yourself on Instagram (${window._agentdropLibrary.length})</h2>
    <div class="sub" style="margin-bottom:10px">Pulled from your real curation ledger (<code>ig-curate.py</code> mirrors your
      Saved collection + self-DMs) — ${window._agentdropLibrary.filter(r=>r.made==="Y").length} of these were actually turned
      into real built tools.</div>
    <div class="row" style="gap:8px;margin-bottom:10px;flex-wrap:wrap">
      <input id="agentdrop_q" placeholder="search captions…" value="${esc(state.agentdropQuery)}"
        style="flex:1;min-width:160px" oninput="state.agentdropQuery=this.value;renderAgentDropOnly()">
      <span class="pill ${!state.agentdropFilter?"on t-lav":""}" style="cursor:pointer" onclick="filt('agentdropFilter',null)">All</span>
      <span class="pill ${state.agentdropFilter==='made'?"on t-mint":""}" style="cursor:pointer" onclick="filt('agentdropFilter','made')">Made into a tool</span>
      <span class="pill ${state.agentdropFilter==='not_made'?"on t-rose":""}" style="cursor:pointer" onclick="filt('agentdropFilter','not_made')">Not built</span>
    </div>
    <div class="list" id="agentdrop_library">${agentDropLibraryRows(window._agentdropLibrary, state.agentdropFilter, state.agentdropQuery)}</div>
  </div>`;
},

async reels() {
  window._reelsCache = await api("reels");
  return `
  <div class="card glass"><h2><span class="dot t-sky"></span>Add reels</h2>
    <div class="row"><input id="reelurls" placeholder="paste one or more Instagram reel links…">
    <button class="act" onclick="addReels(this)">Ingest</button></div>
    <div class="sub" style="margin-top:8px">Downloads audio, transcribes locally (whisper), auto-tags via ollama. Nothing leaves this machine.</div></div>
  <div class="card glass"><h2><span class="dot t-mint"></span>Vault <span id="reelcount"></span></h2>
    <input id="reelsearch" placeholder="search uploader / caption / transcript…" value="${esc(state.reelQuery||"")}"
      style="margin-bottom:12px" oninput="state.reelQuery=this.value;renderReelsOnly()">
    <div id="reelfilters" class="tags" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px"></div>
    <div class="grid2" id="reelgrid"></div></div>`;
},

async life() {
  const hq = await api("lifehq");
  const nw = hq.networth.at(-1);
  const netWorthNow = hq.computed_networth !== null ? hq.computed_networth : (nw ? nw.assets - nw.liabilities : null);
  const subTotal = hq.subscriptions.reduce((a,s)=>a+s.monthly,0);
  const ci = hq.checkin || {energy:5,focus:5,mood:5};
  const plaidStatus = await api("plaid/status");
  setTimeout(() => loadPlaidAccounts(), 50);
  const kindColor = k => k === "Asset" ? "mint" : "rose";
  const accountRow = a => `<div class="item">
      <span class="status-dot ${a.kind==="Asset"?"ok":"err"}"></span>
      <div class="grow">${esc(a.name)} <span class="meta">${esc(a.type)}</span></div>
      <div class="meta">$${a.balance.toLocaleString()}</div>
      <button onclick="delAccount(${a.id})">✕</button>
    </div>`;
  const budgetRow = cat => {
    const spent = hq.spending[cat] || 0;
    const limit = hq.budgets[cat];
    const pct = limit ? Math.min(100, Math.round(spent / limit * 100)) : 0;
    return `<div class="item">
      <div class="grow">${esc(cat)}
        <div class="meta">$${spent.toFixed(0)} of $${limit.toFixed(0)} — ${pct}%</div></div>
      <button onclick="delBudget('${esc(cat)}')">✕</button>
    </div>`;
  };
  const allCats = [...new Set([...Object.keys(hq.budgets), ...Object.keys(hq.spending)])].sort();
  return `
  <div class="card glass"><h2><span class="dot t-sky"></span>Linked Bank Accounts</h2>
    ${!plaidStatus.configured
      ? `<div class="sub">Not set up yet — add PLAID_CLIENT_ID/PLAID_SECRET to mission-control/.env (see .env.example), restart the server, then reload this tab.</div>`
      : `<div class="row" style="margin-bottom:10px"><button class="act" onclick="plaidLink()">Connect a bank</button>
         <span class="sub" style="margin-left:10px">${plaidStatus.env} mode</span></div>
         <div id="plaid_accounts">${plaidStatus.linked_items.length ? "loading balances…" : '<div class="empty">no accounts linked yet</div>'}</div>`}
  </div>
  <div class="grid2">
    <div class="card glass"><h2><span class="dot t-mint"></span>Goals Pad</h2>
      <div class="row"><input id="goaltext" placeholder="new goal…">
        <button class="act ghost" onclick="addGoal(1)">urgent</button><button class="act" onclick="addGoal(0)">add</button></div>
      <div class="list" style="margin-top:12px">${hq.goals.map(goalRow).join("") || '<div class="empty">empty pad</div>'}</div></div>
    <div class="card glass"><h2><span class="dot t-lav"></span>Daily Check-in</h2>
      <div class="slider">
        <label>Energy <b id="ev">${ci.energy}</b></label><input type="range" min="1" max="10" value="${ci.energy}" id="energy" oninput="$('#ev').textContent=this.value">
        <label>Focus <b id="fv">${ci.focus}</b></label><input type="range" min="1" max="10" value="${ci.focus}" id="focus" oninput="$('#fv').textContent=this.value">
        <label>Mood <b id="mv">${ci.mood}</b></label><input type="range" min="1" max="10" value="${ci.mood}" id="mood" oninput="$('#mv').textContent=this.value">
      </div>
      <div style="margin-top:14px"><button class="act" onclick="checkin(this)">Log today</button>
      ${hq.checkin ? `<span class="sub" style="margin-left:10px">today's score: <b>${hq.checkin.score}</b></span>` : ""}</div></div>
  </div>
  <div class="grid2">
    <div class="card glass"><h2><span class="dot t-peach"></span>Subscriptions — $${subTotal.toFixed(0)}/mo</h2>
      <div class="row"><input id="subname" placeholder="name" style="flex:2"><input id="submo" placeholder="$/mo" style="flex:1">
        <button class="act" onclick="addSub()">add</button></div>
      <div class="list" style="margin-top:12px">${hq.subscriptions.map(s=>`<div class="item"><div class="grow">${esc(s.name)}</div>
        <div class="meta">$${s.monthly.toFixed(2)}/mo</div><button onclick="delSub(${s.id})">✕</button></div>`).join("") || '<div class="empty">none tracked</div>'}</div></div>
    <div class="card glass"><h2><span class="dot t-sky"></span>Net Worth</h2>
      ${netWorthNow !== null ? `<div class="stat">$${netWorthNow.toLocaleString()}</div>
        <div class="sub">${hq.computed_networth !== null ? "live from tracked accounts" : `assets $${nw.assets.toLocaleString()} − liabilities $${nw.liabilities.toLocaleString()} · ${nw.date}`}</div>`
        : '<div class="empty">no accounts or snapshot yet</div>'}
      <div class="row" style="margin-top:12px">
        ${hq.accounts.length
          ? `<button class="act" onclick="syncNetWorth(this)">Snapshot from accounts</button>`
          : `<input id="nwa" placeholder="assets $"><input id="nwl" placeholder="liabilities $"><button class="act" onclick="addNW()">snapshot</button>`}
      </div>
      ${hq.networth.length > 1 ? sparkline(hq.networth.map(n=>n.assets-n.liabilities)) : ""}</div>
  </div>
  <div class="grid2">
    <div class="card glass"><h2><span class="dot t-mint"></span>Accounts</h2>
      <div class="sub" style="margin-bottom:10px">Tracked manually — for anything Plaid can't reach (retirement, vehicles, loans not linked).</div>
      <div class="row" style="flex-wrap:wrap;gap:6px">
        <input id="acctname" placeholder="name" style="flex:2;min-width:100px">
        <input id="accttype" placeholder="type (Bank, Loan…)" style="flex:1;min-width:90px">
        <select id="acctkind" style="flex:1;min-width:90px"><option>Asset</option><option>Liability</option></select>
        <input id="acctbal" placeholder="balance $" style="flex:1;min-width:90px">
        <button class="act" onclick="addAccount()">add</button>
      </div>
      <div class="list" style="margin-top:12px">${hq.accounts.map(accountRow).join("") || '<div class="empty">no accounts tracked</div>'}</div>
    </div>
    <div class="card glass"><h2><span class="dot t-peach"></span>Budgets — this month</h2>
      <div class="row"><input id="budgetcat" placeholder="category" style="flex:2"><input id="budgetamt" placeholder="$/mo limit" style="flex:1">
        <button class="act" onclick="addBudget()">set</button></div>
      <div class="list" style="margin-top:12px">${allCats.filter(c=>hq.budgets[c]).map(budgetRow).join("") || '<div class="empty">no budgets set</div>'}</div>
      <div class="row" style="margin-top:12px">
        <input type="file" id="csvfile" accept=".csv" style="flex:1">
        <button class="act ghost" onclick="importCSV(this)">Import bank CSV</button>
      </div>
      <div class="sub" style="margin-top:6px">Needs Date + Amount columns (Description/Category optional) — powers the spending totals above.</div>
    </div>
  </div>`;
},

async briefs() {
  const bs = await api("briefs");
  return `
  <div class="card glass"><h2><span class="dot t-peach"></span>CEO Morning Brief</h2>
    <div class="sub">A local agent (qwen3-coder:30b via Ollama, no cloud) writes this every morning at 8:00 AM — it reads your goals, check-ins, memory index, and job tracker to set today's priorities.</div>
    <div style="margin-top:12px"><button class="act" onclick="genBrief(this)">Generate now</button></div></div>
  ${bs.map(b=>`<div class="brief glass"><h3>${b.name}</h3><div class="md">${mdlite(b.content)}</div></div>`).join("")
    || '<div class="card glass empty">No briefs yet — generate one now, or wait for 8 AM.</div>'}`;
},

async term() {
  const [opts, jobs, snap] = await Promise.all([api("term/options"), api("term/jobs"), api("term/snapshot")]);
  window._termOpts = opts;
  const eng = state.engine || "claude";
  const models = opts[eng] || [];
  const terminalTabs = snap.terminal_tabs || [];
  const browserTabs = snap.browser_tabs || [];
  const tabCounts = browserTabs.reduce((a,t)=>{ a[t.category]=(a[t.category]||0)+1; return a; }, {});
  const guiStamp = snap.gui_generated || snap.generated || "";
  return `
  <div class="card glass"><h2><span class="dot t-mint"></span>Launch Agent</h2>
    <div class="sub" style="margin-bottom:12px">Type a task, pick which agent should do it, and it runs in the background —
      you don't have to sit and watch it. "Local" runs a free Ollama model on this Mac; Claude/Codex use your CLI logins.</div>
    <div class="row" style="margin-bottom:10px;flex-wrap:wrap">
      ${["claude","codex","local"].map(e=>`<span class="pill ${eng===e?"on t-"+({claude:"mint",codex:"peach",local:"sky"}[e]):""}"
        onclick="setEngine('${e}')">${{claude:"Claude Code",codex:"Codex",local:"Ollama (local)"}[e]}</span>`).join("")}
      <select id="tmodel" style="width:auto;min-width:160px">${models.map(m=>`<option>${m}</option>`).join("")||"<option>default</option>"}</select>
      <input id="tcwd" placeholder="~/Projects" value="${state.cwd||"~/Projects"}" style="width:220px;flex:none">
    </div>
    <textarea id="tprompt" rows="3" placeholder="what should the agent do?"></textarea>
    <div style="margin-top:12px" class="row">
      <button class="act" onclick="runJob(this)">Run in background</button>
      <span class="sub">claude runs with acceptEdits · codex sandboxed to workspace</span></div></div>
  <div class="card glass"><h2><span class="dot t-lav"></span>Jobs</h2>
    <div class="list">${jobs.map(j=>`<div class="item ${state.job===j.id?"sel":""}" onclick="openJob('${j.id}')" style="cursor:pointer">
      <span class="status-dot ${j.status==="running"?"run":j.status==="done"?"ok":"err"}"></span>
      <div class="grow"><b>${j.engine}</b>${j.model!=="default"?" · "+j.model:""} — ${esc(j.prompt)}</div>
      <div class="meta">${j.started}${j.ended?" → "+j.ended:""} · ${j.status}</div>
      ${j.status==="running"?`<button onclick="event.stopPropagation();stopJob('${j.id}')" title="stop">■</button>`:""}
    </div>`).join("") || '<div class="empty">no jobs yet — launch one above</div>'}</div></div>
  <div class="grid2">
    <div class="card glass"><h2><span class="dot t-sky"></span>Open CLI Sessions
      <button class="mini-btn" onclick="render()" title="refresh snapshot">refresh</button></h2>
      <div class="sub" style="margin-bottom:12px">${terminalTabs.length} Terminal tabs · GUI snapshot ${esc(guiStamp.replace("T"," "))}</div>
      <div class="list snaplist">${terminalTabs.map(sessionRow).join("") || '<div class="empty">no Terminal tabs detected</div>'}</div></div>
    <div class="card glass"><h2><span class="dot t-peach"></span>Local Services</h2>
      <div class="list">${(snap.tracked_apps||[]).map(trackedAppRow).join("")}</div>
      <div class="sub" style="margin-top:12px">${(snap.services||[]).length} listening TCP services found</div></div>
  </div>
  <div class="card glass"><h2><span class="dot t-mint"></span>Browser Tabs — ${browserTabs.length}</h2>
    <div class="tags" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">
      ${Object.entries(tabCounts).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<span class="pill">${esc(k)} · ${v}</span>`).join("")}
    </div>
    <div class="list tablist">${browserTabs.map(browserTabRow).join("") || '<div class="empty">no browser tabs detected</div>'}</div></div>
  <div class="card glass"><h2><span class="dot t-lav"></span>CLI Process Detail</h2>
    <div class="list proclist">${(snap.cli_processes||[]).map(processRow).join("") || '<div class="empty">no tracked CLI processes detected</div>'}</div></div>
  ${state.job?`<div class="card glass"><h2><span class="dot t-sky"></span>Output — ${state.job}
      <span class="sub" id="tstatus"></span></h2><pre class="termout" id="termout"></pre></div>`:""}`;
},

async swarm() {
  const runs = await api("swarm/runs");
  let detail = "";
  if (state.srun) {
    const d = await api("swarm/" + state.srun);
    detail = `
    <div class="card glass"><h2><span class="dot t-lav"></span>Run ${d.id} — ${d.status}</h2>
      <div class="sub" style="margin-bottom:12px">${esc(d.goal)}</div>
      <div class="grid2">${d.workers.map((w,i)=>`<div class="item">
        <span class="status-dot ${w.status==="running"?"run":w.status==="done"?"ok":"err"}"></span>
        <div class="grow"><b>${esc(d.plan[i]?.title||w.prompt)}</b>
          <div class="meta">${w.engine}${w.model!=="default"?" · "+w.model:""} · ${w.status}</div></div>
        <button onclick="openJob('${w.id}');setView('term')" title="output">❯</button></div>`).join("")}</div>
      ${d.result?`<h2 style="margin-top:16px"><span class="dot t-mint"></span>Result</h2><div class="overseer">${esc(d.result)}</div>`:""}
      <h2 style="margin-top:16px"><span class="dot t-sky"></span>Shared Memory</h2>
      <pre class="termout" style="max-height:260px">${esc(d.memory)}</pre></div>`;
    if (d.status === "running") { clearTimeout(window._swt); window._swt = setTimeout(render, 4000); }
  }
  return `
  <div class="card glass"><h2><span class="dot t-mint"></span>Swarm</h2>
    <div class="sub" style="margin-bottom:12px">Give it one big goal and it splits the work into 2-4 smaller sub-tasks,
      runs them all <i>at the same time</i> on separate agents, then writes a combined summary. Good for anything that
      breaks into independent pieces — Flows (next tab) is better when steps need to happen in order, one feeding the next.</div>
    <textarea id="sgoal" rows="2" placeholder="give the swarm a goal…"></textarea>
    <div class="row" style="margin-top:10px">
      <input id="scwd" placeholder="~/Projects/mission-control/sandbox" value="${state.scwd||"~/Projects/mission-control/sandbox"}" style="width:280px;flex:none">
      <button class="act" onclick="runSwarm(this)">Launch swarm</button>
      <span class="sub">simple→local qwen · medium→haiku · complex→your default Claude</span></div></div>
  <div class="card glass"><h2><span class="dot t-peach"></span>Runs</h2>
    <div class="list">${runs.map(r=>`<div class="item ${state.srun===r.id?"sel":""}" style="cursor:pointer" onclick="openSwarm('${r.id}')">
      <span class="status-dot ${r.status==="running"?"run":"ok"}"></span>
      <div class="grow">${esc(r.goal)}</div><div class="meta">${r.workers} workers · ${r.started} · ${r.status}</div></div>`).join("")
      || '<div class="empty">no swarm runs yet</div>'}</div></div>
  ${detail}`;
},

async flows() {
  const [flows, runs, opts] = await Promise.all([api("flows"), api("flows/runs"), api("term/options")]);
  if (!state.flowDraft) state.flowDraft = {name:"", steps:[{name:"Step 1", engine:"claude", model:"default", prompt:"{input}"}]};
  const draft = state.flowDraft;
  let detail = "";
  if (state.frun) {
    const d = await api("flows/run/" + state.frun);
    if (!d.error) {
      detail = `
      <div class="card glass"><h2><span class="dot t-sky"></span>Run ${d.id} — ${d.status}</h2>
        <div class="sub" style="margin-bottom:12px">${esc(d.input)}</div>
        <div class="flowchain">${d.steps.map((s,i)=>`
          <div class="flowstep glass ${s.status==="running"?"run":s.status==="done"?"ok":s.status==="pending"?"":"err"}">
            <div class="who"><span class="status-dot ${s.status==="running"?"run":s.status==="done"?"ok":s.status==="pending"?"":"err"}"></span> ${esc(s.name)}</div>
            <div class="meta">${esc(s.status)}</div>
            ${s.output ? `<pre class="termout" style="max-height:160px">${esc(s.output.slice(-1200))}</pre>` : ""}
          </div>`).join('<div class="flow-arrow">→</div>')}</div>
        ${d.result ? `<h2 style="margin-top:16px"><span class="dot t-mint"></span>Final Output</h2><div class="overseer">${esc(d.result)}</div>` : ""}
      </div>`;
      if (d.status === "running") { clearTimeout(window._frt); window._frt = setTimeout(render, 3000); }
    }
  }
  return `
  <div class="card glass"><h2><span class="dot t-sky"></span>Describe it</h2>
    <div class="sub" style="margin-bottom:10px">Tell it what you want done, step by step, and it'll draft the whole
      chain below — you can still tweak each step's engine, model, and prompt before saving.</div>
    <div class="row"><textarea id="flowask" rows="2" placeholder="e.g. read a folder of notes, summarize each one, then write one combined report"></textarea></div>
    <div style="margin-top:10px"><button class="act" id="flowplanbtn" onclick="planFlow(this)">Draft flow</button></div>
  </div>
  <div class="card glass"><h2><span class="dot t-lav"></span>Build a Flow — chain agents so each one's output feeds the next</h2>
    <div class="row"><input id="flowname" placeholder="flow name…" value="${esc(draft.name)}" oninput="updateFlowMeta('name',this.value)"></div>
    <div class="flowchain" style="margin-top:12px">
      ${draft.steps.map((s,i)=>flowStepEditor(s,i,draft.steps.length,opts)).join('<div class="flow-arrow">→</div>')}
    </div>
    <div class="row" style="margin-top:12px">
      <button class="act ghost" onclick="addFlowStep()">+ step</button>
      <button class="act" onclick="saveFlow(this)">Save flow</button>
      <span class="sub">each step's prompt can use <code>{input}</code> (previous step's output) and <code>{goal}</code> (the original ask)</span>
    </div>
  </div>
  <div class="card glass"><h2><span class="dot t-mint"></span>Saved Flows</h2>
    <div class="list">${flows.map(flowRow).join("") || '<div class="empty">no flows saved yet</div>'}</div>
  </div>
  <div class="card glass"><h2><span class="dot t-peach"></span>Runs</h2>
    <div class="list">${runs.map(r=>`<div class="item ${state.frun===r.id?"sel":""}" style="cursor:pointer" onclick="openFlowRun('${r.id}')">
      <span class="status-dot ${r.status==="running"?"run":r.status==="done"?"ok":"err"}"></span>
      <div class="grow"><b>${esc(r.flow_name)}</b><div class="meta">${esc(r.input).slice(0,80)}</div></div>
      <div class="meta">${r.started} · ${r.status}</div></div>`).join("") || '<div class="empty">no runs yet</div>'}</div>
  </div>
  ${detail}`;
},


async control() {
  return `
  <div class="card glass"><h2><span class="dot t-mint"></span>Hardware Control</h2>
    <div class="row" style="margin-top:12px; gap:8px">
      <button class="act ghost" onclick="hwCtrl('sleep')">Sleep Mac</button>
      <button class="act ghost" onclick="hwCtrl('volume_up')">Vol Up</button>
      <button class="act ghost" onclick="hwCtrl('volume_down')">Vol Down</button>
      <button class="act ghost" onclick="hwCtrl('mute')">Mute</button>
      <button class="act ghost" onclick="hwCtrl('unmute')">Unmute</button>
    </div>
  </div>
  <div class="card glass"><h2><span class="dot t-lav"></span>Software Control</h2>
    <div class="row" style="margin-top:12px">
      <input id="sw_app_name" placeholder="App Name (e.g. Safari)" style="flex:1">
      <button class="act" onclick="swCtrl('open')">Open App</button>
      <button class="act ghost" onclick="swCtrl('quit')">Quit App</button>
    </div>
  </div>
  `;
},

async tools() {
  const st = await api("status");
  return `
  <div class="card glass"><div class="sub">A read-only reference: what's installed and running — not something you configure here.</div></div>
  <div class="grid2">
    <div class="card glass"><h2><span class="dot t-mint"></span>Installed Skills (${st.skills.length})</h2>
      <div class="tags" style="display:flex;gap:6px;flex-wrap:wrap">${st.skills.map(s=>`<span class="pill">${s}</span>`).join("")}</div></div>
    <div class="card glass"><h2><span class="dot t-sky"></span>Local Models (${st.ollama_models.length})</h2>
      <div class="tags" style="display:flex;gap:6px;flex-wrap:wrap">${st.ollama_models.map(m=>`<span class="pill">${m}</span>`).join("")}</div></div>
  </div>
  <div class="card glass"><h2><span class="dot t-lav"></span>Scheduled Jobs</h2>
    ${st.cron.length ? st.cron.map(c=>`<div class="sub"><code>${esc(c)}</code></div>`).join("") : '<div class="empty">no cron jobs</div>'}</div>
  <div class="card glass"><h2><span class="dot t-peach"></span>Quick Reference</h2>
    <div class="sub"><code>claude-local</code> — Claude Code on local qwen · <code>markitdown f.pdf</code> — PDF→markdown ·
    <code>skills find "query"</code> — discover skills (installed globally 2026-07-20) · <code>/plugin</code> — agent marketplace (claude-code-workflows)</div></div>`;
},

async reeltools() {
  const tools = await api("tools");
  const rows = tools.map(t => `
    <div class="card glass" style="margin-bottom:10px">
      <div class="row" style="justify-content:space-between;align-items:center">
        <div>
          <b>${esc(t.name)}</b>
          <div class="sub">${esc(t.desc)}</div>
          <div class="sub"><code>${esc(t.usage)}</code></div>
        </div>
        <div class="row" style="gap:6px">
          <input id="args_${t.id}" placeholder="args (optional)" style="width:180px"
                 value="${esc((t.usage.split(t.script)[1] || "").trim())}">
          <button class="act" onclick="runReelTool('${t.id}')">Run</button>
        </div>
      </div>
    </div>`).join("");
  return `
  <div class="card glass"><h2><span class="dot t-mint"></span>Reel Tools (${tools.length})</h2>
    <div class="sub" style="margin-bottom:12px">Real tools built from AgentDrop reel source material. Each runs
      locally as a standalone script — no cloud calls unless the tool itself needs one (noted in its usage).</div>
  </div>
  <div class="grid2" style="grid-template-columns:1fr">${rows}</div>
  <div class="card glass"><h2><span class="dot t-sky"></span>Output</h2>
    <pre class="termout" id="reeltool_out" style="min-height:200px">Run a tool to see output here...</pre>
  </div>`;
},

async apps() {
  if (!state.appsQuery) state.appsQuery = "";
  window._appsCache = await api("apps");
  const cats = ["Apps", "Skills", "Websites", "Projects", "Inspo"];
  return `
  <div class="card glass">
    <h2><span class="dot t-lav"></span>Apps (<span id="appscount">${window._appsCache.length}</span>)
      <button class="act ghost" style="margin-left:auto" onclick="rescanApps()">Rescan</button>
    </h2>
    <div class="sub" style="margin-bottom:10px">Every real app, skill, website, and project you've built —
      scanned live from ~/Projects, ~/Applications, and ~/.claude/skills. No placeholders.</div>
    <div class="row" style="gap:8px;margin-bottom:10px;flex-wrap:wrap">
      <input id="apps_q" placeholder="search…" value="${esc(state.appsQuery)}"
        style="flex:1;min-width:160px" oninput="state.appsQuery=this.value;renderAppsOnly()">
      <span class="pill ${!state.appsCategory ? "on t-lav" : ""}" style="cursor:pointer" onclick="filt('appsCategory',null)">All</span>
      ${cats.map(c => `<span class="pill ${state.appsCategory===c?"on t-lav":""}" style="cursor:pointer"
        onclick="filt('appsCategory','${c}')">${c}</span>`).join("")}
    </div>
  </div>
  <div id="apps_grid">${appTiles(window._appsCache)}</div>`;
},

async projects() {
  const projects = await api("projects");
  const statusColor = {
    "active now": "mint", "uncommitted work pending": "peach",
    "up to date": "sky", "stale": "rose", "no commits yet": "lav",
  };
  const card = p => `
    <div class="card glass" style="margin-bottom:14px">
      <h2><span class="dot t-${statusColor[p.status_label] || "sky"}"></span>${esc(p.name)}
        <span class="pill" style="margin-left:8px">${esc(p.branch)}</span>
        <span class="pill" style="margin-left:6px">${esc(p.status_label)}</span>
        ${p.active_session ? `<span class="pill on t-mint" style="margin-left:6px">${esc(p.active_session.engine)} running ${esc(p.active_session.etime || "")}</span>` : ""}
      </h2>
      <div class="sub" style="margin-bottom:8px">last touched ${esc(p.last_touched)}${p.remote ? ` · ${esc(p.remote)}` : ""}</div>
      <div class="grid2">
        <div>
          <b style="font-size:12px">What's been done</b>
          <div class="list" style="margin-top:6px">
            ${p.recent_commits.length ? p.recent_commits.map(c => `
              <div class="item"><div class="grow"><code style="opacity:0.6">${esc(c.hash)}</code> ${esc(c.message)}</div>
                <div class="meta">${esc(c.when)}</div></div>`).join("")
              : '<div class="empty">no commits yet</div>'}
          </div>
        </div>
        <div>
          <b style="font-size:12px">What needs to be done</b>
          <div class="list" style="margin-top:6px">
            ${p.uncommitted.length ? p.uncommitted.slice(0, 10).map(f => `
              <div class="item"><code style="width:28px;display:inline-block;opacity:0.6">${esc(f.status)}</code>
                <div class="grow">${esc(f.path)}</div></div>`).join("")
              : '<div class="empty">nothing uncommitted</div>'}
            ${p.unpushed_count ? `<div class="sub" style="margin-top:6px">${p.unpushed_count} commit(s) not pushed</div>` : ""}
          </div>
        </div>
      </div>
    </div>`;
  return `
  <div class="card glass"><h2><span class="dot t-lav"></span>Projects (${projects.length})</h2>
    <div class="sub">Real git state from your repos, cross-referenced with actually-running Terminal/Claude/Codex
      sessions where the title names the project. No invented hours or fake progress — "running" only shows when
      a live session is actually detected; everything else is real git history.</div>
  </div>
  ${projects.length ? projects.map(card).join("") : '<div class="card glass empty">no git repos found under ~/Projects</div>'}`;
},

async pipeline() {
  const d = await api("pipeline");
  const engineColor = {claude: "lav", agy: "mint", codex: "peach", ollama: "sky"};
  const engineLabel = {claude: "Claude", agy: "agy / Antigravity", codex: "Codex", ollama: "Ollama"};
  const row = p => `<div class="item">
    <span class="pill on t-${engineColor[p.engine]||"sky"}">${esc(engineLabel[p.engine]||p.engine)}</span>
    <div class="grow"><code style="font-size:11px">${esc(p.args)}</code></div>
    <div class="meta">pid ${esc(p.pid)} · up ${esc(p.etime)} · cpu ${esc(p.cpu)}% · mem ${esc(p.mem)}%</div>
  </div>`;
  const ollamaBlock = () => {
    if (d.ollama_loaded === null) return '<div class="empty">Ollama unreachable on :11434</div>';
    if (!d.ollama_loaded.length) return '<div class="empty">Ollama running, nothing loaded in memory right now</div>';
    return d.ollama_loaded.map(m => `<div class="item">
      <div class="grow"><b>${esc(m.name || m.model)}</b></div>
      <div class="meta">${m.size_vram ? (m.size_vram/1e9).toFixed(1)+" GB vram" : ""} · expires ${esc(m.expires_at||"")}</div>
    </div>`).join("");
  };
  return `
  <div class="card glass"><h2><span class="dot t-lav"></span>Pipeline — live, not simulated</h2>
    <div class="sub">Real running processes for the tiered review pipeline: Claude reasons/verifies,
      agy (Antigravity, Gemini-backed) does deeper passes, Ollama runs local models for bulk work.
      Auto-refreshes every 4s while this tab is open.</div>
  </div>
  <div class="card glass"><h2><span class="dot t-mint"></span>Running now (${d.processes.length})</h2>
    <div class="list" id="pipeline_procs">${d.processes.length ? d.processes.map(row).join("") : '<div class="empty">nothing from Claude/agy/Codex/Ollama running right now</div>'}</div>
  </div>
  <div class="card glass"><h2><span class="dot t-sky"></span>Ollama — loaded models</h2>
    <div class="list" id="pipeline_ollama">${ollamaBlock()}</div>
  </div>`;
},

async learn() {
  const history = await api("learn/history");
  return `
  <div class="card glass"><h2><span class="dot t-lav"></span>Learn</h2>
    <div class="sub" style="margin-bottom:12px">Pick a subject. A local model builds a short curriculum, pulls in
      real curated resources where they exist, and gives you a quiz to test yourself — all offline except the
      search links, which just open your browser.</div>
    <div class="row" style="gap:8px;margin-bottom:8px">
      <input id="learn_subject" placeholder="e.g. \"Python generators\", \"the French Revolution\", \"SQL joins\""
             style="flex:1" onkeydown="if(event.key==='Enter')startLearn()">
      <button class="act" onclick="startLearn()">Teach me</button>
    </div>
    ${history.length ? `<div class="sub">Recent: ${history.map(h=>`<span class="pill" style="cursor:pointer" onclick="loadLearn('${esc(h.subject)}')">${esc(h.subject)}</span>`).join(" ")}</div>` : ""}
  </div>
  <div id="learn_body"></div>`;
},

async compare() {
  const rows = await api("compare");
  const form = compareForm();
  if (!rows.length) {
    return `<div class="card glass"><h2><span class="dot t-peach"></span>Compare</h2>
      <div class="sub">Nothing to compare yet.</div></div>${form}`;
  }
  const cards = rows.map(r => `
    <div class="card glass" style="margin-bottom:14px">
      <h2><span class="dot t-peach"></span>${esc(r.feature)}</h2>
      <div class="grid2" style="margin-top:8px">
        <div class="card glass" style="background:rgba(168,216,245,0.06)">
          <b style="color:var(--sky,#a8d8f5)">Claude — ${esc(r.claude.label)}</b>
          <ul style="margin:8px 0 0;padding-left:18px">${r.claude.items.map(i=>`<li class="sub" style="margin-bottom:4px">${esc(i)}</li>`).join("")}</ul>
          <div class="sub" style="margin-top:8px;font-style:italic">${esc(r.claude.note)}</div>
        </div>
        <div class="card glass" style="background:rgba(195,184,245,0.06)">
          <b style="color:var(--lav,#c3b8f5)">Gemini — ${esc(r.gemini.label)}</b>
          <ul style="margin:8px 0 0;padding-left:18px">${r.gemini.items.map(i=>`<li class="sub" style="margin-bottom:4px">${esc(i)}</li>`).join("")}</ul>
          <div class="sub" style="margin-top:8px;font-style:italic">${esc(r.gemini.note)}</div>
        </div>
      </div>
      <div class="sub" style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(255,255,255,0.08)"><b>Verdict:</b> ${esc(r.verdict)}</div>
    </div>`).join("");
  return `<div class="sub" style="margin-bottom:12px">Side-by-side comparison of what Claude built vs. what Gemini/Antigravity built for the same feature, so you can pick what you want from each.</div>${cards}${form}`;
},

async workflows() {
  return `
  <div class="card glass"><h2><span class="dot t-mint"></span>Safe Workflows (Reel Archive)</h2>
    <div class="sub" style="margin-bottom:12px">Test the local workflows generated by the ReelAnalyzer subagents. These run completely offline and locally using shell scripts.</div>
    <div class="row" style="margin-bottom:12px; gap:8px">
      <button class="act" onclick="testWorkflow('python3 ~/Projects/app-projects/mac-dotfiles-backup/scripts/repomap.py ~/Projects/app-projects/command-center/mission-control')">Test Graphify (Map)</button>
      <button class="act" onclick="testWorkflow('python3 ~/Projects/app-projects/mac-dotfiles-backup/scripts/web-search.py &quot;Agentic AI&quot;')">Test Web Search</button>
      <button class="act" onclick="testWorkflow('python3 ~/Projects/app-projects/mac-dotfiles-backup/scripts/web-scrape.py https://example.com')">Test Web Scraper</button>
      <button class="act" onclick="testWorkflow('tail -n 20 ~/Projects/app-projects/mac-dotfiles-backup/scripts/clap_detector.out')">Check Audio Trigger Logs</button>
    </div>
    <pre class="termout" id="wf_out" style="min-height:200px">Select a workflow to test...</pre>
  </div>`;
},

async artifacts() {
  let items = [];
  try { items = await (await fetch("/api/artifacts")).json(); } catch (e) {}
  return `
  <div class="card glass">
    <h2><span class="dot t-lav"></span>Artifacts Ring</h2>
    <div class="sub" style="margin-bottom:12px">Generated markdown reports, task plans, research outputs, and swarm synthesis results across your workspace.</div>
    <div class="list" style="max-height:70vh;overflow-y:auto">
      ${(items || []).map(a => `
        <div class="item" style="cursor:pointer" data-path="${esc(a.path)}" onclick="viewArtifact(this.dataset.path)">
          <span class="pill t-${a.source==='swarm'?'mint':a.source==='flow'?'sky':'peach'}">${esc(a.source)}</span>
          <div class="grow" style="margin-left:8px">
            <b>${esc(a.title)}</b>
            <div class="meta">${esc(a.name)} · ${(a.size/1024).toFixed(1)} KB · ${esc(a.modified)}</div>
          </div>
          <button onclick="event.stopPropagation();viewArtifact(this.closest('.item').dataset.path)">View</button>
        </div>
      `).join("") || '<div class="empty">No artifacts generated yet</div>'}
    </div>
  </div>
  <div id="artifact_modal" hidden style="position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:999;display:flex;align-items:center;justify-content:center;padding:24px" onclick="if(event.target===this)this.hidden=true">
    <div class="card glass" style="width:90%;max-width:800px;max-height:85vh;display:flex;flex-direction:column">
      <div class="row" style="justify-content:space-between;margin-bottom:12px">
        <h3 id="art_title" style="margin:0">Artifact</h3>
        <button onclick="$('#artifact_modal').hidden=true">✕</button>
      </div>
      <pre id="art_content" style="flex:1;overflow:auto;white-space:pre-wrap;font-size:0.85rem;background:rgba(0,0,0,0.3);padding:12px;border-radius:8px"></pre>
    </div>
  </div>`;
},

async filegraph() {
  setTimeout(() => initFileGraph(), 50);
  return `
  <div class="card glass" style="display:flex;flex-direction:column;height:80vh">
    <h2><span class="dot t-lav"></span>Understand Anything (FileGraph)</h2>
    <div style="display:flex;align-items:center;margin-bottom:12px">
      <div class="sub" style="flex:1">Interactive Force-Directed Node Graph mapping all FileGraph DB dependencies.</div>
      <button class="act" id="btn_rebuild_fg" onclick="rebuildFileGraph(this)">⚡ Rebuild Graph</button>
    </div>
    <div id="graph-container" style="flex:1;background:rgba(0,0,0,0.2);border-radius:12px;overflow:hidden;position:relative;">
        <svg id="d3graph" style="width:100%;height:100%"></svg>
    </div>
  </div>`;
}
};

/* ---------- components ---------- */
const goalRow = g => `<div class="item ${g.urgent?"urgent":""}"><div class="grow">${esc(g.text)}</div>
  <div class="meta">${g.created}</div><button title="done" onclick="doneGoal(${g.id})">✓</button>
  <button title="delete" onclick="delGoal(${g.id})">✕</button></div>`;

const chatBubble = m => `<div class="msg ${m.role}"><div class="bubble">${esc(m.content)}</div></div>`;

const compareForm = () => `
  <div class="card glass" style="margin-top:14px">
    <h2><span class="dot t-peach"></span>Record a comparison</h2>
    <div class="sub" style="margin-bottom:10px">For a feature you actually built (or evaluated) both ways — not a generated guess, since there's no honest way to synthesize what the other side actually did.</div>
    <input id="cmp_feature" placeholder="Feature name">
    <div class="grid2" style="margin-top:8px">
      <div>
        <b class="sub" style="color:var(--sky,#a8d8f5)">Claude</b>
        <input id="cmp_claude_label" placeholder="Label" style="margin-top:6px">
        <textarea id="cmp_claude_items" rows="3" placeholder="One point per line" style="margin-top:6px"></textarea>
        <input id="cmp_claude_note" placeholder="Note" style="margin-top:6px">
      </div>
      <div>
        <b class="sub" style="color:var(--lav,#c3b8f5)">Gemini</b>
        <input id="cmp_gemini_label" placeholder="Label" style="margin-top:6px">
        <textarea id="cmp_gemini_items" rows="3" placeholder="One point per line" style="margin-top:6px"></textarea>
        <input id="cmp_gemini_note" placeholder="Note" style="margin-top:6px">
      </div>
    </div>
    <input id="cmp_verdict" placeholder="Verdict" style="margin-top:8px">
    <div class="row" style="margin-top:10px"><button class="act" onclick="submitCompare()">Add comparison</button></div>
  </div>`;

const ENGINE_COLOR = {claude:"mint", codex:"peach", local:"sky"};
const ENGINE_LABEL = {claude:"Claude", codex:"Codex", local:"Local"};

const flowStepEditor = (s,i,total,opts) => `<div class="flowstep glass">
  <input class="fs-name" placeholder="step name" value="${esc(s.name)}" oninput="updateFlowStep(${i},'name',this.value)">
  <div class="row" style="margin:8px 0;flex-wrap:wrap">
    ${["claude","codex","local"].map(e=>`<span class="pill ${s.engine===e?"on t-"+ENGINE_COLOR[e]:""}" onclick="setFlowStepEngine(${i},'${e}')">${ENGINE_LABEL[e]}</span>`).join("")}
  </div>
  <select class="fs-model" onchange="setFlowStepModel(${i},this.value)">
    ${(opts[s.engine]||["default"]).map(m=>`<option ${m===s.model?"selected":""}>${esc(m)}</option>`).join("")}
  </select>
  <textarea class="fs-prompt" rows="3" placeholder="prompt… use {input} / {goal}" oninput="updateFlowStep(${i},'prompt',this.value)">${esc(s.prompt)}</textarea>
  ${total>1 ? `<button class="mini-btn" onclick="removeFlowStep(${i})">remove</button>` : ""}
</div>`;

const flowRow = f => `<div class="item">
  <div class="grow"><b>${esc(f.name)}</b>
    <div class="meta">${f.steps.map(s=>esc(s.name)+" ("+ENGINE_LABEL[s.engine]+")").join(" → ")}</div></div>
  <input placeholder="input for this flow…" style="flex:2;min-width:160px" id="frun-input-${f.id}">
  <button class="act" onclick="runFlow('${f.id}', this)">Run</button>
  <button onclick="deleteFlow('${f.id}')" title="delete">✕</button></div>`;

const VERDICTS = ["review","noted","saved","tracked","reference","partial","installed","rebuilt","applied","done","skipped"];

const reelCard = r => `<div class="reel glass" data-id="${r.id}">
  <div onclick="this.parentElement.classList.toggle('open');loadReelEmbed(this.parentElement)" style="cursor:pointer">
    <div class="who">@${esc(r.uploader)}</div>
    <div class="tags"><span class="pill on t-${TOPIC_COLOR[r.topic]||"lav"}">${esc(r.topic)}</span>
      <span class="pill">${esc(r.verdict)}</span></div>
    <div class="cap">${esc(r.caption)||"<i>no caption</i>"}</div>
  </div>
  <div class="reel-embed" data-src="https://www.instagram.com/reel/${r.id}/embed/captioned/"></div>
  <div class="tx" onclick="event.stopPropagation()">${esc(r.transcript)||"(no speech)"}</div>
  <div class="reel-edit" onclick="event.stopPropagation()">
    <input class="redit-topic" placeholder="topic" value="${esc(r.topic)}">
    <select class="redit-verdict">${VERDICTS.map(v=>`<option ${v===r.verdict?"selected":""}>${v}</option>`).join("")}</select>
    <input class="redit-notes" placeholder="notes…" value="${esc(r.notes)||""}">
    <button class="mini-btn" onclick="saveReel('${r.id}', this)">save</button>
  </div>
  <a href="${r.url}" target="_blank" onclick="event.stopPropagation()">open reel ↗</a></div>`;

const sessionRow = s => `<div class="item session-row">
  <span class="status-dot ${s.status==="busy"?"run":"ok"}"></span>
  <div class="grow"><b>${esc(s.task)}</b>
    <div class="meta">${esc(s.engine)} · ${esc(s.tty)} · ${esc(s.status)}</div>
    <div class="sub clip">${esc(s.processes)}</div></div></div>`;

const trackedAppRow = a => `<div class="item">
  <span class="status-dot ${a.status==="online"?"ok":"err"}"></span>
  <div class="grow"><b>${esc(a.name)}</b><div class="meta">localhost:${esc(a.port)} · ${esc(a.status)}</div></div>
  ${a.status==="online"?`<a href="http://127.0.0.1:${esc(a.port)}" target="_blank" title="open">↗</a>`:""}</div>`;

const browserTabRow = t => `<a class="item tab-row" href="${esc(t.url)}" target="_blank">
  <span class="pill">${esc(t.browser)}</span>
  <div class="grow"><b>${esc(t.title)}</b><div class="meta">${esc(t.domain)} · ${esc(t.category)}</div></div></a>`;

const processRow = p => `<div class="item process-row">
  <div class="meta">${esc(p.pid)} · ${esc(p.etime)} · ${esc(p.stat)} · CPU ${esc(p.cpu)}%</div>
  <div class="grow"><code>${esc(p.args)}</code></div></div>`;

const gb = b => (b / 1073741824).toFixed(b > 107374182400 ? 0 : 1) + " GB";
const vitalMeter = (label, pct, val, tone) => `<div class="vital">
  <div class="vital-top"><span>${label}</span><b>${esc(val)}</b><span class="meta">${pct}%</span></div>
  <div class="meter"><i class="fill-${tone}" style="width:${Math.min(pct,100)}%"></i></div></div>`;

const ACT_COLOR = {goal:"mint", checkin:"lav", reel:"sky", term:"peach", swarm:"lav",
  flow:"sky", brief:"peach", networth:"mint"};
const activityRow = a => `<div class="item act-row">
  <span class="dot-sm t-${ACT_COLOR[a.kind]||"lav"}"></span>
  <div class="grow">${esc(a.detail || a.kind)}</div>
  <div class="meta" title="${esc(a.ts)}">${esc(a.ts.slice(5,16).replace("T"," "))}</div></div>`;

const sparkline = vals => {
  const w=260,h=48,min=Math.min(...vals),max=Math.max(...vals)||1;
  const pts = vals.map((v,i)=>`${(i/(vals.length-1))*w},${h-4-((v-min)/(max-min||1))*(h-8)}`).join(" ");
  return `<svg width="${w}" height="${h}" style="margin-top:10px"><polyline points="${pts}" fill="none"
    stroke="var(--sky)" stroke-width="2" stroke-linecap="round"/></svg>`;
};

const mdlite = s => esc(s).replace(/^### (.*)$/gm,"<strong>$1</strong>").replace(/^## (.*)$/gm,"<strong>$1</strong>")
  .replace(/^# (.*)$/gm,"<strong>$1</strong>").replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>");

/* ---------- actions ---------- */
window.filt = (k,v) => { state[k] = state[k]===v ? null : v; render(); };
window.askOverseer = async btn => { btn.disabled=true; btn.textContent="thinking…";
  const r = await api("overseer", {}); $("#overseer").textContent = r.message; btn.disabled=false; btn.textContent="Consult Overseer"; };
window.addReels = async btn => {
  const urls = $("#reelurls").value.match(/https?:\/\/[^\s,]+/g) || [];
  if (!urls.length) return;
  btn.disabled=true; await api("reels/add", {urls});
  btn.textContent=`ingesting ${urls.length}…`; $("#reelurls").value="";
  setTimeout(()=>render(), 45000); setTimeout(()=>{btn.disabled=false;btn.textContent="Ingest";}, 2000); };
window.addGoal = async urgent => { const t=$("#goaltext").value.trim(); if(!t) return;
  await api("lifehq/goal",{text:t,urgent}); render(); };
window.doneGoal = async id => { await api("lifehq/goal_done",{id}); render(); };
window.delGoal = async id => { await api("lifehq/goal_delete",{id}); render(); };
window.addSub = async () => { const n=$("#subname").value.trim(), m=parseFloat($("#submo").value);
  if(!n||isNaN(m)) return; await api("lifehq/subscription",{name:n,monthly:m}); render(); };
window.delSub = async id => { await api("lifehq/subscription_delete",{id}); render(); };
window.addNW = async () => { const a=parseFloat($("#nwa").value), l=parseFloat($("#nwl").value);
  if(isNaN(a)||isNaN(l)) return; await api("lifehq/networth",{assets:a,liabilities:l}); render(); };
window.syncNetWorth = async btn => { btn.disabled=true; await api("lifehq/networth_sync",{}); render(); };
window.addAccount = async () => {
  const name=$("#acctname").value.trim(), type=$("#accttype").value.trim(),
        kind=$("#acctkind").value, balance=parseFloat($("#acctbal").value);
  if(!name||isNaN(balance)) return;
  await api("lifehq/account",{name,type,kind,balance}); render(); };
window.delAccount = async id => { await api("lifehq/account_delete",{id}); render(); };
window.addBudget = async () => {
  const category=$("#budgetcat").value.trim(), monthly=parseFloat($("#budgetamt").value);
  if(!category||isNaN(monthly)) return;
  await api("lifehq/budget",{category,monthly}); render(); };
window.delBudget = async category => { await api("lifehq/budget",{category,monthly:0}); render(); };
window.importCSV = async btn => {
  const file = $("#csvfile").files[0]; if(!file) return;
  btn.disabled = true; btn.textContent = "importing…";
  const text = await file.text();
  const r = await api("lifehq/txn_import", {csv: text});
  btn.disabled = false; btn.textContent = "Import bank CSV";
  if (r.error) { alert(r.error); return; }
  render(); };
window.checkin = async btn => { btn.disabled=true;
  await api("lifehq/checkin",{energy:$("#energy").value,focus:$("#focus").value,mood:$("#mood").value});
  render(); };
window.genBrief = async btn => { btn.disabled=true; btn.textContent="writing brief… (local model, ~1-2 min)";
  await api("briefs/generate", {}); render(); };

/* ---------- plaid (real bank accounts) ---------- */
window.loadPlaidAccounts = async () => {
  const box = $("#plaid_accounts");
  if (!box) return;
  const status = await api("plaid/status");
  if (!status.configured || !status.linked_items.length) return;
  const accounts = await api("plaid/accounts");
  box.innerHTML = accounts.map(a => a.error
    ? `<div class="item"><div class="grow">${esc(a.institution)}</div><div class="meta" style="color:var(--rose,#f2a9c4)">${esc(a.error)}</div></div>`
    : `<div class="item"><div class="grow">${esc(a.institution)} — ${esc(a.name)}</div>
       <div class="meta">$${(a.current ?? 0).toLocaleString()} ${esc(a.iso_currency_code || "")}</div></div>`
  ).join("");
};

window.plaidLink = async () => {
  const { link_token } = await api("plaid/link-token", {});
  if (!link_token) return;
  const handler = Plaid.create({
    token: link_token,
    onSuccess: async (public_token, metadata) => {
      await api("plaid/exchange", {
        public_token,
        institution_name: metadata?.institution?.name || "Bank",
      });
      render();
    },
    onExit: () => {},
  });
  handler.open();
};

/* ---------- terminal actions ---------- */
window.setEngine = e => { state.engine = e; render(); };
window.runJob = async btn => {
  const prompt = $("#tprompt").value.trim(); if (!prompt) return;
  btn.disabled = true; state.cwd = $("#tcwd").value;
  const r = await api("term/run", {engine: state.engine || "claude",
    model: $("#tmodel").value, prompt, cwd: state.cwd});
  if (r.id) { state.job = r.id; }
  render();
};
window.stopJob = async id => { await api("term/stop", {id}); render(); };
window.openJob = id => { state.job = id; state.tailOff = 0; render(); };

let pipelineTimer = null;
function pipelineLoop() {
  clearTimeout(pipelineTimer);
  if (state.view !== "pipeline" || !$("#pipeline_procs")) return;
  api("pipeline").then(d => {
    if (state.view !== "pipeline") return;
    const engineColor = {claude: "lav", agy: "mint", codex: "peach", ollama: "sky"};
    const engineLabel = {claude: "Claude", agy: "agy / Antigravity", codex: "Codex", ollama: "Ollama"};
    const row = p => `<div class="item">
      <span class="pill on t-${engineColor[p.engine]||"sky"}">${esc(engineLabel[p.engine]||p.engine)}</span>
      <div class="grow"><code style="font-size:11px">${esc(p.args)}</code></div>
      <div class="meta">pid ${esc(p.pid)} · up ${esc(p.etime)} · cpu ${esc(p.cpu)}% · mem ${esc(p.mem)}%</div>
    </div>`;
    $("#pipeline_procs").innerHTML = d.processes.length ? d.processes.map(row).join("")
      : '<div class="empty">nothing from Claude/agy/Codex/Ollama running right now</div>';
    if ($("#pipeline_ollama")) {
      $("#pipeline_ollama").innerHTML = d.ollama_loaded === null
        ? '<div class="empty">Ollama unreachable on :11434</div>'
        : !d.ollama_loaded.length ? '<div class="empty">Ollama running, nothing loaded in memory right now</div>'
        : d.ollama_loaded.map(m => `<div class="item">
            <div class="grow"><b>${esc(m.name || m.model)}</b></div>
            <div class="meta">${m.size_vram ? (m.size_vram/1e9).toFixed(1)+" GB vram" : ""} · expires ${esc(m.expires_at||"")}</div>
          </div>`).join("");
    }
    pipelineTimer = setTimeout(pipelineLoop, 4000);
  }).catch(() => { pipelineTimer = setTimeout(pipelineLoop, 6000); });
}

let tailTimer = null;
function tailLoop() {
  clearTimeout(tailTimer);
  if (state.view !== "term" || !state.job || !$("#termout")) return;
  fetch(`/api/term/out/${state.job}?off=${state.tailOff || 0}`).then(r=>r.json()).then(d=>{
    if (d.text) {
      $("#termout").textContent += d.text;
      $("#termout").scrollTop = $("#termout").scrollHeight;
    }
    state.tailOff = d.off;
    if ($("#tstatus")) $("#tstatus").textContent = "· " + d.status;
    tailTimer = setTimeout(tailLoop, d.status === "running" ? 1200 : 5000);
  }).catch(()=>{ tailTimer = setTimeout(tailLoop, 3000); });
}

/* ---------- swarm actions ---------- */
window.runSwarm = async btn => {
  const goal = $("#sgoal").value.trim(); if (!goal) return;
  btn.disabled = true; btn.textContent = "planning…"; state.scwd = $("#scwd").value;
  const r = await api("swarm/run", {goal, cwd: state.scwd});
  if (r.id) state.srun = r.id;
  render();
};
window.openSwarm = id => { state.srun = id; render(); };
window.setView = v => {
  document.querySelectorAll(".dock button").forEach(x=>x.classList.toggle("active", x.dataset.view===v));
  state.view = v; render();
};

/* ---------- apps catalog ---------- */
function appTiles(list) {
  if (!list.length) return '<div class="empty">nothing matches</div>';
  return list.map(a => `
    <div class="card glass" style="margin-bottom:10px">
      <div class="row" style="justify-content:space-between;align-items:flex-start">
        <div style="flex:1">
          <b>${esc(a.name)}</b> <span class="pill" style="margin-left:6px">${esc(a.kind)}</span>
          <div class="sub" style="margin-top:4px">${esc(a.summary)}</div>
          <div class="sub" style="opacity:0.6">${esc(a.area)}</div>
        </div>
        <button class="act ghost" onclick="openApp('${a.id.replace(/'/g, "\\'")}', this)">
          ${a.appBundle ? "Launch" : a.terminalCommand ? "Run" : "Reveal"}
        </button>
      </div>
    </div>`).join("");
}
window.renderAppsOnly = () => {
  const all = window._appsCache || [];
  const q = (state.appsQuery || "").toLowerCase();
  const shown = all.filter(a => (!state.appsCategory || a.category === state.appsCategory)
    && (!q || a.name.toLowerCase().includes(q) || a.summary.toLowerCase().includes(q)));
  if ($("#appscount")) $("#appscount").textContent = shown.length;
  if ($("#apps_grid")) $("#apps_grid").innerHTML = appTiles(shown);
};
window.openApp = async (id, btn) => {
  btn.disabled = true; const orig = btn.textContent; btn.textContent = "…";
  try { await api("apps/open", {id}); } finally { btn.disabled = false; btn.textContent = orig; }
};
window.rescanApps = async () => { await api("apps?rescan=true"); render(); };

window.openAgentDropFile = async name => { await api("agentdrop/open", {file: name}); };

function agentDropLibraryRows(rows, filter, query) {
  const q = (query || "").toLowerCase();
  const shown = rows.filter(r =>
    (filter === "made" ? r.made === "Y" : filter === "not_made" ? r.made !== "Y" : true) &&
    (!q || (r.caption||"").toLowerCase().includes(q) || (r.category||"").toLowerCase().includes(q)));
  if (!shown.length) return '<div class="empty">nothing matches</div>';
  return shown.map(r => `
    <div class="item">
      <span class="status-dot ${r.made==="Y"?"ok":"err"}"></span>
      <div class="grow">${esc(r.caption || r.reel)}
        <div class="meta">${esc(r.category||"uncategorized")}${r.made_where ? " · " + esc(r.made_where) : ""}${r.new_app ? " · " + esc(r.new_app) : ""}</div>
      </div>
      <div class="meta">${r.made==="Y" ? "built" : "not built"}${r.installed==="Y" ? " · installed" : ""}</div>
    </div>`).join("");
}
function syncedReelRows(rows, query) {
  const q = (query || "").toLowerCase();
  const shown = rows.filter(r => !q || (r.caption||"").toLowerCase().includes(q) || r.code.toLowerCase().includes(q));
  if (!shown.length) return '<div class="empty">nothing matches</div>';
  return shown.map(r => `<div class="item">
    <div class="grow">${esc((r.caption||"").slice(0,140) || r.code)}</div>
    <div class="meta">${esc(r.modified.replace("T"," "))}</div>
    <button onclick="openAgentDropFile('reels/${r.code}.mp4')">open</button>
  </div>`).join("");
}
window.renderSyncedOnly = () => {
  if ($("#synced_reels")) $("#synced_reels").innerHTML = syncedReelRows(window._agentdropSynced || [], state.syncedQuery);
};
window.renderAgentDropOnly = () => {
  if ($("#agentdrop_library")) {
    $("#agentdrop_library").innerHTML = agentDropLibraryRows(window._agentdropLibrary || [], state.agentdropFilter, state.agentdropQuery);
  }
};

/* ---------- reel vault (partial re-render, keeps search focus) ---------- */
window.renderReelsOnly = () => {
  const rows = window._reelsCache || [];
  const topics = [...new Set(rows.map(r=>r.topic))].sort();
  const verdicts = [...new Set(rows.map(r=>r.verdict))].sort();
  const q = (state.reelQuery||"").toLowerCase();
  const shown = rows.filter(r => (!state.topic || r.topic===state.topic) && (!state.verdict || r.verdict===state.verdict)
    && (!q || `${r.uploader} ${r.caption} ${r.transcript}`.toLowerCase().includes(q)));
  if ($("#reelcount")) $("#reelcount").textContent = `— ${shown.length}/${rows.length}`;
  if ($("#reelfilters")) $("#reelfilters").innerHTML =
    topics.map(t=>`<span class="pill ${state.topic===t?"on t-"+(TOPIC_COLOR[t]||"lav"):""}" onclick="filt('topic','${t}')">${esc(t)}</span>`).join("")
    + `<span style="width:10px"></span>`
    + verdicts.map(v=>`<span class="pill ${state.verdict===v?"on t-peach":""}" onclick="filt('verdict','${v}')">${esc(v)}</span>`).join("");
  if ($("#reelgrid")) $("#reelgrid").innerHTML = shown.map(reelCard).join("") || '<div class="empty">nothing matches</div>';
};

window.saveReel = async (id, btn) => {
  const card = btn.closest(".reel");
  const topic = card.querySelector(".redit-topic").value.trim() || "uncategorized";
  const verdict = card.querySelector(".redit-verdict").value;
  const notes = card.querySelector(".redit-notes").value.trim();
  btn.disabled = true; btn.textContent = "…";
  await api("reels/update", {id, topic, verdict, notes});
  const row = (window._reelsCache||[]).find(r=>r.id===id);
  if (row) { row.topic=topic; row.verdict=verdict; row.notes=notes; }
  btn.textContent = "saved"; setTimeout(()=>renderReelsOnly(), 500);
};

window.loadReelEmbed = card => {
  if (!card.classList.contains("open")) return;
  const holder = card.querySelector(".reel-embed");
  if (!holder || holder.dataset.loaded) return;
  holder.dataset.loaded = "1";
  holder.innerHTML = `<iframe src="${holder.dataset.src}" loading="lazy" scrolling="no"
    style="width:100%;border:0;border-radius:14px;min-height:600px;background:rgba(255,255,255,.03)"></iframe>`;
};

window.submitCompare = async () => {
  const v = id => ($(id) ? $(id).value.trim() : "");
  const feature = v("#cmp_feature");
  if (!feature) return;
  const payload = {
    feature,
    claude: {label: v("#cmp_claude_label"), note: v("#cmp_claude_note"),
             items: v("#cmp_claude_items").split("\n").map(s=>s.trim()).filter(Boolean)},
    gemini: {label: v("#cmp_gemini_label"), note: v("#cmp_gemini_note"),
             items: v("#cmp_gemini_items").split("\n").map(s=>s.trim()).filter(Boolean)},
    verdict: v("#cmp_verdict"),
  };
  await api("compare/add", payload);
  render();
};

/* ---------- hands ai (remote WS client for the native Mac app) ---------- */
let handsSocket = null;

function renderHandsLog() {
  const msgs = state.handsMsgs.map(chatBubble).join("");
  const live = state.handsLiveText ? `<div class="msg assistant"><div class="bubble">${esc(state.handsLiveText)}</div></div>` : "";
  return msgs + live || '<div class="empty">no conversation yet</div>';
}

function renderHandsTools() {
  const box = $("#handstools");
  if (!box) return;
  if (!state.handsToolCalls.length) { box.innerHTML = ""; return; }
  box.innerHTML = state.handsToolCalls.slice(0, 6).map(t =>
    `<span class="pill ${t.status === "running" ? "on t-peach" : t.status === "failed" ? "on t-rose" : "on t-mint"}">${esc(t.tool)} — ${esc(t.detail || "")}</span>`
  ).join(" ");
}

function setHandsStatus(status, text) {
  state.handsStatus = status;
  state.handsStatusText = text || status;
  const el = $("#handsstatus");
  if (el) el.textContent = state.handsStatusText;
}

window.connectHands = () => {
  const token = ($("#handstoken") ? $("#handstoken").value : state.handsToken).trim();
  if (!token) { setHandsStatus("error", "enter the token from Hammond → Settings → Remote first"); return; }
  state.handsToken = token;
  localStorage.setItem("hands_token", token);
  if (handsSocket) { try { handsSocket.close(); } catch (e) {} }

  setHandsStatus("connecting", "connecting…");
  const wsHost = (location.hostname === "localhost" || location.hostname === "127.0.0.1") ? "127.0.0.1" : location.hostname;
  const wsPort = (state && state.handsPort) ? state.handsPort : 8787;
  const ws = new WebSocket(`ws://${wsHost}:${wsPort}/agent`);
  handsSocket = ws;

  ws.onopen = () => ws.send(JSON.stringify({type: "message", text: "", token}));

  ws.onmessage = ev => {
    let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (state.handsStatus !== "connected" && msg.type !== "error") setHandsStatus("connected", "connected");
    if (msg.type === "delta") {
      state.handsLiveText = msg.text || "";
      const log = $("#handslog"); if (log) { log.innerHTML = renderHandsLog(); log.scrollTop = log.scrollHeight; }
    } else if (msg.type === "toolCalls") {
      state.handsToolCalls = msg.toolCalls || [];
      renderHandsTools();
    } else if (msg.type === "final") {
      state.handsLiveText = "";
      if (msg.text) {
        state.handsMsgs.push({role: "assistant", content: msg.text});
        api("activity/log", {kind: "hands", detail: msg.text.slice(0, 200)});
      }
      const log = $("#handslog"); if (log) { log.innerHTML = renderHandsLog(); log.scrollTop = log.scrollHeight; }
    } else if (msg.type === "user") {
      if (msg.text) {
        const last = state.handsMsgs[state.handsMsgs.length - 1];
        if (!last || last.role !== "user" || last.content !== msg.text) {
          state.handsMsgs.push({role: "user", content: msg.text});
          const log = $("#handslog"); if (log) { log.innerHTML = renderHandsLog(); log.scrollTop = log.scrollHeight; }
        }
      }
    } else if (msg.type === "history") {
      if (Array.isArray(msg.history)) {
        state.handsMsgs = msg.history.map(h => ({role: h.role, content: h.text}));
        const log = $("#handslog"); if (log) { log.innerHTML = renderHandsLog(); log.scrollTop = log.scrollHeight; }
      }
    } else if (msg.type === "error") {
      setHandsStatus("error", msg.text || "server error");
    }
  };

  ws.onerror = () => setHandsStatus("error", "connection failed — is the Remote server on in Hammond → Settings?");
  ws.onclose = () => { if (state.handsStatus !== "error") setHandsStatus("disconnected", "disconnected"); };
};

window.sendHands = () => {
  const box = $("#handsinput"); const text = box.value.trim();
  if (!text) return;
  if (!handsSocket || handsSocket.readyState !== WebSocket.OPEN) {
    setHandsStatus("error", "not connected — click Connect first");
    return;
  }
  state.handsMsgs.push({role: "user", content: text});
  box.value = "";
  const log = $("#handslog"); if (log) { log.innerHTML = renderHandsLog(); log.scrollTop = log.scrollHeight; }
  const modelForEngine = ["(profile default)"].includes(state.handsModel) ? null : state.handsModel;
  handsSocket.send(JSON.stringify({type: "message", text, token: state.handsToken,
    engine: state.handsEngine, model: modelForEngine}));
};

window.setHandsEngine = e => { state.handsEngine = e; state.handsModel = null; render(); };

/* ---------- flows ---------- */
window.updateFlowMeta = (k,v) => { state.flowDraft[k] = v; };
window.updateFlowStep = (i,k,v) => { state.flowDraft.steps[i][k] = v; };
window.setFlowStepEngine = (i,e) => { state.flowDraft.steps[i].engine = e; state.flowDraft.steps[i].model = "default"; render(); };
window.setFlowStepModel = (i,m) => { state.flowDraft.steps[i].model = m; };
window.addFlowStep = () => { state.flowDraft.steps.push({name:`Step ${state.flowDraft.steps.length+1}`, engine:"claude", model:"default", prompt:"{input}"}); render(); };
window.removeFlowStep = i => { state.flowDraft.steps.splice(i,1); render(); };
window.saveFlow = async btn => {
  const steps = state.flowDraft.steps.filter(s=>s.prompt && s.prompt.trim());
  if (!state.flowDraft.name.trim() || !steps.length) return;
  btn.disabled = true;
  await api("flows", {id: state.flowDraft.id, name: state.flowDraft.name.trim(), steps});
  state.flowDraft = {name:"", steps:[{name:"Step 1", engine:"claude", model:"default", prompt:"{input}"}]};
  render();
};
window.deleteFlow = async fid => { if (!confirm("Delete this flow?")) return; await api(`flows/${fid}/delete`, {}); render(); };
window.runFlow = async (fid, btn) => {
  const input = $(`#frun-input-${fid}`).value.trim(); if (!input) return;
  btn.disabled = true; btn.textContent = "running…";
  const r = await api(`flows/${fid}/run`, {input, cwd: state.flowCwd || "~/Projects/mission-control/sandbox"});
  if (r.id) state.frun = r.id;
  render();
};
window.openFlowRun = id => { state.frun = id; render(); };
window.planFlow = async btn => {
  const goal = $("#flowask").value.trim(); if (!goal) return;
  btn.disabled = true; btn.textContent = "thinking…";
  try {
    const r = await api("flows/plan", {goal});
    if (r.steps) {
      state.flowDraft = {name: r.name || goal.slice(0,60),
        steps: r.steps.map(s=>({name:s.name||"Step", engine:s.engine||"claude", model:s.model||"default", prompt:s.prompt||"{input}"}))};
    }
  } finally {
    btn.disabled = false; btn.textContent = "Draft flow"; render();
  }
};


/* ---------- command palette + keyboard shortcuts ---------- */
const VIEW_ORDER = [...document.querySelectorAll(".dock button")].map(b => b.dataset.view);
const VIEW_LABEL = Object.fromEntries([...document.querySelectorAll(".dock button")]
  .map(b => [b.dataset.view, b.querySelector("span").textContent]));
const PAL_ICON = {nav:"⌂", reel:"▶", goal:"◎", flow:"⛓", subscription:"$", brief:"☰", activity:"⚡"};
const pal = {open:false, items:[], sel:0, q:""};

function navCmds(q) {
  const ql = q.toLowerCase();
  return VIEW_ORDER.map((v,i) => ({type:"nav", view:v, title:"Go to " + VIEW_LABEL[v],
    detail:"tab · press " + (i+1)})).filter(c => !ql || c.title.toLowerCase().includes(ql));
}
window.openPalette = () => {
  pal.open = true; pal.q = ""; pal.sel = 0; pal.items = navCmds("");
  $("#palette").hidden = false; $("#palinput").value = ""; palRender();
  setTimeout(() => $("#palinput").focus(), 0);
};
window.closePalette = () => { pal.open = false; $("#palette").hidden = true; };
window.togglePalette = () => pal.open ? closePalette() : openPalette();

let palTimer = null;
window.palInput = q => {
  pal.q = q; pal.sel = 0;
  clearTimeout(palTimer);
  if (q.trim().length < 2) { pal.items = navCmds(q); palRender(); return; }
  palTimer = setTimeout(async () => {
    const r = await api("search?q=" + encodeURIComponent(q));
    if (r.q !== pal.q.trim()) return;         // stale response
    pal.items = [...navCmds(q), ...(r.results || [])];
    pal.sel = 0; palRender();
  }, 180);
};
function palRender() {
  $("#palresults").innerHTML = pal.items.map((it,i) => `
    <div class="pal-item ${i===pal.sel?"sel":""}" onclick="palGo(${i})" onmousemove="pal.sel=${i};palRender()">
      <span class="pal-ico">${PAL_ICON[it.type]||"·"}</span>
      <div class="grow"><div class="pal-title">${esc(it.title)}</div>
        ${it.detail?`<div class="meta">${esc(it.detail)}</div>`:""}</div>
    </div>`).join("") || '<div class="empty">nothing matches</div>';
  const sel = $("#palresults .pal-item.sel");
  if (sel) sel.scrollIntoView({block:"nearest"});
}
window.palGo = i => {
  const it = pal.items[i]; if (!it) return;
  if (it.type === "reel") { state.reelQuery = pal.q.trim(); state.topic = null; state.verdict = null; }
  closePalette();
  if (it.view) setView(it.view);
};

document.addEventListener("keydown", e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); togglePalette(); return; }
  if (pal.open) {
    if (e.key === "Escape") closePalette();
    else if (e.key === "ArrowDown") { pal.sel = Math.min(pal.sel + 1, pal.items.length - 1); palRender(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { pal.sel = Math.max(pal.sel - 1, 0); palRender(); e.preventDefault(); }
    else if (e.key === "Enter") palGo(pal.sel);
    return;
  }
  const tag = (document.activeElement || {}).tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === "/") { e.preventDefault(); openPalette(); return; }
  if (e.key === "[" || e.key === "ArrowLeft") {
    const idx = VIEW_ORDER.indexOf(state.view);
    if (idx > 0) setView(VIEW_ORDER[idx - 1]);
    return;
  }
  if (e.key === "]" || e.key === "ArrowRight") {
    const idx = VIEW_ORDER.indexOf(state.view);
    if (idx >= 0 && idx < VIEW_ORDER.length - 1) setView(VIEW_ORDER[idx + 1]);
    return;
  }
  const n = parseInt(e.key, 10);
  if (n >= 1 && n <= 9 && n <= VIEW_ORDER.length) setView(VIEW_ORDER[n - 1]);
});

/* ---------- router ---------- */
async function render() {
  $("#view").innerHTML = await views[state.view]();
  if (state.view === "term" && state.job) { state.tailOff = 0; tailLoop(); }
  if (state.view === "pipeline") pipelineLoop();
  if (state.view === "reels") renderReelsOnly();
  if (state.view === "chat") { const l = $("#handslog"); if (l) l.scrollTop = l.scrollHeight; }
}
document.querySelectorAll(".dock button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".dock button").forEach(x=>x.classList.remove("active"));
  b.classList.add("active"); state.view = b.dataset.view; render();
});
render();

window.hwCtrl = async action => {
  await api("hardware/control", {action});
  render();
};
window.swCtrl = async action => {
  const app = $("#sw_app_name").value.trim();
  if (!app) return;
  await api("software/control", {action, app});
  render();
};

window.testWorkflow = async cmd => {
  const out = $("#wf_out");
  if (!out) return;
  out.textContent = "Running: " + cmd + "\n...";
  const r = await api("term/run", {engine: "shell", prompt: cmd, cwd: "~/Projects/app-projects/command-center/mission-control"});
  if (r.id) {
    let off = 0;
    const poll = async () => {
      try {
        const d = await (await fetch("/api/term/out/" + r.id + "?off=" + off)).json();
        if (d.text) {
          out.textContent = out.textContent.replace("\n...", "");
          out.textContent += d.text;
        }
        off = d.off;
        if (d.status === "running") {
          setTimeout(poll, 1000);
        } else {
          out.textContent += "\n\n[Done]";
        }
      } catch (e) {
        setTimeout(poll, 1000);
      }
    };
    setTimeout(poll, 1000);
  }
};

window.rebuildFileGraph = async btn => {
  btn.disabled = true;
  btn.textContent = "Indexing...";
  try {
    const res = await api("filegraph/rebuild", {});
    alert("Indexed " + (res.indexed || 0) + " files and relations into FileGraph DB!");
    initFileGraph();
  } catch (e) {
    alert("Rebuild failed: " + e);
  } finally {
    btn.disabled = false;
    btn.textContent = "⚡ Rebuild Graph";
  }
};

window.viewArtifact = async path => {
  try {
    const res = await (await fetch("/api/artifacts/content?path=" + encodeURIComponent(path))).json();
    if (res.content !== undefined) {
      $("#art_title").textContent = path.split("/").pop();
      $("#art_content").textContent = res.content;
      $("#artifact_modal").hidden = false;
    } else {
      alert("Error: " + (res.error || "Could not read artifact"));
    }
  } catch (e) {
    alert("Failed to load artifact: " + e);
  }
};

function renderLearnPlan(plan) {
  const body = $("#learn_body");
  if (!body) return;
  if (plan.error) { body.innerHTML = `<div class="card glass">${esc(plan.error)}</div>`; return; }
  const topics = (plan.topics || []).map((t,i) => `
    <div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06)">
      <b>${i+1}. ${esc(t.title)}</b>
      <div class="sub">${esc(t.why)}</div>
    </div>`).join("");
  const resources = (plan.curated_resources || []).map(r => `
    <div style="padding:6px 0">
      <a href="${esc(r.url)}" target="_blank" style="color:var(--sky,#a8d8f5)">${esc(r.name)}</a>
      <span class="sub"> — ${esc(r.cost)} — ${esc(r.note)}</span>
    </div>`).join("") || '<div class="sub">No curated match in the local resource library for this subject.</div>';
  const searchLinks = Object.entries(plan.search_links || {}).map(([label,url]) =>
    `<a href="${esc(url)}" target="_blank" class="pill">${esc(label)} →</a>`).join(" ");

  body.innerHTML = `
    <div class="card glass">
      <h2><span class="dot t-sky"></span>${esc(plan.subject)}</h2>
      <div class="sub" style="margin-bottom:10px">${esc(plan.overview)} ${plan.from_cache ? '<em>(cached)</em>' : ''}</div>
    </div>
    <div class="grid2">
      <div class="card glass"><h2><span class="dot t-mint"></span>Curriculum</h2>${topics}</div>
      <div class="card glass"><h2><span class="dot t-lav"></span>Resources</h2>${resources}
        <div style="margin-top:10px">${searchLinks}</div></div>
    </div>
    <div class="card glass"><h2><span class="dot t-peach"></span>Quiz</h2>
      <div id="quiz_area"></div>
      <div id="quiz_result" class="sub" style="margin-top:8px"></div>
    </div>`;
  renderQuiz(plan.quiz || []);
}

function renderQuiz(questions) {
  const area = $("#quiz_area");
  if (!area) return;
  window._quizAnswers = new Array(questions.length).fill(null);
  window._quizQuestions = questions;
  area.innerHTML = questions.map((q,qi) => `
    <div style="margin-bottom:14px">
      <div style="margin-bottom:6px">${qi+1}. ${esc(q.question)}</div>
      <div style="display:flex;flex-direction:column;gap:4px">
        ${q.options.map((opt,oi) => `
          <label style="cursor:pointer;display:flex;gap:6px;align-items:center">
            <input type="radio" name="quiz_${qi}" onchange="window._quizAnswers[${qi}]=${oi}">
            <span>${esc(opt)}</span>
          </label>`).join("")}
      </div>
    </div>`).join("") + `<button class="act" onclick="gradeQuiz()">Check answers</button>`;
}

window.gradeQuiz = () => {
  const qs = window._quizQuestions || [];
  const ans = window._quizAnswers || [];
  let correct = 0;
  const lines = qs.map((q,i) => {
    const got = ans[i];
    const ok = got === q.answer_index;
    if (ok) correct++;
    return `<div style="margin-top:4px">${ok ? "✅" : "❌"} ${esc(q.question)} — ${ok ? "correct" : "answer: " + esc(q.options[q.answer_index])}. <span class="sub">${esc(q.explanation||"")}</span></div>`;
  }).join("");
  $("#quiz_result").innerHTML = `<b>${correct}/${qs.length} correct</b>${lines}`;
};

window.startLearn = async () => {
  const subject = $("#learn_subject").value.trim();
  if (!subject) return;
  $("#learn_body").innerHTML = '<div class="card glass">Generating with local model…</div>';
  const plan = await api("learn/plan", {subject});
  renderLearnPlan(plan);
};

window.loadLearn = async subject => {
  $("#learn_subject").value = subject;
  await window.startLearn();
};

window.runReelTool = async toolId => {
  const out = $("#reeltool_out");
  const argsEl = $("#args_" + toolId);
  const args = argsEl ? argsEl.value.trim() : "";
  if (!out) return;
  out.textContent = "Running " + toolId + (args ? " " + args : "") + "...";
  const r = await api("tools/" + toolId + "/run", {args});
  if (r.error) { out.textContent = "Error: " + r.error; return; }
  if (r.id) {
    let off = 0;
    const poll = async () => {
      try {
        const d = await (await fetch("/api/term/out/" + r.id + "?off=" + off)).json();
        if (d.text) {
          out.textContent = out.textContent.replace(/\.\.\.$/, "");
          out.textContent += d.text;
        }
        off = d.off;
        if (d.status === "running") {
          setTimeout(poll, 1000);
        } else {
          out.textContent += "\n\n[" + d.status + "]";
        }
      } catch (e) {
        setTimeout(poll, 1000);
      }
    };
    setTimeout(poll, 1000);
  }
};

window.initFileGraph = async () => {
  const svg = d3.select("#d3graph");
  if (svg.empty()) return;
  const width = svg.node().getBoundingClientRect().width;
  const height = svg.node().getBoundingClientRect().height;
  
  const data = await api("filegraph/relations");
  if (!data.nodes.length) {
    d3.select("#graph-container").html("<div class='empty'>No graph data found in ~/.filegraph/filegraph.db</div>");
    return;
  }
  
  const simulation = d3.forceSimulation(data.nodes)
      .force("link", d3.forceLink(data.links).id(d => d.id).distance(60))
      .force("charge", d3.forceManyBody().strength(-150))
      .force("center", d3.forceCenter(width / 2, height / 2));

  const link = svg.append("g")
      .attr("stroke", "rgba(255,255,255,0.2)")
      .attr("stroke-opacity", 0.6)
    .selectAll("line")
    .data(data.links)
    .join("line")
      .attr("stroke-width", 1);

  const node = svg.append("g")
      .attr("stroke", "#fff")
      .attr("stroke-width", 1.5)
    .selectAll("circle")
    .data(data.nodes)
    .join("circle")
      .attr("r", 5)
      .attr("fill", d => d.group === "py" ? "var(--mint)" : d.group === "js" ? "var(--peach)" : "var(--sky)")
      .call(d3.drag()
          .on("start", (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
          .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
          .on("end", (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }));

  node.append("title")
      .text(d => d.name + "\\n" + d.path);

  simulation.on("tick", () => {
    link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);
    node
        .attr("cx", d => d.x)
        .attr("cy", d => d.y);
  });
};
