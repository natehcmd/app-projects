/* Jarvis Home (backlog P2) — drafted by Gemini Flash via the pipeline, reviewed by Claude. */
(() => {
  let cpuSamples = [];
  let pollInterval = null;
  const CIRC = 339.29; // 2 * PI * 54

  function ensureStyles() {
    if (document.getElementById("jh-style")) return;
    const style = document.createElement("style");
    style.id = "jh-style";
    style.textContent = `
      .jh-wrap {
        display: flex;
        flex-direction: column;
        gap: 20px;
        color: var(--ink);
        font-family: inherit;
        box-sizing: border-box;
      }
      .jh-header {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .jh-header h1 {
        margin: 0;
        font-size: 1.6rem;
        font-weight: 600;
        letter-spacing: -0.01em;
        color: var(--ink);
      }
      .jh-header p {
        margin: 0;
        font-size: 0.95rem;
        color: var(--ink-dim);
      }
      .jh-dials {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 16px;
      }
      .jh-card {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r, 10px);
        padding: 16px;
        box-sizing: border-box;
      }
      .jh-dial-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 18px 12px;
        text-align: center;
      }
      .jh-dial-svg {
        width: 140px;
        height: 140px;
        overflow: visible;
      }
      .jh-dial-bg {
        fill: none;
        stroke: var(--glass-brd);
        stroke-width: 9;
      }
      .jh-dial-meter {
        fill: none;
        stroke-width: 9;
        stroke-linecap: round;
        transition: stroke-dashoffset 0.4s ease, stroke 0.4s ease;
      }
      .jh-dial-val {
        font-size: 1.5rem;
        font-weight: 600;
        fill: var(--ink);
        text-anchor: middle;
        dominant-baseline: central;
      }
      .jh-dial-err {
        font-size: 0.78rem;
        fill: var(--ink-faint);
        text-anchor: middle;
        dominant-baseline: central;
      }
      .jh-dial-lbl {
        margin-top: 10px;
        font-size: 0.88rem;
        font-weight: 500;
        color: var(--ink-dim);
      }
      .jh-main-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        align-items: start;
      }
      @media (max-width: 900px) {
        .jh-main-grid {
          grid-template-columns: 1fr;
        }
      }
      .jh-col {
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .jh-card-title {
        font-size: 0.95rem;
        font-weight: 600;
        margin: 0 0 14px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: var(--ink);
      }
      .jh-card-title .jh-count {
        font-size: 0.82rem;
        font-weight: 400;
        color: var(--ink-dim);
      }
      .jh-graph-wrap {
        width: 100%;
        height: 100px;
        margin-top: 8px;
      }
      .jh-graph-svg {
        width: 100%;
        height: 100%;
        overflow: visible;
      }
      .jh-graph-grid {
        stroke: var(--glass-brd);
        stroke-width: 1;
        stroke-dasharray: 2 4;
      }
      .jh-graph-area {
        fill: var(--accent, var(--sky));
        opacity: 0.12;
      }
      .jh-graph-line {
        fill: none;
        stroke: var(--accent, var(--sky));
        stroke-width: 2;
        stroke-linecap: round;
        stroke-linejoin: round;
      }
      .jh-group {
        margin-bottom: 18px;
      }
      .jh-group:last-child {
        margin-bottom: 0;
      }
      .jh-group-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }
      .jh-group-title {
        font-size: 0.84rem;
        font-weight: 600;
        color: var(--ink-dim);
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }
      .jh-group-link {
        font-size: 0.8rem;
        color: var(--accent, var(--sky));
        background: none;
        border: none;
        padding: 0;
        cursor: pointer;
        text-decoration: underline;
        font-family: inherit;
      }
      .jh-group-link:hover {
        filter: brightness(1.15);
      }
      .jh-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .jh-item {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
        gap: 12px;
        font-size: 0.88rem;
        min-width: 0;
        line-height: 1.35;
      }
      .jh-item-main {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
        min-width: 0;
      }
      .jh-item-sub {
        font-size: 0.78rem;
        color: var(--ink-dim);
        margin-top: 2px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .jh-item-time {
        font-size: 0.76rem;
        color: var(--ink-faint);
        white-space: nowrap;
        flex-shrink: 0;
      }
      .jh-empty {
        color: var(--ink-faint);
        font-size: 0.85rem;
        font-style: italic;
        padding: 2px 0;
      }
      .jh-error {
        color: var(--ink-faint);
        font-size: 0.85rem;
        padding: 4px 0;
      }
    `;
    document.head.appendChild(style);
  }

  function getDialColor(pct) {
    if (pct >= 90) return "var(--rose)";
    if (pct >= 75) return "var(--peach)";
    return "var(--accent, var(--sky))";
  }

  function formatShortTime(val) {
    if (!val) return "";
    try {
      const d = typeof val === "number" ? new Date(val < 1e11 ? val * 1000 : val) : new Date(val);
      if (isNaN(d.getTime())) return String(val);
      const diffMin = Math.floor((Date.now() - d.getTime()) / 60000);
      if (diffMin < 1) return "just now";
      if (diffMin < 60) return `${diffMin}m ago`;
      const diffHr = Math.floor(diffMin / 60);
      if (diffHr < 24) return `${diffHr}h ago`;
      const diffDays = Math.floor(diffHr / 24);
      if (diffDays < 7) return `${diffDays}d ago`;
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    } catch (_) {
      return String(val);
    }
  }

  function renderDial(id, pct, label, displayText, isError) {
    if (isError) {
      return `
        <div class="jh-card jh-dial-card" id="${id}-card">
          <svg class="jh-dial-svg" viewBox="0 0 140 140">
            <circle class="jh-dial-bg" cx="70" cy="70" r="54" />
            <text class="jh-dial-err" x="70" y="70">Couldn't load</text>
          </svg>
          <div class="jh-dial-lbl">${label}</div>
        </div>
      `;
    }
    const clamped = Math.max(0, Math.min(100, pct));
    const offset = (CIRC * (1 - clamped / 100)).toFixed(2);
    const color = getDialColor(clamped);
    return `
      <div class="jh-card jh-dial-card" id="${id}-card">
        <svg class="jh-dial-svg" viewBox="0 0 140 140">
          <circle class="jh-dial-bg" cx="70" cy="70" r="54" />
          <circle class="jh-dial-meter" id="${id}-meter" cx="70" cy="70" r="54"
            stroke="${color}"
            stroke-dasharray="${CIRC}"
            stroke-dashoffset="${offset}"
            transform="rotate(-90 70 70)" />
          <text class="jh-dial-val" id="${id}-val" x="70" y="70">${displayText}</text>
        </svg>
        <div class="jh-dial-lbl">${label}</div>
      </div>
    `;
  }

  function updateDialInPlace(id, pct, displayText) {
    const clamped = Math.max(0, Math.min(100, pct));
    const offset = (CIRC * (1 - clamped / 100)).toFixed(2);
    const color = getDialColor(clamped);
    const meter = document.getElementById(`${id}-meter`);
    const val = document.getElementById(`${id}-val`);
    if (meter) {
      meter.setAttribute("stroke-dashoffset", offset);
      meter.setAttribute("stroke", color);
    }
    if (val) {
      val.textContent = displayText;
    }
  }

  function getGraphPoints(samples, w = 300, h = 80) {
    if (!samples || samples.length === 0) return { poly: "", area: "" };
    const padTop = 4;
    const padBottom = 4;
    const usableH = h - padTop - padBottom;
    const pts = samples.map((v, i) => {
      const x = samples.length === 1 ? w / 2 : i * (w / (samples.length - 1));
      const clamped = Math.max(0, Math.min(100, v));
      const y = padTop + usableH * (1 - clamped / 100);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    let poly = pts.join(" ");
    if (samples.length === 1) {
      const singleY = pts[0].split(",")[1];
      poly = `0,${singleY} ${w},${singleY}`;
    }
    const area = `0,${h} ${poly} ${w},${h}`;
    return { poly, area };
  }

  function updateVitalsInPlace(vit) {
    if (!vit) return;
    if (vit.cpu && typeof vit.cpu.pct === "number") {
      updateDialInPlace("jh-dial-cpu", vit.cpu.pct, `${Math.round(vit.cpu.pct)}%`);
    }
    if (vit.mem && typeof vit.mem.pct === "number") {
      updateDialInPlace("jh-dial-mem", vit.mem.pct, `${Math.round(vit.mem.pct)}%`);
    }
    if (vit.disk && typeof vit.disk.pct === "number") {
      updateDialInPlace("jh-dial-disk", vit.disk.pct, `${Math.round(vit.disk.pct)}%`);
    }
    const poly = document.getElementById("jh-cpu-line");
    const area = document.getElementById("jh-cpu-area");
    const cur = document.getElementById("jh-cpu-cur");
    const { poly: polyPts, area: areaPts } = getGraphPoints(cpuSamples);
    if (poly) poly.setAttribute("points", polyPts);
    if (area) area.setAttribute("points", areaPts);
    if (cur && cpuSamples.length > 0) {
      cur.textContent = `${Math.round(cpuSamples[cpuSamples.length - 1])}%`;
    }
  }

  window.jhNav = (tabName) => {
    const btn = document.querySelector(`.dock button[data-view="${tabName}"]`);
    if (btn) btn.click();
  };

  views.home = async () => {
    ensureStyles();

    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }

    const [vitalsRes, statusRes, reelsRes, hubRes, activityRes] = await Promise.allSettled([
      api("vitals"),
      api("status"),
      api("reels"),
      fetch("hub.json").then((r) => {
        if (!r.ok) throw new Error("HTTP error");
        return r.json();
      }),
      api("activity?limit=60"),
    ]);

    const vitals = vitalsRes.status === "fulfilled" ? vitalsRes.value : null;
    const status = statusRes.status === "fulfilled" ? statusRes.value : null;
    const reels = reelsRes.status === "fulfilled" ? reelsRes.value : null;
    const hub = hubRes.status === "fulfilled" ? hubRes.value : null;
    const activity = activityRes.status === "fulfilled" ? activityRes.value : null;

    if (vitals && vitals.cpu && typeof vitals.cpu.pct === "number") {
      cpuSamples.push(vitals.cpu.pct);
      if (cpuSamples.length > 60) cpuSamples.shift();
    }

    pollInterval = setInterval(async () => {
      if (typeof state !== "undefined" && state.view !== "home") {
        clearInterval(pollInterval);
        pollInterval = null;
        return;
      }
      try {
        const vit = await api("vitals");
        if (vit && vit.cpu && typeof vit.cpu.pct === "number") {
          cpuSamples.push(vit.cpu.pct);
          if (cpuSamples.length > 60) cpuSamples.shift();
        }
        updateVitalsInPlace(vit);
      } catch (_) {}
    }, 5000);

    const cpuPct = vitals?.cpu?.pct ?? 0;
    const memPct = vitals?.mem?.pct ?? 0;
    const diskPct = vitals?.disk?.pct ?? 0;

    let aiCount = 0;
    let aiPct = 0;
    if (status && Array.isArray(status.ollama_models)) {
      aiCount = status.ollama_models.length;
      aiPct = Math.min(aiCount / 5, 1) * 100;
    }

    const dialsHtml = [
      renderDial("jh-dial-cpu", cpuPct, "CPU", `${Math.round(cpuPct)}%`, !vitals),
      renderDial("jh-dial-mem", memPct, "Memory", `${Math.round(memPct)}%`, !vitals),
      renderDial("jh-dial-disk", diskPct, "Disk", `${Math.round(diskPct)}%`, !vitals),
      renderDial("jh-dial-ai", aiPct, "AI models", `${aiCount}`, !status),
    ].join("");

    let graphBodyHtml = "";
    if (!vitals && cpuSamples.length === 0) {
      graphBodyHtml = `<div class="jh-error">Couldn't load</div>`;
    } else {
      const { poly, area } = getGraphPoints(cpuSamples);
      const currentPct = cpuSamples.length > 0 ? `${Math.round(cpuSamples[cpuSamples.length - 1])}%` : "—";
      graphBodyHtml = `
        <div class="jh-card-title">
          <span>CPU History</span>
          <span class="jh-count" id="jh-cpu-cur">${esc(currentPct)}</span>
        </div>
        <div class="jh-graph-wrap">
          <svg class="jh-graph-svg" viewBox="0 0 300 80" preserveAspectRatio="none">
            <line class="jh-graph-grid" x1="0" y1="20" x2="300" y2="20" />
            <line class="jh-graph-grid" x1="0" y1="40" x2="300" y2="40" />
            <line class="jh-graph-grid" x1="0" y1="60" x2="300" y2="60" />
            <polygon class="jh-graph-area" id="jh-cpu-area" points="${area}" />
            <polyline class="jh-graph-line" id="jh-cpu-line" points="${poly}" />
          </svg>
        </div>
      `;
    }

    let projectsHtml = "";
    if (!hub) {
      projectsHtml = `<div class="jh-error">Couldn't load</div>`;
    } else {
      const reviewProjects = (Array.isArray(hub.projects) ? hub.projects : []).filter(
        (p) => p && p.lane === "review"
      );
      if (reviewProjects.length === 0) {
        projectsHtml = `<div class="jh-empty">Nothing waiting</div>`;
      } else {
        const items = reviewProjects
          .map((p) => {
            const nextItem = Array.isArray(p.next) && p.next.length > 0 ? p.next[0] : null;
            return `
              <li class="jh-item">
                <div class="jh-item-main">
                  <div>${esc(p.name || "Untitled project")}</div>
                  ${nextItem ? `<div class="jh-item-sub">${esc(nextItem)}</div>` : ""}
                </div>
              </li>
            `;
          })
          .join("");
        projectsHtml = `<ul class="jh-list">${items}</ul>`;
      }
    }

    let reelsHtml = "";
    if (!reels) {
      reelsHtml = `<div class="jh-error">Couldn't load</div>`;
    } else {
      const reviewReels = (Array.isArray(reels) ? reels : []).filter(
        (r) => r && r.verdict === "review"
      );
      if (reviewReels.length === 0) {
        reelsHtml = `<div class="jh-empty">Nothing waiting</div>`;
      } else {
        const sorted = [...reviewReels].sort((a, b) => {
          const ta = new Date(a.added).getTime() || 0;
          const tb = new Date(b.added).getTime() || 0;
          return tb - ta;
        });
        const newest = sorted.slice(0, 5);
        const items = newest
          .map((r) => {
            // Reels shared in DMs have no known uploader ("?"): show the topic alone.
            const rawUp = r.uploader && r.uploader !== "?" ? String(r.uploader) : "";
            const topic = r.topic || "Untitled";
            const uploader = rawUp ? (rawUp.startsWith("@") ? rawUp : `@${rawUp}`) : "Reel";
            return `
              <li class="jh-item">
                <div class="jh-item-main">${esc(uploader)} — ${esc(topic)}</div>
                ${r.added ? `<span class="jh-item-time">${esc(formatShortTime(r.added))}</span>` : ""}
              </li>
            `;
          })
          .join("");
        reelsHtml = `<ul class="jh-list">${items}</ul>`;
      }
    }

    let notesHtml = "";
    if (!activity) {
      notesHtml = `<div class="jh-error">Couldn't load</div>`;
    } else {
      const notes = (Array.isArray(activity) ? activity : []).filter(
        (a) => a && a.kind === "note"
      );
      const recentNotes = notes.slice(0, 5);
      if (recentNotes.length === 0) {
        notesHtml = `<div class="jh-empty">Nothing waiting</div>`;
      } else {
        const items = recentNotes
          .map((n) => `
            <li class="jh-item">
              <div class="jh-item-main">${esc(n.detail || "")}</div>
              <span class="jh-item-time">${esc(formatShortTime(n.ts))}</span>
            </li>
          `)
          .join("");
        notesHtml = `<ul class="jh-list">${items}</ul>`;
      }
    }

    let recentActivityHtml = "";
    if (!activity) {
      recentActivityHtml = `<div class="jh-error">Couldn't load</div>`;
    } else {
      const nonNotes = (Array.isArray(activity) ? activity : [])
        .filter((a) => a && a.kind !== "note")
        .slice(0, 8);
      if (nonNotes.length === 0) {
        recentActivityHtml = `<div class="jh-empty">No recent activity</div>`;
      } else {
        const items = nonNotes
          .map((a) => `
            <li class="jh-item">
              <span class="jh-item-time" style="width: 68px;">${esc(formatShortTime(a.ts))}</span>
              <div class="jh-item-main" title="${esc(a.detail || "")}">${esc(a.detail || "")}</div>
            </li>
          `)
          .join("");
        recentActivityHtml = `<ul class="jh-list">${items}</ul>`;
      }
    }

    const hubReviewCount = (hub && Array.isArray(hub.projects))
      ? hub.projects.filter((p) => p && p.lane === "review").length
      : 0;
    const reelsReviewCount = (reels && Array.isArray(reels))
      ? reels.filter((r) => r && r.verdict === "review").length
      : 0;
    const notesCount = (activity && Array.isArray(activity))
      ? activity.filter((a) => a && a.kind === "note").length
      : 0;

    return `
      <div class="jh-wrap">
        <header class="jh-header">
          <h1>Home</h1>
          <p>Your Mac at a glance, and what's waiting on you.</p>
        </header>

        <section class="jh-dials">
          ${dialsHtml}
        </section>

        <section class="jh-main-grid">
          <div class="jh-col">
            <div class="jh-card">
              ${graphBodyHtml}
            </div>

            <div class="jh-card">
              <div class="jh-card-title">
                <span>Recent activity</span>
              </div>
              ${recentActivityHtml}
            </div>
          </div>

          <div class="jh-col">
            <div class="jh-card">
              <div class="jh-card-title">
                <span>Waiting on you</span>
              </div>

              <div class="jh-group">
                <div class="jh-group-header">
                  <span class="jh-group-title">Projects to check (${hubReviewCount})</span>
                  <button type="button" class="jh-group-link" onclick="jhNav('hub')">Open Hub</button>
                </div>
                ${projectsHtml}
              </div>

              <div class="jh-group">
                <div class="jh-group-header">
                  <span class="jh-group-title">Reels to watch (${reelsReviewCount})</span>
                  <button type="button" class="jh-group-link" onclick="jhNav('reels')">Open Reels</button>
                </div>
                ${reelsHtml}
              </div>

              <div class="jh-group">
                <div class="jh-group-header">
                  <span class="jh-group-title">Your notes (${notesCount})</span>
                </div>
                ${notesHtml}
              </div>
            </div>
          </div>
        </section>
      </div>
    `;
  };
})();
