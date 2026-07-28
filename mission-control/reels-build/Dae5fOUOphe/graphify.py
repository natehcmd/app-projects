#!/usr/bin/env python3
"""
Graphify — a small, self-contained codebase knowledge graph builder.

Idea (reconstructed from a vague social-media teaser about a tool called
"Graphify" that claims to map a codebase into a knowledge graph so an AI
coding assistant doesn't have to re-read every file): scan a repo once,
extract a lightweight graph of

    file -> {imports/dependencies, defined symbols (functions/classes)}

and write it to a single JSON file plus a human-readable Markdown index.
An AI assistant (or a human) can then query that graph to find which file
defines a symbol, or what a file depends on, instead of grepping/reading
the whole tree every time.

No external dependencies. Python 3.8+.

Supported languages (best-effort, regex/AST based, not a full parser):
  - Python (.py)      — uses the `ast` module for accurate imports/defs
  - JavaScript/TypeScript (.js, .jsx, .ts, .tsx) — regex-based import/
    export/function/class extraction (good enough for indexing, not a
    substitute for a real JS parser)

Usage:
    python3 graphify.py build <path-to-repo> [--out graph.json] [--index index.md]
    python3 graphify.py query <graph.json> <symbol-or-filename>

Examples:
    python3 graphify.py build ~/Projects/myapp
    python3 graphify.py query graph.json UserService
    python3 graphify.py query graph.json src/utils/date.py
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --- configuration -----------------------------------------------------

DEFAULT_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    "dist", "build", ".next", ".turbo", ".cache", ".mypy_cache",
    ".pytest_cache", "coverage", ".idea", ".vscode", "target",
}

PY_EXT = {".py"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SUPPORTED_EXT = PY_EXT | JS_EXT

# Skip files above this size (bytes) — minified bundles, generated files, etc.
MAX_FILE_BYTES = 500_000


@dataclass
class FileNode:
    path: str
    language: str
    imports: list = field(default_factory=list)      # modules/files this file depends on
    defines: list = field(default_factory=list)       # top-level functions/classes defined here
    loc: int = 0


# --- Python analysis -----------------------------------------------------

def analyze_python(path: Path, text: str) -> FileNode:
    node = FileNode(path=str(path), language="python", loc=text.count("\n") + 1)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return node

    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for alias in n.names:
                node.imports.append(alias.name)
        elif isinstance(n, ast.ImportFrom):
            if n.module:
                node.imports.append(n.module)

    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.defines.append(f"function:{n.name}")
        elif isinstance(n, ast.ClassDef):
            node.defines.append(f"class:{n.name}")
            for sub in n.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    node.defines.append(f"method:{n.name}.{sub.name}")

    node.imports = sorted(set(node.imports))
    return node


# --- JS/TS analysis (regex-based best effort) ---------------------------

JS_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:[\w*{}\s,]+?\s+from\s+)?|require\()\s*['"]([^'"]+)['"]"""
)
JS_FUNC_RE = re.compile(
    r"""^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)""",
    re.MULTILINE,
)
JS_CLASS_RE = re.compile(
    r"""^\s*(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_$]+)""",
    re.MULTILINE,
)
JS_CONST_FUNC_RE = re.compile(
    r"""^\s*(?:export\s+)?const\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\(?[^=]*\)?\s*=>""",
    re.MULTILINE,
)


def analyze_js(path: Path, text: str) -> FileNode:
    node = FileNode(path=str(path), language="javascript", loc=text.count("\n") + 1)
    node.imports = sorted(set(JS_IMPORT_RE.findall(text)))
    for m in JS_FUNC_RE.finditer(text):
        node.defines.append(f"function:{m.group(1)}")
    for m in JS_CLASS_RE.finditer(text):
        node.defines.append(f"class:{m.group(1)}")
    for m in JS_CONST_FUNC_RE.finditer(text):
        node.defines.append(f"function:{m.group(1)}")
    node.defines = sorted(set(node.defines))
    return node


