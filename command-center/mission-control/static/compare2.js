/* Compare (backlog P2): a measured model scoreboard, a live head-to-head through
   the review pipeline, and device research as a background job. The older
   hand-recorded Claude-vs-Gemini notes stay underneath. */
(() => {
  const oldCompare = views.compare;
  const DUEL = [["agy_pro", "Gemini Pro"], ["agy_flash", "Gemini Flash"], ["local_xl", "Local 30B"],
                ["local_small", "Local 8B"], ["claude_adjudicator", "Claude (costs tokens)"]];
  let duelTimer = null;

  const scoreRow = (m) => `<tr><td>${esc(m.name)}</td><td>${esc(String(m.calls))}</td>
    <td>${esc(String(m.success_pct))}%</td><td>${m.avg_secs == null ? "—" : esc(String(m.avg_secs)) + "s"}</td></tr>`;

  function renderDuel(d) {
    const box = document.getElementById("cp2-duel-out");
    if (!box) return;
    box.innerHTML = `<div class="grid2" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr))">${
      Object.entries(d.results).map(([, r]) => `
        <div class="card glass" style="margin:0">
          <b>${esc(r.name)}</b> <span class="meta">${r.status === "running" ? "thinking…" : esc(r.status) + (r.secs != null ? " · " + esc(String(r.secs)) + "s" : "")}</span>
          <div style="white-space:pre-wrap;margin-top:8px;line-height:1.5">${esc(r.text || "")}</div>
        </div>`).join("")}</div>`;
  }

  window.cp2Duel = async (btn) => {
    const prompt = document.getElementById("cp2-prompt").value.trim();
    const models = [...document.querySelectorAll(".cp2-m:checked")].map((c) => c.value);
    const out = document.getElementById("cp2-duel-out");
    if (!prompt || models.length < 2) { out.innerHTML = '<div class="empty">Type a question and tick at least 2 models.</div>'; return; }
    btn.disabled = true;
    try {
      const { id } = await apiOk("compare/duel", { prompt, models, allow_metered: models.includes("claude_adjudicator") });
      clearInterval(duelTimer);
      duelTimer = setInterval(async () => {
        if (!document.getElementById("cp2-duel-out")) return clearInterval(duelTimer);
        try {
          const d = await apiOk("compare/duel?id=" + encodeURIComponent(id));
          renderDuel(d);
          if (d.status === "done") { clearInterval(duelTimer); btn.disabled = false; }
        } catch (e) { clearInterval(duelTimer); btn.disabled = false; }
      }, 2500);
    } catch (e) {
      out.innerHTML = `<div class="empty">${esc(e.message || String(e))}</div>`;
      btn.disabled = false;
    }
  };

  window.cp2Devices = async (btn) => {
    const items = document.getElementById("cp2-dev").value.split(/,|\bvs\b/i).map((s) => s.trim()).filter(Boolean);
    const out = document.getElementById("cp2-dev-out");
    if (items.length < 2) { out.textContent = "Name at least two devices, separated by commas."; return; }
    const prompt = `Research and compare these devices for Nate: ${items.join(" vs ")}. ` +
      "Use current, reputable sources (reviews, spec sheets). Output: a markdown table (price, key specs, " +
      "battery, pros, cons) then 3 plain-English bullets on which to pick and why. Cite sources as links.";
    btn.disabled = true;
    try {
      await apiOk("term/run", { engine: "claude", model: "default", prompt, cwd: "~/Projects" });
      out.innerHTML = 'Started — follow it in <a href="#" onclick="event.preventDefault();document.querySelector(\'.dock button[data-view=&quot;term&quot;]\').click()">Jobs</a>. The result also lands in Results.';
    } catch (e) {
      out.textContent = "Couldn't start: " + (e.message || e);
    } finally { btn.disabled = false; }
  };

  views.compare = async () => {
    let board = [];
    try { board = await apiOk("compare/models"); } catch (e) {}
    const rest = oldCompare ? await oldCompare() : "";
    return `
    <div class="card glass"><h2><span class="dot t-peach"></span>AI scoreboard</h2>
      <div class="sub">Real numbers from every code review the pipeline has run — not claims. How often each model answered, and how fast.</div>
      ${board.length ? `<div style="overflow-x:auto"><table class="cp2-t" style="width:100%;margin-top:10px;border-collapse:collapse">
        <tr style="text-align:left;opacity:.7"><th>Model</th><th>Calls</th><th>Answered</th><th>Avg time</th></tr>
        ${board.map(scoreRow).join("")}</table></div>` : '<div class="empty">No review runs recorded yet.</div>'}
    </div>
    <div class="card glass"><h2><span class="dot t-sky"></span>Head to head</h2>
      <div class="sub">Ask several AIs the same question and see the answers side by side. Local and Gemini are free; Claude uses your tokens.</div>
      <textarea id="cp2-prompt" rows="2" placeholder="e.g. Explain what a vector database is in 3 sentences" style="margin-top:8px"></textarea>
      <div class="row" style="gap:14px;flex-wrap:wrap;margin:8px 0">
        ${DUEL.map(([k, label], i) => `<label style="display:flex;gap:6px;align-items:center;cursor:pointer">
          <input type="checkbox" class="cp2-m" value="${k}" ${i === 1 || i === 2 ? "checked" : ""} style="width:auto">${label}</label>`).join("")}
        <button class="act" onclick="cp2Duel(this)">Ask them</button>
      </div>
      <div id="cp2-duel-out"></div>
    </div>
    <div class="card glass"><h2><span class="dot t-mint"></span>Compare devices</h2>
      <div class="sub">Headphones, laptops, anything. Claude researches the web in the background (uses tokens) and writes a table + a plain answer.</div>
      <div class="row" style="gap:8px;margin-top:8px">
        <input id="cp2-dev" placeholder="e.g. AirPods Pro 3, Sony WF-1000XM6, Bose QC Ultra" style="flex:1">
        <button class="act" onclick="cp2Devices(this)">Research</button>
      </div>
      <div id="cp2-dev-out" class="sub" style="margin-top:8px"></div>
    </div>
    <details class="card glass"><summary style="cursor:pointer">Notes from building things both ways (Claude vs Gemini)</summary>${rest}</details>`;
  };
})();
