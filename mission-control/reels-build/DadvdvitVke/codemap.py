#!/usr/bin/env python3
"""
codemap.py — "Understand-Anything"-style codebase mapper.

Walks a codebase, extracts files / functions / classes and the
import & call relationships between them, and emits:

  1. codemap.json  — the raw graph (nodes + edges) for scripting/analysis
  2. codemap.html  — a single self-contained, clickable HTML graph you can
                      open in a browser and explore (click a node to see
                      its connections; search box to jump to a file).

No third-party dependencies — pure Python 3 standard library
(ast, os, re, json) plus a small vanilla-JS force-directed layout
embedded directly in the generated HTML (no CDN, works fully offline).

This is a best-effort static-analysis tool, not a type-checker:
  - Python files are parsed with `ast`, so imports/functions/classes and
    intra-repo call sites are extracted reasonably reliably.
  - JS/TS/JSX/TSX files are scanned with regexes for import/require
    statements and top-level function/class/const-arrow declarations.
    This catches the common patterns but will miss dynamic imports,
    re-exports, decorators-as-indirection, etc. Honest limitation, same
    one the reel calls out: works great on real hand-written apps,
    thinner on heavily templated/generated code.

Usage:
    python3 codemap.py /path/to/repo
    python3 codemap.py /path/to/repo --out ./out --max-files 2000

Then open out/codemap.html in a browser.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field

DEFAULT_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".nuxt", "target", ".mypy_cache",
    ".pytest_cache", "coverage", ".idea", ".vscode", "vendor",
    ".terraform", ".tox", "site-packages",
}

PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SUPPORTED_EXT = PY_EXT | JS_EXT

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[\w*{}\s,]+\s+from\s+)?|require\()\s*['"]([^'"]+)['"]"""
)
JS_FUNC_RE = re.compile(
    r"""^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)"""
)
JS_ARROW_CONST_RE = re.compile(
    r"""^\s*(?:export\s+)?(?:default\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"""
)
JS_CLASS_RE = re.compile(
    r"""^\s*(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)"""
)


@dataclass
class FileNode:
    path: str            # repo-relative path
    ext: str
    loc: int
    functions: list = field(default_factory=list)   # list of names
    classes: list = field(default_factory=list)      # list of names
    imports: list = field(default_factory=list)      # raw import targets (strings)


def is_ignored(dirname: str) -> bool:
    return dirname in DEFAULT_IGNORE_DIRS or dirname.startswith(".")


def collect_files(root: str, max_files: int) -> list[str]:
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not is_ignored(d)]
        for fn in filenames:
            ext = os.path.splitext(fn)[1]
            if ext in SUPPORTED_EXT:
                files.append(os.path.join(dirpath, fn))
                if len(files) >= max_files:
                    return files
    return files


def parse_python(full_path: str, rel_path: str) -> FileNode:
    node = FileNode(path=rel_path, ext=".py", loc=0)
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
    except OSError:
        return node
    node.loc = src.count("\n") + 1
    try:
        tree = ast.parse(src, filename=rel_path)
    except SyntaxError:
        return node

    for item in ast.walk(tree):
        if isinstance(item, ast.FunctionDef) or isinstance(item, ast.AsyncFunctionDef):
            node.functions.append(item.name)
        elif isinstance(item, ast.ClassDef):
            node.classes.append(item.name)
        elif isinstance(item, ast.Import):
            for alias in item.names:
                node.imports.append(alias.name)
        elif isinstance(item, ast.ImportFrom):
            if item.module:
                node.imports.append(("." * (item.level or 0)) + item.module)
    return node


def parse_js(full_path: str, rel_path: str) -> FileNode:
    ext = os.path.splitext(rel_path)[1]
    node = FileNode(path=rel_path, ext=ext, loc=0)
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            src = f.read()
    except OSError:
        return node
    node.loc = src.count("\n") + 1

    for m in JS_IMPORT_RE.finditer(src):
        node.imports.append(m.group(1))

    for line in src.splitlines():
        m = JS_FUNC_RE.match(line)
        if m:
            node.functions.append(m.group(1))
            continue
        m = JS_ARROW_CONST_RE.match(line)
        if m:
            node.functions.append(m.group(1))
            continue
        m = JS_CLASS_RE.match(line)
        if m:
            node.classes.append(m.group(1))
    return node


