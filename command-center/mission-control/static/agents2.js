/* Agents group (backlog P2): Jobs / Team / Steps / Results explained in one line
   on each page, and Workflows folded into Tools. Plain English, no new behaviour. */
(() => {
  const AGENT_TABS = [
    ["term", "Jobs", "one agent does one task in the background"],
    ["swarm", "Team", "one big goal, split across agents working at the same time"],
    ["flows", "Steps", "a recipe: step 1's answer feeds step 2, and so on"],
    ["artifacts", "Results", "the reports and files those agents made"],
  ];
  const strip = (current) => `
    <div class="card glass ag2-strip" style="padding:10px 14px;display:flex;gap:18px;flex-wrap:wrap;align-items:center">
      ${AGENT_TABS.map(([v, name, what]) => `
        <span style="opacity:${v === current ? 1 : 0.6}">
          <a href="#" onclick="event.preventDefault();document.querySelector('.dock button[data-view=&quot;${v}&quot;]').click()"
             style="color:inherit;font-weight:${v === current ? 700 : 500}">${name}</a> — ${what}</span>`).join("")}
    </div>`;
  for (const [v] of AGENT_TABS) {
    const orig = views[v];
    if (orig) views[v] = async (...a) => strip(v) + (await orig.apply(views, a));
  }
  const tools = views.tools, workflows = views.workflows;
  if (tools && workflows) {
    views.tools = async (...a) => (await tools.apply(views, a)) + (await workflows.apply(views, a));
  }
})();
