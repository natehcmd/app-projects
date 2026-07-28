#![allow(dead_code)]

//! Local APIC timer driver for Daisy OS.
//!
//! Detects LAPIC from MSR, calibrates timer against PIT,
//! and provides periodic timer interrupts.

use core::sync::atomic::{AtomicU32, AtomicU64, Ordering};

// LAPIC register offsets (relative to LAPIC base)
const LAPIC_ID: u32          = 0x020;
const LAPIC_VERSION: u32     = 0x030;
const LAPIC_TPR: u32         = 0x080;
const LAPIC_EOI: u32         = 0x0B0;
const LAPIC_SVR: u32         = 0x0F0;
const LAPIC_ICR_LO: u32      = 0x300;
const LAPIC_ICR_HI: u32      = 0x310;
const LAPIC_TIMER_LVT: u32   = 0x320;
const LAPIC_TIMER_INIT: u32  = 0x380;
const LAPIC_TIMER_CURRENT: u32 = 0x390;
const LAPIC_TIMER_DIV: u32   = 0x3E0;

// SVR bits
const SVR_ENABLE: u32 = 1 << 8;
const SVR_VECTOR: u32 = 0xFF;  // Spurious vector = 0xFF

// Timer LVT bits
const TIMER_PERIODIC: u32 = 1 << 17;
const TIMER_MASKED: u32   = 1 << 16;

// PIT constants for calibration
const PIT_CH2_DATA: u16 = 0x42;
const PIT_CMD: u16 = 0x43;
const PIT_FREQ: u32 = 1193182;

// MSR addresses
const IA32_APIC_BASE_MSR: u32 = 0x1B;

/// LAPIC base address (detected at init).
static LAPIC_BASE: AtomicU64 = AtomicU64::new(0);

/// Ticks per millisecond (calibrated).
static TICKS_PER_MS: AtomicU32 = AtomicU32::new(0);

/// APIC timer tick counter.
static APIC_TICKS: AtomicU64 = AtomicU64::new(0);

#[inline]
unsafe fn outb(port: u16, val: u8) {
    core::arch::asm!("out dx, al", in("dx") port, in("al") val, options(nomem, nostack));
}

#[inline]
unsafe fn inb(port: u16) -> u8 {
    let val: u8;
    core::arch::asm!("in al, dx", in("dx") port, out("al") val, options(nomem, nostack));
    val
}

#[inline]
unsafe fn rdmsr(msr: u32) -> u64 {
    let lo: u32;
    let hi: u32;
    core::arch::asm!(
        "rdmsr",
        in("ecx") msr,
        out("eax") lo,
        out("edx") hi,
        options(nomem, nostack),
    );
    ((hi as u64) << 32) | (lo as u64)
}

/// Read a 32-bit LAPIC register via MMIO.
#[inline]
unsafe fn lapic_read(offset: u32) -> u32 {
    let base = LAPIC_BASE.load(Ordering::Relaxed) as usize;
    core::ptr::read_volatile((base + offset as usize) as *const u32)
}

/// Write a 32-bit LAPIC register via MMIO.
#[inline]
unsafe fn lapic_write(offset: u32, val: u32) {
    let base = LAPIC_BASE.load(Ordering::Relaxed) as usize;
    core::ptr::write_volatile((base + offset as usize) as *mut u32, val);
}

/// Detect and enable the Local APIC.
///
/// # Safety
/// Must be called once during kernel init, with interrupts disabled.
pub unsafe fn init() {
    // Read APIC base from MSR
    let msr = rdmsr(IA32_APIC_BASE_MSR);
    let base = msr & 0xFFFF_F000; // Mask to page-aligned base
    let enabled = msr & (1 << 11) != 0;

    if !enabled {
        crate::serial::print(b"[apic] LAPIC not enabled in MSR\n");
        return;
    }

    LAPIC_BASE.store(base, Ordering::Relaxed);

    crate::serial::print(b"[apic] LAPIC base: 0x");
    print_hex64(base);
    crate::serial::print(b"\n");

    // Read version
    let ver = lapic_read(LAPIC_VERSION);
    let max_lvt = ((ver >> 16) & 0xFF) + 1;
    crate::serial::print(b"[apic] Version: ");
    print_u32(ver & 0xFF);
    crate::serial::print(b", max LVT: ");
    print_u32(max_lvt);
    crate::serial::print(b"\n");

    // Set spurious interrupt vector and enable LAPIC
    lapic_write(LAPIC_SVR, SVR_ENABLE | SVR_VECTOR);

    // Set task priority to 0 (accept all interrupts)
    lapic_write(LAPIC_TPR, 0);

    crate::serial::print(b"[apic] LAPIC enabled\n");
}

