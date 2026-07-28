#!/bin/bash
cd "$(dirname "$0")"

# Prefer venv; fall back to system python3
if [ -d ".venv" ]; then
  PYTHON=".venv/bin/python3"
else
  PYTHON="$(which python3.12 || which python3)"
  # Auto-create venv on first run
  $PYTHON -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
  PYTHON=".venv/bin/python3"
fi

$PYTHON -m uvicorn main:app --host 127.0.0.1 --port 7721 --reload
