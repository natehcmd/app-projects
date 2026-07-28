#![allow(dead_code)]

//! Power management for Daisy OS — shutdown, reboot, halt.

pub fn shutdown() -> ! {
    crate::serial::print(b"[power] Shutting down...\n");
    unsafe {
        // QEMU/Bochs ACPI shutdown (PM1a_CNT at 0x604, SLP_TYP=5 << 10 | SLP_EN=1 << 13)
        core::arch::asm!("out dx, ax", in("dx") 0x604u16, in("ax") 0x2000u16, options(nomem, nostack));
    }
    crate::serial::print(b"[power] ACPI shutdown failed, halting\n");
    loop { unsafe { core::arch::asm!("cli; hlt", options(nomem, nostack)); } }
}

pub fn reboot() -> ! {
    crate::serial::print(b"[power] Rebooting...\n");
    unsafe {
        // Keyboard controller reset (0x64 port, 0xFE command)
        core::arch::asm!("out dx, al", in("dx") 0x64u16, in("al") 0xFEu8, options(nomem, nostack));
    }
    crate::serial::print(b"[power] Reboot failed, halting\n");
    loop { unsafe { core::arch::asm!("cli; hlt", options(nomem, nostack)); } }
}

pub fn halt() -> ! {
    loop { unsafe { core::arch::asm!("cli; hlt", options(nomem, nostack)); } }
}

pub fn idle() {
    unsafe { core::arch::asm!("hlt", options(nomem, nostack)); }
}
