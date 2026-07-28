# Daisy

An experimental operating-system project in three parts, at very different levels
of maturity. This README is the honest map.

| Part | What it is | Status |
|---|---|---|
| [`daisy-microkernel/`](daisy-microkernel/) | Python capability-based microkernel **simulator** | Working — 35 pytest tests pass locally |
| [`daisy-rust-kernel/`](daisy-rust-kernel/) | Bare-metal x86_64 Rust kernel (~50 modules) + UEFI bootloader | Untested here — build **not** verified in this checkout |
| [`daisy-native/daisy-layer`](daisy-native/) | Python "daisy-layer" service/desktop stack (~79 services) | **Missing** — broken submodule, code not present locally |
| `audit-report.json` | Structured code audit: **112 issues** (23 CRITICAL, 79 HIGH, 10 MEDIUM) across 59 files | Open backlog — most flagged files live in the missing daisy-layer |
| `FIX-AGENT-PROMPT.md` | Prompt for an agent to apply the audit fixes | Reference only |

## daisy-microkernel (works)

A userspace simulator of a capability-based microkernel: tasks, endpoints,
synchronous IPC, memory regions, capability copy/revoke. Design notes in
[`daisy-microkernel/docs/DESIGN.md`](daisy-microkernel/docs/DESIGN.md).

Run the tests (pure Python, needs only `pytest`):

```sh
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest daisy-microkernel/tests -q
# 35 passed
```

`daisy-microkernel/deploy-to-daisy.sh` deploys to a physical "Daisy" machine
(`root@192.168.0.248`). Note: it expects `kernel/boot.py`, `hal.py`, and
`config.py`, which are **not in this repo** — the script predates the current
tree and will refuse to run without them.

## daisy-rust-kernel (untested)

A `#![no_std]` bare-metal port of the microkernel design: GDT/IDT, paging,
scheduler, IPC, capabilities, plus drivers (e1000, NVMe, AHCI, xHCI, ACPI,
framebuffer, FAT32, a network stack, …) and a separate UEFI bootloader crate.
Spec in [`daisy-rust-kernel/SPEC.md`](daisy-rust-kernel/SPEC.md).

Not built or booted as part of this checkout. To try it yourself you need a
nightly Rust toolchain with the `x86_64-unknown-none` and `x86_64-unknown-uefi`
targets, plus QEMU with OVMF firmware:

```sh
cd daisy-rust-kernel
./run-qemu.sh        # builds kernel + bootloader, boots in QEMU/UEFI
./run-qemu-full.sh   # same, with more devices wired up
```

## daisy-native (missing)

`daisy-native/daisy-layer` is a git submodule pointer (commit `0b6bbcf`) with
**no `.gitmodules` entry and no known remote URL**, and the directory is empty
on disk. The ~79-service Python layer and desktop apps that `audit-report.json`
references lived there; they are believed lost in the 2026-07-09 `~/Projects`
deletion unless commit `0b6bbcf` exists in a backup or another remote. The
gitlink is left in place deliberately as the recovery breadcrumb — do not
remove it without deciding the submodule's fate.

## Known issues backlog

`audit-report.json` is a machine-readable audit: 112 issues across 59 files,
23 of them CRITICAL (mostly in the missing daisy-layer code).
`FIX-AGENT-PROMPT.md` explains how to feed it to a fix agent. Both are kept at
the repo root as the project's actionable TODO list — but note that many
referenced files cannot currently be fixed because they are not present.

## Housekeeping

- `_attic/` (untracked) holds quarantined junk files — previously committed
  `__pycache__` bytecode was untracked and moved there rather than deleted.
- `.gitignore` now covers `__pycache__/`, `*.pyc`, `_attic/`, and `.venv/`.
