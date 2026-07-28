//! Interrupt Descriptor Table (IDT) for Daisy OS.
//!
//! Sets up handlers for all 256 interrupt vectors.  CPU exceptions 0-31 get
//! named handlers that print diagnostics over serial.  IRQs 32-47 (remapped
//! via the 8259 PIC in `pic.rs`) get hardware-interrupt handlers.  Remaining
//! vectors 48-255 point at a not-present entry (will triple-fault if hit).

#![allow(dead_code)]

use core::mem::size_of;

use crate::{gdt, pic, serial};

// ---------------------------------------------------------------------------
// IDT entry (Gate Descriptor, 16 bytes in long mode)
// ---------------------------------------------------------------------------

/// A single IDT gate descriptor (interrupt/trap gate).
#[derive(Clone, Copy)]
#[repr(C, packed)]
struct IdtEntry {
    offset_low: u16,
    selector: u16,
    ist: u8,         // bits 0-2 = IST index, rest reserved
    type_attr: u8,   // type + DPL + present
    offset_mid: u16,
    offset_high: u32,
    _reserved: u32,
}

impl IdtEntry {
    const fn missing() -> Self {
        Self {
            offset_low: 0,
            selector: 0,
            ist: 0,
            type_attr: 0,
            offset_mid: 0,
            offset_high: 0,
            _reserved: 0,
        }
    }

    /// Create an interrupt-gate entry (DPL 0, present, 64-bit interrupt gate = 0x8E).
    fn new(handler: u64, selector: u16, ist_index: u8) -> Self {
        Self {
            offset_low: handler as u16,
            selector,
            ist: ist_index & 0x07,
            type_attr: 0x8E, // present, DPL 0, 64-bit interrupt gate
            offset_mid: (handler >> 16) as u16,
            offset_high: (handler >> 32) as u32,
            _reserved: 0,
        }
    }

    /// Same as `new` but with DPL=3 so user-mode `int 3` works.
    fn new_user(handler: u64, selector: u16, ist_index: u8) -> Self {
        Self {
            offset_low: handler as u16,
            selector,
            ist: ist_index & 0x07,
            type_attr: 0xEE, // present, DPL 3, 64-bit interrupt gate
            offset_mid: (handler >> 16) as u16,
            offset_high: (handler >> 32) as u32,
            _reserved: 0,
        }
    }

    /// Create a trap-gate entry (DPL 0, present, 64-bit trap gate = 0x8F).
    fn new_trap(handler: u64, selector: u16, ist_index: u8) -> Self {
        Self {
            offset_low: handler as u16,
            selector,
            ist: ist_index & 0x07,
            type_attr: 0x8F, // present, DPL 0, 64-bit trap gate
            offset_mid: (handler >> 16) as u16,
            offset_high: (handler >> 32) as u32,
            _reserved: 0,
        }
    }
}

// ---------------------------------------------------------------------------
// IDT pointer (passed to `lidt`)
// ---------------------------------------------------------------------------

#[repr(C, packed)]
struct IdtPointer {
    limit: u16,
    base: u64,
}

// ---------------------------------------------------------------------------
// Static IDT storage
// ---------------------------------------------------------------------------

const IDT_SIZE: usize = 256;
static mut IDT: [IdtEntry; IDT_SIZE] = [IdtEntry::missing(); IDT_SIZE];

use core::sync::atomic::{AtomicBool, Ordering};
static IDT_INITIALIZED: AtomicBool = AtomicBool::new(false);

// ---------------------------------------------------------------------------
// InterruptStackFrame -- must match CPU push layout exactly
// ---------------------------------------------------------------------------

