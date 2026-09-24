/* Theme switcher + per-tab view attribute — drafted by Gemini Flash, reviewed by Claude. */
(() => {
  const THEMES = ['stark', 'midnight', 'ember', 'forest', 'paper', 'mono'];

  let activeTheme = 'stark';
  try {
    const saved = localStorage.getItem('cc.theme');
    if (saved && THEMES.includes(saved)) {
      activeTheme = saved;
    }
  } catch (_) {}

  document.documentElement.dataset.theme = activeTheme;

  const init = () => {
    const topbar = document.querySelector('.topbar');
    if (topbar) {
      const select = document.createElement('select');
      select.className = 'theme-pick';
      select.setAttribute('aria-label', 'Theme');

      THEMES.forEach((theme) => {
        const option = document.createElement('option');
        option.value = theme;
        option.textContent = theme.charAt(0).toUpperCase() + theme.slice(1);
        if (theme === activeTheme) {
          option.selected = true;
        }
        select.appendChild(option);
      });

      select.addEventListener('change', (e) => {
        const selected = e.target.value;
        document.documentElement.dataset.theme = selected;
        try {
          localStorage.setItem('cc.theme', selected);
        } catch (_) {}
      });

      topbar.appendChild(select);
    }

    const syncView = () => {
      const activeBtn = document.querySelector('.dock button.active');
      if (activeBtn && activeBtn.dataset.view) {
        document.body.dataset.view = activeBtn.dataset.view;
      }
    };

    syncView();

    const dock = document.querySelector('.dock');
    if (dock) {
      const observer = new MutationObserver(syncView);
      observer.observe(dock, {
        attributes: true,
        subtree: true,
        attributeFilter: ['class'],
      });
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
