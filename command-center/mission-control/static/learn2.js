/* Learn (backlog P2): a "learn something" card on top — a coding term, a
   how-to with code, or a fact — written by the local model on each press. */
(() => {
  const oldLearn = views.learn;
  const KINDS = [["term", "Coding term"], ["code", "How to (with code)"], ["fact", "Random fact"]];

  async function deal(kind, btn) {
    const box = document.getElementById("ln2-card");
    if (!box) return;
    document.querySelectorAll(".ln2-k").forEach((b) => (b.disabled = true));
    box.innerHTML = '<div class="empty">Writing and checking… (local AI writes, Gemini checks)</div>';
    try {
      const c = await apiOk("learn/card?kind=" + encodeURIComponent(kind));
      box.innerHTML = `
        <h3 style="margin:0 0 6px">${esc(c.title)}</h3>
        <div style="line-height:1.55">${esc(c.body)}</div>
        ${c.code ? `<pre class="termout" style="margin-top:10px;white-space:pre-wrap">${esc(c.code)}</pre>` : ""}
        <div class="meta" style="margin-top:8px;opacity:.65">${checkLine(c.check)}</div>`;
    } catch (e) {
      box.innerHTML = '<div class="empty">The local model is busy — try again in a minute.</div>';
    } finally {
      document.querySelectorAll(".ln2-k").forEach((b) => (b.disabled = false));
    }
  }
  window.ln2Deal = deal;
  function checkLine(ck) {
    if (!ck) return "Written by a local AI — not checked.";
    if (ck.corrected_by) return "Written by a local AI, corrected by Gemini after a check flagged: " + esc(ck.issue || "");
    if (ck.ok === true) return "Written by a local AI · checked by Gemini ✓";
    if (ck.ok === false) return "⚠️ Gemini flagged this card: " + esc(ck.issue || "") + " — treat it with care.";
    return "Written by a local AI — not checked (" + esc(ck.issue || "checker unavailable") + ").";
  }

  views.learn = async () => {
    const rest = oldLearn ? await oldLearn() : "";
    setTimeout(() => deal(KINDS[Math.floor(Math.random() * KINDS.length)][0]), 0);
    return `
    <div class="card glass"><h2><span class="dot t-lav"></span>Learn something</h2>
      <div class="row" style="gap:8px;margin:6px 0 12px;flex-wrap:wrap">
        ${KINDS.map(([k, label]) => `<button class="act ln2-k" data-kind="${k}" onclick="ln2Deal(this.dataset.kind, this)">${label}</button>`).join("")}
      </div>
      <div id="ln2-card"><div class="empty">…</div></div>
    </div>${rest}`;
  };
})();
