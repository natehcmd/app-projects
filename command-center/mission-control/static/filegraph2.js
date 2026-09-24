/* FileGraph (backlog P2): fills the window, pans/zooms with trackpad or mouse,
   click a file to see what's in it and what it connects to, search to find one. */
(() => {
  const COLORS = { code: "var(--mint)", doc: "var(--peach)", other: "var(--sky)" };
  let sim = null;

  views.filegraph = async () => {
    setTimeout(init, 0);
    return `
    <div class="card glass" style="display:flex;flex-direction:column;height:calc(100vh - 120px);margin:0">
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:10px">
        <h2 style="margin:0"><span class="dot t-lav"></span>FileGraph</h2>
        <div class="sub" style="flex:1;min-width:200px">Your project files and how they connect. Swipe or drag to move, pinch or scroll to zoom, click a dot to see inside.</div>
        <input id="fg2-q" placeholder="find a file…" style="width:200px">
        <button class="act" id="btn_rebuild_fg" onclick="rebuildFileGraph(this)">Rebuild</button>
      </div>
      <div style="flex:1;display:flex;gap:12px;min-height:0">
        <div id="graph-container" style="flex:1;background:rgba(0,0,0,0.2);border-radius:12px;overflow:hidden;position:relative;touch-action:none">
          <svg id="d3graph" style="width:100%;height:100%;cursor:grab"></svg>
          <div class="meta" style="position:absolute;left:12px;bottom:10px;opacity:.7">
            <span style="color:var(--mint)">●</span> code &nbsp; <span style="color:var(--peach)">●</span> docs &nbsp; <span style="color:var(--sky)">●</span> other</div>
        </div>
        <div id="fg2-side" style="width:min(380px,40%);overflow:auto;display:none" class="card glass"></div>
      </div>
    </div>`;
  };

  async function showFile(id) {
    const side = document.getElementById("fg2-side");
    if (!side) return;
    side.style.display = "block";
    side.innerHTML = '<div class="empty">Loading…</div>';
    try {
      const f = await api("filegraph/file?id=" + encodeURIComponent(id));
      side.innerHTML = `
        <div style="display:flex;justify-content:space-between;gap:8px"><h3 style="margin:0;word-break:break-all">${esc(f.name)}</h3>
          <button onclick="document.getElementById('fg2-side').style.display='none'">✕</button></div>
        <div class="meta" style="word-break:break-all;margin:4px 0 8px">${esc(f.path)}</div>
        <div class="meta">${esc(f.kind)} · ${esc(String(Math.round((f.size || 0) / 1024)))} KB · changed ${esc(f.modified)}</div>
        ${f.links.length ? `<div style="margin-top:10px"><b style="font-size:12px">Connected to</b>
          ${f.links.map((l) => `<div class="item" style="cursor:pointer;padding:4px 8px" data-id="${esc(String(l.id))}"
             onclick="fg2Show(this.dataset.id)">${l.dir === "in" ? "←" : "→"} ${esc(l.name)} <span class="meta">${esc(l.kind)}</span></div>`).join("")}</div>` : ""}
        <b style="font-size:12px;display:block;margin-top:10px">What's inside</b>
        <pre class="termout" style="white-space:pre-wrap;max-height:none">${f.preview ? esc(f.preview) : "(no text preview for this kind of file)"}</pre>`;
    } catch (e) {
      side.innerHTML = '<div class="empty">Couldn\'t read that file.</div>';
    }
  }
  window.fg2Show = showFile;

  async function init() {
    const svg = d3.select("#d3graph");
    if (svg.empty()) return;
    if (sim) sim.stop();
    const { width, height } = svg.node().getBoundingClientRect();
    let data;
    try { data = await api("filegraph/relations"); } catch (e) { data = { nodes: [], links: [] }; }
    if (!data.nodes.length) {
      d3.select("#graph-container").html("<div class='empty' style='padding:30px'>No graph yet — press Rebuild.</div>");
      return;
    }
    const degree = {};
    data.links.forEach((l) => { degree[l.source] = (degree[l.source] || 0) + 1; degree[l.target] = (degree[l.target] || 0) + 1; });
    const world = svg.append("g");
    const zoom = d3.zoom().scaleExtent([0.2, 6]).on("zoom", (ev) => {
      world.attr("transform", ev.transform);
      labels.attr("display", ev.transform.k > 1.6 ? null : "none");
    });
    svg.call(zoom);

    sim = d3.forceSimulation(data.nodes)
      .force("link", d3.forceLink(data.links).id((d) => d.id).distance(50))
      .force("charge", d3.forceManyBody().strength(-90))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("x", d3.forceX(width / 2).strength(0.04))
      .force("y", d3.forceY(height / 2).strength(0.04));

    const link = world.append("g").attr("stroke", "rgba(255,255,255,0.18)")
      .selectAll("line").data(data.links).join("line").attr("stroke-width", 1);
    const node = world.append("g").selectAll("circle").data(data.nodes).join("circle")
      .attr("r", (d) => 4 + Math.min(8, Math.sqrt(degree[d.id] || 1) * 1.5))
      .attr("fill", (d) => COLORS[d.group] || "var(--sky)")
      .attr("stroke", "rgba(0,0,0,.4)").style("cursor", "pointer")
      .on("click", (ev, d) => { ev.stopPropagation(); showFile(d.id); })
      .call(d3.drag()
        .on("start", (ev, d) => { if (!ev.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
        .on("end", (ev, d) => { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
    node.append("title").text((d) => d.name + "\n" + d.path);
    const labels = world.append("g").selectAll("text").data(data.nodes).join("text")
      .text((d) => d.name).attr("font-size", 7).attr("fill", "var(--ink)").attr("opacity", 0.8)
      .attr("dx", 8).attr("dy", 3).attr("display", "none").style("pointer-events", "none");

    sim.on("tick", () => {
      link.attr("x1", (d) => d.source.x).attr("y1", (d) => d.source.y).attr("x2", (d) => d.target.x).attr("y2", (d) => d.target.y);
      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      labels.attr("x", (d) => d.x).attr("y", (d) => d.y);
    });

    const q = document.getElementById("fg2-q");
    if (q) q.oninput = () => {
      const s = q.value.trim().toLowerCase();
      node.attr("opacity", (d) => (!s || d.name.toLowerCase().includes(s) ? 1 : 0.12));
      labels.attr("display", (d) => (s && d.name.toLowerCase().includes(s) ? null : "none"));
    };
  }
  window.initFileGraph = init;
})();
