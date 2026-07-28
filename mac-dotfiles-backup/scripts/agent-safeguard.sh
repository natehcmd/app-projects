#!/usr/bin/env bash

BASE_DIR="/Users/natehoward/.agent-safeguard"
PID_FILE="$BASE_DIR/safeguard.pid"
LOG_FILE="$BASE_DIR/safeguard.log"
SCRIPT_PATH="/Users/natehoward/scripts/agent-safeguard.js"

mkdir -p "$BASE_DIR"

start() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
      echo "Agent Safeguard is already running (PID: $PID)"
      return 0
    else
      rm "$PID_FILE"
    fi
  fi

  echo "Starting Agent Safeguard Daemon..."
  nohup node "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1 &
  PID=$!
  echo "$PID" > "$PID_FILE"
  echo "Agent Safeguard started (PID: $PID). Logging to $LOG_FILE"
}

stop() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
      echo "Stopping Agent Safeguard Daemon (PID: $PID)..."
      kill "$PID"
      rm "$PID_FILE"
      echo "Agent Safeguard stopped."
    else
      echo "Process in PID file ($PID) not running. Removing stale PID file."
      rm "$PID_FILE"
    fi
  else
    echo "Agent Safeguard is not running."
  fi
}

status() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
      echo "Agent Safeguard is RUNNING (PID: $PID)"
      echo "Last 10 log entries:"
      tail -n 10 "$LOG_FILE"
    else
      echo "Agent Safeguard is STOPPED (stale PID file found)"
    fi
  else
    echo "Agent Safeguard is STOPPED"
  fi
}

case "$1" in
  start)
    start
    ;;
  stop)
    stop
    ;;
  status)
    status
    ;;
  restart)
    stop
    sleep 1
    start
    ;;
  logs)
    tail -f "$LOG_FILE"
    ;;
  *)
    echo "Usage: $0 {start|stop|status|restart|logs}"
    exit 1
    ;;
esac
