#![allow(dead_code)]

//! POSIX-style signals for Daisy OS.
//!
//! Supports basic signal delivery: SIGTERM, SIGKILL, SIGINT, SIGCHLD, etc.

use core::sync::atomic::{AtomicU64, Ordering};

/// Signal numbers (POSIX subset).
#[derive(Debug, Clone, Copy, PartialEq)]
#[repr(u8)]
pub enum Signal {
    SIGHUP    = 1,
    SIGINT    = 2,
    SIGQUIT   = 3,
    SIGILL    = 4,
    SIGTRAP   = 5,
    SIGABRT   = 6,
    SIGBUS    = 7,
    SIGFPE    = 8,
    SIGKILL   = 9,
    SIGUSR1   = 10,
    SIGSEGV   = 11,
    SIGUSR2   = 12,
    SIGPIPE   = 13,
    SIGALRM   = 14,
    SIGTERM   = 15,
    SIGCHLD   = 17,
    SIGCONT   = 18,
    SIGSTOP   = 19,
    SIGTSTP   = 20,
}

impl Signal {
    pub fn from_num(n: u8) -> Option<Self> {
        match n {
            1 => Some(Self::SIGHUP),
            2 => Some(Self::SIGINT),
            3 => Some(Self::SIGQUIT),
            4 => Some(Self::SIGILL),
            5 => Some(Self::SIGTRAP),
            6 => Some(Self::SIGABRT),
            7 => Some(Self::SIGBUS),
            8 => Some(Self::SIGFPE),
            9 => Some(Self::SIGKILL),
            10 => Some(Self::SIGUSR1),
            11 => Some(Self::SIGSEGV),
            12 => Some(Self::SIGUSR2),
            13 => Some(Self::SIGPIPE),
            14 => Some(Self::SIGALRM),
            15 => Some(Self::SIGTERM),
            17 => Some(Self::SIGCHLD),
            18 => Some(Self::SIGCONT),
            19 => Some(Self::SIGSTOP),
            20 => Some(Self::SIGTSTP),
            _ => None,
        }
    }

    /// Is this signal fatal by default?
    pub fn is_fatal(&self) -> bool {
        matches!(self,
            Signal::SIGHUP | Signal::SIGINT | Signal::SIGQUIT | Signal::SIGILL |
            Signal::SIGABRT | Signal::SIGBUS | Signal::SIGFPE | Signal::SIGKILL |
            Signal::SIGSEGV | Signal::SIGPIPE | Signal::SIGALRM | Signal::SIGTERM
        )
    }

    /// Can this signal be caught/ignored?
    pub fn is_catchable(&self) -> bool {
        !matches!(self, Signal::SIGKILL | Signal::SIGSTOP)
    }
}

/// Signal action for a task.
#[derive(Clone, Copy, PartialEq)]
pub enum SigAction {
    Default,
    Ignore,
    Handler(u64), // user-space handler address
}

/// Maximum tasks for signal tracking.
const MAX_TASKS: usize = 64;
/// Maximum signals (use bitmask in u64).
const MAX_SIGNAL: usize = 32;

/// Per-task signal state.
struct TaskSignals {
    /// Pending signals (bitmask).
    pending: AtomicU64,
    /// Signal mask (blocked signals bitmask).
    mask: AtomicU64,
    /// Signal actions.
    actions: [SigAction; MAX_SIGNAL],
}

impl TaskSignals {
    const fn new() -> Self {
        Self {
            pending: AtomicU64::new(0),
            mask: AtomicU64::new(0),
            actions: [SigAction::Default; MAX_SIGNAL],
        }
    }
}

static mut TASK_SIGNALS: [TaskSignals; MAX_TASKS] = {
    const TS: TaskSignals = TaskSignals::new();
    [TS; MAX_TASKS]
};

/// Send a signal to a task.
pub fn send(task_id: u64, sig: Signal) -> Result<(), &'static str> {
    let idx = task_id as usize;
    if idx >= MAX_TASKS {
        return Err("invalid task");
    }
    let sig_bit = 1u64 << (sig as u8);
    // SAFETY: idx < MAX_TASKS; atomic operation is safe.
    unsafe { TASK_SIGNALS[idx].pending.fetch_or(sig_bit, Ordering::Release); }
    Ok(())
}

/// Check and dequeue the next pending signal for a task.
pub fn dequeue(task_id: u64) -> Option<Signal> {
    let idx = task_id as usize;
    if idx >= MAX_TASKS { return None; }
    // SAFETY: idx < MAX_TASKS.
    unsafe {
        let pending = TASK_SIGNALS[idx].pending.load(Ordering::Acquire);
        let mask   = TASK_SIGNALS[idx].mask.load(Ordering::Acquire);
        let deliverable = pending & !mask;
        if deliverable == 0 { return None; }
        let bit = deliverable.trailing_zeros();
        TASK_SIGNALS[idx].pending.fetch_and(!(1u64 << bit), Ordering::Release);
        Signal::from_num(bit as u8)
    }
}

/// Set signal action for a task.
pub fn set_action(task_id: u64, sig: Signal, action: SigAction) -> Result<(), &'static str> {
    if !sig.is_catchable() {
        return Err("cannot catch SIGKILL/SIGSTOP");
    }

    let idx = task_id as usize;
    if idx >= MAX_TASKS {
        return Err("invalid task");
    }

    unsafe {
        TASK_SIGNALS[idx].actions[sig as u8 as usize] = action;
    }
    Ok(())
}

/// Get the action for a signal on a task.
pub fn get_action(task_id: u64, sig: Signal) -> SigAction {
    let idx = task_id as usize;
    if idx >= MAX_TASKS {
        return SigAction::Default;
    }
    unsafe { TASK_SIGNALS[idx].actions[sig as u8 as usize] }
}

/// Block signals (add to mask).
pub fn block(task_id: u64, signals: u64) {
    let idx = task_id as usize;
    if idx < MAX_TASKS {
        unsafe {
            TASK_SIGNALS[idx].mask.fetch_or(signals, Ordering::Relaxed);
        }
    }
}

/// Unblock signals (remove from mask).
pub fn unblock(task_id: u64, signals: u64) {
    let idx = task_id as usize;
    if idx < MAX_TASKS {
        unsafe {
            TASK_SIGNALS[idx].mask.fetch_and(!signals, Ordering::Relaxed);
        }
    }
}

/// Check if a task has pending signals.
pub fn has_pending(task_id: u64) -> bool {
    let idx = task_id as usize;
    if idx >= MAX_TASKS { return false; }
    unsafe {
        let pending = TASK_SIGNALS[idx].pending.load(Ordering::Relaxed);
        let mask = TASK_SIGNALS[idx].mask.load(Ordering::Relaxed);
        (pending & !mask) != 0
    }
}

