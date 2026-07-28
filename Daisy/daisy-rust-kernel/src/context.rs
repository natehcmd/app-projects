#![allow(dead_code)]

//! Context switching for Daisy OS.
//!
//! Saves/restores CPU register state to switch between tasks.
//! Uses the task module for task management and scheduler for pick_next.

use core::sync::atomic::{AtomicU64, Ordering};

/// Saved CPU context for a task.
#[derive(Clone, Copy)]
#[repr(C)]
pub struct CpuContext {
    // Callee-saved registers (System V ABI)
    pub rbx: u64,
    pub rbp: u64,
    pub r12: u64,
    pub r13: u64,
    pub r14: u64,
    pub r15: u64,
    // Stack pointer
    pub rsp: u64,
    // Instruction pointer (return address)
    pub rip: u64,
    // Flags
    pub rflags: u64,
    // Segment selectors (for user mode transitions)
    pub cs: u64,
    pub ss: u64,
    // CR3 (page table base) for per-process address spaces
    pub cr3: u64,
}

impl CpuContext {
    pub const fn zeroed() -> Self {
        Self {
            rbx: 0, rbp: 0, r12: 0, r13: 0, r14: 0, r15: 0,
            rsp: 0, rip: 0, rflags: 0x202, // IF flag set
            cs: 0x08, // kernel code segment
            ss: 0x10, // kernel data segment
            cr3: 0,
        }
    }

    /// Create a kernel-mode context starting at a given function with a given stack.
    pub fn new_kernel(entry: u64, stack_top: u64) -> Self {
        Self {
            rbx: 0, rbp: 0, r12: 0, r13: 0, r14: 0, r15: 0,
            rsp: stack_top,
            rip: entry,
            rflags: 0x202, // interrupts enabled
            cs: 0x08,      // kernel code
            ss: 0x10,      // kernel data
            cr3: 0,        // 0 = use current CR3
        }
    }

    /// Create a user-mode context.
    pub fn new_user(entry: u64, stack_top: u64, cr3: u64) -> Self {
        Self {
            rbx: 0, rbp: 0, r12: 0, r13: 0, r14: 0, r15: 0,
            rsp: stack_top,
            rip: entry,
            rflags: 0x202,
            cs: 0x1B,      // user code (ring 3, GDT index 3 | RPL 3)
            ss: 0x23,      // user data (ring 3, GDT index 4 | RPL 3)
            cr3,
        }
    }
}

/// Maximum tasks.
pub const MAX_TASKS: usize = 64;

/// Task kernel stack size (16 KB).
pub const TASK_STACK_SIZE: usize = 16384;

/// Per-task context storage.
static mut CONTEXTS: [CpuContext; MAX_TASKS] = [CpuContext::zeroed(); MAX_TASKS];

/// Kernel stacks (statically allocated for simplicity).
static mut STACKS: [[u8; TASK_STACK_SIZE]; MAX_TASKS] = [[0; TASK_STACK_SIZE]; MAX_TASKS];

/// Currently running task ID.
static CURRENT_TASK: AtomicU64 = AtomicU64::new(0);

/// Get the current task ID.
pub fn current() -> u64 {
    CURRENT_TASK.load(Ordering::Relaxed)
}

/// Set up a new task's context.
pub fn setup_task(task_id: u64, entry: fn()) -> bool {
    let idx = task_id as usize;
    if idx >= MAX_TASKS {
        return false;
    }

    unsafe {
        // Stack grows downward; top of stack is end of array
        let stack_top = &STACKS[idx][TASK_STACK_SIZE - 8] as *const u8 as u64;

        CONTEXTS[idx] = CpuContext::new_kernel(entry as u64, stack_top);

        crate::serial::print(b"[ctx] Task ");
        print_u64(task_id);
        crate::serial::print(b" context at RSP=0x");
        print_hex64(stack_top);
        crate::serial::print(b" entry=0x");
        print_hex64(entry as u64);
        crate::serial::print(b"\n");
    }
    true
}

