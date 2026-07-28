#![allow(dead_code)]

//! PIT (Programmable Interval Timer) driver for Daisy OS.
//!
//! Configures channel 0 of the 8253/8254 PIT for periodic interrupts.
//! Used for preemptive scheduling until APIC timer is available.

use core::sync::atomic::{AtomicU64, Ordering};

const PIT_CH0_DATA: u16 = 0x40;
const PIT_CMD: u16 = 0x43;
const PIT_FREQUENCY: u32 = 1193182; // Base oscillator frequency in Hz

/// Global tick counter, incremented on every timer IRQ.
static TICKS: AtomicU64 = AtomicU64::new(0);

/// Configured timer frequency.
static TIMER_HZ: AtomicU64 = AtomicU64::new(0);

#[inline]
unsafe fn outb(port: u16, val: u8) {
    core::arch::asm!("out dx, al", in("dx") port, in("al") val, options(nomem, nostack));
}

/// Initialize PIT channel 0 at the given frequency (Hz).
/// Common values: 100 (10ms ticks), 1000 (1ms ticks).
pub fn init(hz: u32) {
    if hz == 0 {
        crate::serial::print(b"[timer] ERROR: hz must be > 0\n");
        return;
    }
    let divisor = (PIT_FREQUENCY / hz).clamp(1, 65535);

    TIMER_HZ.store(hz as u64, Ordering::Relaxed);

    unsafe {
        // Channel 0, access mode lo/hi, mode 2 (rate generator), binary
        outb(PIT_CMD, 0x34);
        // Low byte of divisor
        outb(PIT_CH0_DATA, (divisor & 0xFF) as u8);
        // High byte of divisor
        outb(PIT_CH0_DATA, ((divisor >> 8) & 0xFF) as u8);
    }

    crate::serial::print(b"[timer] PIT initialized at ");
    // Print frequency to serial (simple decimal)
    print_u32(hz);
    crate::serial::print(b" Hz\n");
}

/// Called from IRQ0 handler. Increments the tick counter.
pub fn handle_irq() {
    TICKS.fetch_add(1, Ordering::Relaxed);
}

/// Get the current tick count.
pub fn ticks() -> u64 {
    TICKS.load(Ordering::Relaxed)
}

/// Get uptime in milliseconds.
pub fn uptime_ms() -> u64 {
    let hz = TIMER_HZ.load(Ordering::Relaxed);
    if hz == 0 { return 0; }
    (TICKS.load(Ordering::Relaxed) * 1000) / hz
}

/// Get uptime in seconds.
pub fn uptime_secs() -> u64 {
    let hz = TIMER_HZ.load(Ordering::Relaxed);
    if hz == 0 { return 0; }
    TICKS.load(Ordering::Relaxed) / hz
}

/// Busy-wait for the given number of milliseconds.
pub fn sleep_ms(ms: u64) {
    let target = uptime_ms() + ms;
    while uptime_ms() < target {
        core::hint::spin_loop();
    }
}

fn print_u32(mut n: u32) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 10];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}
