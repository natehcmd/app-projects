/* Apps (backlog P2) — drafted by Gemini Flash via the pipeline, reviewed by Claude. */
(() => {
  let currentFilter = 'All';
  let searchQuery = '';
  let appsCache = [];
  let eventsAttached = false;

  const CHIP_CATEGORIES = ['All', 'Apps', 'Tools', 'Skills', 'Web', 'Projects'];

  const FILTER_MAP = {
    Apps: ['Built App', 'Mac App'],
    Tools: ['Tool (command line)', 'Python'],
    Skills: ['Claude Skill'],
    Web: ['Web / Node', 'Website', 'Chrome Extension'],
    Projects: ['Project'],
  };

  function injectStyles() {
    if (document.getElementById('ap2-style')) return;
    const style = document.createElement('style');
    style.id = 'ap2-style';
    style.textContent = `
      .ap2-wrap {
        display: flex;
        flex-direction: column;
        gap: 20px;
        color: var(--ink);
        box-sizing: border-box;
      }
      .ap2-header {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .ap2-title {
        font-size: 26px;
        font-weight: 700;
        margin: 0;
        color: var(--ink);
        line-height: 1.2;
      }
      .ap2-desc {
        font-size: 14px;
        margin: 0;
        color: var(--ink-dim);
        line-height: 1.4;
      }
      .ap2-controls {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }
      .ap2-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .ap2-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        color: var(--ink-dim);
        font-size: 13px;
        padding: 6px 12px;
        cursor: pointer;
        user-select: none;
        transition: all 0.15s ease;
      }
      .ap2-chip:hover {
        color: var(--ink);
        border-color: var(--accent, var(--sky));
      }
      .ap2-chip.ap2-active {
        color: var(--ink);
        border-color: var(--accent, var(--sky));
        font-weight: 600;
      }
      .ap2-chip-count {
        font-size: 11px;
        color: var(--ink-faint);
      }
      .ap2-search {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        color: var(--ink);
        font-size: 13px;
        padding: 6px 12px;
        min-width: 220px;
        outline: none;
        transition: border-color 0.15s ease;
      }
      .ap2-search:focus {
        border-color: var(--accent, var(--sky));
      }
      .ap2-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
        gap: 16px;
      }
      .ap2-card {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-sizing: border-box;
      }
      .ap2-card-head {
        display: flex;
        gap: 12px;
        align-items: flex-start;
      }
      .ap2-icon-wrap {
        width: 64px;
        height: 64px;
        min-width: 64px;
        min-height: 64px;
        border-radius: var(--r);
        overflow: hidden;
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .ap2-icon {
        width: 64px;
        height: 64px;
        object-fit: cover;
        display: block;
      }
      .ap2-monogram {
        width: 64px;
        height: 64px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, var(--accent, var(--sky)), var(--lav));
        color: var(--ink);
        font-weight: 700;
        font-size: 20px;
        letter-spacing: 0.5px;
        user-select: none;
      }
      .ap2-card-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
        flex: 1;
      }
      .ap2-card-name {
        font-size: 15px;
        font-weight: 600;
        line-height: 1.25;
        color: var(--ink);
        word-break: break-word;
      }
      .ap2-badge {
        display: inline-block;
        font-size: 11px;
        padding: 2px 6px;
        border-radius: var(--r);
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        color: var(--ink-dim);
        align-self: flex-start;
      }
      .ap2-summary {
        font-size: 13px;
        line-height: 1.4;
        color: var(--ink-dim);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        text-overflow: ellipsis;
        min-height: 2.8em;
        margin: 0;
      }
      .ap2-meta-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        font-size: 12px;
      }
      .ap2-modified {
        color: var(--ink-faint);
        font-size: 12px;
        white-space: nowrap;
      }
      .ap2-status-container {
        display: flex;
        align-items: center;
      }
      .ap2-status-select {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        color: var(--ink);
        font-size: 12px;
        padding: 3px 6px;
        outline: none;
        cursor: pointer;
      }
      .ap2-status-select:focus {
        border-color: var(--accent, var(--sky));
      }
      .ap2-confirm-box {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 11px;
        color: var(--ink);
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        padding: 2px 6px;
      }
      .ap2-confirm-btn {
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        color: var(--ink);
        font-size: 11px;
        padding: 2px 6px;
        cursor: pointer;
      }
      .ap2-confirm-yes {
        border-color: var(--accent, var(--sky));
        font-weight: 600;
      }
      .ap2-btn-main {
        width: 100%;
        padding: 8px 12px;
        border-radius: var(--r);
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        color: var(--ink);
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .ap2-btn-main:hover {
        border-color: var(--accent, var(--sky));
      }
      .ap2-feedback {
        font-size: 12px;
        color: var(--ink-dim);
        text-align: center;
        min-height: 16px;
        line-height: 16px;
        word-break: break-word;
      }
      .ap2-empty {
        padding: 40px 20px;
        text-align: center;
        color: var(--ink-dim);
        font-size: 14px;
        background: var(--glass);
        border: 1px solid var(--glass-brd);
        border-radius: var(--r);
        grid-column: 1 / -1;
      }
    `;
    document.head.appendChild(style);
  }

  function getBadge(kind) {
    switch (kind) {
      case 'Built App':
      case 'Mac App':
        return 'Mac app';
      case 'Tool (command line)':
        return 'Command-line tool';
      case 'Claude Skill':
        return 'Claude skill';
      case 'Web / Node':
        return 'Web app';
      case 'Python':
        return 'Python script';
      case 'Project':
        return 'Project';
      case 'Website':
        return 'Website';
      case 'Chrome Extension':
        return 'Chrome extension';
      default:
        return kind || 'App';
    }
  }

  function getActionInfo(kind) {
    if (kind === 'Built App' || kind === 'Mac App') {
      return { label: 'Open app', type: 'open' };
    }
    if (kind === 'Tool (command line)') {
      return { label: 'Run in Tools', type: 'tools' };
    }
    if (kind === 'Claude Skill') {
      return { label: 'Show skill', type: 'open' };
    }
    if (kind === 'Web / Node' || kind === 'Website' || kind === 'Chrome Extension') {
      return { label: 'Open', type: 'open' };
    }
    return { label: 'Open folder', type: 'open' };
  }

  function getInitials(name) {
    if (!name) return '??';
    const words = name.replace(/[^\w\s]/g, '').trim().split(/\s+/).filter(Boolean);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    if (words.length === 1 && words[0].length >= 2) {
      return words[0].slice(0, 2).toUpperCase();
    }
    return (name.slice(0, 2) || '??').toUpperCase();
  }

  function formatModified(dateVal) {
    if (!dateVal) return '';
    try {
      const d = new Date(dateVal);
      if (!isNaN(d.getTime())) {
        const now = new Date();
        const opts = { month: 'short', day: 'numeric' };
        if (d.getFullYear() !== now.getFullYear()) {
          opts.year = 'numeric';
        }
        return esc(d.toLocaleDateString('en-US', opts));
      }
    } catch (_) {}
    return esc(String(dateVal));
  }

  function matchesCategory(app, filter) {
    if (filter === 'All') return true;
    const allowed = FILTER_MAP[filter];
    return allowed ? allowed.includes(app.kind) : true;
  }

  function getFilteredApps() {
    const q = searchQuery.toLowerCase().trim();
    return appsCache.filter(app => {
      if (!matchesCategory(app, currentFilter)) return false;
      if (!q) return true;
      const name = (app.name || '').toLowerCase();
      const summary = (app.summary || '').toLowerCase();
      return name.includes(q) || summary.includes(q);
    });
  }

  function renderCard(app) {
    const action = getActionInfo(app.kind);
    const initials = esc(getInitials(app.name));
    const iconHtml = app.appBundle
      ? `<div class="ap2-icon-wrap">
          <img class="ap2-icon" src="/api/apps/icon?id=${encodeURIComponent(app.id)}" alt="" onerror="this.style.display='none';if(this.nextElementSibling)this.nextElementSibling.style.display='flex';">
          <div class="ap2-monogram" style="display:none;">${initials}</div>
        </div>`
      : `<div class="ap2-icon-wrap">
          <div class="ap2-monogram">${initials}</div>
        </div>`;

    const statusOptions = (APP_STATUS_OPTIONS || []).map(opt => {
      const sel = app.status === opt ? 'selected' : '';
      return `<option value="${esc(opt)}" ${sel}>${esc(opt)}</option>`;
    }).join('');

    return `
      <div class="ap2-card" data-app-id="${esc(app.id)}">
        <div class="ap2-card-head">
          ${iconHtml}
          <div class="ap2-card-info">
            <div class="ap2-card-name" title="${esc(app.name || '')}">${esc(app.name || 'Untitled')}</div>
            <span class="ap2-badge">${esc(getBadge(app.kind))}</span>
          </div>
        </div>
        <p class="ap2-summary" title="${esc(app.summary || '')}">${esc(app.summary || '')}</p>
        <div class="ap2-meta-row">
          <span class="ap2-modified">${formatModified(app.modified)}</span>
          <div class="ap2-status-container">
            <select class="ap2-status-select" data-app-id="${esc(app.id)}" data-prev="${esc(app.status || '')}">
              <option value="" disabled ${!app.status ? 'selected' : ''}>Status</option>
              ${statusOptions}
            </select>
            <div class="ap2-confirm-box" style="display:none;">
              <span>Mark done?</span>
              <button type="button" class="ap2-confirm-btn ap2-confirm-yes">Yes</button>
              <button type="button" class="ap2-confirm-btn ap2-confirm-cancel">Cancel</button>
            </div>
          </div>
        </div>
        <button type="button" class="ap2-btn-main" data-app-id="${esc(app.id)}" data-kind="${esc(app.kind)}">${esc(action.label)}</button>
        <div class="ap2-feedback" aria-live="polite"></div>
      </div>
    `;
  }

  function updateGrid() {
    const grid = document.querySelector('.ap2-grid');
    if (!grid) return;
    const filtered = getFilteredApps();
    grid.innerHTML = filtered.length
      ? filtered.map(renderCard).join('')
      : `<div class="ap2-empty">No matching apps found.</div>`;
  }

  function bindEvents() {
    if (eventsAttached) return;
    eventsAttached = true;

    document.addEventListener('input', (e) => {
      if (e.target.matches('.ap2-search')) {
        searchQuery = e.target.value;
        updateGrid();
      }
    });

    document.addEventListener('click', async (e) => {
      const chip = e.target.closest('.ap2-chip');
      if (chip) {
        const filter = chip.dataset.filter;
        if (filter && filter !== currentFilter) {
          currentFilter = filter;
          document.querySelectorAll('.ap2-chip').forEach(c => {
            c.classList.toggle('ap2-active', c.dataset.filter === currentFilter);
          });
          updateGrid();
        }
        return;
      }

      const mainBtn = e.target.closest('.ap2-btn-main');
      if (mainBtn) {
        const card = mainBtn.closest('.ap2-card');
        const feedback = card?.querySelector('.ap2-feedback');
        const appId = mainBtn.dataset.appId;
        const kind = mainBtn.dataset.kind;
        const action = getActionInfo(kind);

        if (feedback) feedback.textContent = 'Opening…';

        if (action.type === 'tools') {
          const toolsBtn = document.querySelector('.dock button[data-view="tools"]');
          if (toolsBtn) {
            toolsBtn.click();
            if (feedback) {
              feedback.textContent = 'Opened';
              setTimeout(() => {
                if (feedback.textContent === 'Opened') feedback.textContent = '';
              }, 3000);
            }
          } else if (feedback) {
            feedback.textContent = 'Tools view not found';
          }
        } else {
          try {
            await api('apps/open', { id: appId });
            if (feedback) {
              feedback.textContent = 'Opened';
              setTimeout(() => {
                if (feedback.textContent === 'Opened') feedback.textContent = '';
              }, 3000);
            }
          } catch (err) {
            if (feedback) feedback.textContent = esc(err?.message || String(err));
          }
        }
        return;
      }

      const confirmYes = e.target.closest('.ap2-confirm-yes');
      if (confirmYes) {
        const card = confirmYes.closest('.ap2-card');
        const select = card?.querySelector('.ap2-status-select');
        const confirmBox = card?.querySelector('.ap2-confirm-box');
        const feedback = card?.querySelector('.ap2-feedback');
        const appId = select?.dataset.appId;

        try {
          await api('apps/status', { id: appId, status: 'Done' });
          if (select) {
            select.value = 'Done';
            select.dataset.prev = 'Done';
            select.style.display = '';
          }
          if (confirmBox) confirmBox.style.display = 'none';
          const app = appsCache.find(a => String(a.id) === String(appId));
          if (app) app.status = 'Done';
          if (feedback) {
            feedback.textContent = 'Marked done';
            setTimeout(() => {
              if (feedback.textContent === 'Marked done') feedback.textContent = '';
            }, 3000);
          }
        } catch (err) {
          if (select) {
            select.value = select.dataset.prev || '';
            select.style.display = '';
          }
          if (confirmBox) confirmBox.style.display = 'none';
          if (feedback) feedback.textContent = esc(err?.message || String(err));
        }
        return;
      }

      const confirmCancel = e.target.closest('.ap2-confirm-cancel');
      if (confirmCancel) {
        const card = confirmCancel.closest('.ap2-card');
        const select = card?.querySelector('.ap2-status-select');
        const confirmBox = card?.querySelector('.ap2-confirm-box');
        if (select) {
          select.value = select.dataset.prev || '';
          select.style.display = '';
        }
        if (confirmBox) confirmBox.style.display = 'none';
      }
    });

    document.addEventListener('change', async (e) => {
      const select = e.target.closest('.ap2-status-select');
      if (!select) return;

      const card = select.closest('.ap2-card');
      const confirmBox = card?.querySelector('.ap2-confirm-box');
      const feedback = card?.querySelector('.ap2-feedback');
      const appId = select.dataset.appId;
      const nextStatus = select.value;
      const prevStatus = select.dataset.prev || '';

      if (nextStatus === 'Done') {
        select.style.display = 'none';
        if (confirmBox) confirmBox.style.display = 'flex';
      } else {
        try {
          await api('apps/status', { id: appId, status: nextStatus });
          select.dataset.prev = nextStatus;
          const app = appsCache.find(a => String(a.id) === String(appId));
          if (app) app.status = nextStatus;
          if (feedback) {
            feedback.textContent = 'Status updated';
            setTimeout(() => {
              if (feedback.textContent === 'Status updated') feedback.textContent = '';
            }, 3000);
          }
        } catch (err) {
          select.value = prevStatus;
          if (feedback) feedback.textContent = esc(err?.message || String(err));
        }
      }
    });
  }

  views.apps = async () => {
    injectStyles();
    bindEvents();

    try {
      const data = await api('apps');
      appsCache = Array.isArray(data) ? data : [];
    } catch (err) {
      appsCache = [];
      return `
        <div class="ap2-wrap">
          <div class="ap2-header">
            <h1 class="ap2-title">Apps</h1>
            <p class="ap2-desc">Everything you've built or installed — what each one is, and one button to use it.</p>
          </div>
          <div class="ap2-empty">Failed to load apps: ${esc(err?.message || String(err))}</div>
        </div>
      `;
    }

    const counts = {};
    CHIP_CATEGORIES.forEach(cat => {
      if (cat === 'All') {
        counts[cat] = appsCache.length;
      } else {
        const allowed = FILTER_MAP[cat] || [];
        counts[cat] = appsCache.filter(a => allowed.includes(a.kind)).length;
      }
    });

    const chipsHtml = CHIP_CATEGORIES.map(cat => {
      const active = currentFilter === cat ? 'ap2-active' : '';
      return `<button type="button" class="ap2-chip ${active}" data-filter="${esc(cat)}">${esc(cat)} <span class="ap2-chip-count">${counts[cat] || 0}</span></button>`;
    }).join('');

    const filtered = getFilteredApps();
    const gridHtml = filtered.length
      ? filtered.map(renderCard).join('')
      : `<div class="ap2-empty">No matching apps found.</div>`;

    return `
      <div class="ap2-wrap">
        <div class="ap2-header">
          <h1 class="ap2-title">Apps</h1>
          <p class="ap2-desc">Everything you've built or installed — what each one is, and one button to use it.</p>
        </div>
        <div class="ap2-controls">
          <div class="ap2-chips">${chipsHtml}</div>
          <input type="search" class="ap2-search" placeholder="Search apps…" value="${esc(searchQuery)}" autocomplete="off" spellcheck="false">
        </div>
        <div class="ap2-grid">${gridHtml}</div>
      </div>
    `;
  };
})();
