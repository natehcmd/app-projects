#!/bin/bash
# Build and run the Daisy Rust kernel in QEMU with UEFI.
# Searches common OVMF paths on Linux and macOS.

set -euo pipefail

KERNEL_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$KERNEL_DIR/target/x86_64-unknown-none/release"
BOOT_SRC="$KERNEL_DIR/bootloader/target/x86_64-unknown-uefi/release/daisy_bootloader.efi"

echo "[build] Building kernel..."
cargo build --release --target x86_64-unknown-none

echo "[build] Building bootloader..."
(cd "$KERNEL_DIR/bootloader" && cargo build --release --target x86_64-unknown-uefi)

[[ -f "$BOOT_SRC" ]] || { echo "Error: bootloader binary not found at $BOOT_SRC"; exit 1; }

ESP_DIR="$(mktemp -d)"
trap 'rm -rf "$ESP_DIR"' EXIT

mkdir -p "$ESP_DIR/EFI/BOOT" "$ESP_DIR/EFI/daisy"
cp "$BOOT_SRC" "$ESP_DIR/EFI/BOOT/BOOTX64.EFI"
[[ -f "$TARGET_DIR/daisy-kernel" ]] && cp "$TARGET_DIR/daisy-kernel" "$ESP_DIR/EFI/daisy/kernel.elf"

OVMF=""
for path in \
    /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/edk2/ovmf/OVMF_CODE.fd \
    /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
    /usr/local/share/qemu/edk2-x86_64-code.fd; do
  [[ -f "$path" ]] && { OVMF="$path"; break; }
done

[[ -n "$OVMF" ]] || {
  echo "OVMF not found. Install with:"
  echo "  brew install qemu   (macOS)"
  echo "  apt install ovmf    (Debian/Ubuntu)"
  exit 1
}

echo "[qemu] Starting Daisy OS..."
exec qemu-system-x86_64 \
  -machine q35 \
  -cpu qemu64 \
  -m 512M \
  -bios "$OVMF" \
  -drive format=raw,file=fat:rw:"$ESP_DIR" \
  -serial stdio \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0 \
  -device qemu-xhci \
  -device usb-kbd \
  -no-reboot \
  -no-shutdown \
  "$@"
