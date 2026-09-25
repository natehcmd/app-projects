/* Deep links: http://127.0.0.1:8450/#pipeline opens that tab (bookmarkable,
   and lets a headless screenshot land on a specific view). The app renders its
   default tab during startup, so keep asking until the tab really switched. */
(() => {
  const go = (tries = 12) => {
    const v = decodeURIComponent(location.hash.slice(1));
    const btn = v && [...document.querySelectorAll(".dock button[data-view]")].find((b) => b.dataset.view === v);
    if (!btn) return;
    if (!btn.classList.contains("active")) btn.click();
    if (tries > 0) setTimeout(() => { if (!btn.classList.contains("active")) go(tries - 1); }, 400);
  };
  window.addEventListener("hashchange", () => go());
  window.addEventListener("load", () => setTimeout(go, 300));
})();
