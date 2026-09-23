# Codemap — a real "turn your codebase into a clickable brain" tool

## Where this came from

The source reel (`DadvdvitVke`) is a "comment X for the link" engagement-bait
post. It gates an external repo called "Understand-Anything" behind a
comment, and describes the *outcome* in one sentence — "it turns your whole
codebase into a brain you can click through. Every file, every function,
every connection, mapped" — but discloses zero actual technique,
architecture, or implementation detail. There's nothing to reverse-engineer.

Rather than treat that as nothing-to-build (the sentence above is a real,
buildable product idea, just with no method given), this directory is an
independent, from-scratch implementation of the concept it's describing:
a tool that statically analyzes a codebase and produces a clickable graph
of files, functions/classes, and the import/call connections between them.
None of the gated repo's code, name, or assets are used — this is original.

## What it does

`codemap.py` walks a directory tree and:

1. Parses every Python file with the standard library `ast` module to
   extract its functions, classes, and imports.
2. Scans every JS/TS/JSX/TSX file with a set of regexes to extract the
   same (best-effort — no type resolution, no build-tool awareness).
3. Resolves relative/local imports back to files inside the same repo,
   building a graph edge between the importer and the imported file.
4. Writes out:
   - `codemap.json` — the raw graph (nodes = files with their functions/
     classes/loc, edges = import relationships) for scripting or feeding
     into another tool.
   - `codemap.html` — a **single self-contained HTML file** (no CDN, no
     internet required) with an interactive, force-directed graph you can
     open in any browser: click a node to see its functions/classes and
     everything it connects to, search to jump to a file or function,
     pan/zoom the canvas.

## Honest limitations (same ones the reel admits to)

- This is static analysis via AST/regex, not a language server — it does
  **not** resolve dynamic imports, monorepo path aliases, re-exports,
  reflection-based calls, or cross-language boundaries (e.g. a Python
  backend calling a JS frontend over HTTP won't show an edge).
- JS/TS parsing is regex-based, not a real parser, so unusual formatting
  or heavily minified/templated/generated code will under-report.
- It only draws edges for imports it can resolve to a file *inside* the
  scanned directory — external packages (`numpy`, `react`, etc.) are
  counted (`num_external_deps` in the summary) but not drawn as nodes,
  to keep the graph about *your* code.
- Function-to-function call graphs across files are not attempted (only
  file-to-file import edges) — that requires real symbol resolution,
  which is out of scope for a small dependency-free script.

## Requirements

- Python 3.9+ (standard library only — no `pip install` needed).

## How to run it

```bash
python3 codemap.py /path/to/your/codebase
```

This writes `./out/codemap.json` and `./out/codemap.html`. Open the HTML
file in any browser:

```bash
open ./out/codemap.html      # macOS
```

Options:

```bash
python3 codemap.py /path/to/your/codebase --out ./somewhere --max-files 5000
```

- `--out` — output directory (default `./out`)
- `--max-files` — safety cap on how many source files to scan (default 3000)

It automatically skips `.git`, `node_modules`, `__pycache__`, `.venv`,
`dist`, `build`, `.next`, `vendor`, and other common noise directories.

## Setup / API-key notes

None. This tool makes no network calls, needs no API key, and sends your
code nowhere — everything runs and stays local. That's a deliberate
difference from a hosted "upload your repo" product: point it at a
directory and it writes two files next to it.

## Files in this directory

- `codemap.py` — the whole tool (one file, stdlib only).
- `README.md` — this file.
