/* Hub — project + agent status board. Self-contained tab add-on.
   Load AFTER os.js:  <script src="hub.js"></script>
   Plus one nav button in index.html:
     <button data-view="hub" title="Hub">🗂<span>Hub</span></button>
   Nothing else to wire — os.js's dock loop + render() pick it up generically.
   Data lives in static/hub.json (hand-editable). Drag cards between lanes;
   overrides persist in this browser via localStorage ("Reset" clears them). */
(function () {
  var _$ = window.$ || (s => document.querySelector(s));
  var _esc = window.esc || (s => (s || "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])));
  var OVR_KEY = "cc_hub_overrides";
  var KIND_KEY = "cc_hub_kind";

  function loadOverrides() {
    try { return JSON.parse(localStorage.getItem(OVR_KEY) || "{}"); } catch (e) { return {}; }
  }
  function saveOverrides(o) {
    try { localStorage.setItem(OVR_KEY, JSON.stringify(o)); } catch (e) {}
  }

  window.hubDrop = function (ev, laneId) {
    ev.preventDefault();
    var name = ev.dataTransfer.getData("text/plain");
    if (!name) return;
    var o = loadOverrides();
    o[name] = laneId;
    saveOverrides(o);
    if (typeof api === "function") {
      api("hub/move", { name: name, lane: laneId }).catch(function (e) {
        console.warn("Could not persist hub move to server:", e);
      });
    }
    if (typeof render === "function") render();
  };
  window.hubDragOver = function (ev) { ev.preventDefault(); ev.dataTransfer.dropEffect = "move"; };
  window.hubReset = function () {
    try { localStorage.removeItem(OVR_KEY); } catch (e) {}
    if (typeof render === "function") render();
  };
  window.hubKind = function (k) {
    try { localStorage.setItem(KIND_KEY, k || ""); } catch (e) {}
    if (typeof render === "function") render();
  };

  function ensureStyle() {
    if (document.getElementById("hub-style")) return;
    var s = document.createElement("style");
    s.id = "hub-style";
    s.textContent = [
      ".kb{display:flex;gap:16px;overflow-x:auto;padding:4px 4px 16px;align-items:flex-start}",
      ".kb-col{flex:0 0 300px;display:flex;flex-direction:column;gap:10px;padding:16px;border-radius:20px;",
      "  background:rgba(255,255,255,0.02);border:1px solid var(--glass-brd,rgba(255,255,255,0.08));min-height:120px}",
      ".kb-col.drag{border-color:var(--mint,#3bffd2);background:rgba(59,255,210,0.06)}",
      ".kb-col h3{font-size:0.72rem;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;",
      "  color:var(--ink-dim,#a5b4d6);display:flex;align-items:center;gap:8px;margin:2px 0 4px}",
      ".kb-col h3 .n{margin-left:auto;color:var(--ink-faint,#677496);font-weight:600}",
      ".kb-col .blurb{color:var(--ink-faint,#677496);font-size:0.75rem;margin:-4px 0 4px}",
      ".kb-card{padding:14px 16px;border-radius:14px;background:rgba(255,255,255,0.03);",
      "  border:1px solid var(--glass-brd,rgba(255,255,255,0.08));cursor:grab;transition:all .2s}",
      ".kb-card:hover{border-color:rgba(255,255,255,0.25);transform:translateY(-1px)}",
      ".kb-card.open{background:rgba(255,255,255,0.06)}",
      ".kb-card b{font-size:0.9rem;display:block;line-height:1.35}",
      ".kb-card .kmeta{color:var(--ink-faint,#677496);font-size:0.72rem;margin-top:5px;display:flex;gap:8px;flex-wrap:wrap}",
      ".kb-card .kbody{margin-top:10px;font-size:0.8rem;color:var(--ink-dim,#a5b4d6);display:none}",
      ".kb-card.open .kbody{display:block}",
      ".kb-card .kbody ul{margin:4px 0 8px 16px;padding:0}",
      ".kb-card .kbody li{margin:2px 0}",
      ".kb-card .klbl{color:var(--ink,#fff);font-weight:700;font-size:0.72rem;letter-spacing:0.08em;text-transform:uppercase}",
      ".kb-card .knote{margin-top:6px;font-style:italic;color:var(--ink-faint,#677496)}",
      ".hub-agents .item .adot{width:9px;height:9px;border-radius:50%;flex:none;box-shadow:0 0 8px currentColor}",
      ".hub-agents .adot.ok{color:var(--mint,#3bffd2);background:var(--mint,#3bffd2)}",
      ".hub-agents .adot.warn{color:var(--peach,#ffb570);background:var(--peach,#ffb570)}",
      ".hub-agents .adot.err{color:var(--rose,#ff6b9d);background:var(--rose,#ff6b9d)}"
    ].join("\n");
    document.head.appendChild(s);
  }

  var KINDS = ["app", "native", "web", "infra", "skill", "pipeline", "extension", "venture", "experiment", "research", "misc"];

  views.hub = async function () {
    ensureStyle();
    var data;
    try {
      data = await (await fetch("hub.json?" + Date.now())).json();
    } catch (e) {
      return '<div class="card glass empty">Could not load hub.json — it should sit next to index.html in static/.</div>';
    }
    var ovr = loadOverrides();
    var kindFilter = "";
    try { kindFilter = localStorage.getItem(KIND_KEY) || ""; } catch (e) {}

    var projects = (data.projects || []).map(function (p) {
      return Object.assign({}, p, { lane: ovr[p.name] || p.lane, _moved: !!ovr[p.name] });
    });
    if (kindFilter) projects = projects.filter(function (p) { return p.kind === kindFilter; });

    var byLane = {};
    projects.forEach(function (p) { (byLane[p.lane] = byLane[p.lane] || []).push(p); });

    var card = function (p) {
      var done = (p.done || []).map(function (d) { return "<li>" + _esc(d) + "</li>"; }).join("");
      var next = (p.next || []).map(function (d) { return "<li>" + _esc(d) + "</li>"; }).join("");
      return '<div class="kb-card" draggable="true" '
        + 'ondragstart="event.dataTransfer.setData(\'text/plain\',this.dataset.name);event.dataTransfer.effectAllowed=\'move\'" '
        + 'data-name="' + _esc(p.name) + '" '
        + 'onclick="this.classList.toggle(\'open\')">'
        + '<b>' + _esc(p.name) + (p._moved ? ' <span class="pill" style="padding:1px 8px;font-size:0.62rem">moved</span>' : '') + '</b>'
        + '<div class="kmeta">'
        + '<span class="dot t-' + _esc(p.tone || "sky") + '" style="width:7px;height:7px;border-radius:50%;align-self:center;box-shadow:0 0 8px currentColor"></span>'
        + '<span>' + _esc(p.kind || "") + '</span>'
        + (p.repo ? '<span>· ' + _esc(p.repo) + '</span>' : '')
        + (p.touched ? '<span>· touched ' + _esc(p.touched) + '</span>' : '')
        + '</div>'
        + '<div class="kbody">'
        + '<code style="opacity:0.6;font-size:0.72rem">' + _esc(p.path || "") + '</code>'
        + (done ? '<div style="margin-top:8px"><span class="klbl" style="color:var(--mint,#3bffd2)">Done</span><ul>' + done + '</ul></div>' : '')
        + (next ? '<div><span class="klbl" style="color:var(--peach,#ffb570)">Next</span><ul>' + next + '</ul></div>' : '')
        + (p.note ? '<div class="knote">' + _esc(p.note) + '</div>' : '')
        + '</div></div>';
    };

    var cols = (data.lanes || []).map(function (ln) {
      var items = byLane[ln.id] || [];
      return '<div class="kb-col" ondragover="hubDragOver(event)" ondrop="hubDrop(event,\'' + ln.id + '\')" '
        + 'ondragenter="this.classList.add(\'drag\')" ondragleave="this.classList.remove(\'drag\')">'
        + '<h3><span class="dot t-' + _esc(ln.tone) + '" style="width:8px;height:8px;border-radius:50%;box-shadow:0 0 8px currentColor"></span>'
        + _esc(ln.name) + '<span class="n">' + items.length + '</span></h3>'
        + '<div class="blurb">' + _esc(ln.blurb || "") + '</div>'
        + (items.length ? items.map(card).join("") : '<div class="empty" style="padding:16px;font-size:0.8rem">—</div>')
        + '</div>';
    }).join("");

    var kindPills = ['<span class="pill ' + (!kindFilter ? "on t-lav" : "") + '" onclick="hubKind(\'\')">all</span>']
      .concat(KINDS.map(function (k) {
        return '<span class="pill ' + (kindFilter === k ? "on t-lav" : "") + '" onclick="hubKind(\'' + k + '\')">' + k + '</span>';
      })).join("");

    var agents = (data.agents || []).map(function (a) {
      return '<div class="item"><span class="adot ' + _esc(a.status) + '"></span>'
        + '<div class="grow"><b>' + _esc(a.name) + '</b><div class="meta">' + _esc(a.detail) + '</div></div></div>';
    }).join("");

    var total = (data.projects || []).length;
    var movedCount = Object.keys(ovr).length;

    return ''
      + '<div class="card glass"><h2><span class="dot t-lav"></span>Hub — project status board'
      + '<span class="pill" style="margin-left:auto">' + total + ' projects</span></h2>'
      + '<div class="sub">Every project across your git + local dirs, one card each, triaged into lanes. '
      + 'Click a card for what\'s done / what\'s next. Drag a card to move it — moves save in this browser only'
      + (movedCount ? ' (<b>' + movedCount + '</b> moved) ' : ' ')
      + '<span class="pill" onclick="hubReset()" style="cursor:pointer">reset</span>. '
      + 'Edit <code>static/hub.json</code> to make changes permanent. Generated ' + _esc(data.generated || "") + '.</div>'
      + '<div class="row" style="gap:6px;margin-top:10px;flex-wrap:wrap">' + kindPills + '</div>'
      + '</div>'
      + '<div class="kb">' + cols + '</div>'
      + '<div class="card glass hub-agents"><h2><span class="dot t-mint"></span>Agents &amp; automation</h2>'
      + '<div class="sub" style="margin-bottom:10px">Scheduled / always-on agents and the skill infra behind them. '
      + '<span style="color:var(--peach,#ffb570)">amber</span> = running but needs attention.</div>'
      + '<div class="list">' + agents + '</div></div>';
  };
})();
