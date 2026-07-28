#![allow(dead_code)]

//! SMP (Symmetric Multi-Processing) for Daisy OS.

use core::sync::atomic::{AtomicU32, Ordering};

static AP_COUNT: AtomicU32 = AtomicU32::new(0);

pub fn detect_cpus() -> u32 {
    let lo: u32;
    let hi: u32;
    unsafe {
        core::arch::asm!(
            "rdmsr",
            in("ecx") 0x1Bu32,
            out("eax") lo,
            out("edx") hi,
            options(nomem, nostack),
        );
    }
    let lapic_base = ((hi as u64) << 32) | (lo as u64);
    crate::serial::print(b"[smp] LAPIC base: 0x");
    print_hex64(lapic_base & 0xFFFF_F000);
    crate::serial::print(b"\n");

    // Placeholder: return 1 CPU for now
    // Real detection requires parsing ACPI MADT for LAPIC entries
    1
}

pub fn init() {
    let cpus = detect_cpus();
    crate::serial::print(b"[smp] ");
    print_u32(cpus);
    crate::serial::print(b" CPU(s) detected\n");

    if cpus > 1 {
        crate::serial::print(b"[smp] AP boot not yet implemented\n");
    }
}

pub fn cpu_count() -> u32 {
    AP_COUNT.load(Ordering::Relaxed) + 1
}

fn print_u32(mut n: u32) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 10];
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
