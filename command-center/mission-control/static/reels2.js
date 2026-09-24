/* Reels + AgentDrop merged (backlog P2) — drafted by Gemini Flash via the pipeline, reviewed by Claude. */
const oldReels = views.reels, oldDrop = views.agentdrop;

(() => {
  let reelsData = [];
  let currentFilter = 'review';
  let searchQuery = '';
  let autoMode = false;
  let autoIndex = 0;
  let isPolling = false;
  let pollInterval = null;
  const expandedLogs = new Set();
  const cardErrors = new Map();

  function ensureStyles() {
    if (document.getElementById('rv2-style')) return;
    const style = document.createElement('style');
    style.id = 'rv2-style';
    style.textContent = `
      .rv2-wrap { color: var(--ink); display: flex; flex-direction: column; gap: 18px; width: 100%; box-sizing: border-box; }
      .rv2-header { display: flex; flex-direction: column; gap: 4px; }
      .rv2-header h2 { margin: 0; font-size: 1.25rem; font-weight: 600; line-height: 1.3; }
      .rv2-counts { font-size: 0.88rem; opacity: 0.75; font-weight: 500; }
      .rv2-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; }
      .rv2-filters { display: flex; flex-wrap: wrap; gap: 6px; }
      .rv2-toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
      .rv2-chip { background: var(--glass); border: 1px solid var(--glass-brd); color: var(--ink); padding: 5px 12px; border-radius: 20px; font-size: 0.82rem; cursor: pointer; transition: border-color 0.15s, background 0.15s; }
      .rv2-chip:hover { border-color: var(--accent); }
      .rv2-chip.active { background: var(--accent); color: #fff; border-color: var(--accent); }
      .rv2-search { background: var(--glass); border: 1px solid var(--glass-brd); color: var(--ink); padding: 6px 12px; border-radius: 8px; font-size: 0.82rem; min-width: 180px; }
      .rv2-search:focus { outline: none; border-color: var(--accent); }
      .rv2-btn { background: var(--glass); border: 1px solid var(--glass-brd); color: var(--ink); padding: 5px 10px; border-radius: 7px; font-size: 0.82rem; cursor: pointer; transition: all 0.15s; font-weight: 500; display: inline-flex; align-items: center; justify-content: center; gap: 4px; }
      .rv2-btn:hover { border-color: var(--accent); }
      .rv2-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }
      .rv2-btn-sm { padding: 3px 8px; font-size: 0.78rem; }
      .rv2-btn-accent { background: var(--accent); color: #fff; border-color: var(--accent); }
      .rv2-btn-mint { background: var(--mint); color: #000; border-color: var(--mint); }
      .rv2-auto-panel { background: var(--glass); border: 1px solid var(--accent); border-radius: 14px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
      .rv2-auto-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 0.9rem; }
      .rv2-auto-body { display: grid; grid-template-columns: 260px 1fr; gap: 16px; align-items: start; }
      @media (max-width: 640px) { .rv2-auto-body { grid-template-columns: 1fr; } }
      .rv2-auto-video { width: 100%; aspect-ratio: 9/16; max-height: 420px; border-radius: 10px; background: #000; object-fit: contain; }
      .rv2-auto-info { display: flex; flex-direction: column; gap: 10px; }
      .rv2-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; width: 100%; }
      .rv2-card { background: var(--glass); border: 1px solid var(--glass-brd); border-radius: 14px; padding: 12px; display: flex; flex-direction: column; gap: 8px; box-sizing: border-box; }
      .rv2-media { position: relative; aspect-ratio: 9/16; max-height: 320px; border-radius: 10px; overflow: hidden; background: rgba(0,0,0,0.2); display: flex; align-items: center; justify-content: center; }
      .rv2-thumb-wrap { width: 100%; height: 100%; position: relative; cursor: pointer; }
      .rv2-thumb { width: 100%; height: 100%; object-fit: cover; display: block; }
      .rv2-play-btn { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 34px; color: #fff; background: rgba(0,0,0,0.3); transition: transform 0.15s, background 0.15s; }
      .rv2-thumb-wrap:hover .rv2-play-btn { background: rgba(0,0,0,0.45); transform: scale(1.06); }
      .rv2-video { width: 100%; height: 100%; object-fit: contain; background: #000; border-radius: 10px; }
      .rv2-no-video { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 42px; font-weight: 700; opacity: 0.35; }
      .rv2-card-title { font-size: 0.92rem; font-weight: 600; line-height: 1.3; margin: 0; }
      .rv2-card-about { font-size: 0.82rem; opacity: 0.85; line-height: 1.4; margin: 0; flex-grow: 1; }
      .rv2-link { font-size: 0.78rem; color: var(--sky); text-decoration: none; display: inline-flex; align-items: center; gap: 3px; align-self: flex-start; }
      .rv2-link:hover { text-decoration: underline; }
      .rv2-build-area { display: flex; flex-direction: column; gap: 6px; padding-top: 8px; border-top: 1px solid var(--glass-brd); }
      .rv2-status-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
      .rv2-pill { font-size: 0.74rem; padding: 2px 7px; border-radius: 10px; font-weight: 600; display: inline-flex; align-items: center; border: 1px solid transparent; }
      .rv2-pill-not-built { background: rgba(128,128,128,0.15); color: var(--ink); }
      .rv2-pill-built-before { background: rgba(100,200,255,0.15); color: var(--sky); border-color: rgba(100,200,255,0.3); }
      .rv2-pill-building { background: rgba(255,180,50,0.2); color: #ffb432; border-color: rgba(255,180,50,0.4); animation: rv2-pulse 1.5s infinite; }
      .rv2-pill-ready { background: rgba(50,220,120,0.2); color: var(--mint); border-color: rgba(50,220,120,0.4); }
      .rv2-pill-failed { background: rgba(255,80,80,0.2); color: var(--rose); border-color: rgba(255,80,80,0.4); }
      .rv2-btn-group { display: flex; flex-wrap: wrap; gap: 6px; }
      .rv2-log { background: rgba(0,0,0,0.45); color: #ddd; font-family: monospace; font-size: 0.72rem; padding: 6px; border-radius: 6px; overflow-x: auto; max-height: 160px; margin: 2px 0 0; white-space: pre-wrap; word-break: break-all; }
      .rv2-error { color: var(--rose); font-size: 0.78rem; line-height: 1.3; }
      .rv2-verdict-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; font-size: 0.78rem; padding-top: 6px; border-top: 1px dashed var(--glass-brd); }
      .rv2-details { background: var(--glass); border: 1px solid var(--glass-brd); border-radius: 12px; padding: 10px 14px; }
      .rv2-details summary { font-weight: 600; cursor: pointer; user-select: none; font-size: 0.9rem; }
      .rv2-details[open] summary { margin-bottom: 10px; }
      .rv2-muted { opacity: 0.6; font-size: 0.82rem; margin: 4px 0; }
      @keyframes rv2-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
      @media (prefers-reduced-motion: reduce) {
        .rv2-pill-building, .rv2-btn, .rv2-play-btn { animation: none !important; transition: none !important; }
      }
    `;
    document.head.appendChild(style);
  }

  function isTabActive() {
    const tab = document.querySelector('.dock button[data-view="reels"]');
    return !!(tab && tab.classList.contains('active'));
  }

  function getTitle(r) {
    const uploader = (r.uploader || 'unknown').trim();
    const firstLine = (r.caption || '').split('\n')[0].trim();
    let clean = firstLine;
    if (uploader) {
      const rx = new RegExp(`^@?${uploader.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[:\\s-]*`, 'i');
      clean = clean.replace(rx, '').trim();
    }
    if (!clean) {
      // DM'd reels have no caption and uploader "?": use the transcript's first sentence instead.
      const t = (r.transcript || '').replace(/^\[[^\]]*\]\s*/, '').trim();
      const first = t.split(/(?<=[.!?])\s/)[0] || '';
      clean = first || (uploader && uploader !== '?' ? `Reel from @${uploader}` : 'Reel');
    }
    return clean.length > 70 ? clean.slice(0, 67) + '…' : clean;
  }

  function getAbout(r) {
    const text = (r.transcript || r.caption || '').trim();
    if (!text) return 'No description available';
    return text.length > 160 ? text.slice(0, 157) + '…' : text;
  }

  function getBuildPill(state) {
    switch (state) {
      case 'built_before': return { text: 'Built earlier', cls: 'built-before' };
      case 'queued':
      case 'running': return { text: 'Building…', cls: 'building' };
      case 'ready_for_nate': return { text: 'Ready for you to check', cls: 'ready' };
      case 'failed': return { text: 'Build stopped', cls: 'failed' };
      case 'not_built':
      default: return { text: 'Not built', cls: 'not-built' };
    }
  }

  function getCountsText() {
    const total = reelsData.length;
    const toReview = reelsData.filter(r => r.verdict === 'review' && r.build?.state !== 'running' && r.build?.state !== 'queued').length;
    const building = reelsData.filter(r => r.build?.state === 'running' || r.build?.state === 'queued').length;
    return `${total} reels · ${toReview} to review · ${building} building`;
  }

  function filterReels(list, filter, search) {
    const q = (search || '').toLowerCase().trim();
    return list.filter(r => {
      const state = r.build?.state || 'not_built';
      let pass = true;
      if (filter === 'review') pass = r.verdict === 'review' && state !== 'running' && state !== 'queued';
      else if (filter === 'building') pass = state === 'running' || state === 'queued';
      else if (filter === 'ready') pass = state === 'ready_for_nate';
      else if (filter === 'built') pass = r.verdict === 'built';
      if (!pass) return false;
      if (q) {
        const text = `${r.uploader || ''} ${r.caption || ''} ${r.transcript || ''}`.toLowerCase();
        if (!text.includes(q)) return false;
      }
      return true;
    });
  }

  function renderBuildArea(r) {
    const state = r.build?.state || 'not_built';
    const pill = getBuildPill(state);
    const hasError = cardErrors.has(r.id);
    const isLogOpen = expandedLogs.has(r.id);
    const canBuild = state === 'not_built' || state === 'failed';
    const canReview = state === 'ready_for_nate' || state === 'built_before';

    let logHtml = '';
    if (isLogOpen) {
      const step = esc(r.build?.step || 'None');
      const lines = (r.build?.log || []).slice(-12).map(l => esc(l)).join('\n') || 'No logs';
      logHtml = `<pre class="rv2-log"><b>Step:</b> ${step}\n${lines}</pre>`;
    }
    const errHtml = hasError ? `<div class="rv2-error">${esc(cardErrors.get(r.id))}</div>` : '';

    return `
      <div class="rv2-status-row">
        <span class="rv2-pill rv2-pill-${esc(pill.cls)}">${esc(pill.text)}</span>
        <button class="rv2-btn rv2-btn-sm" data-action="toggle-log" data-id="${esc(r.id)}">${isLogOpen ? 'Hide' : 'Progress'}</button>
      </div>
      ${errHtml}
      ${logHtml}
      ${(canBuild || canReview) ? `
        <div class="rv2-btn-group">
          ${canBuild ? `<button class="rv2-btn rv2-btn-sm rv2-btn-accent" data-action="build" data-id="${esc(r.id)}">Build</button>` : ''}
          ${canReview ? `
            <button class="rv2-btn rv2-btn-sm rv2-btn-mint" data-action="looks-good" data-id="${esc(r.id)}">Looks good ✓</button>
            <button class="rv2-btn rv2-btn-sm" data-action="needs-work" data-id="${esc(r.id)}">Needs work</button>
          ` : ''}
        </div>
      ` : ''}
    `;
  }

  function renderCard(r) {
    const title = getTitle(r);
    const about = getAbout(r);
    const hasIg = typeof r.url === 'string' && r.url.startsWith('https://');

    return `
      <div class="rv2-card" data-id="${esc(r.id)}">
        <div class="rv2-media" data-id="${esc(r.id)}">
          ${r.has_video ? `
            <div class="rv2-thumb-wrap" data-action="play" data-id="${esc(r.id)}">
              <img class="rv2-thumb" src="/api/reels/thumb?id=${encodeURIComponent(r.id)}" alt="Thumbnail" loading="lazy">
              <div class="rv2-play-btn">▶</div>
            </div>
          ` : `
            <div class="rv2-no-video"><span>${esc((r.uploader || '?').charAt(0).toUpperCase())}</span></div>
          `}
        </div>
        <h3 class="rv2-card-title">${esc(title)}</h3>
        <p class="rv2-card-about">${esc(about)}</p>
        ${hasIg ? `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" class="rv2-link">Open on Instagram ↗</a>` : ''}
        <div class="rv2-build-area" data-build-id="${esc(r.id)}">${renderBuildArea(r)}</div>
        <div class="rv2-verdict-row">
          <span>Verdict: <strong>${esc(r.verdict || 'none')}</strong></span>
          <button class="rv2-btn rv2-btn-sm" data-action="skip" data-id="${esc(r.id)}">Skip</button>
        </div>
      </div>
    `;
  }

  function renderAutoPanel() {
    if (!autoMode) return '';
    const reviewList = reelsData.filter(r => r.verdict === 'review' && r.build?.state !== 'running' && r.build?.state !== 'queued');
    if (reviewList.length === 0) {
      return `
        <div class="rv2-auto-panel">
          <div class="rv2-auto-header"><span>Auto Mode</span><button class="rv2-btn rv2-btn-sm" data-action="toggle-auto">Exit Auto</button></div>
          <p class="rv2-card-about">No reels left to review!</p>
        </div>
      `;
    }
    if (autoIndex >= reviewList.length) autoIndex = Math.max(0, reviewList.length - 1);
    const r = reviewList[autoIndex];
    const title = getTitle(r);
    const about = getAbout(r);
    const hasIg = typeof r.url === 'string' && r.url.startsWith('https://');

    return `
      <div class="rv2-auto-panel" data-id="${esc(r.id)}">
        <div class="rv2-auto-header">
          <span>Auto mode · ${autoIndex + 1} of ${reviewList.length}</span>
          <button class="rv2-btn rv2-btn-sm" data-action="toggle-auto">Exit Auto</button>
        </div>
        <div class="rv2-auto-body">
          <div>
            ${r.has_video ? `
              <video class="rv2-auto-video" controls playsinline src="/api/reels/video?id=${encodeURIComponent(r.id)}" poster="/api/reels/thumb?id=${encodeURIComponent(r.id)}"></video>
            ` : `
              <div class="rv2-media" style="max-height: 420px;"><div class="rv2-no-video"><span>${esc((r.uploader || '?').charAt(0).toUpperCase())}</span></div></div>
            `}
          </div>
          <div class="rv2-auto-info">
            <h3 style="margin:0; font-size:1.05rem;">${esc(title)}</h3>
            <p class="rv2-card-about">${esc(about)}</p>
            ${hasIg ? `<a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" class="rv2-link">Open on Instagram ↗</a>` : ''}
            <div class="rv2-build-area" data-build-id="${esc(r.id)}">${renderBuildArea(r)}</div>
            <div class="rv2-btn-group" style="margin-top:6px;">
              <button class="rv2-btn rv2-btn-accent" data-action="build" data-id="${esc(r.id)}">Build it</button>
              <button class="rv2-btn" data-action="skip" data-id="${esc(r.id)}">Skip</button>
              <button class="rv2-btn rv2-btn-mint" data-action="looks-good" data-id="${esc(r.id)}">Looks good ✓</button>
              <button class="rv2-btn" data-action="auto-next">Next →</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function updateCounts() {
    const el = document.getElementById('rv2-counts');
    if (el) el.textContent = getCountsText();
  }

  function updateBuildAreas(id) {
    const r = reelsData.find(x => x.id === id);
    if (!r) return;
    document.querySelectorAll('.rv2-build-area').forEach(area => {
      if (area.dataset.buildId === id) area.innerHTML = renderBuildArea(r);
    });
    updateCounts();
  }

  function refreshGrid() {
    const grid = document.getElementById('rv2-grid');
    if (!grid) return;
    const list = filterReels(reelsData, currentFilter, searchQuery);
    grid.innerHTML = list.length === 0 
      ? '<p style="grid-column: 1/-1; opacity:0.6; text-align:center; padding:30px 0;">No reels found.</p>'
      : list.map(renderCard).join('');
    updateCounts();
  }

  function refreshAutoPanel() {
    const container = document.getElementById('rv2-auto-wrap');
    if (container) container.innerHTML = renderAutoPanel();
  }

  function refreshAll() {
    refreshAutoPanel();
    refreshGrid();
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  function checkPolling() {
    const hasBuilding = reelsData.some(r => r.build?.state === 'running' || r.build?.state === 'queued');
    if (hasBuilding && isTabActive()) {
      startPolling();
    } else {
      stopPolling();
    }
  }

  function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(async () => {
      if (!isTabActive()) {
        stopPolling();
        return;
      }
      if (isPolling) return;
      isPolling = true;
      try {
        const fresh = await api("reels/board");
        if (Array.isArray(fresh)) {
          reelsData = fresh;
          document.querySelectorAll('.rv2-build-area').forEach(area => {
            const id = area.dataset.buildId;
            const r = reelsData.find(x => x.id === id);
            if (r) area.innerHTML = renderBuildArea(r);
          });
          updateCounts();
        }
        if (!reelsData.some(r => r.build?.state === 'running' || r.build?.state === 'queued')) {
          stopPolling();
        }
      } catch (err) {
        console.error('Reels poll error:', err);
      } finally {
        isPolling = false;
      }
    }, 4000);
  }

  async function handleAction(action, id) {
    const r = reelsData.find(x => x.id === id);
    if (!r) return;

    if (action === 'build') {
      try {
        cardErrors.delete(id);
        if (r.build) r.build.state = 'queued';
        else r.build = { state: 'queued' };
        updateBuildAreas(id);
        await api("reels/build", { id });
        checkPolling();
      } catch (err) {
        cardErrors.set(id, err.message || 'Build failed to start');
        if (r.build && r.build.state === 'queued') r.build.state = 'not_built';
        updateBuildAreas(id);
      }
    } else if (action === 'looks-good') {
      try {
        cardErrors.delete(id);
        await api("reels/update", { id, topic: r.topic, verdict: 'built', notes: r.notes });
        r.verdict = 'built';
        refreshAll();
      } catch (err) {
        cardErrors.set(id, err.message || 'Failed to update');
        updateBuildAreas(id);
      }
    } else if (action === 'needs-work') {
      try {
        cardErrors.delete(id);
        const newNotes = r.notes ? `${r.notes} · needs work` : 'needs work';
        await api("reels/update", { id, topic: r.topic, verdict: 'review', notes: newNotes });
        r.verdict = 'review';
        r.notes = newNotes;
        refreshAll();
      } catch (err) {
        cardErrors.set(id, err.message || 'Failed to update');
        updateBuildAreas(id);
      }
    } else if (action === 'skip') {
      try {
        cardErrors.delete(id);
        await api("reels/update", { id, topic: r.topic, verdict: 'skipped', notes: r.notes });
        r.verdict = 'skipped';
        refreshAll();
      } catch (err) {
        cardErrors.set(id, err.message || 'Failed to skip');
        updateBuildAreas(id);
      }
    }
  }

  function bindEvents(root) {
    root.addEventListener('click', async (e) => {
      const playBtn = e.target.closest('[data-action="play"]');
      if (playBtn) {
        const id = playBtn.dataset.id;
        const media = Array.from(root.querySelectorAll('.rv2-media')).find(m => m.dataset.id === id);
        if (media) {
          media.innerHTML = `<video class="rv2-video" controls autoplay playsinline src="/api/reels/video?id=${encodeURIComponent(id)}"></video>`;
        }
        return;
      }

      const logBtn = e.target.closest('[data-action="toggle-log"]');
      if (logBtn) {
        const id = logBtn.dataset.id;
        if (expandedLogs.has(id)) expandedLogs.delete(id);
        else expandedLogs.add(id);
        updateBuildAreas(id);
        return;
      }

      const chip = e.target.closest('[data-filter]');
      if (chip) {
        currentFilter = chip.dataset.filter;
        root.querySelectorAll('[data-filter]').forEach(c => {
          c.classList.toggle('active', c.dataset.filter === currentFilter);
        });
        refreshGrid();
        return;
      }

      const autoToggle = e.target.closest('[data-action="toggle-auto"]');
      if (autoToggle) {
        autoMode = !autoMode;
        autoIndex = 0;
        const btn = root.querySelector('.rv2-toolbar [data-action="toggle-auto"]');
        if (btn) btn.classList.toggle('active', autoMode);
        refreshAutoPanel();
        return;
      }

      const nextBtn = e.target.closest('[data-action="auto-next"]');
      if (nextBtn) {
        const reviewList = reelsData.filter(r => r.verdict === 'review' && r.build?.state !== 'running' && r.build?.state !== 'queued');
        if (reviewList.length > 0) autoIndex = (autoIndex + 1) % reviewList.length;
        refreshAutoPanel();
        return;
      }

      const actionBtn = e.target.closest('[data-action]');
      if (actionBtn) {
        const action = actionBtn.dataset.action;
        const id = actionBtn.dataset.id;
        if (id && ['build', 'looks-good', 'needs-work', 'skip'].includes(action)) {
          actionBtn.disabled = true;
          await handleAction(action, id);
          actionBtn.disabled = false;
          return;
        }
      }
    });

    const searchInput = root.querySelector('.rv2-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value;
        refreshGrid();
      });
    }
  }

  views.reels = async () => {
    ensureStyles();
    stopPolling();

    try {
      reelsData = await api("reels/board");
    } catch (err) {
      setTimeout(() => {
        const root = document.getElementById('rv2-root');
        if (root) {
          root.addEventListener('click', async (e) => {
            if (e.target.closest('[data-action="retry"]')) {
              const view = document.getElementById('view');
              if (view) {
                view.innerHTML = '<p class="rv2-muted" style="padding:20px;">Loading…</p>';
                view.innerHTML = await views.reels();
              }
            }
          });
        }
      }, 0);
      return `
        <div id="rv2-root" class="rv2-wrap">
          <div class="rv2-card" style="text-align:center; padding:32px;">
            <p style="font-size:1rem; margin-bottom:12px;">Can't load reels right now</p>
            <button class="rv2-btn rv2-btn-accent" data-action="retry">Retry</button>
          </div>
        </div>
      `;
    }

    let oldReelsHtml = '<p class="rv2-muted">Unavailable</p>';
    try {
      if (typeof oldReels === 'function') oldReelsHtml = await oldReels();
    } catch (e) {
      oldReelsHtml = `<p class="rv2-error">Error loading: ${esc(e.message || String(e))}</p>`;
    }

    let oldDropHtml = '<p class="rv2-muted">Unavailable</p>';
    try {
      if (typeof oldDrop === 'function') oldDropHtml = await oldDrop();
    } catch (e) {
      oldDropHtml = `<p class="rv2-error">Error loading: ${esc(e.message || String(e))}</p>`;
    }

    const initialCards = filterReels(reelsData, currentFilter, searchQuery).map(renderCard).join('');

    setTimeout(() => {
      const root = document.getElementById('rv2-root');
      if (root) {
        bindEvents(root);
        checkPolling();
      }
    }, 0);

    return `
      <div id="rv2-root" class="rv2-wrap">
        <div class="rv2-header">
          <h2>Every reel you've sent yourself. Watch it, build it, then you decide if it's done.</h2>
          <div id="rv2-counts" class="rv2-counts">${esc(getCountsText())}</div>
        </div>
        <div class="rv2-toolbar">
          <div class="rv2-filters">
            <button class="rv2-chip ${currentFilter === 'review' ? 'active' : ''}" data-filter="review">To review</button>
            <button class="rv2-chip ${currentFilter === 'building' ? 'active' : ''}" data-filter="building">Building</button>
            <button class="rv2-chip ${currentFilter === 'ready' ? 'active' : ''}" data-filter="ready">Ready for you</button>
            <button class="rv2-chip ${currentFilter === 'built' ? 'active' : ''}" data-filter="built">Built</button>
            <button class="rv2-chip ${currentFilter === 'all' ? 'active' : ''}" data-filter="all">All</button>
          </div>
          <div class="rv2-toolbar-right">
            <input type="search" class="rv2-search" placeholder="Search reels…" value="${esc(searchQuery)}">
            <button class="rv2-btn ${autoMode ? 'active' : ''}" data-action="toggle-auto">Auto</button>
          </div>
        </div>
        <div id="rv2-auto-wrap">${renderAutoPanel()}</div>
        <div id="rv2-grid" class="rv2-grid">
          ${initialCards || '<p style="grid-column: 1/-1; opacity:0.6; text-align:center; padding:30px 0;">No reels found.</p>'}
        </div>
        <details class="rv2-details">
          <summary>Add reels by link</summary>
          ${oldReelsHtml}
        </details>
        <details class="rv2-details">
          <summary>AgentDrop workspace files</summary>
          ${oldDropHtml}
        </details>
      </div>
    `;
  };
})();
