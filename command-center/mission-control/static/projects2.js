/* Projects pin board (backlog P2) — drafted by Gemini Flash via the pipeline, reviewed by Claude. */
(() => {
  const safeEsc = typeof esc === "function" ? esc : (s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c])));

  function injectStyles() {
    if (document.getElementById("pb-style")) return;
    const style = document.createElement("style");
    style.id = "pb-style";
    style.textContent = `
      .pb-wrap {
        padding: 24px;
        max-width: none;
        margin: 0 auto;
        color: var(--ink);
        font-family: inherit;
      }
      .pb-header {
        margin-bottom: 24px;
      }
      .pb-title {
        font-size: 28px;
        font-weight: 700;
        margin: 0 0 6px 0;
        color: var(--ink);
      }
      .pb-subtitle {
        font-size: 14px;
        color: var(--ink-dim);
        margin: 0;
      }
      .pb-filter-row {
        display: flex;
        gap: 8px;
        margin-bottom: 28px;
        flex-wrap: wrap;
      }
      .pb-chip {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: 9999px;
        padding: 6px 14px;
        font-size: 13px;
        color: var(--ink-dim);
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .pb-chip:hover {
        color: var(--ink);
        border-color: var(--ink-faint);
      }
      .pb-chip.pb-chip-active {
        background: color-mix(in srgb, var(--accent) 16%, transparent);
        color: var(--accent);
        border-color: var(--accent);
        font-weight: 600;
      }
      .pb-grid {
        columns: 330px; /* fill the window: as many columns as fit */
        column-gap: 22px;
      }
      
      @media (max-width: 760px) {
        .pb-grid {
          column-count: 1;
        }
      }
      .pb-card {
        break-inside: avoid;
        margin-bottom: 24px;
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        padding: 22px 18px 16px;
        position: relative;
        box-shadow: 0 4px 16px color-mix(in srgb, var(--ink) 5%, transparent);
        transition: box-shadow 0.2s ease;
        display: flex;
        flex-direction: column;
        gap: 13px;
      }
      .pb-card:hover {
        box-shadow: 0 8px 24px color-mix(in srgb, var(--ink) 9%, transparent);
      }
      .pb-pin {
        position: absolute;
        top: -6px;
        left: 50%;
        transform: translateX(-50%);
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: var(--accent, var(--rose));
        box-shadow: 0 2px 4px color-mix(in srgb, var(--ink) 25%, transparent);
        z-index: 2;
      }
      .pb-card-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 8px;
      }
      .pb-card-name {
        font-weight: 700;
        font-size: 17px;
        color: var(--ink);
        margin: 0;
        line-height: 1.3;
        word-break: break-word;
      }
      .pb-active-badge {
        font-size: 10px;
        padding: 2px 7px;
        border-radius: 9999px;
        background: color-mix(in srgb, var(--mint) 18%, transparent);
        color: var(--mint);
        border: 1px solid color-mix(in srgb, var(--mint) 35%, transparent);
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        white-space: nowrap;
        flex-shrink: 0;
      }
      .pb-location-row {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--ink-dim);
        min-width: 0;
      }
      .pb-location-path {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        flex: 1;
      }
      .pb-btn-copy {
        background: transparent;
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        color: var(--ink-dim);
        font-size: 11px;
        padding: 2px 7px;
        cursor: pointer;
        line-height: 1.2;
        transition: all 0.15s ease;
        flex-shrink: 0;
      }
      .pb-btn-copy:hover {
        color: var(--ink);
        border-color: var(--ink-faint);
      }
      .pb-btn-copy.pb-copied {
        color: var(--mint);
        border-color: var(--mint);
      }
      .pb-meta-line {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 12px;
        color: var(--ink-dim);
      }
      .pb-branch {
        font-weight: 500;
        color: var(--ink);
      }
      .pb-commit-when {
        color: var(--ink-faint);
      }
      .pb-lane-row {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        flex-wrap: wrap;
      }
      .pb-lane-label {
        color: var(--ink-faint);
      }
      .pb-select {
        background: var(--glass);
        color: var(--ink);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        padding: 3px 8px;
        font-size: 12px;
        cursor: pointer;
        outline: none;
      }
      .pb-select:focus {
        border-color: var(--accent);
      }
      .pb-lane-error {
        color: var(--rose);
        font-size: 11px;
        width: 100%;
      }
      .pb-checklist {
        background: color-mix(in srgb, var(--glass) 50%, transparent);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .pb-progress-wrap {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .pb-progress-label {
        display: flex;
        justify-content: space-between;
        font-size: 11px;
        font-weight: 600;
        color: var(--ink-dim);
      }
      .pb-progress-label span {
        color: var(--ink);
      }
      .pb-progress-bar {
        height: 5px;
        background: color-mix(in srgb, var(--ink-faint) 20%, transparent);
        border-radius: 9999px;
        overflow: hidden;
      }
      .pb-progress-fill {
        height: 100%;
        background: var(--mint);
        border-radius: 9999px;
        transition: width 0.25s ease;
      }
      .pb-check-items {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .pb-check-item {
        display: flex;
        align-items: center;
        gap: 7px;
        font-size: 12px;
      }
      .pb-check-item.pb-met {
        color: var(--ink);
      }
      .pb-check-item.pb-miss {
        color: var(--ink-dim);
      }
      .pb-check-icon {
        width: 13px;
        text-align: center;
        font-weight: 700;
      }
      .pb-check-item.pb-met .pb-check-icon {
        color: var(--mint);
      }
      .pb-check-item.pb-miss .pb-check-icon {
        color: var(--ink-faint);
      }
      .pb-notes-wrap {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .pb-notes-list {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .pb-note {
        background: color-mix(in srgb, var(--peach) 22%, transparent);
        border: 1px solid color-mix(in srgb, var(--peach) 35%, transparent);
        border-radius: var(--r);
        padding: 7px 10px;
        font-size: 12px;
        line-height: 1.4;
        color: var(--ink);
        word-break: break-word;
      }
      .pb-note-input {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        padding: 6px 10px;
        font-size: 12px;
        color: var(--ink);
        outline: none;
        width: 100%;
        box-sizing: border-box;
      }
      .pb-note-input::placeholder {
        color: var(--ink-faint);
      }
      .pb-note-input:focus {
        border-color: var(--accent);
      }
    `;
    document.head.appendChild(style);
  }

  function hashStr(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) {
      h = Math.imul(31, h) + str.charCodeAt(i) | 0;
    }
    return h;
  }

  function getCardRotation(name) {
    const h = Math.abs(hashStr(name || ""));
    return (((h % 241) - 120) / 100).toFixed(2);
  }

  function matchHubCard(proj, hubProjects) {
    if (!Array.isArray(hubProjects) || !proj) return null;
    const pName = (proj.name || "").trim().toLowerCase();
    const cleanPath = (proj.path || "").trim().replace(/[\/\\]+$/, "");
    const parts = cleanPath.split(/[\/\\]/);
    const lastFolder = (parts[parts.length - 1] || "").toLowerCase();

    return hubProjects.find(hp => {
      if (!hp) return false;
      const hpName = (hp.name || "").trim().toLowerCase();
      if (pName && hpName === pName) return true;
      if (hp.path && lastFolder) {
        const hpPath = hp.path.trim().replace(/[\/\\]+$/, "").toLowerCase();
        if (hpPath.endsWith("/" + lastFolder) || hpPath.endsWith("\\" + lastFolder) || hpPath === lastFolder) {
          return true;
        }
      }
      return false;
    }) || null;
  }

  window.pbCopyPath = async (btn) => {
    const fullPath = btn.dataset.path || "";
    if (!fullPath) return;
    try {
      await navigator.clipboard.writeText(fullPath);
      const prev = btn.textContent;
      btn.textContent = "copied";
      btn.classList.add("pb-copied");
      setTimeout(() => {
        btn.textContent = prev;
        btn.classList.remove("pb-copied");
      }, 1500);
    } catch (e) {
      console.error("Clipboard copy failed", e);
    }
  };

  window.pbMoveLane = async (selectEl, errId) => {
    const errEl = document.getElementById(errId);
    if (errEl) errEl.textContent = "";
    const hubName = selectEl.dataset.hubName;
    const prevLane = selectEl.dataset.currentLane;
    const nextLane = selectEl.value;
    try {
      const res = await api("hub/move", { name: hubName, lane: nextLane });
      if (res && res.error) throw new Error(res.error);
      selectEl.dataset.currentLane = nextLane;
    } catch (err) {
      selectEl.value = prevLane;
      if (errEl) {
        errEl.textContent = (err && err.message) ? err.message : "Move refused";
      }
    }
  };

  window.pbAddNote = async (event, input) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    const projName = input.dataset.projName;
    const cardId = input.dataset.cardId;

    input.disabled = true;
    try {
      await api("activity/log", { kind: "pnote", detail: `${projName}::${text}` });
      input.value = "";
      const card = document.getElementById(cardId);
      if (card) {
        const list = card.querySelector(".pb-notes-list");
        if (list) {
          const noteEl = document.createElement("div");
          noteEl.className = "pb-note";
          noteEl.textContent = text;
          list.prepend(noteEl);
          while (list.children.length > 3) {
            list.lastElementChild.remove();
          }
        }
      }
    } catch (e) {
      console.error("Failed to add note", e);
    } finally {
      input.disabled = false;
      input.focus();
    }
  };

  window.pbFilter = (btn, mode) => {
    document.querySelectorAll(".pb-chip").forEach(c => c.classList.remove("pb-chip-active"));
    btn.classList.add("pb-chip-active");
    const cards = document.querySelectorAll(".pb-card");
    cards.forEach(card => {
      const met = parseInt(card.dataset.met || "0", 10);
      const unsaved = card.dataset.unsaved === "1";
      const notReviewed = card.dataset.notReviewed === "1";
      let show = true;
      if (mode === "needs-work") show = met < 5;
      else if (mode === "unsaved") show = unsaved;
      else if (mode === "not-reviewed") show = notReviewed;
      card.style.display = show ? "" : "none";
    });
  };

  views.projects = async () => {
    injectStyles();

    let rawProjects = [];
    let reviews = {};
    let hubData = { lanes: [], projects: [] };
    let activity = [];

    const pProjects = (async () => {
      try {
        const res = await api("projects");
        if (Array.isArray(res)) rawProjects = res;
      } catch (e) {
        console.error("Error loading projects", e);
      }
    })();

    const pReviews = (async () => {
      try {
        const res = await api("review/latest");
        if (res && typeof res === "object") reviews = res;
      } catch (e) {
        reviews = {};
      }
    })();

    const pHub = (async () => {
      try {
        const res = await fetch("hub.json");
        if (res.ok) hubData = await res.json();
      } catch (e) {
        console.error("Error loading hub.json", e);
      }
    })();

    const pActivity = (async () => {
      try {
        const res = await api("activity?limit=200");
        if (Array.isArray(res)) activity = res;
      } catch (e) {
        console.error("Error loading activity", e);
      }
    })();

    await Promise.all([pProjects, pReviews, pHub, pActivity]);

    const notesByProject = {};
    if (Array.isArray(activity)) {
      const sortedActivity = [...activity].sort((a, b) => new Date(b.ts || 0) - new Date(a.ts || 0));
      for (const item of sortedActivity) {
        if (item && item.kind === "pnote" && typeof item.detail === "string") {
          const sep = item.detail.indexOf("::");
          if (sep !== -1) {
            const pName = item.detail.slice(0, sep).trim().toLowerCase();
            const noteText = item.detail.slice(sep + 2).trim();
            if (!notesByProject[pName]) notesByProject[pName] = [];
            if (notesByProject[pName].length < 3) {
              notesByProject[pName].push(noteText);
            }
          }
        }
      }
    }

    const projects = [...rawProjects].sort((a, b) => {
      const aAct = a.active_session ? 1 : 0;
      const bAct = b.active_session ? 1 : 0;
      if (aAct !== bAct) return bAct - aAct;
      const aTouch = a.last_touched ? new Date(a.last_touched).getTime() : 0;
      const bTouch = b.last_touched ? new Date(b.last_touched).getTime() : 0;
      return bTouch - aTouch;
    });

    const cardsHtml = projects.map((proj, idx) => {
      const cardId = `pb-card-${idx}`;
      const rot = getCardRotation(proj.name);
      const rawPath = proj.path || "";
      const shortPath = rawPath.replace(/^\/Users\/[^\/]+/, "~");

      const cleanPath = rawPath.trim().replace(/[\/\\]+$/, "");
      const folderName = cleanPath.split(/[\/\\]/).pop() || proj.name || "";
      const rev = reviews[folderName] || reviews[proj.name] || null;

      const uncommittedCount = Array.isArray(proj.uncommitted) ? proj.uncommitted.length : 0;
      const gitMet = uncommittedCount === 0;
      const gitText = gitMet ? "Saved in git" : `${uncommittedCount} unsaved ${uncommittedCount === 1 ? "file" : "files"}`;

      let pushMet = false;
      let pushText = "No GitHub remote";
      if (!proj.remote) {
        pushMet = false;
        pushText = "No GitHub remote";
      } else if (proj.unpushed_count === 0 || proj.unpushed_count === undefined || proj.unpushed_count === null) {
        pushMet = true;
        pushText = "Pushed to GitHub";
      } else {
        pushMet = false;
        pushText = `${proj.unpushed_count} unpushed`;
      }

      const testsMet = Boolean(proj.has_tests);
      const testsText = "Has tests";

      const readmeMet = Boolean(proj.has_readme);
      const readmeText = "Has a README";

      let revMet = false;
      let revText = "Not reviewed yet";
      if (rev) {
        const v = String(rev.verdict || "").trim().toLowerCase();
        const findingsCount = Array.isArray(rev.findings)
          ? rev.findings.length
          : (typeof rev.findings === "number" ? rev.findings : 0);

        if (v.startsWith("clean")) {
          revMet = true;
          revText = "Reviewed clean";
        } else if (findingsCount > 0) {
          revMet = false;
          revText = `${findingsCount} ${findingsCount === 1 ? "issue" : "issues"} found`;
        } else {
          revMet = false;
          revText = "Not reviewed yet";
        }
      }

      const checklist = [
        { met: gitMet, text: gitText },
        { met: pushMet, text: pushText },
        { met: testsMet, text: testsText },
        { met: readmeMet, text: readmeText },
        { met: revMet, text: revText }
      ];
      const metCount = checklist.filter(item => item.met).length;
      const pct = (metCount / 5) * 100;

      const hubCard = matchHubCard(proj, hubData.projects);
      let laneHtml = "";
      if (hubCard && Array.isArray(hubData.lanes) && hubData.lanes.length > 0) {
        const laneOpts = hubData.lanes.map(l =>
          `<option value="${safeEsc(l.id)}" ${l.id === hubCard.lane ? "selected" : ""}>${safeEsc(l.name)}</option>`
        ).join("");
        laneHtml = `
          <div class="pb-lane-row">
            <span class="pb-lane-label">Status</span>
            <select class="pb-select" data-hub-name="${safeEsc(hubCard.name)}" data-current-lane="${safeEsc(hubCard.lane)}" onchange="pbMoveLane(this, 'pb-err-${idx}')">
              ${laneOpts}
            </select>
            <div id="pb-err-${idx}" class="pb-lane-error"></div>
          </div>
        `;
      }

      const projNotes = notesByProject[(proj.name || "").trim().toLowerCase()] || [];

      return `
        <div class="pb-card" id="${cardId}"
             data-met="${metCount}"
             data-unsaved="${uncommittedCount > 0 ? "1" : "0"}"
             data-not-reviewed="${revText === "Not reviewed yet" ? "1" : "0"}"
             style="transform: rotate(${rot}deg);"
        >
          <div class="pb-pin"></div>
          
          <div class="pb-card-top">
            <h2 class="pb-card-name">${safeEsc(proj.name)}</h2>
            ${proj.active_session ? `<span class="pb-active-badge">active</span>` : ""}
          </div>

          <div class="pb-location-row">
            <span class="pb-location-path" title="${safeEsc(rawPath)}">${safeEsc(shortPath)}</span>
            <button type="button" class="pb-btn-copy" data-path="${safeEsc(rawPath)}" onclick="pbCopyPath(this)" title="Copy path">copy</button>
          </div>

          <div class="pb-meta-line">
            ${proj.branch ? `<span class="pb-branch">${safeEsc(proj.branch)}</span>` : ""}
            ${proj.last_commit && proj.last_commit.when ? `<span class="pb-commit-when">${safeEsc(proj.last_commit.when)}</span>` : ""}
          </div>

          ${laneHtml}

          <div class="pb-checklist">
            <div class="pb-progress-wrap">
              <div class="pb-progress-label">
                <span>To be perfect</span>
                <span>${metCount} of 5</span>
              </div>
              <div class="pb-progress-bar">
                <div class="pb-progress-fill" style="width: ${pct}%;"></div>
              </div>
            </div>
            <ul class="pb-check-items">
              ${checklist.map(item => `
                <li class="pb-check-item ${item.met ? "pb-met" : "pb-miss"}">
                  <span class="pb-check-icon">${item.met ? "✓" : "○"}</span>
                  <span>${safeEsc(item.text)}</span>
                </li>
              `).join("")}
            </ul>
          </div>

          <div class="pb-notes-wrap">
            <div class="pb-notes-list">
              ${projNotes.map(n => `<div class="pb-note">${safeEsc(n)}</div>`).join("")}
            </div>
            <input type="text" class="pb-note-input" placeholder="Add a note…" data-card-id="${cardId}" data-proj-name="${safeEsc(proj.name)}" onkeydown="pbAddNote(event, this)" />
          </div>
        </div>
      `;
    }).join("");

    return `
      <div class="pb-wrap">
        <div class="pb-header">
          <h1 class="pb-title">Projects</h1>
          <p class="pb-subtitle">Every project, where it lives, and what's left before it's perfect.</p>
        </div>

        <div class="pb-filter-row">
          <button type="button" class="pb-chip pb-chip-active" onclick="pbFilter(this, 'all')">All</button>
          <button type="button" class="pb-chip" onclick="pbFilter(this, 'needs-work')">Needs work (&lt;5 met)</button>
          <button type="button" class="pb-chip" onclick="pbFilter(this, 'unsaved')">Unsaved changes</button>
          <button type="button" class="pb-chip" onclick="pbFilter(this, 'not-reviewed')">Not reviewed</button>
        </div>

        <div class="pb-grid">
          ${cardsHtml}
        </div>
      </div>
    `;
  };
})();
