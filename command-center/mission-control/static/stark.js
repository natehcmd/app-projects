/* Stark HUD — reactor, live status line, ops rail, boot sequence.
   Reads os.js's shared `state` (handsStatus, handsToolCalls) and polls
   /api/vitals + /api/activity. Adds DOM only; never writes to `state`. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const store = { get(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
                  set(k, v) { try { localStorage.setItem(k, v); } catch {} } };
  const S = () => (typeof state !== "undefined" ? state : {});

  const reactorSVG = `<svg viewBox="0 0 40 40" aria-hidden="true">
    <circle class="ring r1" cx="20" cy="20" r="17"/><circle class="ring r2" cx="20" cy="20" r="12"/>
    <circle class="core" cx="20" cy="20" r="5"/></svg>`;

  // Plain-English phrasing so a glance says what Jarvis is doing.
  const PHRASE = {
    read_file: "Reading", Read: "Reading", list_dir: "Looking in", Glob: "Looking in",
    search_files: "Searching the Mac for", search_file_contents: "Searching files for", Grep: "Searching files for",
    write_file: "Writing", Write: "Writing", Edit: "Editing", move_file: "Moving", copy_file: "Copying",
    trash_file: "Moving to Trash", run_bash: "Running", Bash: "Running", web_search: "Searching the web for",
    WebSearch: "Searching the web for", web_fetch: "Reading page", WebFetch: "Reading page", open_url: "Opening",
    open_app: "Opening", run_applescript: "Scripting", calendar_today: "Checking calendar",
    reminders_list: "Checking reminders", reminders_add: "Adding reminder", send_imessage: "Messaging",
    music: "Music:", run_shortcut: "Running shortcut", use_skill: "Using skill", remember: "Remembering",
    recall: "Recalling", search_reels: "Searching reels for", latest_reels: "Checking new reels",
    run_claude_cli: "Delegating to Claude Code:", run_agy: "Delegating to Antigravity:", get_stats: "Checking system",
    weather: "Checking weather",
  };
  const say = t => PHRASE[t.tool] || t.tool || "Working";
  const statusOf = t => {
    const s = String(t.status || "").toLowerCase();
    return s.includes("run") ? "run" : s.includes("fail") || s.includes("error") ? "bad" : "ok";
  };

  function boot() {
    let seen = false;
    try { seen = sessionStorage.getItem("stark.booted") === "1"; } catch {}
    if (seen || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const el = document.createElement("div");
    el.id = "stark-boot";
    el.innerHTML = `<div><div class="reactor" data-state="thinking">${reactorSVG}</div>
      <div class="bt">J.A.R.V.I.S.<br><span style="font-size:10px;color:var(--ink-dim)">SYSTEMS ONLINE</span></div></div>`;
    document.body.appendChild(el);
    setTimeout(() => { el.classList.add("done"); setTimeout(() => el.remove(), 600); }, 1300);
    try { sessionStorage.setItem("stark.booted", "1"); } catch {}
  }

  function mountTopbar() {
    const bar = $(".topbar");
    if (!bar || $(".stark-brand", bar)) return;
    const brand = document.createElement("div");
    brand.className = "stark-brand";
    brand.innerHTML = `<div class="reactor" id="stark-reactor" data-state="offline" title="Agent state">${reactorSVG}</div>
      <div style="min-width:0"><div class="stark-word">J.A.R.V.I.S.</div>
      <div class="stark-status" id="stark-status" aria-live="polite">Standing by</div></div>`;
    bar.prepend(brand);
  }

  const gauge = (id, label) => `<div class="gauge"><svg viewBox="0 0 80 80">
    <circle class="trk" cx="40" cy="40" r="32"/><circle class="val" id="g-${id}" cx="40" cy="40" r="32"
    stroke-dasharray="201" stroke-dashoffset="201"/><text x="40" y="40" id="gt-${id}">–</text></svg>${label}</div>`;

  function mountRail() {
    if ($("#stark-rail")) return;
    const rail = document.createElement("aside");
    rail.id = "stark-rail";
    rail.className = "glass";
    rail.setAttribute("aria-label", "What Jarvis is doing");
    rail.innerHTML = `<div class="rail-h"><span>OPS FEED</span><small id="stark-clock"></small></div>
      <div class="gauges">${gauge("cpu", "CPU")}${gauge("mem", "MEMORY")}${gauge("disk", "DISK")}</div>
      <div class="now"><div class="lbl">NOW</div><div class="txt" id="stark-now">Standing by</div></div>
      <div class="rail-h"><span>STEPS</span><small id="stark-count"></small></div>
      <div class="feed" id="stark-feed"></div>`;
    document.body.appendChild(rail);
    const btn = document.createElement("button");
    btn.id = "stark-rail-toggle";
    const apply = () => {
      const hidden = store.get("stark.rail", "open") === "closed";
      rail.classList.toggle("collapsed", hidden);
      document.body.classList.toggle("rail-open", !hidden);
      btn.textContent = hidden ? "◂ Ops feed" : "Hide ▸";
    };
    btn.onclick = () => { store.set("stark.rail", store.get("stark.rail", "open") === "closed" ? "open" : "closed"); apply(); };
    document.body.appendChild(btn);
    apply();
  }

  function setGauge(id, pct) {
    const v = $("#g-" + id), t = $("#gt-" + id);
    if (!v || pct == null || isNaN(pct)) return;
    const p = Math.max(0, Math.min(100, pct));
    v.style.strokeDashoffset = 201 - 201 * p / 100;
    v.classList.toggle("hot", p >= 75 && p < 90);
    v.classList.toggle("crit", p >= 90);
    t.textContent = Math.round(p) + "%";
  }

  async function pollVitals() {
    try {
      const v = await (await fetch("/api/vitals")).json();
      setGauge("cpu", v.cpu?.pct); setGauge("mem", v.mem?.pct); setGauge("disk", v.disk?.pct);
    } catch {}
  }

  let activity = [];
  async function pollActivity() {
    try {
      const r = await fetch("/api/activity?limit=12");
      if (r.ok) activity = await r.json();
    } catch {}
  }

  let lastSig = "";
  function render() {
    const st = S();
    const calls = Array.isArray(st.handsToolCalls) ? st.handsToolCalls : [];
    const connected = st.handsStatus === "connected";
    const running = calls.find(c => statusOf(c) === "run");
    const failed = calls[0] && statusOf(calls[0]) === "bad";
    const mode = !connected ? "offline" : running ? "working" : failed ? "error" : "idle";

    const reactor = $("#stark-reactor");
    if (reactor) reactor.dataset.state = mode;
    const nowTxt = running ? `${say(running)} ${running.detail || ""}`.trim()
      : !connected ? "Hands AI offline — start the Mac app to see live steps"
      : calls[0] ? `Done — ${say(calls[0]).toLowerCase()} ${calls[0].detail || ""}`.trim()
      : "Standing by";
    const status = $("#stark-status"), now = $("#stark-now");
    if (status) status.innerHTML = running ? `<b>${esc(say(running))}</b> ${esc(running.detail || "")}` : esc(nowTxt);
    if (now) now.textContent = nowTxt;
    const clock = $("#stark-clock");
    if (clock) clock.textContent = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit"});

    const sig = JSON.stringify(calls.slice(0, 20).map(c => [c.tool, c.detail, c.status])) + activity.length + (activity[0]?.id ?? "");
    if (sig === lastSig) return;
    lastSig = sig;
    const steps = calls.slice(0, 20).map(c => {
      const k = statusOf(c);
      return `<div class="step ${k}"><div class="ic">${k === "run" ? "●" : k === "bad" ? "✕" : "✓"}</div>
        <div><div class="what">${esc(say(c))}</div>${c.detail ? `<div class="det">${esc(c.detail)}</div>` : ""}</div></div>`;
    });
    const logs = activity.map(a => `<div class="step ok"><div class="ic">·</div>
      <div><div class="what">${esc(a.detail)}</div><time>${esc(a.kind)} · ${esc(String(a.ts).replace("T", " ").slice(0, 16))}</time></div></div>`);
    const feed = $("#stark-feed");
    if (feed) feed.innerHTML = steps.join("") + (logs.length ? `<div class="rail-h" style="margin-top:6px"><span>RECENT</span></div>` + logs.join("") : "")
      || `<div class="step"><div class="ic">·</div><div class="what" style="color:var(--ink-faint)">No activity yet</div></div>`;
    const count = $("#stark-count");
    if (count) count.textContent = running ? "1 running" : calls.length ? `${calls.length} done` : "";
  }

  function start() {
    boot(); mountTopbar(); mountRail();
    pollVitals(); pollActivity();
    setInterval(pollVitals, 5000);
    setInterval(pollActivity, 15000);
    setInterval(render, 500);
    render();
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
