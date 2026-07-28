#!/bin/bash
# Deploy Daisy OS microkernel updates to the Daisy machine.
# Usage: bash deploy-to-daisy.sh [user@host] [remote-dir]

set -euo pipefail

TARGET="${1:-root@192.168.0.248}"
REMOTE_DIR="${2:-/opt/daisy-os}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Deploying to $TARGET:$REMOTE_DIR ==="

ssh -o ConnectTimeout=5 "$TARGET" hostname || { echo "Daisy offline or unreachable"; exit 1; }

REQUIRED_FILES=(
  "$SCRIPT_DIR/kernel/boot.py"
  "$SCRIPT_DIR/kernel/hal.py"
  "$SCRIPT_DIR/kernel/config.py"
)
for f in "${REQUIRED_FILES[@]}"; do
  [[ -f "$f" ]] || { echo "Missing required file: $f"; exit 1; }
done

echo "[1/6] Deploying kernel files..."
scp "$SCRIPT_DIR/kernel/boot.py"   "$TARGET:$REMOTE_DIR/kernel/boot.py"
scp "$SCRIPT_DIR/kernel/hal.py"    "$TARGET:$REMOTE_DIR/lib/daisy_hal_v2.py"
scp "$SCRIPT_DIR/kernel/config.py" "$TARGET:$REMOTE_DIR/kernel/config.py"

echo "[2/6] Fixing permissions..."
ssh "$TARGET" "chown -R nate:nate /var/lib/daisy/data/ /var/log/daisy/ || true"

echo "[3/6] Normalising Python interpreter references..."
ssh "$TARGET" "find $REMOTE_DIR -name '*.py' -exec sed -i 's/python3\\.12/python3/g' {} +"

echo "[4/6] Fixing hard-coded DAISY_HOME paths..."
ssh "$TARGET" "find $REMOTE_DIR/desktop -name '*.py' -exec sed -i \
  \"s|sys.path.insert(0, \\\"/opt/daisy-os/desktop\\\")|sys.path.insert(0, os.path.join(os.environ.get(\\\"DAISY_HOME\\\", \\\"/opt/daisy-os\\\"), \\\"desktop\\\"))|g\" {} +"

echo "[5/6] Setting Plymouth boot theme..."
ssh "$TARGET" "printf '[Daemon]\nTheme=daisy\nShowDelay=0\n' > /etc/plymouth/plymouthd.conf && update-initramfs -u"

echo "[6/6] Disabling sleep targets..."
ssh "$TARGET" "systemctl mask sleep.target suspend.target hibernate.target"

echo "=== Running syntax check ==="
ssh "$TARGET" python3 - <<PYEOF
import py_compile, glob, sys
failures = []
for f in glob.glob("$REMOTE_DIR/**/*.py", recursive=True):
    try:
        py_compile.compile(f, doraise=True)
    except py_compile.PyCompileError as e:
        failures.append(str(e))
if failures:
    print(f"FAIL: {len(failures)} syntax error(s):")
    print("\\n".join(failures))
    sys.exit(1)
print(f"OK: all files pass syntax check")
PYEOF

echo "=== Deploy complete ==="
