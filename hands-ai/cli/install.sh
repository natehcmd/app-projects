#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install CLI dependencies into the same interpreter used by hands.py's
# /usr/bin/env python3 shebang.
PYTHON=$(which python3)

# Try user install first (works even with brew-managed python)
$PYTHON -m pip install --user click requests rich 2>/dev/null || \
  $PYTHON -m pip install --break-system-packages click requests rich

# Install symlink
ln -sf "$SCRIPT_DIR/hands.py" /usr/local/bin/hands 2>/dev/null || \
  ln -sf "$SCRIPT_DIR/hands.py" "$HOME/.local/bin/hands"

chmod +x "$SCRIPT_DIR/hands.py"
echo "Hands AI CLI installed. Run: hands status"
