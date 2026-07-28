#!/bin/bash
# Hands AI — one-command runner.
# Usage: bash start-all.sh [--daemon-only]
#   Bootstraps agent/.venv and app/node_modules on first run,
#   starts the daemon on 127.0.0.1:7721, then launches the Electron panel.
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

DAEMON_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --daemon-only) DAEMON_ONLY=1 ;;
    *) echo "Unknown option: $arg (supported: --daemon-only)" >&2; exit 1 ;;
  esac
done

# ── Daemon (auto-bootstrap venv on first run) ────────────────────────────────
cd "$SCRIPT_DIR/agent"
if [ ! -d ".venv" ]; then
  echo "[Hands AI] No venv found — creating agent/.venv and installing deps..."
  PYTHON="$(command -v python3.12 || command -v python3)"
  "$PYTHON" -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
source .venv/bin/activate

echo "[Hands AI] Starting daemon..."
python3 -m uvicorn main:app --host 127.0.0.1 --port 7721 &
DAEMON_PID=$!
echo "[Hands AI] Daemon PID: $DAEMON_PID"

# Wait for daemon to be ready
READY=0
for i in $(seq 1 16); do
  sleep 0.5
  if curl -sf http://127.0.0.1:7721/health > /dev/null 2>&1; then
    READY=1
    echo "[Hands AI] Daemon ready."
    break
  fi
done
if [ "$READY" -ne 1 ]; then
  echo "[Hands AI] Daemon failed to become healthy on :7721 — is the port in use?" >&2
  kill "$DAEMON_PID" 2>/dev/null || true
  exit 1
fi

if [ "$DAEMON_ONLY" -eq 1 ]; then
  echo "[Hands AI] --daemon-only: daemon running (PID $DAEMON_PID). Ctrl+C to stop."
  trap 'kill $DAEMON_PID 2>/dev/null || true' INT TERM
  wait "$DAEMON_PID"
  exit 0
fi

# ── Electron app (auto-install node_modules on first run) ────────────────────
cd "$SCRIPT_DIR/app"
if [ ! -d "node_modules" ]; then
  echo "[Hands AI] Installing Electron dependencies (first run, may take a while)..."
  npm install
fi

echo "[Hands AI] Launching Electron app..."
npm start

# If Electron exits, also kill the daemon this script started
kill $DAEMON_PID 2>/dev/null || true
