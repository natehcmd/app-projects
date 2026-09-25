// subs2.js — subscription watcher UI. Reads GET /api/subs (server.py + subs_watch.py,
// already written — this file never touches either). Two things:
//  1. A "Subscriptions" card prepended to the Control tab (wraps views.control).
//  2. A small top-bar pill polling every 60s, colored by how close Claude is to its
//     limit (or flagging a Gemini model that's currently out).
// Claude's numbers come straight from Claude Code's own /usage (exact pct + a
// human "resets" string per entry, no raw token counts, no learned limit, no
// by-model split, no "just stopped me" buttons — /api/subs/hit is unused here).
// Numbers through esc(String(x)) only; no data in inline onclick — one delegated
// listener keyed off data-s2 attributes.
(() => {
  const E = v => esc(String(v ?? ""));
  const ok = r => r && typeof r === "object" && !r.error;

  /* ---------- formatting ---------- */
  const humanNum = n => {
    if (n === null || n === undefined) return null;
    const a = Math.abs(n);
    if (a >= 1e6) return (n / 1e6).toFixed(2).replace(/\.?0+$/, "") + "M";
    if (a >= 1e3) return (n / 1e3).toFixed(1).replace(/\.?0+$/, "") + "K";
    return String(n);
  };
  const humanTok = n => (n === null || n === undefined) ? null : `${humanNum(n)} tokens`;
  const fmtTime = epoch => {
    if (!epoch) return null;
    try { return new Date(epoch * 1000).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); }
    catch (e) { return null; }
  };

  /* ---------- CSS ---------- */
  const CSS = `<style>
  .s2-advice{background:rgba(255,107,157,0.08);border:1px solid rgba(255,107,157,0.28);
    border-radius:10px;padding:10px 12px;margin-bottom:14px;font-size:13px}
  .s2-advice .s2-arow{margin:3px 0}
  .s2-sub{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
  .s2-sub .card{margin:0}
  .s2-modelrow{margin-bottom:12px}
  .s2-modelrow:last-child{margin-bottom:0}
  .s2-rowhead{display:flex;justify-content:space-between;gap:8px;font-size:13px;margin-bottom:5px}
  .s2-rowhead b{font-weight:600}
  .s2-track{position:relative;height:10px;border-radius:6px;background:rgba(255,255,255,0.06);
    border:1px solid var(--glass-brd);overflow:hidden;margin-bottom:4px}
  .s2-fill{height:100%;border-radius:6px 0 0 6px;transition:width .3s ease}
  .s2-target{position:absolute;top:-2px;bottom:-2px;width:2px;background:var(--ink);opacity:.55}
  .s2-meta{font-size:12px;color:var(--ink-dim)}
  .s2-note{font-size:12px;color:var(--ink-faint);margin-top:8px;line-height:1.5}
  .s2-out{font-size:12px;color:var(--ink-dim);margin-top:6px;min-height:1em}
  .s2-out.bad{color:var(--rose)}
  .s2-local{font-size:20px;font-weight:700}
  .s2-pill{margin-left:10px;padding:4px 10px;border-radius:999px;border:1px solid;background:transparent;
    font-size:12px;cursor:pointer;flex:none}
  </style>`;

  /* ---------- bar + row rendering ---------- */
  function pctColor(pct) {
    if (pct === null || pct === undefined) return "var(--ink-faint)";
    if (pct >= 80) return "var(--rose)";
    if (pct >= 60) return "var(--peach)";
    return "var(--mint)";
  }

  function bar(used, limit, pct, targetPct) {
    const usedTxt = humanTok(used) ?? "0 tokens";
    const color = pctColor(pct);
    const w = pct === null || pct === undefined ? 0 : Math.max(0, Math.min(100, pct));
    const target = (typeof targetPct === "number")
      ? `<div class="s2-target" style="left:${E(targetPct)}%" title="${E(targetPct)}% target"></div>` : "";
    const track = `<div class="s2-track"><div class="s2-fill" style="width:${w}%;background:${color}"></div>${target}</div>`;
    if (limit === null || limit === undefined || pct === null || pct === undefined) {
      return `${track}<div class="s2-meta">${E(usedTxt)} used &middot; limit not learned yet</div>`;
    }
    return `${track}<div class="s2-meta">${E(usedTxt)} of ${E(humanTok(limit))} &middot; ${E(pct)}%</div>`;
  }

  function windowRow(label, w, targetPct, resetLabel) {
    const resets = resetLabel ? ` &middot; ${E(resetLabel)}` : "";
    return `<div class="s2-modelrow">
      <div class="s2-rowhead"><b>${E(label)}</b><span class="s2-meta">${resets}</span></div>
      ${bar(w.used, w.limit, w.pct, targetPct)}
    </div>`;
  }

  // Claude side: exact numbers from Claude Code's own /usage — pct + a human
  // "resets" string only (no raw token counts, no learned limit, no by-model split).
  function claudeBarOnly(pct, targetPct) {
    const color = pctColor(pct);
    const w = (pct === null || pct === undefined) ? 0 : Math.max(0, Math.min(100, pct));
    const target = (typeof targetPct === "number")
      ? `<div class="s2-target" style="left:${E(targetPct)}%" title="${E(targetPct)}% target"></div>` : "";
    return `<div class="s2-track"><div class="s2-fill" style="width:${w}%;background:${color}"></div>${target}</div>`;
  }

  function claudeLimitRow(l, targetPct) {
    const pctTxt = (l.pct === null || l.pct === undefined) ? "" : `${E(l.pct)}%`;
    return `<div class="s2-modelrow">
      <div class="s2-rowhead"><b>${E(l.label)}</b><span class="s2-meta">${pctTxt}</span></div>
      ${claudeBarOnly(l.pct, targetPct)}
      <div class="s2-meta">${l.resets ? `resets ${E(l.resets)}` : ""}</div>
    </div>`;
  }

  function claudeCard(c, targetPct) {
    if (c.error) {
      return `<div class="card glass">
        <h2><span class="dot t-mint"></span>Claude</h2>
        <div class="s2-out bad">${E(c.error)}</div>
      </div>`;
    }
    const rows = (Array.isArray(c.limits) ? c.limits : []).map(l => claudeLimitRow(l, targetPct)).join("");
    return `<div class="card glass">
      <h2><span class="dot t-mint"></span>Claude</h2>
      ${rows || `<div class="s2-meta">No usage data yet.</div>`}
      <div class="s2-note">${E(c.note)}</div>
    </div>`;
  }

  function geminiCard(g, targetPct) {
    const rows = (g.models || []).map(m => {
      if (m.out_until) {
        const until = fmtTime(m.out_until);
        return `<div class="s2-modelrow">
          <div class="s2-rowhead"><b>${E(m.name)}</b><span class="s2-meta" style="color:var(--rose)">out${until ? ` until ${E(until)}` : ""}</span></div>
          <div class="s2-track"><div class="s2-fill" style="width:100%;background:var(--rose)"></div></div>
        </div>`;
      }
      const rt = fmtTime(m.resets_at);
      return windowRow(m.name, m, targetPct, rt ? `resets at ${rt}` : null);
    }).join("");
    return `<div class="card glass">
      <h2><span class="dot t-sky"></span>Gemini (Antigravity)</h2>
      ${rows || `<div class="s2-meta">No model data yet.</div>`}
      <div class="s2-note">${E(g.note)}</div>
    </div>`;
  }

  function localCard(l) {
    const used = l.day && l.day.used;
    const txt = used === null || used === undefined ? "not measured" : humanTok(used);
    return `<div class="card glass">
      <h2><span class="dot t-peach"></span>Local models (Ollama)</h2>
      <div class="s2-local">${E(txt)}</div>
      <div class="s2-meta">${E(l.day && l.day.label)}</div>
      <div class="s2-note">${E(l.note)}</div>
    </div>`;
  }

  function adviceHtml(advice) {
    if (!Array.isArray(advice) || !advice.length) return "";
    return `<div class="s2-advice">${advice.map(a => `<div class="s2-arow">${E(a)}</div>`).join("")}</div>`;
  }

  function cardHtml(data) {
    if (!ok(data)) {
      return `<div class="card glass" id="s2card"><h2><span class="dot t-rose"></span>Subscriptions
        <button class="act ghost" style="margin-left:auto" data-s2="refresh">Refresh</button></h2>
        <div class="s2-out bad">Couldn't load subscription usage${data && data.error ? `: ${E(data.error)}` : ""}.</div></div>`;
    }
    const target = data.target_pct;
    const subs = Array.isArray(data.subs) ? data.subs : [];
    const claude = subs.find(s => s.id === "claude");
    const gemini = subs.find(s => s.id === "gemini");
    const local = subs.find(s => s.id === "local");
    return `<div class="card glass" id="s2card">
      <h2><span class="dot t-lav"></span>Subscriptions
        <button class="act ghost" style="margin-left:auto" data-s2="refresh">Refresh</button></h2>
      ${adviceHtml(data.advice)}
      <div class="s2-sub">
        ${claude ? claudeCard(claude, target) : ""}
        ${gemini ? geminiCard(gemini, target) : ""}
        ${local ? localCard(local) : ""}
      </div>
    </div>`;
  }

  async function buildCard() {
    const data = await api("subs").catch(e => ({ error: String(e) }));
    return cardHtml(data);
  }

  /* ---------- wrap views.control ---------- */
  const prevControl = views.control;
  views.control = async () => {
    const card = await buildCard();
    return CSS + card + await prevControl();
  };

  document.addEventListener("click", async ev => {
    const b = ev.target.closest("[data-s2]");
    if (!b || b.disabled) return;
    const action = b.dataset.s2;
    if (action === "refresh") {
      const el = document.getElementById("s2card");
      if (el) el.outerHTML = await buildCard();
    }
  });

  /* ---------- top-bar pill ---------- */
  let pill = null;
  function pillColor(pct) {
    if (pct === null || pct === undefined) return "var(--sky,#4bd3ff)";
    if (pct >= 80) return "var(--rose,#ff6b9d)";
    if (pct >= 60) return "var(--peach,#ffb570)";
    return "var(--mint,#3bffd2)";
  }
  async function checkPill() {
    const bar = document.querySelector(".topbar");
    if (!bar) return;
    let data;
    try { data = await apiOk("subs"); } catch (e) { if (pill) pill.hidden = true; return; }
    const subs = Array.isArray(data.subs) ? data.subs : [];
    const claude = subs.find(s => s.id === "claude") || {};
    const gemini = subs.find(s => s.id === "gemini") || {};
    const outModel = (gemini.models || []).find(m => m.out_until);
    let label, color;
    if (outModel) {
      label = `${outModel.name} out`;
      color = "var(--rose,#ff6b9d)";
    } else {
      const pcts = (Array.isArray(claude.limits) ? claude.limits : [])
        .map(l => l.pct).filter(p => p !== null && p !== undefined);
      const pct = pcts.length ? Math.max(...pcts) : null;
      label = pct === null ? "Claude" : `Claude ${pct}%`;
      color = pillColor(pct);
    }
    if (!pill) {
      pill = document.createElement("button");
      pill.type = "button";
      pill.className = "s2-pill";
      pill.onclick = () => document.querySelector('.dock button[data-view="control"]')?.click();
      bar.appendChild(pill);
    }
    pill.style.borderColor = color;
    pill.style.color = color;
    pill.textContent = label;
    pill.hidden = false;
  }
  const startPill = () => { checkPill(); setInterval(checkPill, 60000); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startPill);
  else startPill();
})();
