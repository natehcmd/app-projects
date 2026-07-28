#![allow(dead_code)]

//! Syscall dispatch table for Daisy OS.
//!
//! Maps Linux-compatible syscall numbers to kernel handlers.
//! Syscalls: read(0), write(1), open(2), close(3), getpid(39),
//! exit(60), uname(63), gettimeofday(96), sched_yield(24).

#[derive(Clone, Copy, PartialEq)]
enum SyscallId {
    Read,
    Write,
    Open,
    Close,
    Getpid,
    Exit,
    SchedYield,
    Uname,
    Gettimeofday,
}

/// Sparse table: index = syscall number, value = handler id.
/// Linux x86_64 syscall numbers:
///   read=0, write=1, open=2, close=3, sched_yield=24,
///   getpid=39, exit=60, uname=63, gettimeofday=96
const MAX_SYSCALL: usize = 160;

static SYSCALL_TABLE: [Option<SyscallId>; MAX_SYSCALL] = {
    let mut table: [Option<SyscallId>; MAX_SYSCALL] = [None; MAX_SYSCALL];
    table[0] = Some(SyscallId::Read);
    table[1] = Some(SyscallId::Write);
    table[2] = Some(SyscallId::Open);
    table[3] = Some(SyscallId::Close);
    table[24] = Some(SyscallId::SchedYield);
    table[39] = Some(SyscallId::Getpid);
    table[60] = Some(SyscallId::Exit);
    table[63] = Some(SyscallId::Uname);
    table[96] = Some(SyscallId::Gettimeofday);
    table
};

/// Dispatch a syscall by number.
///
/// Arguments follow the Linux x86_64 ABI:
///   a0..a5 = rdi, rsi, rdx, r10, r8, r9
///
/// Returns the syscall result (negative = errno).
pub fn dispatch(num: u64, a0: u64, a1: u64, a2: u64, _a3: u64, _a4: u64, _a5: u64) -> i64 {
    let idx = num as usize;
    if idx >= MAX_SYSCALL {
        return -38; // ENOSYS
    }

    match SYSCALL_TABLE[idx] {
        Some(SyscallId::Read) => sys_read(a0, a1, a2),
        Some(SyscallId::Write) => sys_write(a0, a1, a2),
        Some(SyscallId::Open) => sys_open(),
        Some(SyscallId::Close) => sys_close(),
        Some(SyscallId::SchedYield) => sys_sched_yield(),
        Some(SyscallId::Getpid) => sys_getpid(),
        Some(SyscallId::Exit) => sys_exit(),
        Some(SyscallId::Uname) => sys_uname(a0),
        Some(SyscallId::Gettimeofday) => sys_gettimeofday(a0),
        None => -38, // ENOSYS
    }
}

/// sys_read: fd=a0. For fd 0 (stdin), read one key from keyboard.
fn sys_read(fd: u64, buf_ptr: u64, count: u64) -> i64 {
    if fd != 0 || count == 0 {
        return -9; // EBADF for non-stdin
    }
    let key = unsafe { crate::keyboard::read_key() };
    match key {
        Some(byte) => {
            unsafe {
                let ptr = buf_ptr as *mut u8;
                *ptr = byte;
            }
            1
        }
        None => 0, // no key available
    }
}

/// sys_write: fd=a0, buf=a1, count=a2. Writes to serial for fd 1 (stdout) or 2 (stderr).
fn sys_write(fd: u64, buf_ptr: u64, count: u64) -> i64 {
    match fd {
        1 | 2 => {
            // SAFETY: caller guarantees buf_ptr points to count valid bytes.
            unsafe {
                let buf = core::slice::from_raw_parts(buf_ptr as *const u8, count as usize);
                crate::serial::print(buf);
            }
            count as i64
        }
        _ => -9, // EBADF
    }
}

/// sys_open: stub, logs and returns 0.
fn sys_open() -> i64 {
    crate::serial::print(b"[syscall] open stub\n");
    0
}

/// sys_close: stub, logs and returns 0.
fn sys_close() -> i64 {
    crate::serial::print(b"[syscall] close stub\n");
    0
}

/// sys_getpid: returns current task id.
fn sys_getpid() -> i64 {
    crate::context::current() as i64
}

/// sys_exit: halts the current task (spins forever for now).
fn sys_exit() -> i64 {
    crate::serial::print(b"[syscall] exit called\n");
    loop {
        core::hint::spin_loop();
    }
}

/// sys_uname: writes "DaisyOS\0" to the user buffer at a0.
fn sys_uname(buf_ptr: u64) -> i64 {
    const UNAME: &[u8] = b"DaisyOS\0";
    unsafe {
        core::ptr::copy_nonoverlapping(UNAME.as_ptr(), buf_ptr as *mut u8, UNAME.len());
    }
    0
}

/// sys_gettimeofday: writes uptime_ms as u64 to the user buffer at a0.
fn sys_gettimeofday(buf_ptr: u64) -> i64 {
    let ms = crate::timer::uptime_ms();
    unsafe {
        *(buf_ptr as *mut u64) = ms;
    }
    0
}

/// sys_sched_yield: yields the current timeslice.
fn sys_sched_yield() -> i64 {
    crate::context::timer_preempt();
    0
}