/// Set up a user-mode task.
pub fn setup_user_task(task_id: u64, entry: u64, user_stack: u64, cr3: u64) -> bool {
    let idx = task_id as usize;
    if idx >= MAX_TASKS {
        return false;
    }

    unsafe {
        // Kernel stack for syscall/interrupt handling
        let kstack_top = &STACKS[idx][TASK_STACK_SIZE - 8] as *const u8 as u64;

        // The context starts in kernel mode; we'll iretq to user mode
        CONTEXTS[idx] = CpuContext::new_user(entry, user_stack, cr3);
        // Save kernel stack pointer for TSS RSP0
        CONTEXTS[idx].rbp = kstack_top;
    }
    true
}

/// Perform a context switch from `old_task` to `new_task`.
///
/// # Safety
/// Must be called with interrupts disabled. The caller is responsible for
/// ensuring task IDs are valid and different.
pub unsafe fn switch(old_task: u64, new_task: u64) {
    let old_idx = old_task as usize;
    let new_idx = new_task as usize;

    if old_idx >= MAX_TASKS || new_idx >= MAX_TASKS {
        return;
    }

    CURRENT_TASK.store(new_task, Ordering::Relaxed);

    // Switch page tables if different
    let new_cr3 = CONTEXTS[new_idx].cr3;
    if new_cr3 != 0 {
        let current_cr3: u64;
        core::arch::asm!("mov {}, cr3", out(reg) current_cr3, options(nomem, nostack));
        if current_cr3 != new_cr3 {
            core::arch::asm!("mov cr3, {}", in(reg) new_cr3, options(nostack));
        }
    }

    // Save old context and restore new context
    // We save/restore callee-saved registers + RSP + RIP
    context_switch_asm(
        &mut CONTEXTS[old_idx] as *mut CpuContext,
        &CONTEXTS[new_idx] as *const CpuContext,
    );
}

/// Assembly context switch: save callee-saved regs to old, restore from new.
///
/// # Safety
/// Both pointers must be valid CpuContext structures.
#[inline(never)]
unsafe fn context_switch_asm(old: *mut CpuContext, new: *const CpuContext) {
    core::arch::asm!(
        // Save callee-saved registers to old context
        "mov [rdi + 0x00], rbx",
        "mov [rdi + 0x08], rbp",
        "mov [rdi + 0x10], r12",
        "mov [rdi + 0x18], r13",
        "mov [rdi + 0x20], r14",
        "mov [rdi + 0x28], r15",
        "mov [rdi + 0x30], rsp",
        // Save return address as RIP
        "lea rax, [rip + 2f]",
        "mov [rdi + 0x38], rax",

        // Restore callee-saved registers from new context
        "mov rbx, [rsi + 0x00]",
        "mov rbp, [rsi + 0x08]",
        "mov r12, [rsi + 0x10]",
        "mov r13, [rsi + 0x18]",
        "mov r14, [rsi + 0x20]",
        "mov r15, [rsi + 0x28]",
        "mov rsp, [rsi + 0x30]",

        // Jump to new task's saved RIP
        "jmp [rsi + 0x38]",

        // Return point for the old task when it resumes
        "2:",

        in("rdi") old,
        in("rsi") new,
        // Clobber caller-saved registers
        out("rax") _,
        out("rcx") _,
        out("rdx") _,
        out("r8") _,
        out("r9") _,
        out("r10") _,
        out("r11") _,
        options(nostack),
    );
}

/// Timer-driven preemptive switch (called from timer IRQ handler).
pub fn timer_preempt() {
    let current = CURRENT_TASK.load(Ordering::Relaxed);

    // Ask scheduler for next task
    if let Some(next) = crate::scheduler::Scheduler::new().next() {
        if next != current {
            unsafe { switch(current, next); }
        }
    }
}

fn print_u64(mut n: u64) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 20];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}

fn print_hex64(val: u64) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut buf = [0u8; 16];
    for (i, slot) in buf.iter_mut().enumerate().rev() {
        *slot = HEX[((val >> (i * 4)) & 0xF) as usize];
    }
    crate::serial::print(&buf);
}