/// Calibrate the APIC timer using PIT channel 2 (10ms one-shot).
///
/// # Safety
/// Must be called after `init()`. Interrupts should be disabled.
pub unsafe fn calibrate_timer(target_hz: u32) {
    let base = LAPIC_BASE.load(Ordering::Relaxed);
    if base == 0 {
        crate::serial::print(b"[apic] Cannot calibrate: LAPIC not initialized\n");
        return;
    }

    // Set APIC timer divisor to 16
    lapic_write(LAPIC_TIMER_DIV, 0x03); // divide by 16

    // Mask the timer during calibration
    lapic_write(LAPIC_TIMER_LVT, TIMER_MASKED);

    // Set up PIT channel 2 for a 10ms one-shot
    let pit_count: u16 = (PIT_FREQ / 100) as u16; // ~10ms

    // Gate off, speaker off, channel 2 mode
    let port61 = inb(0x61);
    outb(0x61, (port61 & 0xFC) | 0x01); // enable gate, disable speaker

    // PIT channel 2, mode 0 (one-shot), binary
    outb(PIT_CMD, 0xB0);
    outb(PIT_CH2_DATA, (pit_count & 0xFF) as u8);
    outb(PIT_CH2_DATA, ((pit_count >> 8) & 0xFF) as u8);

    // Start APIC timer with max initial count
    lapic_write(LAPIC_TIMER_INIT, 0xFFFF_FFFF);

    // Wait for PIT to count down (bit 5 of port 0x61 goes high)
    // Timeout after ~100ms to avoid deadlock if PIT doesn't fire
    let mut timeout = 10_000_000u32;
    while inb(0x61) & 0x20 == 0 {
        timeout -= 1;
        if timeout == 0 {
            crate::serial::print(b"[apic] PIT calibration timeout\n");
            lapic_write(LAPIC_TIMER_LVT, TIMER_MASKED);
            return;
        }
        core::hint::spin_loop();
    }

    // Stop APIC timer
    lapic_write(LAPIC_TIMER_LVT, TIMER_MASKED);

    // Calculate ticks elapsed in 10ms
    let remaining = lapic_read(LAPIC_TIMER_CURRENT);
    let elapsed = 0xFFFF_FFFFu32 - remaining;
    let ticks_per_ms = elapsed / 10; // since we timed 10ms

    TICKS_PER_MS.store(ticks_per_ms, Ordering::Relaxed);

    crate::serial::print(b"[apic] Calibrated: ");
    print_u32(ticks_per_ms);
    crate::serial::print(b" ticks/ms\n");

    // Now set up periodic mode at target_hz
    if target_hz == 0 {
        crate::serial::print(b"[apic] WARNING: target_hz is 0, not starting timer\n");
        return;
    }

    // Calculate init count: ticks_per_ms * (1000 / target_hz)
    // Use multiplication first to avoid truncation for high frequencies
    let init_count = (ticks_per_ms as u64 * 1000 / target_hz as u64) as u32;
    let init_count = if init_count == 0 { 1 } else { init_count };

    // Timer vector 0x20, periodic mode
    lapic_write(LAPIC_TIMER_LVT, 0x20 | TIMER_PERIODIC);
    lapic_write(LAPIC_TIMER_DIV, 0x03); // divide by 16
    lapic_write(LAPIC_TIMER_INIT, init_count);

    crate::serial::print(b"[apic] Timer started at ");
    print_u32(target_hz);
    crate::serial::print(b" Hz (init_count=");
    print_u32(init_count);
    crate::serial::print(b")\n");

    // Restore port 0x61
    outb(0x61, port61);
}

/// Called from the APIC timer interrupt handler (vector 0x20).
pub fn handle_irq() {
    APIC_TICKS.fetch_add(1, Ordering::Relaxed);
}

/// Get the current APIC timer tick count.
pub fn ticks() -> u64 {
    APIC_TICKS.load(Ordering::Relaxed)
}

/// Read the current APIC timer countdown value.
pub fn read_timer_count() -> u32 {
    if LAPIC_BASE.load(Ordering::Relaxed) == 0 {
        return 0;
    }
    unsafe { lapic_read(LAPIC_TIMER_CURRENT) }
}

/// Send end-of-interrupt to the LAPIC.
pub fn send_eoi() {
    if LAPIC_BASE.load(Ordering::Relaxed) == 0 {
        return;
    }
    unsafe { lapic_write(LAPIC_EOI, 0); }
}

fn print_hex64(val: u64) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut buf = [0u8; 16];
    for (i, slot) in buf.iter_mut().enumerate().rev() {
        *slot = HEX[((val >> (i * 4)) & 0xF) as usize];
    }
    crate::serial::print(&buf);
}

fn print_u32(mut n: u32) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 10];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}
