#!/bin/bash
# Run the Daisy Rust kernel in QEMU with full hardware emulation.
# Expects a pre-built kernel binary and OVMF at default path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KERNEL="$SCRIPT_DIR/target/x86_64-unknown-none/release/daisy-kernel"
OVMF="/usr/share/OVMF/OVMF_CODE.fd"

[[ -f "$KERNEL" ]] || { echo "Kernel not found: $KERNEL — run cargo build first"; exit 1; }
[[ -f "$OVMF" ]]   || { echo "OVMF not found: $OVMF — install ovmf package"; exit 1; }

exec qemu-system-x86_64 \
  -machine q35 \
  -cpu qemu64 \
  -smp 4 \
  -m 512M \
  -serial stdio \
  -display gtk \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0 \
  -device qemu-xhci \
  -device usb-kbd \
  -device usb-mouse \
  -device virtio-gpu-pci \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF" \
  -kernel "$KERNEL" \
  -append "console=ttyS0" \
  -no-reboot \
  -d int,cpu_reset \
  "$@"
