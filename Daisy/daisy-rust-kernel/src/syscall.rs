#![allow(dead_code)]

//! x86_64 syscall/sysret setup for Daisy OS.
//! Configures STAR, LSTAR, FMASK MSRs and provides a dispatch table.

use core::sync::atomic::{AtomicU64, Ordering};

const MSR_STAR: u32 = 0xC000_0081;
const MSR_LSTAR: u32 = 0xC000_0082;
const MSR_FMASK: u32 = 0xC000_0084;
const MSR_EFER: u32 = 0xC000_0080;

static NEXT_PID: AtomicU64 = AtomicU64::new(1);

#[inline]
unsafe fn wrmsr(msr: u32, val: u64) {
    let lo = val as u32;
    let hi = (val >> 32) as u32;
    core::arch::asm!("wrmsr", in("ecx") msr, in("eax") lo, in("edx") hi, options(nomem, nostack));
}

#[inline]
unsafe fn rdmsr(msr: u32) -> u64 {
    let lo: u32;
    let hi: u32;
    core::arch::asm!("rdmsr", in("ecx") msr, out("eax") lo, out("edx") hi, options(nomem, nostack));
    (hi as u64) << 32 | lo as u64
}

/// Initialize syscall/sysret MSRs.
pub fn init() {
    unsafe {
        // Enable SCE (System Call Extensions) in EFER
        let efer = rdmsr(MSR_EFER);
        wrmsr(MSR_EFER, efer | 1);

        // STAR: kernel CS/SS in bits 32-47, user CS/SS in bits 48-63
        // Kernel CS=0x08, SS=0x10, User CS=0x18|3, SS=0x20|3
        let star = (0x08u64 << 32) | (0x18u64 << 48);
        wrmsr(MSR_STAR, star);

        // LSTAR: syscall entry point address
        wrmsr(MSR_LSTAR, syscall_entry as u64);

        // FMASK: clear IF (bit 9) on syscall entry
        wrmsr(MSR_FMASK, 0x200);
    }
    crate::serial::print(b"[syscall] MSRs configured\n");
}

/// Syscall entry — called by the CPU on `syscall` instruction.
#[unsafe(naked)]
extern "C" fn syscall_entry() {
    unsafe {
        core::arch::naked_asm!(
            // rcx = user RIP, r11 = user RFLAGS (saved by CPU)
            // rax = syscall number
            "push rcx",        // save user RIP
            "push r11",        // save user RFLAGS
            "push rbp",
            "push rbx",
            "push r12",
            "push r13",
            "push r14",
            "push r15",
            "mov rdi, rax",    // arg0 = syscall number
            "mov rsi, rdi",    // arg1 = original rdi (first user arg)
            "call {dispatch}",
            "pop r15",
            "pop r14",
            "pop r13",
            "pop r12",
            "pop rbx",
            "pop rbp",
            "pop r11",         // restore RFLAGS
            "pop rcx",         // restore RIP
            "sysretq",
            dispatch = sym dispatch,
        );
    }
}

/// Dispatch syscall by number. Returns result in rax.
extern "C" fn dispatch(num: u64, _arg1: u64) -> u64 {
    match num {
        0 => sys_exit(),
        1 => sys_write(),
        2 => sys_read(),
        5 => sys_getpid(),
        _ => {
            crate::serial::print(b"[syscall] unknown: ");
            crate::serial::write_byte(b'0' + (num % 10) as u8);
            crate::serial::print(b"\n");
            !0 // error value
        }
    }
}

fn sys_exit() -> u64 {
    crate::serial::print(b"[syscall] exit\n");
    0
}

fn sys_write() -> u64 {
    crate::serial::print(b"[syscall] write\n");
    0
}

fn sys_read() -> u64 {
    crate::serial::print(b"[syscall] read\n");
    0
}

fn sys_getpid() -> u64 {
    NEXT_PID.fetch_add(1, Ordering::Relaxed)
}
