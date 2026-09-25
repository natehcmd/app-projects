/* Results (view key `artifacts`): what the agents made, as readable cards.
   Groups Flows / Team runs / Reports, newest first. Previews load lazily from
   /api/artifacts/content; click a card to expand the full result inline.
   Every data value goes through esc()/mdlite(); one delegated listener. */
(() => {
  const S = (v) => (v == null ? "" : typeof v === "string" ? v : JSON.stringify(v, null, 2));
  const GROUPS = [
    { key: "flow", label: "Flows", note: "Step-by-step recipes you ran from the Flows tab" },
    { key: "swarm", label: "Team runs", note: "Notes and write-ups from agent team / swarm runs" },
    { key: "sandbox", label: "Reports", note: "Files your agents saved to the sandbox folder" },
  ];
  const cache = new Map();   // path -> parsed { kind, data|text } or { error }
  let items = [];

  function when(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso || "";
    const mins = Math.round((Date.now() - d) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return mins + " min ago";
    if (mins < 1440) return Math.round(mins / 60) + " h ago";
    if (mins < 10080) return Math.round(mins / 1440) + " d ago";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  }

  function steps(d) {
    let s = d && d.steps;
    if (typeof s === "string") { try { s = JSON.parse(s); } catch (e) { return []; } }
    return Array.isArray(s) ? s : [];
  }

  // The "actual result" of a JSON run, as plain text.
  function jsonResult(d) {
    if (!d || typeof d !== "object") return S(d);
    if (d.result) return S(d.result);
    const st = steps(d).filter((x) => x && x.output);
    if (st.length) return S(st[st.length - 1].output);
    if (d.synthesis) return S(d.synthesis);
    if (d.goal) return "Goal: " + S(d.goal) + (Array.isArray(d.plan) ? "\nPlan: " + d.plan.map((p) => p && p.title).filter(Boolean).join(", ") : "");
    return "";
  }

  // First real paragraph of markdown/plain text (skip headings, rules, empty lines).
  function firstPara(t) {
    const paras = S(t).split(/\n\s*\n/).map((p) => p.split("\n").filter((l) => !/^\s*(#|---|===|```)/.test(l)).join(" ").trim());
    return paras.find((p) => p.length > 3) || "";
  }
  function firstHeading(t) { const m = S(t).match(/^#{1,3}\s+(.+)$/m); return m ? m[1].trim() : ""; }
  function plain(t) { return S(t).replace(/[*`>#]+/g, "").replace(/\s+/g, " ").trim(); }

  function parse(it, content) {
    if (it.ext === "json") { try { return { kind: "json", data: JSON.parse(content) }; } catch (e) { /* fall through */ } }
    return { kind: "text", text: content };
  }

  function titleOf(it, c) {
    if (c && c.kind === "json" && c.data) {
      if (c.data.flow_name) return S(c.data.flow_name);
      if (c.data.goal) return S(c.data.goal);
    }
    if (c && c.kind === "text") { const h = firstHeading(c.text); if (h) return h; }
    return S(it.title).replace(/^(Swarm|Flow|Sandbox):\s*/, "") || it.name;
  }

  function previewOf(c) {
    if (!c) return "Loading preview…";
    if (c.error) return "Couldn't load this one: " + c.error;
    const t = c.kind === "json" ? jsonResult(c.data) : firstPara(c.text);
    return plain(t).slice(0, 320) || "No written result in this file.";
  }

  function fullOf(c) {
    if (!c) return '<div class="meta">Loading…</div>';
    if (c.error) return `<div class="meta">${esc(c.error)}</div>`;
    if (c.kind === "text") return `<div class="md rs2-md">${mdlite(c.text)}</div>`;
    const d = c.data, out = [];
    if (d && typeof d === "object" && !Array.isArray(d)) {
      if (d.input) out.push(sec("Input", d.input));
      if (d.goal) out.push(sec("Goal", d.goal));
      if (Array.isArray(d.plan) && d.plan.length) out.push(sec("Plan", d.plan.map((p, i) => (i + 1) + ". " + S(p && (p.title || p.prompt))).join("\n")));
      steps(d).forEach((s, i) => out.push(sec("Step " + (i + 1) + ": " + S(s && s.name) + (s && s.status ? " (" + S(s.status) + ")" : ""), s && s.output || "(no output)")));
      if (d.result) out.push(sec("Result", d.result, true));
    }
    if (!out.length) out.push(`<pre class="rs2-pre">${esc(S(d))}</pre>`);
    return out.join("");
  }
  function sec(h, body, main) {
    return `<div class="rs2-sec${main ? " rs2-main" : ""}"><div class="rs2-h">${esc(h)}</div><div class="md rs2-md">${mdlite(S(body))}</div></div>`;
  }

  function card(it, i) {
    const c = cache.get(it.path);
    return `<div class="card glass rs2-card" data-idx="${i}" tabindex="0" role="button" aria-expanded="false">
      <div class="rs2-top"><b class="rs2-title">${esc(titleOf(it, c))}</b><span class="meta" title="${esc(S(it.modified))}">${esc(when(it.modified))}</span></div>
      <div class="rs2-prev">${esc(previewOf(c))}</div>
      <div class="meta rs2-file">${esc(S(it.name))}</div>
      <div class="rs2-full" hidden></div>
    </div>`;
  }

  function paint() {
    const box = document.getElementById("rs2-list");
    if (!box) return;
    const q = (document.getElementById("rs2-q") || {}).value || "";
    const needle = q.trim().toLowerCase();
    const hit = (it) => {
      if (!needle) return true;
      const c = cache.get(it.path);
      return [titleOf(it, c), it.name, it.title, c ? previewOf(c) : ""].join(" ").toLowerCase().includes(needle);
    };
    const html = GROUPS.map((g) => {
      const list = items.map((it, i) => [it, i]).filter(([it]) => (it.source === g.key || (g.key === "sandbox" && !GROUPS.some((x) => x.key === it.source))) && hit(it));
      if (!list.length) return "";
      return `<section class="rs2-group"><h3>${esc(g.label)} <span class="meta">${list.length} · ${esc(g.note)}</span></h3>
        <div class="rs2-grid">${list.map(([it, i]) => card(it, i)).join("")}</div></section>`;
    }).join("");
    box.innerHTML = html || (items.length
      ? `<div class="empty">Nothing matches “${esc(q)}”.</div>`
      : `<div class="empty">Nothing here yet. When you run a Flow, ask your agent Team for something, or an agent saves a report to the sandbox folder, the finished result shows up here as a card you can open and read.</div>`);
  }

  async function load(it) {
    if (cache.has(it.path)) return;
    try { const r = await apiOk("artifacts/content?path=" + encodeURIComponent(it.path)); cache.set(it.path, parse(it, S(r.content))); }
    catch (e) { cache.set(it.path, { error: e.message || String(e) }); }
  }

  async function loadAll() {
    const queue = items.slice();
    const worker = async () => { while (queue.length && document.getElementById("rs2-list")) { await load(queue.shift()); } };
    let n = 0;
    const tick = setInterval(() => { if (++n > 200 || !document.getElementById("rs2-list")) clearInterval(tick); else paintKeep(); }, 400);
    await Promise.all([worker(), worker(), worker(), worker()]);
    clearInterval(tick);
    paintKeep();
  }

  // Repaint without losing which cards are open.
  function paintKeep() {
    const open = [...document.querySelectorAll(".rs2-card[aria-expanded=true]")].map((el) => el.dataset.idx);
    paint();
    open.forEach((idx) => { const el = document.querySelector(`.rs2-card[data-idx="${CSS.escape(idx)}"]`); if (el) expand(el, true); });
  }

  async function expand(el, force) {
    const it = items[+el.dataset.idx];
    const full = el.querySelector(".rs2-full");
    if (!it || !full) return;
    const open = force || el.getAttribute("aria-expanded") !== "true";
    el.setAttribute("aria-expanded", String(open));
    el.classList.toggle("rs2-open", open);
    full.hidden = !open;
    if (!open) return;
    full.innerHTML = fullOf(cache.get(it.path));
    if (!cache.has(it.path)) { await load(it); full.innerHTML = fullOf(cache.get(it.path)); }
  }

  if (!window.__rs2Bound) {
    window.__rs2Bound = true;
    document.addEventListener("click", (e) => {
      const el = e.target.closest && e.target.closest(".rs2-card");
      if (!el || e.target.closest(".rs2-full")) return;
      expand(el);
    });
    document.addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("rs2-card")) { e.preventDefault(); expand(e.target); }
    });
    document.addEventListener("input", (e) => { if (e.target.id === "rs2-q") paint(); });
  }

  const CSS_TEXT = `
    .rs2-wrap{width:100%;max-width:none}
    .rs2-head{display:flex;gap:16px;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;margin-bottom:14px}
    .rs2-head h2{margin:0}
    #rs2-q{flex:0 1 340px;min-width:0;width:100%;padding:9px 12px;border-radius:10px;border:1px solid var(--glass-brd);background:var(--glass);color:var(--ink)}
    .rs2-group{margin:18px 0 6px}
    .rs2-group h3{margin:0 0 10px;font-size:15px}
    .rs2-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}
    .rs2-card{margin:0;cursor:pointer;padding:14px 16px;border:1px solid var(--glass-brd);transition:border-color .15s}
    .rs2-card:hover,.rs2-card:focus-visible{border-color:var(--accent);outline:none}
    .rs2-card.rs2-open{grid-column:1/-1;cursor:default}
    .rs2-top{display:flex;gap:10px;justify-content:space-between;align-items:baseline}
    .rs2-title{overflow-wrap:anywhere}
    .rs2-top .meta{white-space:nowrap}
    .rs2-prev{margin-top:6px;opacity:.85;line-height:1.45;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
    .rs2-open .rs2-prev{display:none}
    .rs2-file{margin-top:6px;font-size:11px}
    .rs2-full{margin-top:12px;border-top:1px solid var(--glass-brd);padding-top:12px;cursor:text}
    .rs2-sec{margin:0 0 14px}
    .rs2-h{font-weight:600;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--sky);margin-bottom:4px}
    .rs2-main .rs2-h{color:var(--mint)}
    .rs2-md{white-space:pre-wrap;line-height:1.5;overflow-wrap:anywhere;max-height:60vh;overflow:auto}
    .rs2-pre{white-space:pre-wrap;overflow:auto;max-height:60vh;font-size:12px}`;

  views.artifacts = async () => {
    try { items = await apiOk("artifacts"); } catch (e) { items = []; }
    if (!Array.isArray(items)) items = [];
    items = items.slice().sort((a, b) => S(b.modified).localeCompare(S(a.modified)));
    setTimeout(() => { paint(); loadAll(); }, 0);
    return `<style>${CSS_TEXT}</style>
    <div class="card glass rs2-wrap">
      <div class="rs2-head">
        <div><h2><span class="dot t-mint"></span>What your agents made</h2>
          <div class="sub">Finished results from your Flows, Team runs and saved reports. Newest first. Click a card to read it.</div></div>
        <input id="rs2-q" type="search" placeholder="Search results…" aria-label="Search results">
      </div>
      <div id="rs2-list"><div class="meta">Loading…</div></div>
    </div>`;
  };
})();
