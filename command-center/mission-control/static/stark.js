/* Stark HUD — minimal: a reactor + one true status line in the top bar, and a
   live step list that only exists while Jarvis is working on something.
   Reads os.js's shared `state`; never writes to it. No history, no filler. */
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const S = () => (typeof state !== "undefined" ? state : {});

  const PHRASE = {
    read_file: "Reading", Read: "Reading", list_dir: "Looking in", Glob: "Looking in",
    search_files: "Searching the Mac for", search_file_contents: "Searching files for", Grep: "Searching files for",
    write_file: "Writing", Write: "Writing", Edit: "Editing", move_file: "Moving", copy_file: "Copying",
    trash_file: "Moving to Trash", run_bash: "Running", Bash: "Running", web_search: "Searching the web for",
    WebSearch: "Searching the web for", web_fetch: "Reading page", WebFetch: "Reading page", open_url: "Opening",
    open_app: "Opening", run_applescript: "Scripting", calendar_today: "Checking calendar",
    reminders_list: "Checking reminders", reminders_add: "Adding reminder", send_imessage: "Messaging",
    run_shortcut: "Running shortcut", use_skill: "Using skill", remember: "Remembering", recall: "Recalling",
    search_reels: "Searching reels for", latest_reels: "Checking new reels", get_stats: "Checking system",
    run_claude_cli: "Asking Claude Code", run_agy: "Asking Antigravity", weather: "Checking weather",
  };
  const say = t => PHRASE[t.tool] || t.tool || "Working";
  const kind = t => { const s = String(t.status || "").toLowerCase();
    return s.includes("run") ? "run" : (s.includes("fail") || s.includes("error")) ? "bad" : "ok"; };

  function mount() {
    const bar = $(".topbar");
    if (!bar || $(".stark-brand", bar)) return;
    const el = document.createElement("div");
    el.className = "stark-brand";
    el.innerHTML = `<div class="reactor" id="stark-reactor" data-state="offline" aria-hidden="true">
        <svg viewBox="0 0 40 40"><circle class="ring r1" cx="20" cy="20" r="16"/><circle class="core" cx="20" cy="20" r="5"/></svg></div>
      <span class="stark-status" id="stark-status" aria-live="polite"></span>`;
    bar.prepend(el);
    const steps = document.createElement("div");
    steps.id = "stark-steps";
    steps.className = "glass";
    steps.hidden = true;
    bar.after(steps);
  }

  // Steps stay visible while something runs and for 20s after the last one ends.
  let lastBusy = 0, lastSig = "";
  function render() {
    const st = S();
    const calls = Array.isArray(st.handsToolCalls) ? st.handsToolCalls : [];
    const connected = st.handsStatus === "connected";
    const running = calls.find(c => kind(c) === "run");
    if (running) lastBusy = Date.now();

    const reactor = $("#stark-reactor"), status = $("#stark-status"), box = $("#stark-steps");
    if (!reactor) return;
    reactor.dataset.state = !connected ? "offline" : running ? "working" : "idle";
    status.innerHTML = !connected ? "Not connected to Hands AI"
      : running ? `<b>${esc(say(running))}</b> ${esc(running.detail || "")}`
      : "Ready";

    const show = connected && calls.length && Date.now() - lastBusy < 20000;
    box.hidden = !show;
    if (!show) return;
    const recent = calls.slice(0, 6);
    const sig = JSON.stringify(recent.map(c => [c.tool, c.detail, c.status]));
    if (sig === lastSig) return;
    lastSig = sig;
    box.innerHTML = recent.map(c => {
      const k = kind(c);
      return `<div class="step ${k}"><span class="ic">${k === "run" ? "•" : k === "bad" ? "✕" : "✓"}</span>
        <span class="what">${esc(say(c))}</span><span class="det">${esc(c.detail || "")}</span></div>`;
    }).join("");
  }

  const start = () => { mount(); render(); setInterval(render, 500); };
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", start) : start();
})();
