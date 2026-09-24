/* Team (Nate's request): a cast of agent characters. Scroll researches, Thomas
   doubts it, Tess tests it, Frank keeps it real — in that order, each seeing the
   others. Diane does work on request (a background Job). The old parallel
   "swarm" runner stays underneath. */
(() => {
  const oldSwarm = views.swarm;
  const MODEL = { agy_pro: "Gemini Pro", agy_flash: "Gemini Flash", agy_deep: "Gemini", local_xl: "Local 30B",
                  local_small: "Local 8B", claude_adjudicator: "Claude" };
  let timer = null;

  function renderRun(d) {
    const box = document.getElementById("tm2-out");
    if (!box) return;
    box.innerHTML = `<div class="sub" style="margin:4px 0 10px">Idea: ${esc(d.idea)}</div>` + d.replies.map((r) => `
      <div class="card glass tm2-reply" style="margin:0 0 10px">
        <div style="display:flex;gap:10px;align-items:center">
          <span style="font-size:22px">${esc(r.emoji || "")}</span><b>${esc(r.name)}</b>
          <span class="meta">${r.status === "done" ? "via " + esc(MODEL[r.served_by] || r.served_by || "") + " · " + esc(String(r.secs)) + "s"
            : r.status === "thinking" ? "thinking…" : esc(r.status)}</span></div>
        ${r.text ? `<div class="md" style="margin-top:8px;white-space:pre-wrap">${mdlite(r.text)}</div>` : ""}
      </div>`).join("");
  }

  function follow(id) {
    clearInterval(timer);
    const tick = async () => {
      if (!document.getElementById("tm2-out")) return clearInterval(timer);
      try {
        const d = await api("team/run?id=" + encodeURIComponent(id));
        renderRun(d);
        if (d.status === "done") { clearInterval(timer); const b = document.getElementById("tm2-go"); if (b) b.disabled = false; }
      } catch (e) { clearInterval(timer); }
    };
    tick();
    timer = setInterval(tick, 3000);
  }
  window.tm2Follow = follow;

  window.tm2Ask = async (btn) => {
    const idea = document.getElementById("tm2-idea").value.trim();
    if (!idea) return;
    btn.disabled = true;
    try { follow((await api("team/ask", { idea })).id); }
    catch (e) { btn.disabled = false; document.getElementById("tm2-out").innerHTML = `<div class="empty">${esc(e.message || String(e))}</div>`; }
  };

  window.tm2Research = async (btn) => {
    const idea = document.getElementById("tm2-idea").value.trim();
    if (!idea) return;
    btn.disabled = true;
    try {
      await api("term/run", { engine: "claude", model: "default", cwd: "~/Projects", prompt:
        "You are Scroll, a chronically online researcher. Search the web for real, current evidence about this idea: " + idea +
        ". Find what already exists (with links), what people actually say (quote with source links), prices, and the real gap. " +
        "Then a short 'Doubting Thomas' section: which of your findings are weak or could be wrong. Plain English bullets." });
      btn.textContent = "Started — see Jobs";
    } catch (e) { btn.textContent = "Couldn't start"; btn.disabled = false; }
  };

  window.tm2Diane = async (btn) => {
    const task = document.getElementById("tm2-diane").value.trim();
    const out = document.getElementById("tm2-diane-out");
    if (!task) return;
    btn.disabled = true;
    try {
      await api("term/run", { engine: "claude", model: "default", cwd: "~/Projects", prompt:
        "You are Diane, Nate's assistant who gets things done. Do this task fully and carefully, then report back in 3-5 " +
        "plain bullets: what you did, where it is, anything Nate must check. Never mark anything as done for Nate. Task: " + task });
      out.innerHTML = 'Diane is on it — follow along in <a href="#" onclick="event.preventDefault();document.querySelector(\'.dock button[data-view=&quot;term&quot;]\').click()">Jobs</a>.';
      document.getElementById("tm2-diane").value = "";
    } catch (e) { out.textContent = "Diane couldn't start: " + (e.message || e); }
    finally { btn.disabled = false; }
  };

  views.swarm = async () => {
    let team = { members: [], diane: null }, runs = [];
    try { [team, runs] = await Promise.all([api("team"), api("team/runs")]); } catch (e) {}
    const rest = oldSwarm ? await oldSwarm() : "";
    return `
    <div class="card glass"><h2><span class="dot t-peach"></span>Your team</h2>
      <div class="sub">Pitch an idea. They answer in order, each hearing the ones before. Free models by default.</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin:12px 0">
        ${[...team.members, ...(team.diane ? [team.diane] : [])].map((m) => `
          <div class="card glass" style="margin:0;padding:12px"><div style="font-size:26px">${esc(m.emoji || "")}</div>
            <b>${esc(m.name)}</b><div class="meta">${esc(m.role)}</div></div>`).join("")}
      </div>
      <textarea id="tm2-idea" rows="3" placeholder="e.g. An app that turns my saved reels into working tools automatically"></textarea>
      <div class="row" style="gap:8px;margin-top:8px;flex-wrap:wrap">
        <button class="act" id="tm2-go" onclick="tm2Ask(this)">Pitch it to the team</button>
        <button onclick="tm2Research(this)" title="Uses Claude tokens">Scroll: research online for real (uses Claude)</button>
      </div>
      <div id="tm2-out" style="margin-top:12px"></div>
      ${runs.length ? `<div class="sub" style="margin-top:6px">Earlier: ${runs.map((r) =>
        `<span class="pill" style="cursor:pointer" data-id="${esc(r.id)}" onclick="tm2Follow(this.dataset.id)">${esc(r.idea.slice(0, 40))}</span>`).join(" ")}</div>` : ""}
    </div>
    <div class="card glass"><h2><span class="dot t-mint"></span>💼 Ask Diane</h2>
      <div class="sub">Diane does real work for you in the background (Claude, uses tokens). She reports back; you decide if it's done.</div>
      <div class="row" style="gap:8px;margin-top:8px">
        <input id="tm2-diane" placeholder="e.g. Draft a README for the net-worth app" style="flex:1" onkeydown="if(event.key==='Enter')tm2Diane(this.nextElementSibling)">
        <button class="act" onclick="tm2Diane(this)">Send to Diane</button>
      </div>
      <div id="tm2-diane-out" class="sub" style="margin-top:8px"></div>
    </div>
    <details class="card glass"><summary style="cursor:pointer">Split a big goal across parallel agents (old Team runner)</summary>${rest}</details>`;
  };
})();