# --- graph building -------------------------------------------------------

def iter_source_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SUPPORTED_EXT:
            continue
        if any(part in DEFAULT_IGNORE_DIRS for part in p.parts):
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield p


def build_graph(root: Path) -> dict:
    root = root.resolve()
    files = {}
    symbol_index = {}  # symbol name -> [file paths]

    for p in sorted(iter_source_files(root)):
        rel = str(p.relative_to(root))
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if p.suffix.lower() in PY_EXT:
            node = analyze_python(Path(rel), text)
        else:
            node = analyze_js(Path(rel), text)

        node.path = rel
        files[rel] = asdict(node)

        for d in node.defines:
            name = d.split(":", 1)[-1]
            symbol_index.setdefault(name, []).append(rel)

    return {
        "root": str(root),
        "file_count": len(files),
        "files": files,
        "symbol_index": symbol_index,
    }


# --- markdown index --------------------------------------------------------

def write_markdown_index(graph: dict, out_path: Path):
    lines = [f"# Graphify index — {graph['root']}", "", f"Files indexed: {graph['file_count']}", ""]
    for rel, node in sorted(graph["files"].items()):
        lines.append(f"## {rel} ({node['language']}, {node['loc']} lines)")
        if node["imports"]:
            lines.append(f"- imports: {', '.join(node['imports'])}")
        if node["defines"]:
            lines.append(f"- defines: {', '.join(node['defines'])}")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


# --- CLI --------------------------------------------------------------------

def cmd_build(args):
    root = Path(args.path)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 1
    graph = build_graph(root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=2), encoding="utf-8")

    # Default the markdown index to sit next to --out rather than always
    # landing in the current directory (which used to pollute wherever the
    # command was run from, including this tool's own source folder).
    index_path = Path(args.index) if args.index is not None else out.parent / "index.md"
    if args.index != "":
        write_markdown_index(graph, index_path)

    print(f"Indexed {graph['file_count']} files -> {out}")
    if args.index != "":
        print(f"Markdown index -> {index_path}")
    return 0


def cmd_query(args):
    graph_path = Path(args.graph)
    if not graph_path.is_file():
        print(f"error: {graph_path} not found (run 'build' first)", file=sys.stderr)
        return 1
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    q = args.query

    # 1. exact filename match
    if q in graph["files"]:
        node = graph["files"][q]
        print(json.dumps(node, indent=2))
        return 0

    # 2. symbol match
    if q in graph["symbol_index"]:
        for rel in graph["symbol_index"][q]:
            node = graph["files"][rel]
            defs = [d for d in node["defines"] if d.endswith(f":{q}") or d.endswith(f".{q}")]
            print(f"{rel}  ->  {', '.join(defs) or q}")
        return 0

    # 3. fuzzy fallback: substring match over filenames and symbols
    hits = []
    for rel in graph["files"]:
        if q.lower() in rel.lower():
            hits.append(("file", rel))
    for sym, files in graph["symbol_index"].items():
        if q.lower() in sym.lower():
            for rel in files:
                hits.append(("symbol", f"{sym} in {rel}"))

    if not hits:
        print(f"No match for '{q}'.")
        return 1

    for kind, val in hits:
        print(f"[{kind}] {val}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Graphify — codebase knowledge graph builder")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build", help="scan a repo and build the graph")
    p_build.add_argument("path", help="path to the repo root")
    p_build.add_argument("--out", default="graph.json", help="output JSON path (default: graph.json)")
    p_build.add_argument("--index", default=None,
                         help="output Markdown index path (default: index.md next to --out); pass '' to skip")
    p_build.set_defaults(func=cmd_build)

    p_query = sub.add_parser("query", help="look up a file or symbol in an existing graph")
    p_query.add_argument("graph", help="path to graph.json produced by 'build'")
    p_query.add_argument("query", help="symbol name or file path to look up")
    p_query.set_defaults(func=cmd_query)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
