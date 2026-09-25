/* Tools tab v2: a searchable grid of the small command-line tools built from
   Instagram reels (reels-build/<id>/, listed in tools_manifest.json). Each card
   says in plain English what the tool does, and can be tried inline: "Try it"
   runs a safe demo or your own arguments, "Show help" runs it with --help.
   Runs go through POST /api/tools/{id}/run and are polled via /api/term/out.
   The old read-only reference (skills/models/cron) stays below, and agents2.js
   still appends Workflows after that. */
(() => {
  // Plain-English overrides where the manifest line is vague or jargon-y.
  // kind: cli (default) | web (starts a local server) | lib (code library, no command)
  // demo: args for a harmless demo run; "" = run with no args; omitted = --help
  // needs: short plain note about what it needs to do real work
  const INFO = {
    "Daa8fy8PKC1": {demo: "--random 5", what: "Prints a hand-picked, offline list of good free computer-science learning resources."},
    "DaagbUMP8Tg": {needs: "a project folder", what: "Looks at one of your projects and suggests Claude Code hooks, skills, helpers and MCP servers worth adding."},
    "DactwNnswpk": {needs: "a skill folder + Claude", what: "Checks a downloaded Claude skill for dangerous tricks (piping scripts from the web, sending your data out, hiding on startup) before you install it."},
    "DadvdvitVke": {needs: "a project folder", what: "Draws a map of a codebase: which files import which, as an HTML graph plus a JSON file."},
    "Dae5fOUOphe": {needs: "a project folder", what: "Builds a searchable index of a codebase (imports and definitions) as JSON and Markdown."},
    "DafiQ5iPlC7": {needs: "a project folder or URL", what: "Pulls the colours, fonts and spacing out of a project and writes them up as a design-system doc."},
    "Dai5Uq0COe1": {needs: "a project folder", what: "Writes a starter DESIGN.md (colours, type, spacing rules) into a new project."},
    "Dalkk16Sy81": {needs: "Claude", what: "Batch-writes content in three stations: a smart model writes the spec, cheap models draft, a checker rejects bad ones."},
    "DaNjtbcFSLE": {needs: "a project folder", what: "Drops a ready-made behaviour-rules CLAUDE.md into a project so Claude follows good habits there."},
    "DappXCcvuE3": {needs: "a project folder", what: "Finds every animated UI component in a frontend project."},
    "DarPBb4sxlg": {needs: "Claude", what: "Has Claude write a draft, then tear it apart like a stranger wrote it, score it and fix it, in a loop until it is good."},
    "DaSlpSjPVe-": {what: "Writes a hand-off note at the end of a Claude Code session so the next session picks up without losing context."},
    "DaSwegFCZO7": {what: "Creates new Claude Code skills from a template and checks existing ones for mistakes."},
    "DaTUI9xChIR": {what: "Type a request in plain English and it works out which built-in action to run."},
    "DaWVAIrh_EB": {demo: "--coupon 0.05 --years 10 --price 950", what: "Works out a bond's yield, duration and price from its coupon, term and price."},
    "dm_32917943269963244995258185722888192": {needs: "an AI model", what: "Puts a business idea in front of four AI critics with different viewpoints and collects their verdicts."},
    "dm_32917944601702137096864179318423552": {what: "Paste a job ad and it suggests a portfolio project that would impress that employer."},
    "DWwLhCEAtV_": {needs: "a project folder", what: "Pre-launch safety check for a quickly-built app: leaked keys, open settings, missing basic protections."},
    "DY_SoPGKv2A": {needs: "Claude", what: "Splits a job across several Claude agents and sends each piece to the cheapest model that can handle it."},
    "DYaA7dnxfUi": {demo: "list", what: "Offline list of real software discounts you can get with a student email address."},
    "DYkjSXcA45p": {demo: "--mau 500 --growth 12", what: "Tells you whether an app is at the Vibing, Growing or Scaling stage, with a checklist for what to do next."},
    "DYnFlSKK-Qg": {demo: "--touches-code y --multi-step y", what: "Answer a few yes/no questions and it tells you whether Claude Chat, Cowork or Code fits the task."},
    "DYNm5GcSswI": {kind: "lib", what: "A code library (not a command) with defences against prompt-injection for AI agents. Import it from Python; running it does nothing."},
    "DYQu6P0KOeL": {needs: "Claude", what: "Sends a prompt to a cheap or a strong Claude model depending on how hard the task looks."},
    "DYXFtTFsbLt": {kind: "web", needs: "Ollama", what: "Starts a local server that lets Claude Code talk to a free local model in Ollama instead of Anthropic's cloud. Keeps running until stopped."},
    "DZdkrPthOoM": {needs: "a Terraform folder", what: "Scans Terraform cloud config for the mistakes that cause surprise bills and security holes."},
    "DZDksUcipwZ": {needs: "a skill folder", what: "Safety-checks a Claude skill before you install it."},
    "DZe-GLFy9DW": {what: "A personal notes database where notes are linked by how they relate, not just by backlinks."},
    "DZLHHJuOPVs": {needs: "some documents", what: "Searches your own documents by both keywords and meaning, then ranks the best matches."},
    "DZow139P5Wd": {needs: "a project folder", what: "Flags code that looks like careless AI output (\"slop\"): filler comments, dead code, copy-paste patterns."},
    "DZpeo9rId8j": {needs: "internet", what: "Searches GitHub for Claude Code skills that match a task, ranked by stars, with install steps."},
    "DZY4CWVPiXl": {needs: "microphone + sounddevice module", what: "Listens for a double clap and runs a command you choose."},
    "DYSUqcsuGX9": {demo: "--dry-run", needs: "Notion API key", what: "Copies your saved Instagram posts into a Notion database."},
    "DZ5WrbDNrSZ": {needs: "resume + job files, Claude", what: "Rewrites your resume to fit a specific job ad using three Claude prompts in a row."},
    "DX5MzljR0n7": {demo: "", what: "Offline list of real, free tech certifications for students."},
    "DZqg7QoMKI4": {demo: "list", what: "Expands shortcuts like /critique or /godmode into the full prompt text they stand for."},
    "DZsq1Ervqk7": {demo: "1", what: "Prints three ready-to-paste vibe-coding prompts."},
  };
  const KIND = {cli: ["command-line tool", "t-sky"], web: ["local web server", "t-peach"], lib: ["code library", "t-lav"]};
  let tools = [], q = "";
  const runs = {}; // id -> {job, t0, timer}

  const info = t => INFO[t.id] || {};
  const pretty = t => (/\.py$/.test(t.name) ? t.name.replace(/\.py$/, "").replace(/[_-]/g, " ") : t.name);
  const hasPlaceholder = t => /<[^>]+>/.test(t.usage || "");
  const usageArgs = t => ((t.usage || "").split(t.script)[1] || "").trim();
  const demoArgs = t => {
    const i = info(t);
    if (i.demo !== undefined) return i.demo;
    return hasPlaceholder(t) ? "--help" : usageArgs(t) || "--help";
  };
  const hay = t => [t.name, t.desc, info(t).what, t.script, info(t).needs].join(" ").toLowerCase();

  const css = `<style>
  #t2 .t2-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
  #t2 .t2-card{display:flex;flex-direction:column;gap:8px;margin:0}
  #t2 .t2-card.open{grid-column:1/-1}
  #t2 .t2-head{display:flex;gap:8px;align-items:flex-start;justify-content:space-between}
  #t2 .t2-name{font-weight:700;font-size:15px;color:var(--ink)}
  #t2 .t2-what{color:var(--ink);opacity:.9;line-height:1.4}
  #t2 .t2-meta{display:flex;gap:6px;flex-wrap:wrap;font-size:11px}
  #t2 .t2-meta .pill{font-size:11px;padding:2px 8px}
  #t2 .t2-btns{display:flex;gap:6px;margin-top:auto;flex-wrap:wrap}
  #t2 .t2-panel{border-top:1px solid var(--glass-brd);padding-top:10px;display:flex;flex-direction:column;gap:8px}
  #t2 .t2-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
  #t2 .t2-row input{flex:1;min-width:200px;font-family:var(--font-data,ui-monospace,monospace)}
  #t2 .t2-out{min-height:80px;max-height:360px;overflow:auto;white-space:pre-wrap;margin:0}
  #t2 .t2-stat{font-size:12px;color:var(--ink-dim)}
  #t2 .t2-err{color:var(--rose)}
  #t2 .t2-ok{color:var(--mint)}
  #t2 .t2-hide,#t2 [hidden]{display:none!important}
  </style>`;

  const card = t => {
    const i = info(t), [kname, kcol] = KIND[i.kind || "cli"];
    const what = i.what || t.desc || "No description yet.";
    const canRun = (i.kind || "cli") !== "lib";
    return `<div class="card glass t2-card" data-tid="${esc(t.id)}" data-hay="${esc(hay(t))}">
      <div class="t2-head"><span class="t2-name">${esc(pretty(t))}</span>
        <span class="pill ${kcol}" title="what kind of tool this is">${esc(kname)}</span></div>
      <div class="t2-what">${esc(what)}</div>
      <div class="t2-meta"><code title="the script that runs">${esc(t.script)}</code>
        ${i.needs ? `<span class="pill" title="what it needs to do real work">needs ${esc(i.needs)}</span>` : ""}</div>
      <div class="t2-btns">
        ${canRun ? `<button class="act" data-t2="try">Try it</button>` : ""}
        <button class="act ghost" data-t2="help">Show help</button>
      </div>
      <div class="t2-panel" hidden>
        <div class="sub">Usage: <code>${esc(t.usage || t.script)}</code></div>
        <div class="t2-row">
          <input data-t2="args" placeholder="arguments, e.g. --help" value="${esc(demoArgs(t))}">
          <button class="act" data-t2="run">Run</button>
          <button class="act ghost" data-t2="stop" hidden>Stop</button>
          <button class="act ghost" data-t2="close">Close</button>
        </div>
        ${hasPlaceholder(t) ? `<div class="sub">Replace anything in &lt;angle brackets&gt; with a real value. Use a full path (e.g. /Users/you/Projects/my-app); <code>~</code> is not expanded. Relative paths start from the tool's own folder.</div>` : ""}
        <div class="t2-stat">Not run yet.</div>
        <pre class="termout t2-out">Press Run to see output here.</pre>
      </div>
    </div>`;
  };

  const plainError = e => {
    const m = String((e && e.message) || e || "");
    if (/unauthorized/i.test(m)) return "The dashboard refused the run because it could not confirm it's you (no valid token). Reload the page and try again.";
    if (/unknown tool/i.test(m)) return "That tool is no longer in the tools list. Reload the page.";
    if (/script missing/i.test(m)) return "The tool's script file is missing from its reels-build folder, so it can't run.";
    if (/fetch|network/i.test(m)) return "Couldn't reach the Command Center server. Is it running on port 8450?";
    return "Something went wrong: " + m;
  };
  const explainExit = (status, text) => {
    if (status === "done") return null;
    const mod = text.match(/ModuleNotFoundError: No module named '([^']+)'/);
    if (mod) return "It needs a Python package that isn't installed: " + mod[1] + ". Install it into the dashboard's .venv to use this tool.";
    if (/error: the following arguments are required/.test(text)) return "It needs more arguments. Click \"Show help\" to see which ones.";
    if (/unrecognized arguments|invalid choice/.test(text)) return "It didn't understand those arguments. Click \"Show help\" to see what it accepts.";
    if (/API[_ ]KEY|api key|token/i.test(text)) return "It looks like it needs an API key or token that isn't set up.";
    if (status === "stopped") return "Stopped.";
    return "It ended with a problem (" + status + "). The output above shows what it said.";
  };

  const setStat = (el, html) => { el.querySelector(".t2-stat").innerHTML = html; };
  const secs = t0 => ((performance.now() - t0) / 1000).toFixed(1) + "s";

  const run = async (cardEl, args) => {
    const id = cardEl.dataset.tid, out = cardEl.querySelector(".t2-out");
    const stopBtn = cardEl.querySelector('[data-t2="stop"]'), runBtn = cardEl.querySelector('[data-t2="run"]');
    if (runs[id]) return;
    const t0 = performance.now();
    out.textContent = "$ " + (tools.find(t => t.id === id) || {}).script + (args ? " " + args : "") + "\n";
    setStat(cardEl, "Starting…");
    runBtn.disabled = true;
    let r;
    try {
      r = await api("tools/" + encodeURIComponent(id) + "/run", {args});
      if (!r || r.error || !r.id) throw new Error((r && r.error) || "no job id returned");
    } catch (e) {
      runBtn.disabled = false;
      setStat(cardEl, `<span class="t2-err">${esc(plainError(e))}</span>`);
      return;
    }
    const st = runs[id] = {job: r.id, t0, off: 0, text: ""};
    stopBtn.hidden = false;
    const tick = async () => {
      if (!document.body.contains(cardEl)) { delete runs[id]; return; } // tab changed
      try {
        const d = await api("term/out/" + encodeURIComponent(st.job) + "?off=" + st.off);
        if (d.error) throw new Error(d.error);
        if (d.text) { st.text += d.text; out.textContent += d.text; out.scrollTop = out.scrollHeight; }
        st.off = d.off || st.off;
        if (d.status === "running") {
          setStat(cardEl, `Running… ${esc(secs(t0))}`);
          st.timer = setTimeout(tick, 700);
          return;
        }
        delete runs[id];
        runBtn.disabled = false; stopBtn.hidden = true;
        if (!st.text.trim()) out.textContent += "(it finished without printing anything)";
        const why = explainExit(d.status, st.text);
        setStat(cardEl, why
          ? `<span class="t2-err">${esc(why)}</span> · ${esc(secs(t0))}`
          : `<span class="t2-ok">Finished</span> in ${esc(secs(t0))}`);
      } catch (e) {
        st.fails = (st.fails || 0) + 1;
        if (st.fails > 5) {
          delete runs[id]; runBtn.disabled = false; stopBtn.hidden = true;
          setStat(cardEl, `<span class="t2-err">${esc(plainError(e))}</span>`);
          return;
        }
        st.timer = setTimeout(tick, 1200);
      }
    };
    st.timer = setTimeout(tick, 400);
  };

  const open = (cardEl, show) => {
    cardEl.querySelector(".t2-panel").hidden = !show;
    cardEl.classList.toggle("open", show);
  };

  const onClick = async ev => {
    const b = ev.target.closest("#t2 [data-t2]");
    if (!b || b.tagName === "INPUT") return;
    const cardEl = b.closest(".t2-card"), act = b.dataset.t2;
    const input = cardEl.querySelector('[data-t2="args"]');
    if (act === "try") { open(cardEl, true); input.focus(); run(cardEl, input.value.trim()); }
    else if (act === "help") { open(cardEl, true); input.value = "--help"; run(cardEl, "--help"); }
    else if (act === "run") run(cardEl, input.value.trim());
    else if (act === "close") open(cardEl, false);
    else if (act === "stop") {
      const st = runs[cardEl.dataset.tid];
      if (st) { try { await api("term/stop", {id: st.job}); } catch (e) { setStat(cardEl, `<span class="t2-err">${esc(plainError(e))}</span>`); } }
    }
  };
  const onKey = ev => {
    if (ev.key === "Enter" && ev.target.matches && ev.target.matches('#t2 [data-t2="args"]'))
      run(ev.target.closest(".t2-card"), ev.target.value.trim());
  };
  const onInput = ev => {
    if (!ev.target.matches || !ev.target.matches("#t2_q")) return;
    q = ev.target.value.trim().toLowerCase();
    filter();
  };
  const filter = () => {
    const root = document.getElementById("t2");
    if (!root) return;
    let n = 0;
    root.querySelectorAll(".t2-card").forEach(c => {
      const hit = !q || q.split(/\s+/).every(w => c.dataset.hay.includes(w));
      c.classList.toggle("t2-hide", !hit); if (hit) n++;
    });
    root.querySelector("#t2_count").textContent = n === tools.length ? `${n} tools` : `${n} of ${tools.length} tools`;
    root.querySelector("#t2_none").hidden = n > 0;
  };
  document.addEventListener("click", onClick);
  document.addEventListener("keydown", onKey);
  document.addEventListener("input", onInput);

  const oldTools = views.tools;
  views.tools = async (...a) => {
    let head;
    try {
      tools = await api("tools");
      if (!Array.isArray(tools)) throw new Error((tools && tools.error) || "bad tools list");
      head = `
      <div class="card glass"><h2><span class="dot t-mint"></span>Reel Tools <span class="sub" id="t2_count" style="margin-left:6px">${tools.length} tools</span></h2>
        <div class="sub" style="margin-bottom:10px">Small programs built from Instagram reels you saved. Each one runs on this Mac from its own
          folder in <code>reels-build/</code>. <b>Try it</b> runs a safe demo (or your own arguments); <b>Show help</b> lists everything it accepts.</div>
        <input id="t2_q" placeholder="Search tools — e.g. security, resume, codebase, offline…" value="${esc(q)}" style="width:100%">
      </div>
      <div class="t2-grid">${tools.map(card).join("")}</div>
      <div class="empty" id="t2_none" hidden>No tools match that search.</div>`;
    } catch (e) {
      head = `<div class="card glass"><h2><span class="dot t-rose"></span>Reel Tools</h2>
        <div class="sub t2-err">Couldn't load the tools list. ${esc(plainError(e))}</div></div>`;
    }
    setTimeout(filter, 0);
    const rest = oldTools ? await oldTools.apply(views, a) : "";
    return `${css}<div id="t2">${head}</div>` + rest;
  };
})();
