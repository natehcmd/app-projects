# Daisy Kernel — Rust Implementation

Port the Python microkernel (29 passing tests) to bare-metal Rust.

## Modules needed

> Status: all modules below exist in `src/` (the kernel has since grown to 50 modules, plus `bootloader/src/main.rs`).

1. `src/lib.rs` — kernel main, ties everything together
2. `src/boot.rs` — UEFI bootloader entry
3. `src/gdt.rs` — Global Descriptor Table setup
4. `src/idt.rs` — Interrupt Descriptor Table + handlers
5. `src/memory.rs` — physical frame allocator + page table setup
6. `src/task.rs` — task management (create/destroy/yield)
7. `src/capability.rs` — UUID-less capability system using u64 IDs + bitflags permissions
8. `src/ipc.rs` — endpoint-based message passing with fixed 4KB messages
9. `src/scheduler.rs` — round-robin with 10 priority levels
10. `src/framebuffer.rs` — write text/pixels to UEFI GOP framebuffer
11. `src/serial.rs` — serial port output for early debug

## Key design
- #![no_std] #![no_main] throughout
- spin::Mutex for thread safety
- BTreeMap/VecDeque from alloc crate
- Capability checks on every syscall
- Match the Python microkernel's API exactly
