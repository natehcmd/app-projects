/* Deep links: http://127.0.0.1:8450/#pipeline opens that tab (bookmarkable,
   and lets a headless screenshot land on a specific view). */
(() => {
  const go = () => {
    const v = decodeURIComponent(location.hash.slice(1));
    const btn = v && [...document.querySelectorAll(".dock button[data-view]")].find((b) => b.dataset.view === v);
    if (btn) btn.click();
  };
  window.addEventListener("hashchange", go);
  window.addEventListener("load", () => setTimeout(go, 300));
})();
