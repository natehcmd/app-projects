# File Graph

A local knowledge graph of every file on your Mac, with semantic search — built
so Claude and other AIs have real context about your files, **on your terms**.

100% local: SQLite for storage, ollama (`nomic-embed-text`) for embeddings,
server bound to `127.0.0.1`. Nothing ever leaves the machine.

## Pieces

| Piece | What it does |
|---|---|
| Scanner | Walks `~`, indexes metadata + text previews. Cloud-streamed folders (Google Drive / OneDrive) are metadata-only — never downloads. |
| Embedder | Embeds text-file previews with local ollama for search-by-meaning. |
| **Native app** | `~/Applications/FileGraph.app` (SwiftUI, source in `FileGraphApp/`). 2D + 3D graph modes, tap to expand/collapse, Expand All / Minimize All, search, privacy panel. Auto-starts the backend. Rebuild: `FileGraphApp/make-app.sh` (requires macOS 14+ and Xcode Command Line Tools). |
| Web UI | `http://127.0.0.1:8437` — explorable force-directed graph, search, and the AI Access Control panel. |
| MCP server | What Claude talks to. Every result is filtered through your access rules. |

## Prerequisites

- Python 3.11+ (tested on 3.14)
- [ollama](https://ollama.com) with the embedding model, for semantic search
  (optional — keyword search and the graph work without it):

  ```bash
  ollama pull nomic-embed-text
  ```

## Quick start

```bash
cd ~/Projects/file-graph
./run.sh            # creates .venv, installs deps, serves http://127.0.0.1:8437
```

`run.sh` passes its first argument through to the CLI:

```bash
./run.sh scan       # index home dir + embed (re-run any time; incremental)
./run.sh embed      # embed pending files only (needs ollama)
./run.sh mcp        # run the MCP server (stdio; what Claude launches)
./run.sh stats      # file counts by kind + embedded total
```

Equivalent manual setup: `python3 -m venv .venv && .venv/bin/pip install -e .`
then `.venv/bin/python -m filegraph <command>`. Dependencies are declared in
`pyproject.toml`.

All state lives in `~/.filegraph/filegraph.db` (created on first scan).

### Smoke test

```bash
.venv/bin/python -c "import filegraph, fastapi, uvicorn, numpy, mcp"  # deps OK
curl -s http://127.0.0.1:8437/api/stats                               # server OK
```

## The web UI, at a glance

- **Graph canvas** — full-screen force-directed graph of your home directory.
  Nodes are colored by kind (folders indigo, code green, docs pink, data amber,
  images cyan). Click a folder to expand it; drag to reposition; scroll to zoom.
- **Top bar** — search field (semantic or keyword mode), Rescan button, and
  live index stats.
- **Right inspector** — details for the selected file: metadata, similar files
  (by embedding), and same-folder siblings.
- **Bottom-left: AI Access Control** — the privacy panel. Path-prefix
  allow/deny rules with toggles; add a folder to block it from every MCP tool.

## Privacy model

- Rules are path prefixes with allow/deny; **longest match wins**; default allow.
- `~/.ssh`, `~/.aws`, `~/.gnupg`, `~/.config` are denied out of the box.
- Toggle any folder in the web UI (lock button on a folder, or the panel
  bottom-left).
- Denied paths are invisible to all MCP tools — search results, folder listings,
  related-file lists, everything.
- The web UI itself always shows the full graph (it's for you, not the AIs).

## MCP tools exposed to AIs

- `graph_overview()` — file counts + project folders found
- `search_files(query, mode, limit)` — semantic (default) or keyword search
- `get_file_context(path)` — metadata, preview, folder siblings, similar files
- `list_folder(path)` — indexed folder contents

Registered in Claude Code as `file-graph` (user scope).
