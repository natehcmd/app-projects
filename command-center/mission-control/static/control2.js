// control2.js — more controls on the Control tab. Wraps views.control from os.js.
// Uses only endpoints that already exist in server.py. No inline handlers with data:
// every button carries data-c2="<action>" (+ data-id) and one delegated listener runs it.
(() => {
  const E = v => esc(String(v ?? ""));
  const gb = n => (n / 1073741824).toFixed(0) + " GB";
  const ok = r => r && !r.error;

  const CSS = `<style>
  .c2-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-bottom:12px}
  .c2-grid .card{margin:0}
  .c2-btns{display:flex;flex-direction:column;gap:8px;margin-top:10px}
  .c2-btn{width:100%;text-align:left;padding:12px 14px;font-size:14px;border-radius:10px;cursor:pointer;
    background:var(--glass);border:1px solid var(--glass-brd);color:var(--ink)}
  .c2-btn:hover{border-color:var(--accent)}
  .c2-btn[data-armed="1"]{border-color:#e5484d;color:#e5484d;font-weight:600}
  .c2-btn:disabled{opacity:.6;cursor:wait}
  .c2-btn small{display:block;opacity:.65;font-size:12px;margin-top:2px}
  a.c2-btn{text-decoration:none;display:block;box-sizing:border-box}
  .c2-out{font-size:13px;opacity:.85;min-height:1em;margin-top:2px;white-space:pre-wrap}
  .c2-out.bad{color:#e5484d;opacity:1}
  .c2-stats{display:flex;gap:10px;flex-wrap:wrap}
  .c2-stat{flex:1;min-width:110px;padding:10px 12px;border-radius:10px;border:1px solid var(--glass-brd)}
  .c2-stat b{font-size:20px;display:block}
  .c2-job{display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid var(--glass-brd)}
  .c2-job .grow{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .c2-job .c2-btn{width:auto;padding:6px 12px}
  .c2-row{display:flex;gap:8px;margin-top:10px}
  .c2-row select{flex:1;min-width:0}
  </style>`;

  const btn = (action, label, hint, extra = "") =>
    `<button class="c2-btn" data-c2="${action}" ${extra}>${label}${hint ? `<small>${hint}</small>` : ""}</button>
     <div class="c2-out" data-out="${action}"></div>`;

  const running = jobs => (Array.isArray(jobs) ? jobs : []).filter(j => j.status === "running");

  function jobsHtml(jobs) {
    if (!Array.isArray(jobs)) return `<div class="c2-out bad">Couldn't load the job list (${E(jobs && jobs.error)}).</div>`;
    const run = running(jobs);
    if (!run.length) return `<div class="sub">Nothing is running right now.</div>`;
    return run.map(j => `<div class="c2-job">
      <div class="grow"><b>${E(j.engine)}</b> ${E(j.model)} · started ${E(j.started)}<div class="sub">${E(j.prompt)}</div></div>
      <button class="c2-btn" data-c2="stop-one" data-id="${E(j.id)}" data-danger="1">Stop</button></div>`).join("");
  }

  function statsHtml(v, roots) {
    if (!ok(v)) return `<div class="c2-out bad">Couldn't read this Mac's vitals.</div>`;
    const loaded = v.ollama_loaded === null ? "Ollama isn't running"
      : v.ollama_loaded.length ? v.ollama_loaded.map(E).join(", ") : "none loaded";
    const p = (ok(roots) && roots.processes) || {};
    return `<div class="c2-stats">
      <div class="c2-stat"><b>${E(v.cpu.pct)}%</b>CPU busy</div>
      <div class="c2-stat"><b>${E(v.mem.pct)}%</b>Memory used (${E(gb(v.mem.used))} of ${E(gb(v.mem.total))})</div>
      <div class="c2-stat"><b>${E(v.disk.pct)}%</b>Disk full (${E(gb(v.disk.total - v.disk.used))} free)</div>
      <div class="c2-stat"><b>${E(p.claude || 0)} / ${E(p.agy || 0)} / ${E(p.ollama || 0)}</b>Claude / Gemini / Ollama processes</div>
    </div>
    <div class="sub" style="margin-top:8px">Local models in memory: ${loaded} · Mac up ${E(v.uptime)}</div>`;
  }

  const oldControl = views.control;
  views.control = async () => {
    const [v, jobs, roots, apps, synced] = await Promise.all(
      ["vitals", "term/jobs", "roots", "apps", "agentdrop/synced"].map(p => api(p).catch(e => ({error: String(e)}))));
    const appList = Array.isArray(apps) ? apps.filter(a => a.category === "Apps") : [];
    const hands = appList.find(a => /hands ai|hammond/i.test(a.name));
    const reelCount = ok(synced) && synced.exists ? synced.reels.length : null;
    const nRun = running(jobs).length;
    const NEW_HTML = `${CSS}
    <div class="card glass"><h2><span class="dot t-sky"></span>Right now
      <button class="act ghost" style="margin-left:auto" data-c2="refresh">Refresh</button></h2>
      <div id="c2_stats">${statsHtml(v, roots)}</div></div>
    <div class="c2-grid">
      <div class="card glass"><h2><span class="dot t-lav"></span>AI</h2>
        <div class="c2-btns">
          ${btn("stop-all", `Stop all running agent jobs (${nRun})`, "Stops every Claude / Codex / local job started from Term or Swarm", 'data-danger="1"')}
          ${btn("chat", "Talk to Hammond here", "Opens the Chat tab")}
          <a class="c2-btn" href="http://127.0.0.1:8470" target="_blank" rel="noopener">Open Arena (code review)<small>Opens in a new tab</small></a>
        </div></div>
      <div class="card glass"><h2><span class="dot t-mint"></span>Apps</h2>
        <div class="c2-btns">
          ${hands ? btn("open-app", `Open ${E(hands.name)} (Hammond)`, "The menu bar app", `data-id="${E(hands.id)}"`)
                  : `<div class="sub">Hammond's app wasn't found in ~/Applications.</div>`}
        </div>
        <div class="c2-row"><select id="c2_app">${appList.map(a => `<option value="${E(a.id)}">${E(a.name)}</option>`).join("")}</select>
          <button class="act" data-c2="open-picked">Open</button></div>
        <div class="c2-out" data-out="open-picked"></div></div>
      <div class="card glass"><h2><span class="dot t-peach"></span>Content</h2>
        <div class="c2-btns">
          ${btn("brief", "Write today's brief", "Takes a minute or two — result shows here")}
          ${btn("filegraph", "Rebuild FileGraph", "Re-scans ~/Projects/app-projects (first 1,000 files)")}
          ${btn("reels", "How many reels are synced?", reelCount === null ? "AgentDrop reels folder not found" : `${reelCount} reel videos on disk`)}
        </div></div>
      <div class="card glass"><h2><span class="dot t-sky"></span>This Mac</h2>
        <div class="c2-btns">
          ${btn("mute", "Mute sound", "")}
          ${btn("unmute", "Turn sound back on", "")}
          ${btn("sleep", "Put the Mac to sleep", "The dashboard goes offline until it wakes", 'data-danger="1"')}
        </div></div>
    </div>
    <div class="card glass"><h2><span class="dot t-lav"></span>Running jobs</h2>
      <div id="c2_jobs">${jobsHtml(jobs)}</div><div class="c2-out" data-out="stop-one"></div></div>`;
    return NEW_HTML + (await oldControl());
  };

  const say = (key, text, bad) => {
    const el = document.querySelector(`[data-out="${key}"]`);
    if (el) { el.textContent = text; el.classList.toggle("bad", !!bad); }
  };
  const reloadJobs = async () => {
    const jobs = await api("term/jobs").catch(e => ({error: String(e)}));
    const box = document.getElementById("c2_jobs");
    if (box) box.innerHTML = jobsHtml(jobs);
    const all = document.querySelector('[data-c2="stop-all"]');
    if (all) all.firstChild.textContent = `Stop all running agent jobs (${running(jobs).length})`;
  };

  const ACTIONS = {
    async refresh() {
      const [v, roots] = await Promise.all([api("vitals"), api("roots")]);
      document.getElementById("c2_stats").innerHTML = statsHtml(v, roots);
      await reloadJobs();
    },
    async "stop-all"() {
      const run = running(await api("term/jobs"));
      if (!run.length) return say("stop-all", "Nothing was running.");
      const res = await Promise.all(run.map(j => api("term/stop", {id: j.id})));
      const n = res.filter(ok).length;
      say("stop-all", `Stopped ${n} of ${run.length} job${run.length === 1 ? "" : "s"}.`, n < run.length);
      await reloadJobs();
    },
    async "stop-one"(b) {
      const r = await api("term/stop", {id: b.dataset.id});
      say("stop-one", ok(r) ? `Stopped job ${b.dataset.id}.` : `Couldn't stop it: ${r.error}`, !ok(r));
      await reloadJobs();
    },
    chat() { document.querySelector('.dock button[data-view="chat"]')?.click(); },
    async "open-app"(b) { await openApp(b.dataset.id, "open-app"); },
    async "open-picked"() { await openApp(document.getElementById("c2_app").value, "open-picked"); },
    async brief() {
      const r = await api("briefs/generate", {});
      say("brief", ok(r) && r.ok ? "Done — today's brief is written. See the Briefs tab."
        : `The brief didn't finish: ${(r && (r.error || r.log)) || "unknown error"}`, !(ok(r) && r.ok));
    },
    async filegraph() {
      const r = await api("filegraph/rebuild", {});
      say("filegraph", ok(r) ? `Done — indexed ${r.indexed} files.` : `Rebuild failed: ${r.error}`, !ok(r));
    },
    async reels() {
      const r = await api("agentdrop/synced");
      if (!ok(r) || !r.exists) return say("reels", "The AgentDrop reels folder wasn't found.", true);
      const newest = r.reels[0];
      say("reels", `${r.reels.length} reels on disk.` + (newest ? ` Newest: ${newest.modified.replace("T", " ")}.` : ""));
    },
    async mute() { await hw("mute", "Sound is muted."); },
    async unmute() { await hw("unmute", "Sound is back on."); },
    async sleep() { await hw("sleep", "Going to sleep now."); },
  };
  async function hw(action, msg) {
    const r = await api("hardware/control", {action});
    say(action, ok(r) ? msg : `That didn't work: ${r.error}`, !ok(r));
  }
  async function openApp(id, key) {
    if (!id) return say(key, "Pick an app first.", true);
    const r = await api("apps/open", {id});
    say(key, ok(r) ? `Opening (${r.action || "done"}).` : `Couldn't open it: ${r.error}`, !ok(r));
  }

  document.addEventListener("click", async ev => {
    const b = ev.target.closest("[data-c2]");
    if (!b || b.disabled) return;
    const action = b.dataset.c2;
    if (b.dataset.danger && b.dataset.armed !== "1") {  // destructive: needs a second click
      b.dataset.armed = "1";
      b.dataset.label = b.innerHTML;
      b.textContent = "Are you sure? Click again";
      b._c2t = setTimeout(() => { b.dataset.armed = ""; b.innerHTML = b.dataset.label; }, 4000);
      return;
    }
    clearTimeout(b._c2t);
    if (b.dataset.armed === "1") { b.dataset.armed = ""; b.innerHTML = b.dataset.label; }
    const key = action === "stop-one" ? "stop-one" : action;
    b.disabled = true;
    say(key, "Working…");
    try { await ACTIONS[action](b); }
    catch (e) { say(key, `Something went wrong: ${e.message || e}`, true); }
    finally { b.disabled = false; if (document.querySelector(`[data-out="${key}"]`)?.textContent === "Working…") say(key, ""); }
  });
})();
