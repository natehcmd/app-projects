#![allow(dead_code)]

use core::sync::atomic::{AtomicU8, Ordering};

const PS2_DATA: u16 = 0x60;
const PS2_STATUS: u16 = 0x64;
const PS2_CMD: u16 = 0x64;

// Circular key buffer
const KEY_BUF_SIZE: usize = 64;
static KEY_BUF: [AtomicU8; KEY_BUF_SIZE] = {
    const INIT: AtomicU8 = AtomicU8::new(0);
    [INIT; KEY_BUF_SIZE]
};
static KEY_HEAD: AtomicU8 = AtomicU8::new(0);
static KEY_TAIL: AtomicU8 = AtomicU8::new(0);

// Modifier state
static SHIFT_HELD: AtomicU8 = AtomicU8::new(0);
static CTRL_HELD: AtomicU8 = AtomicU8::new(0);
static ALT_HELD: AtomicU8 = AtomicU8::new(0);

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

/// Wait for PS/2 controller input buffer to be empty.
fn wait_write() {
    for _ in 0..10000 {
        unsafe {
            if inb(PS2_STATUS) & 0x02 == 0 {
                return;
            }
        }
        core::hint::spin_loop();
    }
}

/// Wait for PS/2 controller output buffer to have data.
fn wait_read() -> bool {
    for _ in 0..10000 {
        unsafe {
            if inb(PS2_STATUS) & 0x01 != 0 {
                return true;
            }
        }
        core::hint::spin_loop();
    }
    false
}

/// Initialize PS/2 keyboard controller.
pub fn init() {
    unsafe {
        // Disable both PS/2 ports
        wait_write();
        outb(PS2_CMD, 0xAD);
        wait_write();
        outb(PS2_CMD, 0xA7);

        // Flush output buffer
        let _ = inb(PS2_DATA);

        // Read config byte
        wait_write();
        outb(PS2_CMD, 0x20);
        if wait_read() {
            let config = inb(PS2_DATA);
            // Enable port 1 IRQ (bit 0), disable port 2 IRQ (bit 1), disable translation (bit 6)
            let new_config = (config | 0x01) & !0x42;
            wait_write();
            outb(PS2_CMD, 0x60);
            wait_write();
            outb(PS2_DATA, new_config);
        }

        // Self test
        wait_write();
        outb(PS2_CMD, 0xAA);
        if wait_read() {
            let result = inb(PS2_DATA);
            if result != 0x55 {
                crate::serial::print(b"[kbd] PS/2 controller self-test failed\n");
                return;
            }
        }

        // Enable port 1
        wait_write();
        outb(PS2_CMD, 0xAE);

        // Reset keyboard
        wait_write();
        outb(PS2_DATA, 0xFF);
        if wait_read() {
            let _ = inb(PS2_DATA); // ACK
        }

        // Use scancode set 1 (matches our decode tables in handle_irq)
        // Note: we disabled translation (bit 6) above, and our tables are set 1,
        // so we explicitly request set 1 from the keyboard.
        wait_write();
        outb(PS2_DATA, 0xF0);
        wait_write();
        outb(PS2_DATA, 0x01);

        // Enable scanning
        wait_write();
        outb(PS2_DATA, 0xF4);

        crate::serial::print(b"[kbd] PS/2 keyboard initialized\n");
    }
}

/// Called from IRQ1 handler. Reads scancode and buffers the key.
pub fn handle_irq() {
    let scancode = unsafe { inb(PS2_DATA) };

    // Handle modifier keys
    match scancode {
        0x2A | 0x36 => { SHIFT_HELD.store(1, Ordering::Relaxed); return; }
        0xAA | 0xB6 => { SHIFT_HELD.store(0, Ordering::Relaxed); return; }
        0x1D => { CTRL_HELD.store(1, Ordering::Relaxed); return; }
        0x9D => { CTRL_HELD.store(0, Ordering::Relaxed); return; }
        0x38 => { ALT_HELD.store(1, Ordering::Relaxed); return; }
        0xB8 => { ALT_HELD.store(0, Ordering::Relaxed); return; }
        _ => {}
    }

    // Ignore key releases (bit 7 set)
    if scancode & 0x80 != 0 {
        return;
    }

    // Translate scancode to ASCII
    let shifted = SHIFT_HELD.load(Ordering::Relaxed) != 0;
    if let Some(ch) = scancode_to_ascii(scancode, shifted) {
        push_key(ch);
    }
}

/// Push a key into the circular buffer.
fn push_key(ch: u8) {
    let head = KEY_HEAD.load(Ordering::Relaxed) as usize;
    let next = (head + 1) % KEY_BUF_SIZE;
    if next != KEY_TAIL.load(Ordering::Relaxed) as usize {
        KEY_BUF[head].store(ch, Ordering::Relaxed);
        KEY_HEAD.store(next as u8, Ordering::Relaxed);
    }
}

/// Read a key from the buffer. Returns None if empty.
pub fn read_key() -> Option<u8> {
    let tail = KEY_TAIL.load(Ordering::Relaxed) as usize;
    let head = KEY_HEAD.load(Ordering::Relaxed) as usize;
    if tail == head {
        return None;
    }
    let ch = KEY_BUF[tail].load(Ordering::Relaxed);
    KEY_TAIL.store(((tail + 1) % KEY_BUF_SIZE) as u8, Ordering::Relaxed);
    Some(ch)
}

/// Blocking read — spin until a key is available.
pub fn read_key_blocking() -> u8 {
    loop {
        if let Some(ch) = read_key() {
            return ch;
        }
        core::hint::spin_loop();
    }
}

/// Check if keys are available.
pub fn has_key() -> bool {
    KEY_HEAD.load(Ordering::Relaxed) != KEY_TAIL.load(Ordering::Relaxed)
}

/// US QWERTY scancode set 1 → ASCII.
fn scancode_to_ascii(sc: u8, shift: bool) -> Option<u8> {
    let normal: &[u8; 58] = b"\0\x1B1234567890-=\x08\tqwertyuiop[]\n\0asdfghjkl;'`\0\\zxcvbnm,./\0*\0 ";
    let shifted: &[u8; 58] = b"\0\x1B!@#$%^&*()_+\x08\tQWERTYUIOP{}\n\0ASDFGHJKL:\"~\0|ZXCVBNM<>?\0*\0 ";

    if (sc as usize) < 58 {
        let ch = if shift { shifted[sc as usize] } else { normal[sc as usize] };
        if ch != 0 { Some(ch) } else { None }
    } else {
        None
    }
}

/// Get current modifier state.
pub fn modifiers() -> (bool, bool, bool) {
    (
        SHIFT_HELD.load(Ordering::Relaxed) != 0,
        CTRL_HELD.load(Ordering::Relaxed) != 0,
        ALT_HELD.load(Ordering::Relaxed) != 0,
    )
}