def resolve_import_to_file(root: str, importer_rel: str, target: str,
                            all_files: set[str]) -> str | None:
    """Best-effort resolution of an import string to a repo-relative file path."""
    importer_dir = os.path.dirname(importer_rel)

    # Relative JS/TS import ("./foo", "../bar/baz")
    if target.startswith("."):
        candidate_base = os.path.normpath(os.path.join(importer_dir, target))
        for ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
            for suffix in ("", "/index"):
                candidate = candidate_base + suffix + ext
                candidate = candidate.replace("\\", "/")
                if candidate in all_files:
                    return candidate
        return None

    # Python dotted module path, e.g. "pkg.sub.mod" or ".sub" (level captured as leading dots)
    if target and (target[0].isalpha() or target[0] == "_"):
        # try as a path under repo root: pkg/sub/mod.py or pkg/sub/mod/__init__.py
        as_path = target.replace(".", "/")
        for cand in (as_path + ".py", as_path + "/__init__.py"):
            cand = cand.replace("\\", "/")
            if cand in all_files:
                return cand
    return None


def build_graph(root: str, max_files: int):
    files = collect_files(root, max_files)
    file_nodes: dict[str, FileNode] = {}

    for full_path in files:
        rel_path = os.path.relpath(full_path, root).replace("\\", "/")
        ext = os.path.splitext(rel_path)[1]
        if ext in PY_EXT:
            fn = parse_python(full_path, rel_path)
        else:
            fn = parse_js(full_path, rel_path)
        file_nodes[rel_path] = fn

    all_paths = set(file_nodes.keys())

    edges = []
    unresolved_external = set()
    for rel_path, fn in file_nodes.items():
        for target in fn.imports:
            resolved = resolve_import_to_file(root, rel_path, target, all_paths)
            if resolved and resolved != rel_path:
                edges.append({"from": rel_path, "to": resolved, "type": "import"})
            else:
                unresolved_external.add(target)

    nodes = []
    for rel_path, fn in sorted(file_nodes.items()):
        nodes.append({
            "id": rel_path,
            "ext": fn.ext,
            "loc": fn.loc,
            "functions": fn.functions,
            "classes": fn.classes,
            "num_connections": 0,  # filled below
        })

    conn_count: dict[str, int] = {}
    for e in edges:
        conn_count[e["from"]] = conn_count.get(e["from"], 0) + 1
        conn_count[e["to"]] = conn_count.get(e["to"], 0) + 1
    for n in nodes:
        n["num_connections"] = conn_count.get(n["id"], 0)

    total_functions = sum(len(fn.functions) for fn in file_nodes.values())
    total_classes = sum(len(fn.classes) for fn in file_nodes.values())

    summary = {
        "root": os.path.abspath(root),
        "num_files": len(nodes),
        "num_connections": len(edges),
        "num_functions": total_functions,
        "num_classes": total_classes,
        "num_external_deps": len(unresolved_external),
    }

    return {"summary": summary, "nodes": nodes, "edges": edges}


HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Codemap — {root_name}</title>
<style>
  :root { --bg:#0b0d12; --panel:#151822; --border:#262b3a; --text:#e6e8ee;
          --muted:#8b93a7; --accent:#7dd3fc; --accent2:#c4b5fd; --edge:#3a4054; }
  @media (prefers-color-scheme: light) {
    :root { --bg:#f6f7fb; --panel:#ffffff; --border:#e2e5ee; --text:#1a1d29;
            --muted:#5b6272; --accent:#0369a1; --accent2:#6d28d9; --edge:#c7ccdb; }
  }
  * { box-sizing: border-box; }
  html, body { margin:0; padding:0; background:var(--bg); color:var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    height:100%; overflow:hidden; }
  #app { display:flex; height:100vh; }
  #sidebar { width:320px; flex-shrink:0; border-right:1px solid var(--border);
    background:var(--panel); padding:16px; overflow-y:auto; }
  #sidebar h1 { font-size:16px; margin:0 0 4px; }
  #sidebar .sub { color:var(--muted); font-size:12px; margin-bottom:14px; }
  #search { width:100%; padding:8px 10px; border-radius:8px; border:1px solid var(--border);
    background:var(--bg); color:var(--text); font-size:13px; margin-bottom:12px; }
  .stat-row { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }
  .stat { background:var(--bg); border:1px solid var(--border); border-radius:8px;
    padding:8px 10px; font-size:11px; color:var(--muted); flex:1 1 40%; }
  .stat b { display:block; font-size:16px; color:var(--text); font-weight:600; }
  #detail { border-top:1px solid var(--border); padding-top:12px; margin-top:8px; }
  #detail h2 { font-size:14px; margin:0 0 6px; word-break:break-all; }
  #detail .meta { color:var(--muted); font-size:12px; margin-bottom:10px; }
  #detail ul { list-style:none; margin:0 0 10px; padding:0; }
  #detail li { font-size:12px; padding:2px 0; font-family: ui-monospace, monospace; }
  #detail .section-label { font-size:11px; text-transform:uppercase; letter-spacing:.04em;
    color:var(--accent); margin:10px 0 4px; }
  #canvas-wrap { flex:1; position:relative; }
  svg { width:100%; height:100%; display:block; cursor:grab; }
  svg:active { cursor:grabbing; }
  .edge { stroke:var(--edge); stroke-width:1; }
  .edge.hl { stroke:var(--accent); stroke-width:2; }
  .node circle { stroke:var(--border); stroke-width:1.5; cursor:pointer; }
  .node text { fill:var(--muted); font-size:9px; pointer-events:none; }
  .node.hl circle { stroke:var(--accent); stroke-width:2.5; }
  .node.dim { opacity:0.15; }
  #hint { position:absolute; bottom:10px; left:10px; font-size:11px; color:var(--muted);
    background:var(--panel); border:1px solid var(--border); padding:6px 10px; border-radius:8px; }
</style>
</head>
<body>
<div id="app">
  <div id="sidebar">
    <h1>Codemap</h1>
    <div class="sub">{root_name}</div>
    <input id="search" placeholder="Search files or functions...">
    <div class="stat-row" id="stats"></div>
    <div id="detail"><div class="meta">Click a node to inspect it.</div></div>
  </div>
  <div id="canvas-wrap">
    <svg id="svg"></svg>
    <div id="hint">Drag to pan &middot; scroll to zoom &middot; click a node</div>
  </div>
