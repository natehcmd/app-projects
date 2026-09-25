/* Pipeline roots view (backlog P2) — drafted by Gemini Flash via the pipeline, reviewed by Claude. */
(() => {
  // 1. Inject Styles once into document.head
  if (!document.getElementById("roots-style")) {
    const style = document.createElement("style");
    style.id = "roots-style";
    style.textContent = `
      .rt-wrap {
        display: flex;
        flex-direction: column;
        width: 100%;
        box-sizing: border-box;
        color: var(--ink);
        padding: 10px 16px 16px 16px;
        gap: 8px;
        font-family: inherit;
      }
      .rt-header {
        font-size: 13px;
        color: var(--ink);
        opacity: 0.82;
        text-align: center;
        letter-spacing: 0.01em;
      }
      .rt-box {
        width: 100%;
        height: 70vh;
        min-height: 420px;
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 8px;
        position: relative;
        overflow: hidden;
      }
      .rt-svg {
        width: 100%;
        height: 100%;
        display: block;
      }
      .rt-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 12px;
        padding: 6px 12px;
        font-size: 12px;
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 6px;
        color: var(--ink);
      }
      .rt-footer-run { font-weight: 500; }
      .rt-footer-ledger {
        opacity: 0.85;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }
      .rt-msg {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        min-height: 240px;
        color: var(--ink);
        opacity: 0.7;
        font-size: 14px;
      }

      /* Root paths */
      .rt-path {
        fill: none;
        stroke: var(--ink);
        stroke-opacity: 0.16;
        stroke-linecap: round;
        transition: stroke 0.3s ease, stroke-opacity 0.3s ease;
      }
      .rt-path-nate { stroke-width: 6px; }
      .rt-path-tier2 { stroke-width: 3.5px; }
      .rt-path-tier3 { stroke-width: 2.2px; }
      .rt-extra-path { stroke-width: 1.5px; }
      .rt-path-lit {
        stroke: var(--accent) !important;
        stroke-opacity: 0.95 !important;
        filter: drop-shadow(0 0 5px var(--accent));
      }
      .rt-path-animated {
        stroke-dasharray: 8 6;
        animation: rt-flow 1.2s linear infinite;
      }
      @keyframes rt-flow {
        from { stroke-dashoffset: 28; }
        to { stroke-dashoffset: 0; }
      }
      @media (prefers-reduced-motion: reduce) {
        .rt-path-animated { animation: none !important; stroke-dasharray: none !important; }
        .rt-pulse-ring { animation: none !important; }
      }

      /* Nodes */
      .rt-node { transition: opacity 0.3s ease; }
      .rt-node.rt-dim { opacity: 0.35; }
      .rt-node.rt-lit { opacity: 1; }
      .rt-circle {
        fill: var(--glass);
        stroke: var(--glass-brd);
        stroke-width: 2px;
        transition: fill 0.3s ease, stroke 0.3s ease;
      }
      .rt-node.rt-lit .rt-circle {
        fill: var(--accent);
        stroke: var(--accent);
        filter: drop-shadow(0 0 10px var(--accent));
      }
      .rt-nate-circle {
        fill: var(--glass);
        stroke: var(--glass-brd);
        stroke-width: 2.5px;
      }
      .rt-nate-lit {
        stroke: var(--accent);
        filter: drop-shadow(0 0 8px var(--accent));
      }
      .rt-pulse-ring {
        fill: none;
        stroke: var(--sky, #38bdf8);
        stroke-width: 2px;
        animation: rt-pulse 2.2s cubic-bezier(0.2, 0.8, 0.4, 1) infinite;
        transform-origin: center;
      }
      @keyframes rt-pulse {
        0% { r: 18px; opacity: 0.9; }
        100% { r: 34px; opacity: 0; }
      }

      /* Text */
      .rt-row-lbl {
        font-size: 12px;
        font-weight: 600;
        fill: var(--ink);
        opacity: 0.65;
        letter-spacing: 0.02em;
      }
      .rt-row-sub {
        font-size: 10px;
        fill: var(--sky, #38bdf8);
        font-weight: 500;
      }
      .rt-node-title {
        font-size: 12px;
        font-weight: 500;
        fill: var(--ink);
        user-select: none;
      }
      .rt-nate-title {
        font-size: 13px;
        font-weight: 700;
        fill: var(--ink);
        user-select: none;
      }
      .rt-caption {
        font-size: 10.5px;
        fill: var(--accent);
        font-weight: 600;
      }
      .rt-badge {
        font-size: 10px;
        fill: var(--ink);
        opacity: 0.65;
      }
      .rt-raw { margin-top: 18px; }
      .rt-raw summary { cursor: pointer; opacity: .75; }
      .rt-extra-dot {
        fill: var(--accent);
        filter: drop-shadow(0 0 3px var(--accent));
      }
    `;
    document.head.appendChild(style);
  }

  // 2. Constants & Helpers
  const LABELS = {
    claude_adjudicator: "Claude (checks & decides)",
    agy_deep: "Gemini Deep",
    agy_pro: "Gemini Pro",
    agy_flash: "Gemini Flash",
    local_xl: "Local XL (30B)",
    local_big: "Local Big",
    local_small: "Local Small"
  };

  function fmtTokens(val) {
    const n = Number(val) || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1) + "k";
    return String(n);
  }

  function isTabActive() {
    const btn = document.querySelector('.dock button[data-view="pipeline"]');
    return Boolean(btn && btn.classList.contains("active"));
  }

  // 3. SVG Diagram Renderer
  function renderSvg(data) {
    const tierMap = {};
    if (Array.isArray(data.tiers)) {
      for (const t of data.tiers) tierMap[t.key] = t;
    }
    const claudeNode = (tierMap.claude?.nodes && tierMap.claude.nodes[0]) || { key: "claude_adjudicator", active: [], recent: 0 };
    const agyNodes = tierMap.agy?.nodes || [];
    const localNodes = tierMap.local?.nodes || [];
    const processes = data.processes || {};

    const isNodeLit = (n) => Boolean(n && Array.isArray(n.active) && n.active.length > 0);

    // Layout coordinates
    const natePos = { x: 480, y: 50, r: 24 };
    const claudePos = { x: 480, y: 160, r: 18, node: claudeNode };

    const agyPositions = agyNodes.map((node, i) => {
      const count = agyNodes.length;
      const x = count === 1 ? 480 : 250 + (i / (count - 1 || 1)) * 460;
      return { x, y: 310, r: 14, node };
    });

    const localPositions = localNodes.map((node, i) => {
      const count = localNodes.length;
      const x = count === 1 ? 480 : 250 + (i / (count - 1 || 1)) * 460;
      const parentPos = agyPositions.length > 0 ? agyPositions[i % agyPositions.length] : { x: 480, y: 310, r: 14 };
      return { x, y: 460, r: 14, node, parentPos };
    });

    // Ancestor lighting logic
    const localLitState = localPositions.map(lp => isNodeLit(lp.node));
    const agyBranchLit = agyPositions.map((ap) => {
      const selfLit = isNodeLit(ap.node);
      const childLit = localPositions.some((lp, idx) => lp.parentPos === ap && localLitState[idx]);
      return selfLit || childLit;
    });

    const claudeSelfLit = isNodeLit(claudeNode);
    const treeLitBelowClaude = agyBranchLit.some(Boolean);
    const claudePathLit = claudeSelfLit || treeLitBelowClaude;
    const nateLit = claudePathLit;

    let pathsSvg = "";

    // Nate -> Claude root
    const nateD = `M 480 74 C 475 102, 485 118, 480 142`;
    pathsSvg += `<path d="${nateD}" class="rt-path rt-path-nate ${claudePathLit ? 'rt-path-lit rt-path-animated' : ''}" />`;

    // Claude -> Agy roots
    agyPositions.forEach((ap, i) => {
      const lit = agyBranchLit[i];
      const startX = 480, startY = 206;  // below the Claude caption, not through it
      const endX = ap.x, endY = ap.y - ap.r;
      let d = "";
      if (Math.abs(endX - startX) < 5) {
        d = `M ${startX} ${startY} C 472 235, 488 260, ${endX} ${endY}`;
      } else {
        const cx1 = startX + (endX > startX ? 15 : -15);
        const cx2 = endX + (endX > startX ? -20 : 20);
        d = `M ${startX} ${startY} C ${cx1} 250, ${cx2} 255, ${endX} ${endY}`;
      }
      pathsSvg += `<path d="${d}" class="rt-path rt-path-tier2 ${lit ? 'rt-path-lit rt-path-animated' : ''}" />`;
    });

    // Agy -> Local roots
    localPositions.forEach((lp, i) => {
      const lit = localLitState[i];
      const startX = lp.parentPos.x, startY = lp.parentPos.y + lp.parentPos.r + 34;  // below the label + badge, not through them
      const endX = lp.x, endY = lp.y - lp.r;
      let d = "";
      if (Math.abs(endX - startX) < 5) {
        d = `M ${startX} ${startY} C ${startX - 8} 390, ${startX + 8} 415, ${endX} ${endY}`;
      } else {
        d = `M ${startX} ${startY} C ${startX} 395, ${endX} 405, ${endX} ${endY}`;
      }
      pathsSvg += `<path d="${d}" class="rt-path rt-path-tier3 ${lit ? 'rt-path-lit rt-path-animated' : ''}" />`;
    });

    // Sprouting extra active calls
    function renderSprouts(node, cx, cy, r) {
      if (!node.active || node.active.length <= 1) return "";
      const extras = Math.min(node.active.length - 1, 6);
      let res = "";
      for (let k = 0; k < extras; k++) {
        const spread = (k - (extras - 1) / 2) * 16;
        const ex = cx + spread;
        const ey = cy + r + 38 + (k % 2) * 8;
        const d = `M ${cx} ${cy + r} C ${cx + spread * 0.3} ${cy + r + 16}, ${ex} ${ey - 16}, ${ex} ${ey}`;
        res += `<path d="${d}" class="rt-path rt-extra-path rt-path-lit rt-path-animated" />`;
        res += `<circle cx="${ex}" cy="${ey}" r="2.5" class="rt-extra-dot" />`;
      }
      return res;
    }

    // Node renderer
    function renderNodeMarkup(x, y, r, node, defaultLabel) {
      const lit = isNodeLit(node) || (node.key === "claude_adjudicator" && claudePathLit);
      const label = LABELS[node.key] || defaultLabel || node.key || "";
      const isClaude = node.key === "claude_adjudicator";
      const claudeProcs = Number(processes.claude) || 0;

      let markup = `<g class="rt-node ${lit ? 'rt-lit' : 'rt-dim'}">`;
      if (isClaude && claudeProcs > 0) {
        markup += `<circle cx="${x}" cy="${y}" r="${r}" class="rt-pulse-ring" />`;
      }
      markup += `<circle cx="${x}" cy="${y}" r="${r}" class="rt-circle" />`;
      markup += `<text x="${x}" y="${y + r + 14}" class="rt-node-title" text-anchor="middle">${esc(label)}</text>`;

      if (lit && !isNodeLit(node)) {
        markup += `<text x="${x}" y="${y + r + 27}" class="rt-caption" text-anchor="middle">sent work down</text>`;
      } else if (lit) {
        const act = node.active[0] || {};
        const cap = `${esc(act.stage || "")} · ${esc(act.repo || "")} · ${esc(String(act.secs ?? 0))}s`;
        markup += `<text x="${x}" y="${y + r + 27}" class="rt-caption" text-anchor="middle">${cap}</text>`;
      } else if (isClaude && claudeProcs > 0) {
        markup += `<text x="${x}" y="${y + r + 27}" class="rt-row-sub" text-anchor="middle">Claude is open (${esc(String(claudeProcs))} processes)</text>`;
      } else if (Number(node.recent) > 0) {
        markup += `<text x="${x}" y="${y + r + 27}" class="rt-badge" text-anchor="middle">${esc(String(node.recent))} in last 10m</text>`;
      }

      markup += renderSprouts(node, x, y, r);
      markup += `</g>`;
      return markup;
    }

    // Row Labels
    const agyProcs = Number(processes.agy) || 0;
    const ollamaProcs = Number(processes.ollama) || 0;

    let rowsSvg = `
      <g>
        <text x="35" y="54" class="rt-row-lbl">You</text>
        <text x="35" y="164" class="rt-row-lbl">Claude</text>
        <text x="35" y="310" class="rt-row-lbl">Gemini (agy)</text>
        ${agyProcs > 0 ? `<text x="35" y="325" class="rt-row-sub">${esc(String(agyProcs))} agy sessions</text>` : ""}
        <text x="35" y="460" class="rt-row-lbl">Local — free</text>
        ${ollamaProcs > 0 ? `<text x="35" y="475" class="rt-row-sub">${esc(String(ollamaProcs))} ollama sessions</text>` : ""}
      </g>
    `;

    // Nate Node
    let nateMarkup = `
      <g class="rt-node ${nateLit ? 'rt-lit' : ''}">
        <circle cx="${natePos.x}" cy="${natePos.y}" r="${natePos.r}" class="rt-nate-circle ${nateLit ? 'rt-nate-lit' : ''}" />
        <text x="${natePos.x}" y="${natePos.y + 4}" class="rt-nate-title" text-anchor="middle">Nate</text>
      </g>
    `;

    let nodesSvg = nateMarkup;
    nodesSvg += renderNodeMarkup(claudePos.x, claudePos.y, claudePos.r, claudeNode, "Claude");
    agyPositions.forEach(p => { nodesSvg += renderNodeMarkup(p.x, p.y, p.r, p.node); });
    localPositions.forEach(p => { nodesSvg += renderNodeMarkup(p.x, p.y, p.r, p.node); });

    return `
      <svg class="rt-svg" viewBox="0 0 960 550" preserveAspectRatio="xMidYMid meet">
        ${rowsSvg}
        ${pathsSvg}
        ${nodesSvg}
      </svg>
    `;
  }

  // 4. Footer Renderer
  function renderFooter(data) {
    const run = data.run;
    let runStr = "No review running";
    if (run && !run.ended) {
      runStr = `Run: ${esc(run.id || "")} · ${esc(run.repo || "")}`;
    }

    const ledger = (run && run.ledger) || {};
    const ledgerNames = { ollama: "Ollama", agy_cli: "Gemini", claude_cli: "Claude" };
    const ledgerItems = [];
    for (const [k, v] of Object.entries(ledger)) {
      const name = ledgerNames[k] || k;
      ledgerItems.push(`${esc(name)}: ${esc(fmtTokens(v))}`);
    }

    return `
      <span class="rt-footer-run">${runStr}</span>
      ${ledgerItems.length > 0 ? `<span class="rt-footer-ledger">${ledgerItems.join(" · ")}</span>` : ""}
    `;
  }

  // 5. Polling & View Lifecycle
  let pollInterval = null;
  let fetching = false;

  async function updateData() {
    if (!isTabActive()) {
      if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
      }
      return;
    }
    if (fetching) return;
    fetching = true;

    try {
      const data = await apiOk("roots");
      const box = document.getElementById("rt-box");
      const footer = document.getElementById("rt-footer");
      if (box) box.innerHTML = renderSvg(data);
      if (footer) footer.innerHTML = renderFooter(data);
    } catch (_) {
      const box = document.getElementById("rt-box");
      if (box) {
        box.innerHTML = `<div class="rt-msg">Can't reach the pipeline data right now</div>`;
      }
    } finally {
      fetching = false;
    }
  }

  // 6. Global View Assignment
  const rawPipeline = views.pipeline;  // the old process list, kept under the diagram
  views.pipeline = async () => {
    setTimeout(() => {
      if (pollInterval) clearInterval(pollInterval);
      updateData();
      pollInterval = setInterval(updateData, 3000);
    }, 0);

    return `
      <div class="rt-wrap">
        <div class="rt-header">Work flows down from you. A glowing root means an AI is working on it right now.</div>
        <div class="rt-box" id="rt-box">
          <div class="rt-msg">Connecting to roots...</div>
        </div>
        <div class="rt-footer" id="rt-footer">
          <span class="rt-footer-run">Checking review status...</span>
        </div>
        ${rawPipeline ? `<details class="rt-raw"><summary>Every running AI process (details)</summary>${await rawPipeline()}</details>` : ""}
      </div>
    `;
  };
})();
