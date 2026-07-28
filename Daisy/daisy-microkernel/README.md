# daisy-microkernel

Python userspace simulator of a capability-based microkernel (tasks, endpoints,
synchronous IPC, memory regions, capability transfer/revocation).

- Design: [`docs/DESIGN.md`](docs/DESIGN.md)
- Kernel: [`kernel/microkernel.py`](kernel/microkernel.py)
- Tests: `python3 -m pytest tests -q` (35 tests, all passing as of 2026-07-09)
- `deploy-to-daisy.sh` targets a physical machine and expects `kernel/boot.py`,
  `hal.py`, `config.py` — files not present in this repo; the script is stale.
