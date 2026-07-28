# daisy-rust-kernel

Bare-metal x86_64 Rust port of the Daisy microkernel design, ~50 `src/` modules
plus a UEFI bootloader crate in `bootloader/`.

- Spec / module map: [`SPEC.md`](SPEC.md)
- Build & boot: `./run-qemu.sh` (or `./run-qemu-full.sh`)
- Prerequisites: nightly Rust with `x86_64-unknown-none` and
  `x86_64-unknown-uefi` targets, QEMU, and OVMF UEFI firmware.

Status: NOT built or verified in this checkout — treat as experimental until a
successful QEMU boot is reproduced.