</div>
<script>
const GRAPH = {graph_json};
</script>
<script>
(function () {
  const nodesData = GRAPH.nodes;
  const edgesData = GRAPH.edges;
  const summary = GRAPH.summary;

  document.getElementById('stats').innerHTML = [
    ['Files', summary.num_files],
    ['Connections', summary.num_connections],
    ['Functions', summary.num_functions],
    ['Classes', summary.num_classes],
  ].map(([label, val]) =>
    `<div class="stat"><b>${val}</b>${label}</div>`
  ).join('');

  const svg = document.getElementById('svg');
  const NS = 'http://www.w3.org/2000/svg';
  const width = window.innerWidth - 320;
  const height = window.innerHeight;

  const byId = {};
  const nodes = nodesData.map((n, i) => {
    const angle = (i / nodesData.length) * Math.PI * 2;
    const r = Math.min(width, height) * 0.35;
    const obj = Object.assign({}, n, {
      x: width / 2 + r * Math.cos(angle) + (Math.random() - 0.5) * 40,
      y: height / 2 + r * Math.sin(angle) + (Math.random() - 0.5) * 40,
      vx: 0, vy: 0,
    });
    byId[n.id] = obj;
    return obj;
  });
  const edges = edgesData
    .map(e => ({ source: byId[e.from], target: byId[e.to] }))
    .filter(e => e.source && e.target);

  // simple force simulation (no deps)
  function tick() {
    const k = 0.002, rep = 900, damp = 0.85, center = 0.0006;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      a.vx += (width / 2 - a.x) * center;
      a.vy += (height / 2 - a.y) * center;
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j];
        let dx = a.x - b.x, dy = a.y - b.y;
        let d2 = dx * dx + dy * dy || 1;
        let f = rep / d2;
        let d = Math.sqrt(d2);
        dx /= d; dy /= d;
        a.vx += dx * f; a.vy += dy * f;
        b.vx -= dx * f; b.vy -= dy * f;
      }
    }
    for (const e of edges) {
      let dx = e.target.x - e.source.x, dy = e.target.y - e.source.y;
      e.source.vx += dx * k; e.source.vy += dy * k;
      e.target.vx -= dx * k; e.target.vy -= dy * k;
    }
    for (const n of nodes) {
      n.vx *= damp; n.vy *= damp;
      n.x += n.vx; n.y += n.vy;
      n.x = Math.max(20, Math.min(width - 20, n.x));
      n.y = Math.max(20, Math.min(height - 20, n.y));
    }
  }
  for (let s = 0; s < 220; s++) tick();

  const g = document.createElementNS(NS, 'g');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.appendChild(g);

  const edgeEls = edges.map(e => {
    const line = document.createElementNS(NS, 'line');
    line.setAttribute('class', 'edge');
    line.setAttribute('x1', e.source.x); line.setAttribute('y1', e.source.y);
    line.setAttribute('x2', e.target.x); line.setAttribute('y2', e.target.y);
    g.appendChild(line);
    return { el: line, e };
  });

  function radiusFor(n) {
    return 4 + Math.min(10, Math.sqrt(n.num_connections + 1) * 2.2);
  }
  function colorFor(n) {
    if (n.ext === '.py') return '#7dd3fc';
    if (n.ext === '.ts' || n.ext === '.tsx') return '#c4b5fd';
    if (n.ext === '.js' || n.ext === '.jsx') return '#fcd34d';
    return '#a1a1aa';
  }

  const nodeEls = nodes.map(n => {
    const grp = document.createElementNS(NS, 'g');
    grp.setAttribute('class', 'node');
    grp.setAttribute('transform', `translate(${n.x},${n.y})`);
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('r', radiusFor(n));
    c.setAttribute('fill', colorFor(n));
    grp.appendChild(c);
    const t = document.createElementNS(NS, 'text');
    t.setAttribute('x', radiusFor(n) + 3);
    t.setAttribute('y', 3);
    t.textContent = n.id.split('/').pop();
    grp.appendChild(t);
    grp.addEventListener('click', () => selectNode(n));
    g.appendChild(grp);
    return { el: grp, n };
  });

  function layout() {
    for (const { el, n } of nodeEls) el.setAttribute('transform', `translate(${n.x},${n.y})`);
    for (const { el, e } of edgeEls) {
      el.setAttribute('x1', e.source.x); el.setAttribute('y1', e.source.y);
      el.setAttribute('x2', e.target.x); el.setAttribute('y2', e.target.y);
    }
  }
  layout();

  // pan & zoom
  let vb = { x: 0, y: 0, w: width, h: height };
  function applyVB() { svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); }
  let dragging = false, last = null;
  svg.addEventListener('mousedown', e => { dragging = true; last = [e.clientX, e.clientY]; });
  window.addEventListener('mouseup', () => dragging = false);
  window.addEventListener('mousemove', e => {
    if (!dragging) return;
    const dx = (e.clientX - last[0]) * (vb.w / width);
    const dy = (e.clientY - last[1]) * (vb.h / height);
    vb.x -= dx; vb.y -= dy; last = [e.clientX, e.clientY]; applyVB();
  });
  svg.addEventListener('wheel', e => {
    e.preventDefault();
    const factor = e.deltaY > 0 ? 1.1 : 0.9;
    const mx = vb.x + (e.offsetX / width) * vb.w;
    const my = vb.y + (e.offsetY / height) * vb.h;
    vb.w *= factor; vb.h *= factor;
    vb.x = mx - (e.offsetX / width) * vb.w;
    vb.y = my - (e.offsetY / height) * vb.h;
    applyVB();
  }, { passive: false });

  const detail = document.getElementById('detail');
  let selectedId = null;

  function selectNode(n) {
    selectedId = n.id;
    const connectedIds = new Set([n.id]);
    for (const e of edgesData) {
      if (e.from === n.id) connectedIds.add(e.to);
      if (e.to === n.id) connectedIds.add(e.from);
    }
    for (const { el, n: nn } of nodeEls) {
      el.classList.toggle('hl', nn.id === n.id);
      el.classList.toggle('dim', !connectedIds.has(nn.id));
    }
    for (const { el, e } of edgeEls) {
      const on = e.source.id === n.id || e.target.id === n.id;
      el.classList.toggle('hl', on);
      el.style.opacity = (e.source.id === n.id || e.target.id === n.id || connectedIds.size === nodesData.length) ? 1 : 0.08;
    }
    const funcs = n.functions.map(f => `<li>fn ${f}()</li>`).join('') || '<li style="color:var(--muted)">none found</li>';
    const classes = n.classes.map(c => `<li>class ${c}</li>`).join('') || '<li style="color:var(--muted)">none found</li>';
    const links = [...connectedIds].filter(id => id !== n.id);
    const linkItems = links.map(id => `<li><a href="#" data-goto="${id}" style="color:var(--accent);text-decoration:none;">${id}</a></li>`).join('') || '<li style="color:var(--muted)">no intra-repo connections</li>';
    detail.innerHTML = `
      <h2>${n.id}</h2>
      <div class="meta">${n.loc} lines &middot; ${n.num_connections} connections</div>
      <div class="section-label">Functions (${n.functions.length})</div>
      <ul>${funcs}</ul>
      <div class="section-label">Classes (${n.classes.length})</div>
      <ul>${classes}</ul>
      <div class="section-label">Connected files</div>
      <ul>${linkItems}</ul>
    `;
    detail.querySelectorAll('[data-goto]').forEach(a => {
      a.addEventListener('click', ev => {
        ev.preventDefault();
        const target = nodesData.find(x => x.id === a.dataset.goto);
        const full = nodeEls.find(x => x.n.id === target.id);
        if (full) selectNode(full.n);
      });
    });
  }

  const search = document.getElementById('search');
  search.addEventListener('input', () => {
    const q = search.value.trim().toLowerCase();
    if (!q) {
      nodeEls.forEach(({ el }) => el.classList.remove('dim', 'hl'));
      edgeEls.forEach(({ el }) => { el.classList.remove('hl'); el.style.opacity = 1; });
      return;
    }
    for (const { el, n } of nodeEls) {
      const hit = n.id.toLowerCase().includes(q) ||
        n.functions.some(f => f.toLowerCase().includes(q)) ||
        n.classes.some(c => c.toLowerCase().includes(q));
      el.classList.toggle('dim', !hit);
      el.classList.toggle('hl', hit);
    }
  });
})();
</script>
</body>
</html>
"""


def render_html(graph: dict, root: str) -> str:
    root_name = os.path.basename(os.path.abspath(root)) or root
    return (
        HTML_TEMPLATE
        .replace("{root_name}", root_name)
        .replace("{graph_json}", json.dumps(graph))
    )


def main():
    ap = argparse.ArgumentParser(description="Map a codebase into a clickable file/function graph.")
    ap.add_argument("path", help="Path to the codebase to analyze")
    ap.add_argument("--out", default="./out", help="Output directory (default: ./out)")
    ap.add_argument("--max-files", type=int, default=3000, help="Safety cap on number of files scanned")
    args = ap.parse_args()

    if not os.path.isdir(args.path):
        print(f"error: {args.path} is not a directory", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)

    graph = build_graph(args.path, args.max_files)

    json_path = os.path.join(args.out, "codemap.json")
    html_path = os.path.join(args.out, "codemap.html")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(graph, args.path))

    s = graph["summary"]
    print(f"Scanned {s['num_files']} files, found {s['num_connections']} intra-repo connections, "
          f"{s['num_functions']} functions, {s['num_classes']} classes.")
    print(f"Wrote {json_path}")
    print(f"Wrote {html_path}  <-- open this in a browser")


if __name__ == "__main__":
    main()
