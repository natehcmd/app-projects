# Graphify (reconstructed)

## Where this came from

The source reel for this build was engagement bait: *"Comment REPO and I'll
send you the GitHub link."* It named a tool called **Graphify** and made two
vague claims — it "maps your codebase into a knowledge graph" and "lowers
token usage" for Claude Code — but disclosed zero actual technique,
architecture, or code. The entire value of the original post was a gated
DM/link, not any real content.

Rather than fabricate a link or copy a product that doesn't actually exist
in the source material, this is a **from-scratch, honest implementation of
the general idea being gestured at**: a small tool that scans a codebase
once and produces a lightweight "knowledge graph" (which files import what,
and which functions/classes each file defines), so an AI assistant — or a
human — can look up "where is `UserService` defined" or "what does
`utils/date.py` depend on" from a small JSON/Markdown index instead of
grepping or re-reading the whole tree every time.

It is not affiliated with, and does not claim to be, the "Graphify" from the
video.

## What it does

`graphify.py` has two subcommands:

- **`build`** — walks a directory, skips common noise directories
  (`node_modules`, `.git`, `dist`, `venv`, etc.) and any file over 500KB,
  and for each Python/JavaScript/TypeScript file records:
  - what it imports
  - what top-level functions/classes it defines (and methods, for Python)
  - line count

  It writes this out as:
  - a single `graph.json` (the machine-readable graph + a symbol index)
  - an `index.md` (a human-readable Markdown summary of the same data)

- **`query`** — looks up a symbol name or a file path in an existing
  `graph.json` and prints where it's defined / what it contains, without
  re-scanning the repo or reading the source files again.

### Language support

- **Python** — parsed with the standard-library `ast` module (accurate).
- **JavaScript / TypeScript** (`.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`)
  — parsed with regexes for `import`/`require`, `function`, `class`, and
  arrow-function-assigned-to-const declarations. This is best-effort
  indexing, not a full parser — good enough to point an assistant at the
  right file, not a substitute for a real AST tool like `ts-morph`.

Anything else (Go, Rust, etc.) is currently skipped; the file-walking and
JSON/Markdown output plumbing is generic, so adding another language means
writing one more `analyze_*` function.

## Setup

No dependencies beyond the Python standard library. Requires **Python 3.8+**.

```bash
cd /Users/natehoward/Projects/mission-control/reels-build/Dae5fOUOphe
python3 --version   # confirm 3.8+
```

No API keys, no network access, nothing to configure. It only reads files
from the directory you point it at.

## How to run it

Build a graph of some repo:

```bash
python3 graphify.py build /path/to/your/repo --out graph.json --index index.md
```

This prints how many files were indexed and where the outputs went. Skip the
Markdown index with `--index ''` if you only want the JSON.

Look something up in an existing graph:

```bash
# find where a function/class is defined
python3 graphify.py query graph.json UserService

# see everything recorded about one file
python3 graphify.py query graph.json src/utils/date.py

# fuzzy fallback — substring match over both filenames and symbol names
python3 graphify.py query graph.json date
```

### Example (indexing this tool against itself)

```bash
$ python3 graphify.py build . --out graph.json --index index.md
Indexed 1 files -> graph.json
Markdown index -> index.md

$ python3 graphify.py query graph.json build_graph
graphify.py  ->  function:build_graph
```

## Honest limitations

- The graph only captures *structural* facts (imports + top-level
  definitions), not call relationships or runtime behavior — it's an index,
  not a real dependency/call graph.
- JS/TS extraction is regex-based and will miss unusual syntax (dynamic
  imports built from string concatenation, re-exports via `export * from`,
  decorators-heavy class definitions, etc.).
- It does not integrate with Claude Code automatically — you'd wire that up
  yourself, e.g. by having an agent run `query` before reading a file, or by
  feeding `index.md` into context instead of raw source. There is no hidden
  magic here for "lowering token usage" beyond "read a compact index instead
  of full files when you can."
