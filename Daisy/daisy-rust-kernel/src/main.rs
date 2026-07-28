#![no_std]
#![no_main]
#![feature(abi_x86_interrupt)]

extern crate alloc;

use daisy_kernel::*;

#[no_mangle]
pub extern "C" fn kernel_main(boot_info: &boot::BootInfo) -> ! {
    // 1. Serial output (earliest possible output)
    serial::init();
    serial::print(b"\n");
    serial::print(b"  ____        _             ___  ____\n");
    serial::print(b" |  _ \\  __ _(_)___ _   _  / _ \\/ ___|\n");
    serial::print(b" | | | |/ _` | / __| | | || | | \\___ \\\n");
    serial::print(b" | |_| | (_| | \\__ \\ |_| || |_| |___) |\n");
    serial::print(b" |____/ \\__,_|_|___/\\__, | \\___/|____/\n");
    serial::print(b"                    |___/  v2.0\n");
    serial::print(b"\n");
    serial::print(b"[kernel] Daisy OS kernel starting...\n");

    // 2. GDT + TSS
    gdt::init();

    // 3. IDT + exception handlers
    idt::init();

    // 4. PIC remapping
    pic::init();

    // 5. PIT timer (1000 Hz = 1ms ticks)
    timer::init(1000);

    // 6. PS/2 Keyboard
    keyboard::init();

    // 7. Enable interrupts
    idt::enable_interrupts();
    serial::print(b"[kernel] Interrupts enabled\n");

    // 8. Initialize memory allocator from boot info
    serial::print(b"[kernel] Framebuffer at 0x");
    print_hex(boot_info.framebuffer_addr as u64);
    serial::print(b" (");
    print_dec(boot_info.framebuffer_width as u64);
    serial::print(b"x");
    print_dec(boot_info.framebuffer_height as u64);
    serial::print(b")\n");

    // 9. ACPI (find RSDP, parse tables)
    acpi::init();

    // 10. PCI bus scan
    pci::init();

    // 11. Storage (NVMe + AHCI)
    nvme::init();
    ahci::init();

    // 12. Network (e1000)
    e1000::init();

    // 13. USB (XHCI)
    xhci::init();

    // 14. Initialize the Daisy kernel subsystems
    serial::print(b"[kernel] Initializing Daisy subsystems...\n");
    {
        let mut kernel = DaisyKernel::new();
        let root_task = kernel.boot();
        serial::print(b"[kernel] Root task created (id=");
        print_dec(root_task);
        serial::print(b")\n");

        // Store kernel in global
        *KERNEL.lock() = Some(kernel);
    }

    // 15. Set up framebuffer console
    if boot_info.framebuffer_addr != 0 {
        let mut fb = framebuffer::FrameBuffer::new(
            boot_info.framebuffer_addr as *mut u32,
            boot_info.framebuffer_width,
            boot_info.framebuffer_height,
            boot_info.framebuffer_stride,
        );
        // Dark blue background
        fb.clear(0x001a1a2e);
        // Show boot message
        fb.print_str(20, 20, b"Daisy OS v2.0", 0x00e0e0e0);
        fb.print_str(20, 50, b"Kernel initialized", 0x00a0a0c0);
        serial::print(b"[kernel] Framebuffer console ready\n");
    }

    serial::print(b"[kernel] Boot complete. Uptime: ");
    print_dec(timer::uptime_ms());
    serial::print(b"ms\n");
    serial::print(b"[kernel] Entering main loop...\n");

    // Main kernel loop
    loop {
        // Check for keyboard input
        while let Some(ch) = keyboard::read_key() {
            serial::write_byte(ch);
            if ch == b'q' {
                serial::print(b"\n[kernel] Shutdown requested\n");
                acpi::shutdown();
            }
        }

        // Yield CPU until next interrupt
        unsafe {
            core::arch::asm!("hlt", options(nomem, nostack));
        }
    }
}

#[panic_handler]
fn panic(info: &core::panic::PanicInfo) -> ! {
    serial::print(b"\n!!! KERNEL PANIC !!!\n");
    if let Some(msg) = info.message().as_str() {
        serial::print(msg.as_bytes());
    }
    if let Some(loc) = info.location() {
        serial::print(b"\n  at ");
        serial::print(loc.file().as_bytes());
        serial::print(b":");
        print_dec(loc.line() as u64);
    }
    serial::print(b"\n");
    loop {
        unsafe { core::arch::asm!("cli; hlt", options(nomem, nostack)); }
    }
}

#[inline]
fn print_hex(val: u64) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut buf = [0u8; 16];
    for (i, slot) in buf.iter_mut().enumerate() {
        *slot = HEX[((val >> ((15 - i) * 4)) & 0xF) as usize];
    }
    serial::print(&buf);
}

#[inline]
fn print_dec(mut val: u64) {
    if val == 0 { serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 20];
    let mut i = 0;
    while val > 0 { buf[i] = b'0' + (val % 10) as u8; val /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { serial::write_byte(b); }
}
