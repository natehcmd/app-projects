#!/bin/bash
# Mission Control — one-command dev run.
# NOTE: on Nate's machine the server is normally managed by launchd
# (com.nate.mission-control, KeepAlive). To restart that instance use:
#   launchctl kickstart -k gui/501/com.nate.mission-control
# Running this script while launchd holds :8450 will fail to bind — that's expected.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/uvicorn server:app --host 127.0.0.1 --port "${PORT:-8450}"
