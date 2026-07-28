#!/bin/bash
# One-command bootstrap + run for File Graph.
#   ./run.sh          -> serve web UI at http://127.0.0.1:8437
#   ./run.sh scan     -> index home dir + embed (needs ollama for embeddings)
#   ./run.sh stats    -> file counts
# Any argument is passed through to `python -m filegraph <arg>`.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "Creating .venv and installing dependencies…"
  python3 -m venv .venv
  .venv/bin/pip install --quiet --upgrade pip
  .venv/bin/pip install --quiet -e .
fi

exec .venv/bin/python -m filegraph "${1:-serve}"
