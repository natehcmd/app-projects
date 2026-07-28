//! 8259 PIC (Programmable Interrupt Controller) driver for Daisy OS.
//!
//! Remaps the two cascaded 8259 PICs so that IRQ 0-7 map to vectors 32-39
//! and IRQ 8-15 map to vectors 40-47, avoiding conflicts with CPU exceptions.

#![allow(dead_code)]

/// Base vector for the master PIC (IRQ 0-7).
pub const PIC1_OFFSET: u8 = 32;
/// Base vector for the slave PIC (IRQ 8-15).
pub const PIC2_OFFSET: u8 = 40;

// 8259 port addresses
const PIC1_COMMAND: u16 = 0x20;
const PIC1_DATA: u16 = 0x21;
const PIC2_COMMAND: u16 = 0xA0;
const PIC2_DATA: u16 = 0xA1;

// ICW1 flags
const ICW1_INIT: u8 = 0x10;
const ICW1_ICW4: u8 = 0x01;

// ICW4 flags
const ICW4_8086: u8 = 0x01;

// OCW2 — End of Interrupt
const EOI: u8 = 0x20;

// ---------------------------------------------------------------------------
// Minimal port I/O helpers (no external crate needed)
// ---------------------------------------------------------------------------

#[inline(always)]
unsafe fn outb(port: u16, val: u8) {
    core::arch::asm!(
        "out dx, al",
        in("dx") port,
        in("al") val,
        options(nomem, nostack, preserves_flags),
    );
}

#[inline(always)]
unsafe fn inb(port: u16) -> u8 {
    let val: u8;
    core::arch::asm!(
        "in al, dx",
        in("dx") port,
        out("al") val,
        options(nomem, nostack, preserves_flags),
    );
    val
}

/// Short I/O delay (the traditional approach: write to port 0x80).
#[inline(always)]
unsafe fn io_wait() {
    outb(0x80, 0);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Initialise both 8259 PICs with the standard cascade configuration and
/// remap IRQs to vectors 32-47.  All IRQs are masked except the cascade
/// line (IRQ 2 on master) so that callers can selectively unmask what they
/// need.
pub fn init() {
    unsafe {
        // Save current masks
        let mask1 = inb(PIC1_DATA);
        let mask2 = inb(PIC2_DATA);

        // ICW1: begin initialisation sequence (cascade, ICW4 needed)
        outb(PIC1_COMMAND, ICW1_INIT | ICW1_ICW4);
        io_wait();
        outb(PIC2_COMMAND, ICW1_INIT | ICW1_ICW4);
        io_wait();

        // ICW2: vector offsets
        outb(PIC1_DATA, PIC1_OFFSET);
        io_wait();
        outb(PIC2_DATA, PIC2_OFFSET);
        io_wait();

        // ICW3: cascade wiring — master has slave on IRQ 2, slave cascade id 2
        outb(PIC1_DATA, 0x04); // bit 2 = IRQ2 has a slave
        io_wait();
        outb(PIC2_DATA, 0x02); // slave cascade identity
        io_wait();

        // ICW4: 8086 mode
        outb(PIC1_DATA, ICW4_8086);
        io_wait();
        outb(PIC2_DATA, ICW4_8086);
        io_wait();

        // Restore saved masks (or mask everything initially)
        // We mask everything except the cascade line (IRQ2) so the slave
        // PIC can still signal the master.
        outb(PIC1_DATA, 0xFB); // all masked except IRQ2
        outb(PIC2_DATA, 0xFF); // all masked
    }
}

/// Send an End-Of-Interrupt signal for the given IRQ number (0-15).
///
/// If the IRQ came from the slave PIC (8-15) we must send EOI to *both*
/// the slave and the master.
pub fn send_eoi(irq: u8) {
    unsafe {
        if irq >= 8 {
            outb(PIC2_COMMAND, EOI);
        }
        outb(PIC1_COMMAND, EOI);
    }
}

/// Unmask (enable) a specific IRQ line (0-15).
pub fn unmask(irq: u8) {
    unsafe {
        if irq < 8 {
            let mask = inb(PIC1_DATA) & !(1 << irq);
            outb(PIC1_DATA, mask);
        } else {
            let mask = inb(PIC2_DATA) & !(1 << (irq - 8));
            outb(PIC2_DATA, mask);
        }
    }
}

/// Mask (disable) a specific IRQ line (0-15).
pub fn mask(irq: u8) {
    unsafe {
        if irq < 8 {
            let mask = inb(PIC1_DATA) | (1 << irq);
            outb(PIC1_DATA, mask);
        } else {
            let mask = inb(PIC2_DATA) | (1 << (irq - 8));
            outb(PIC2_DATA, mask);
        }
    }
}

/// Disable both PICs entirely by masking all IRQs.
pub fn disable() {
    unsafe {
        outb(PIC1_DATA, 0xFF);
        outb(PIC2_DATA, 0xFF);
    }
}