/// The stack frame pushed by the CPU on an interrupt or exception in 64-bit
/// long mode.  The `x86-interrupt` calling convention requires the handler's
/// first parameter to be `InterruptStackFrame` by value; the compiler
/// actually passes it as an implicit pointer to the on-stack frame.
#[derive(Clone, Copy, Debug)]
#[repr(C)]
pub struct InterruptStackFrame {
    pub instruction_pointer: u64,
    pub code_segment: u64,
    pub cpu_flags: u64,
    pub stack_pointer: u64,
    pub stack_segment: u64,
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

/// Build the full IDT and load it with `lidt`.  Idempotent.
pub fn init() {
    if IDT_INITIALIZED.swap(true, Ordering::SeqCst) {
        return; // already initialized
    }
    {
        let cs = gdt::KERNEL_CODE_SELECTOR;

        unsafe {
            // -- CPU exceptions (0-31) -------------------------------------------

            IDT[0]  = IdtEntry::new_trap(isr_divide_by_zero as u64, cs, 0);
            IDT[1]  = IdtEntry::new_trap(isr_debug as u64, cs, 0);
            // Vector 2 (NMI) -- left not-present for now
            IDT[3]  = IdtEntry::new_user(isr_breakpoint as u64, cs, 0); // DPL 3
            IDT[4]  = IdtEntry::new_trap(isr_overflow as u64, cs, 0);
            IDT[5]  = IdtEntry::new_trap(isr_bound_range as u64, cs, 0);
            IDT[6]  = IdtEntry::new_trap(isr_invalid_opcode as u64, cs, 0);
            IDT[7]  = IdtEntry::new_trap(isr_device_not_available as u64, cs, 0);
            IDT[8]  = IdtEntry::new(isr_double_fault as u64, cs,
                                     gdt::DOUBLE_FAULT_IST_INDEX as u8 + 1);
            // Vector 9 -- legacy, unused in long mode
            IDT[10] = IdtEntry::new_trap(isr_invalid_tss as u64, cs, 0);
            IDT[11] = IdtEntry::new_trap(isr_segment_not_present as u64, cs, 0);
            IDT[12] = IdtEntry::new_trap(isr_stack_segment as u64, cs, 0);
            IDT[13] = IdtEntry::new_trap(isr_general_protection as u64, cs, 0);
            IDT[14] = IdtEntry::new_trap(isr_page_fault as u64, cs, 0);
            // Vectors 15-31: reserved by Intel, left not-present

            // -- Hardware IRQs (32-47, remapped via 8259 PIC) --------------------

            IDT[32] = IdtEntry::new(isr_timer as u64, cs, 0);
            IDT[33] = IdtEntry::new(isr_keyboard as u64, cs, 0);

            // -- Load IDT --------------------------------------------------------

            let idt_ptr = IdtPointer {
                limit: (size_of::<[IdtEntry; IDT_SIZE]>() - 1) as u16,
                base: IDT.as_ptr() as u64,
            };

            core::arch::asm!(
                "lidt [{}]",
                in(reg) &idt_ptr,
                options(readonly, nostack, preserves_flags),
            );
        }

        serial::print(b"[idt] IDT loaded (256 vectors)\n");
    }
}

// ===========================================================================
// Naked ISR wrappers
//
// The `extern "x86-interrupt"` calling convention is unstable and has had
// ABI-compatibility issues across nightly versions.  To be maximally
// portable we write *naked* assembly stubs that save all registers, call
// a normal Rust function, restore registers, and `iretq`.
//
// Each wrapper:
//   1. Pushes a dummy error code (0) if the CPU did not push one.
//   2. Pushes all general-purpose registers.
//   3. Calls the Rust handler with a pointer to the saved state.
//   4. Pops all registers, skips the error code, and does `iretq`.
// ===========================================================================

// Macro for exceptions that do NOT push an error code.
macro_rules! isr_no_error {
    ($name:ident, $handler:ident) => {
        #[unsafe(naked)]
        extern "C" fn $name() {
            unsafe {
                core::arch::naked_asm!(
                    "push 0",          // fake error code
                    "push rax",
                    "push rcx",
                    "push rdx",
                    "push rbx",
                    "push rbp",
                    "push rsi",
                    "push rdi",
                    "push r8",
                    "push r9",
                    "push r10",
                    "push r11",
                    "push r12",
                    "push r13",
                    "push r14",
                    "push r15",
                    "mov  rdi, rsp",   // arg0 = pointer to saved state
                    "call {handler}",
                    "pop  r15",
                    "pop  r14",
                    "pop  r13",
                    "pop  r12",
                    "pop  r11",
                    "pop  r10",
                    "pop  r9",
                    "pop  r8",
                    "pop  rdi",
                    "pop  rsi",
                    "pop  rbp",
                    "pop  rbx",
                    "pop  rdx",
                    "pop  rcx",
                    "pop  rax",
                    "add  rsp, 8",     // skip error code
                    "iretq",
                    handler = sym $handler,
                );
            }
        }
    };
}

// Macro for exceptions that DO push an error code.
macro_rules! isr_with_error {
    ($name:ident, $handler:ident) => {
        #[unsafe(naked)]
        extern "C" fn $name() {
            unsafe {
                core::arch::naked_asm!(
                // error code is already on stack
                "push rax",
                "push rcx",
                "push rdx",
                "push rbx",
                "push rbp",
                "push rsi",
                "push rdi",
                "push r8",
                "push r9",
                "push r10",
                "push r11",
                "push r12",
                "push r13",
                "push r14",
                "push r15",
                "mov  rdi, rsp",   // arg0 = pointer to saved state
                "call {handler}",
                "pop  r15",
                "pop  r14",
                "pop  r13",
                "pop  r12",
                "pop  r11",
                "pop  r10",
                "pop  r9",
                "pop  r8",
                "pop  rdi",
                "pop  rsi",
                "pop  rbp",
                "pop  rbx",
                "pop  rdx",
                "pop  rcx",
                "pop  rax",
                "add  rsp, 8",     // skip error code
                "iretq",
                handler = sym $handler,
                );
            }
        }
    };
}

// ---------------------------------------------------------------------------
// Saved register frame passed to Rust handlers
// ---------------------------------------------------------------------------

/// Register state saved by the ISR wrappers.
/// Layout must match the push order above exactly (r15 at lowest address).
#[repr(C)]
struct IsrFrame {
    // Pushed by our stub (in order of pop, i.e. r15 first at low addr)
    pub r15: u64,
    pub r14: u64,
    pub r13: u64,
    pub r12: u64,
    pub r11: u64,
    pub r10: u64,
    pub r9: u64,
    pub r8: u64,
    pub rdi: u64,
    pub rsi: u64,
    pub rbp: u64,
    pub rbx: u64,
    pub rdx: u64,
    pub rcx: u64,
    pub rax: u64,
    // Error code (real or dummy 0)
    pub error_code: u64,
    // Pushed by CPU
    pub rip: u64,
    pub cs: u64,
    pub rflags: u64,
    pub rsp: u64,
    pub ss: u64,
}

// ---------------------------------------------------------------------------
// Generate naked ISR stubs
// ---------------------------------------------------------------------------

// Exceptions without error code
isr_no_error!(isr_divide_by_zero,       handle_divide_by_zero);
isr_no_error!(isr_debug,                handle_debug);
isr_no_error!(isr_breakpoint,           handle_breakpoint);
isr_no_error!(isr_overflow,             handle_overflow);
isr_no_error!(isr_bound_range,          handle_bound_range);
isr_no_error!(isr_invalid_opcode,       handle_invalid_opcode);
isr_no_error!(isr_device_not_available, handle_device_not_available);

// Exceptions with error code
isr_with_error!(isr_double_fault,        handle_double_fault);
isr_with_error!(isr_invalid_tss,         handle_invalid_tss);
isr_with_error!(isr_segment_not_present, handle_segment_not_present);
isr_with_error!(isr_stack_segment,       handle_stack_segment);
isr_with_error!(isr_general_protection,  handle_general_protection);
isr_with_error!(isr_page_fault,          handle_page_fault);

// Hardware IRQs (no error code)
isr_no_error!(isr_timer,    handle_timer);
isr_no_error!(isr_keyboard, handle_keyboard);

// ===========================================================================
// Rust exception handlers (called from naked stubs)
// ===========================================================================

// ---------------------------------------------------------------------------
// Helper: print a hex u64 over serial (no alloc, no format machinery)
// ---------------------------------------------------------------------------

fn serial_print_hex(val: u64) {
    let mut buf = [b'0'; 16];
    let mut v = val;
    for i in (0..16).rev() {
        let nibble = (v & 0xF) as u8;
        buf[i] = if nibble < 10 { b'0' + nibble } else { b'a' + nibble - 10 };
        v >>= 4;
    }
    serial::print(b"0x");
    serial::print(&buf);
}

// ---------------------------------------------------------------------------
// Exception handlers (no error code)
// ---------------------------------------------------------------------------

extern "C" fn handle_divide_by_zero(_frame: *const IsrFrame) {
    serial::print(b"[exception] DIVIDE BY ZERO (#DE)\n");
    loop { halt(); }
}

extern "C" fn handle_debug(_frame: *const IsrFrame) {
    serial::print(b"[exception] DEBUG (#DB)\n");
}

extern "C" fn handle_breakpoint(_frame: *const IsrFrame) {
    serial::print(b"[exception] BREAKPOINT (#BP)\n");
}

extern "C" fn handle_overflow(_frame: *const IsrFrame) {
    serial::print(b"[exception] OVERFLOW (#OF)\n");
}

extern "C" fn handle_bound_range(_frame: *const IsrFrame) {
    serial::print(b"[exception] BOUND RANGE EXCEEDED (#BR)\n");
}

extern "C" fn handle_invalid_opcode(_frame: *const IsrFrame) {
    serial::print(b"[exception] INVALID OPCODE (#UD)\n");
    loop { halt(); }
}

extern "C" fn handle_device_not_available(_frame: *const IsrFrame) {
    serial::print(b"[exception] DEVICE NOT AVAILABLE (#NM)\n");
    loop { halt(); }
}

// ---------------------------------------------------------------------------
// Exception handlers (with error code)
// ---------------------------------------------------------------------------

extern "C" fn handle_double_fault(_frame: *const IsrFrame) -> ! {
    serial::print(b"[exception] DOUBLE FAULT (#DF) -- HALTING\n");
    loop { halt(); }
}

extern "C" fn handle_invalid_tss(frame: *const IsrFrame) {
    let ec = unsafe { (*frame).error_code };
    serial::print(b"[exception] INVALID TSS (#TS) error=");
    serial_print_hex(ec);
    serial::print(b"\n");
    loop { halt(); }
}

extern "C" fn handle_segment_not_present(frame: *const IsrFrame) {
    let ec = unsafe { (*frame).error_code };
    serial::print(b"[exception] SEGMENT NOT PRESENT (#NP) error=");
    serial_print_hex(ec);
    serial::print(b"\n");
    loop { halt(); }
}

extern "C" fn handle_stack_segment(frame: *const IsrFrame) {
    let ec = unsafe { (*frame).error_code };
    serial::print(b"[exception] STACK-SEGMENT FAULT (#SS) error=");
    serial_print_hex(ec);
    serial::print(b"\n");
    loop { halt(); }
}

extern "C" fn handle_general_protection(frame: *const IsrFrame) {
    let ec = unsafe { (*frame).error_code };
    serial::print(b"[exception] GENERAL PROTECTION FAULT (#GP) error=");
    serial_print_hex(ec);
    serial::print(b"\n");
    loop { halt(); }
}

extern "C" fn handle_page_fault(frame: *const IsrFrame) {
    let ec = unsafe { (*frame).error_code };
    // The faulting linear address is in CR2.
    let cr2: u64;
    unsafe {
        core::arch::asm!("mov {}, cr2", out(reg) cr2, options(nomem, nostack));
    }
    serial::print(b"[exception] PAGE FAULT (#PF) addr=");
    serial_print_hex(cr2);
    serial::print(b" error=");
    serial_print_hex(ec);
    serial::print(b"\n");
    loop { halt(); }
}

// ---------------------------------------------------------------------------
// Hardware IRQ handlers
// ---------------------------------------------------------------------------

extern "C" fn handle_timer(_frame: *const IsrFrame) {
    // Acknowledge the IRQ so the PIC will deliver the next one.
    pic::send_eoi(0);
}

extern "C" fn handle_keyboard(_frame: *const IsrFrame) {
    // Read the scancode from the keyboard data port (0x60).
    let scancode: u8;
    unsafe {
        core::arch::asm!(
            "in al, dx",
            in("dx") 0x60u16,
            out("al") scancode,
            options(nomem, nostack, preserves_flags),
        );
    }
    serial::print(b"[irq] keyboard scancode=0x");
    let hi = (scancode >> 4) & 0xF;
    let lo = scancode & 0xF;
    let hex = [
        if hi < 10 { b'0' + hi } else { b'a' + hi - 10 },
        if lo < 10 { b'0' + lo } else { b'a' + lo - 10 },
    ];
    serial::print(&hex);
    serial::print(b"\n");

    pic::send_eoi(1);
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

#[inline(always)]
fn halt() {
    unsafe {
        core::arch::asm!("hlt", options(nomem, nostack));
    }
}

/// Enable hardware interrupts (sti).
pub fn enable_interrupts() {
    unsafe {
        core::arch::asm!("sti", options(nomem, nostack));
    }
}

/// Disable hardware interrupts (cli).
pub fn disable_interrupts() {
    unsafe {
        core::arch::asm!("cli", options(nomem, nostack));
    }
}
