#![allow(dead_code)]
use core::fmt;

const COM1: u16 = 0x3F8;

/// Write a byte to an I/O port.
#[cfg(target_arch = "x86_64")]
#[inline]
unsafe fn outb(port: u16, val: u8) {
    core::arch::asm!("out dx, al", in("dx") port, in("al") val, options(nomem, nostack));
}

/// Read a byte from an I/O port.
#[cfg(target_arch = "x86_64")]
#[inline]
unsafe fn inb(port: u16) -> u8 {
    let val: u8;
    core::arch::asm!("in al, dx", in("dx") port, out("al") val, options(nomem, nostack));
    val
}

/// Initialize COM1 serial port at 115200 baud.
pub fn init() {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        outb(COM1 + 1, 0x00); // Disable interrupts
        outb(COM1 + 3, 0x80); // Enable DLAB (baud rate divisor)
        outb(COM1 + 0, 0x01); // Divisor 1 = 115200 baud
        outb(COM1 + 1, 0x00); // High byte
        outb(COM1 + 3, 0x03); // 8 bits, no parity, 1 stop bit
        outb(COM1 + 2, 0xC7); // Enable FIFO, clear, 14-byte threshold
        outb(COM1 + 4, 0x0B); // IRQs enabled, RTS/DSR set
        outb(COM1 + 4, 0x1E); // Loopback mode for test
        outb(COM1 + 0, 0xAE); // Test byte

        if inb(COM1 + 0) != 0xAE {
            return; // Serial port failed self-test
        }

        // Switch to normal operation (not loopback)
        outb(COM1 + 4, 0x0F);
    }
}

/// Wait for transmit buffer to be empty, then send byte.
pub fn write_byte(byte: u8) {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        // Wait for transmit holding register empty (bit 5 of LSR)
        while inb(COM1 + 5) & 0x20 == 0 {
            core::hint::spin_loop();
        }
        outb(COM1, byte);
    }
    #[cfg(not(target_arch = "x86_64"))]
    let _ = byte;
}

/// Read a byte from COM1 (blocking).
pub fn read_byte() -> u8 {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        while inb(COM1 + 5) & 0x01 == 0 {
            core::hint::spin_loop();
        }
        inb(COM1)
    }
    #[cfg(not(target_arch = "x86_64"))]
    0
}

/// Check if data is available to read.
pub fn data_available() -> bool {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        inb(COM1 + 5) & 0x01 != 0
    }
    #[cfg(not(target_arch = "x86_64"))]
    false
}

/// Print a byte slice to serial.
pub fn print(s: &[u8]) {
    for &b in s {
        if b == b'\n' {
            write_byte(b'\r');
        }
        write_byte(b);
    }
}

pub struct SerialWriter;

impl fmt::Write for SerialWriter {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        print(s.as_bytes());
        Ok(())
    }
}

/// Print formatted text to serial.
#[macro_export]
macro_rules! serial_print {
    ($($arg:tt)*) => {
        {
            use core::fmt::Write;
            let _ = write!($crate::serial::SerialWriter, $($arg)*);
        }
    };
}

#[macro_export]
macro_rules! serial_println {
    () => ($crate::serial_print!("\n"));
    ($($arg:tt)*) => {
        $crate::serial_print!($($arg)*);
        $crate::serial_print!("\n");
    };
}
