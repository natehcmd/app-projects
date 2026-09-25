/* Hammond watch (backlog "found while working"): Hammond was found quietly not
   running. Poll /api/hands/status every 30s and, when it's down, show a small
   top-bar notice with a one-click "Open it". */
(() => {
  let pill = null;
  async function findHammond() {
    const apps = await apiOk("apps");
    return (Array.isArray(apps) ? apps : []).find((a) => /hands ai|hammond/i.test(a.name || "") && a.appBundle);
  }
  async function check() {
    let running = true;
    try { running = !!(await apiOk("hands/status")).running; } catch (e) { return; } // unknown: say nothing
    const bar = document.querySelector(".topbar");
    if (!bar) return;
    if (running) { if (pill) pill.hidden = true; return; }
    if (!pill) {
      pill = document.createElement("button");
      pill.type = "button";
      pill.className = "hw-pill";
      pill.style.cssText = "margin-left:10px;padding:4px 10px;border-radius:999px;border:1px solid var(--rose,#f87171);" +
        "background:transparent;color:var(--rose,#f87171);font-size:12px;cursor:pointer;flex:none";
      pill.onclick = async () => {
        pill.textContent = "Opening Hammond…";
        try {
          const app = await findHammond();
          if (!app) throw new Error("not found");
          await apiOk("apps/open", { id: app.id });
          setTimeout(check, 6000);
        } catch (e) { pill.textContent = "Couldn't open Hammond — open Hands AI yourself"; }
      };
      bar.appendChild(pill);
    }
    pill.textContent = "Hammond is off — open it";
    pill.hidden = false;
  }
  const start = () => { check(); setInterval(check, 30000); };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
