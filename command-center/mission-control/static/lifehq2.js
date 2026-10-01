/* Life HQ: "From your Mac" — reminders + calendar read through Hammond (backlog P2).
   Hammond already holds the macOS permissions, so Command Center asks it over
   the socket instead of prompting for its own. Read-only: Hammond refuses any
   other tool name from a remote client. Each pull is also logged (kind
   "lifehq_sync") so Claude and Hammond can see what was on Nate's plate. */
(() => {
  const oldLife = views.life;

  function askHammond(tools) {
    return new Promise(async (resolve) => {
      const out = {};
      // Hammond's Remote server accepts one connection per token and drops the
      // older one when a second connects — opening our own socket here used to
      // silently disconnect an active Chat tab session. Reuse that live socket
      // instead of competing with it; only open a private one as a fallback
      // when Chat isn't connected (found 2026-09-30: visiting Life HQ dropped
      // Chat's connection every time).
      const shared = (typeof handsSocket !== "undefined") ? handsSocket : null;
      if (shared && shared.readyState === WebSocket.OPEN) {
        const token = state.handsToken;
        const finish = () => { clearTimeout(timer); shared.removeEventListener("message", onMsg); resolve(out); };
        const timer = setTimeout(() => { out._error = out._error || "Hammond didn't answer in time"; finish(); }, 20000);
        const onMsg = (ev) => {
          let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
          if (m.type === "toolResult" && m.tool) out[m.tool] = m.text || "";
          if (m.type === "error") out._error = m.text || "error";
          if (tools.every((t) => t in out) || out._error) finish();
        };
        shared.addEventListener("message", onMsg);
        tools.forEach((tool) => shared.send(JSON.stringify({ type: "message", text: "", token, tool })));
        return;
      }
      let token;
      try { token = (await apiOk("hands/token")).token; } catch (e) { return resolve({ _error: "no Hammond token" }); }
      let ws;
      try { ws = new WebSocket("ws://127.0.0.1:8787/agent"); } catch (e) { return resolve({ _error: "Hammond not reachable" }); }
      const done = () => { try { ws.close(); } catch (e) {} resolve(out); };
      const timer = setTimeout(() => { out._error = out._error || "Hammond didn't answer in time"; done(); }, 20000);
      ws.onerror = () => { out._error = "Hammond isn't running"; clearTimeout(timer); done(); };
      ws.onopen = () => tools.forEach((tool) => ws.send(JSON.stringify({ type: "message", text: "", token, tool })));
      ws.onmessage = (ev) => {
        let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
        if (m.type === "toolResult" && m.tool) out[m.tool] = m.text || "";
        if (m.type === "error") out._error = m.text || "error";
        if (tools.every((t) => t in out) || out._error) { clearTimeout(timer); done(); }
      };
    });
  }

  const lines = (txt) => (txt || "").split("\n").map((l) => l.replace(/^- /, "").trim()).filter(Boolean);

  function listHtml(txt, emptyMsg, errMsg) {
    if (txt === undefined) return `<div class="empty">${esc(errMsg || "…")}</div>`;
    if (/^error:/i.test(txt)) {
      const perm = /-600|not allowed|access/i.test(txt);
      return `<div class="empty">${perm
        ? "Hammond needs permission: System Settings → Privacy &amp; Security → Calendars → turn on Hands AI."
        : esc(txt.slice(0, 160))}</div>`;
    }
    const items = lines(txt).filter((l) => !/^no (open reminders|events)/i.test(l));
    if (!items.length) return `<div class="empty">${esc(emptyMsg)}</div>`;
    return items.map((l) => `<div class="item"><div class="grow">${esc(l)}</div></div>`).join("");
  }

  async function pull() {
    const box = document.getElementById("lh2-box");
    if (!box) return;
    box.querySelector("#lh2-status").textContent = "Asking Hammond…";
    const r = await askHammond(["reminders_list", "calendar_today"]);
    if (!document.getElementById("lh2-box")) return;
    box.querySelector("#lh2-rem").innerHTML = listHtml(r.reminders_list, "No open reminders", r._error);
    box.querySelector("#lh2-cal").innerHTML = listHtml(r.calendar_today, "Nothing today or tomorrow", r._error);
    box.querySelector("#lh2-status").textContent = r._error
      ? r._error
      : "Updated " + new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    if (!r._error && r.reminders_list !== undefined) {
      const detail = "reminders: " + lines(r.reminders_list).join(" | ").slice(0, 900);
      try { await apiOk("activity/log", { kind: "lifehq_sync", detail }); } catch (e) {}
    }
  }

  views.life = async () => {
    const rest = oldLife ? await oldLife() : "";
    setTimeout(pull, 0);
    return `
    <div class="card glass" id="lh2-box"><h2><span class="dot t-mint"></span>From your Mac</h2>
      <div class="sub">Your reminders and calendar, read through Hammond. <span id="lh2-status"></span>
        <button onclick="document.getElementById('lh2-box') && window.lh2Pull()" style="margin-left:8px">Refresh</button></div>
      <div class="grid2" style="margin-top:10px">
        <div><h3 style="margin:0 0 6px;font-size:13px">Reminders</h3><div class="list" id="lh2-rem"><div class="empty">…</div></div></div>
        <div><h3 style="margin:0 0 6px;font-size:13px">Today &amp; tomorrow</h3><div class="list" id="lh2-cal"><div class="empty">…</div></div></div>
      </div>
    </div>${rest}`;
  };
  window.lh2Pull = pull;
})();
