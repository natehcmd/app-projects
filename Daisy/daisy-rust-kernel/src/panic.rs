#![allow(dead_code)]

use core::arch::asm;

pub fn kernel_panic(msg: &[u8], file: &[u8], line: u32) -> ! {
    unsafe {
        crate::serial::print(b"=== KERNEL PANIC ===\n");
        crate::serial::print(msg);
        crate::serial::print(b"\nFile: ");
        crate::serial::print(file);
        crate::serial::print(b"\nLine: ");
        print_number(line);

        // Register dump
        let (rsp, rbp): (u64, u64);
        asm!(
            "mov {}, rsp",
            "mov {}, rbp",
            out(reg) rsp,
            out(reg) rbp,
            options(nomem, nostack),
        );
        crate::serial::print(b"\nRSP: ");
        print_hex(rsp);
        crate::serial::print(b"\nRBP: ");
        print_hex(rbp);

        // Stack trace attempt
        crate::serial::print(b"\nStack Trace:\n");
        let mut frame_pointer = rbp;
        while frame_pointer != 0 {
            let return_address: u64;
            asm!(
                "mov {}, [{} + 8]",
                out(reg) return_address,
                in(reg) frame_pointer,
                options(nostack),
            );
            print_hex(return_address);
            crate::serial::write_byte(b'\n');
            asm!(
                "mov {}, [{}]",
                out(reg) frame_pointer,
                in(reg) frame_pointer,
                options(nostack),
            );
        }

        asm!("cli", options(nomem, nostack));
        loop { asm!("hlt", options(nomem, nostack)); }
    }
}

fn print_number(mut num: u32) {
    if num == 0 {
        crate::serial::write_byte(b'0');
        return;
    }
    let mut buffer = [0u8; 10];
    let mut i = 0;
    while num > 0 {
        buffer[i] = b'0' + (num % 10) as u8;
        num /= 10;
        i += 1;
    }
    for j in (0..i).rev() {
        crate::serial::write_byte(buffer[j]);
    }
}

fn print_hex(num: u64) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut buf = [0u8; 16];
    for (i, slot) in buf.iter_mut().enumerate().rev() {
        *slot = HEX[((num >> (i * 4)) & 0xF) as usize];
    }
    crate::serial::print(&buf);
}
