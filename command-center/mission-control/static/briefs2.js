/* Briefs (backlog P2): each brief shows 5 plain-English bullets first (local
   model, cached server-side), the full text one click away. */
(() => {
  const nice = (name) => {
    const m = name.match(/^(\d{4}-\d{2}-\d{2})-?(.*)$/);
    const title = (m && m[2] ? m[2] : name).replace(/-/g, " ");
    return { date: m ? m[1] : "", title: title.charAt(0).toUpperCase() + title.slice(1) || "Morning brief" };
  };
  const bullets = (txt) => `<ul class="br2-ul">${txt.split("\n").filter(Boolean)
    .map((l) => `<li>${esc(l.replace(/^[-•*]\s*/, ""))}</li>`).join("")}</ul>`;

  async function loadShort(el) {
    try {
      const r = await api("briefs/short?name=" + encodeURIComponent(el.dataset.name));
      el.innerHTML = r && r.short ? bullets(r.short) : '<div class="empty">No summary</div>';
    } catch (e) {
      el.innerHTML = '<div class="empty">Short version not ready (local model busy) — open the full brief below.</div>';
    }
  }

  views.briefs = async () => {
    const bs = await api("briefs");
    setTimeout(async () => {
      for (const el of document.querySelectorAll(".br2-short[data-name]")) await loadShort(el); // one at a time: one local model
    }, 0);
    return `
    <style>.br2-ul{margin:6px 0 4px 18px;padding:0;line-height:1.55}.br2-ul li{margin:3px 0}
      .br2 h3{margin:0 0 2px}.br2 .meta{opacity:.6;font-size:12px}.br2 details{margin-top:8px}
      .br2 summary{cursor:pointer;opacity:.7;font-size:12px}</style>
    <div class="card glass"><h2><span class="dot t-peach"></span>Briefs</h2>
      <div class="sub">Short notes on what's going on. Each one starts with 5 simple bullets; tap "Full brief" for everything.
        A local AI writes a new morning brief at 8 AM.</div>
      <div style="margin-top:10px"><button class="act" onclick="genBrief(this)">Write today's brief now</button></div></div>
    ${bs.map((b) => { const n = nice(b.name); return `
      <div class="brief glass br2"><h3>${esc(n.title)}</h3><div class="meta">${esc(n.date)}</div>
        <div class="br2-short" data-name="${esc(b.name)}"><div class="empty">Writing the short version…</div></div>
        <details><summary>Full brief</summary><div class="md">${mdlite(b.content)}</div></details>
      </div>`; }).join("") || '<div class="card glass empty">No briefs yet — write one now, or wait for 8 AM.</div>'}`;
  };
})();
