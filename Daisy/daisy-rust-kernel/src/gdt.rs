//! Global Descriptor Table (GDT) and Task State Segment (TSS) for Daisy OS.
//!
//! Provides a complete 64-bit GDT with kernel/user segments and a TSS entry
//! for interrupt stack switching.

#![allow(dead_code)]

use core::mem::size_of;
use core::sync::atomic::{AtomicBool, Ordering};

use crate::serial;

// ---------------------------------------------------------------------------
// Segment selector indices (byte-offset / 8)
// ---------------------------------------------------------------------------

/// Selector for the kernel code segment (ring 0, 64-bit).
pub const KERNEL_CODE_SELECTOR: u16 = 0x08;
/// Selector for the kernel data segment (ring 0).
pub const KERNEL_DATA_SELECTOR: u16 = 0x10;
/// Selector for the user code segment (ring 3, 64-bit).  RPL = 3.
pub const USER_CODE_SELECTOR: u16 = 0x18 | 3;
/// Selector for the user data segment (ring 3).  RPL = 3.
pub const USER_DATA_SELECTOR: u16 = 0x20 | 3;
/// Selector for the TSS segment.
pub const TSS_SELECTOR: u16 = 0x28;

// ---------------------------------------------------------------------------
// Segment descriptor flags
// ---------------------------------------------------------------------------

// Access byte bits
const ACCESS_PRESENT: u8 = 1 << 7;
const ACCESS_DPL_RING0: u8 = 0 << 5;
const ACCESS_DPL_RING3: u8 = 3 << 5;
const ACCESS_DESCRIPTOR: u8 = 1 << 4; // code/data (not system)
const ACCESS_EXECUTABLE: u8 = 1 << 3;
const ACCESS_RW: u8 = 1 << 1; // readable code / writable data
const ACCESS_ACCESSED: u8 = 1 << 0;

// Flags nibble (upper 4 bits of limit_hi_flags byte)
const FLAG_GRANULARITY: u8 = 1 << 7; // 4 KiB pages
const FLAG_SIZE_32: u8 = 1 << 6;     // 32-bit protected mode
const FLAG_LONG_MODE: u8 = 1 << 5;   // 64-bit code segment

// TSS access byte (system segment type = 0x9 = available 64-bit TSS)
const TSS_ACCESS: u8 = ACCESS_PRESENT | 0x09;

// ---------------------------------------------------------------------------
// Static storage
// ---------------------------------------------------------------------------

/// Interrupt stack size: 16 KiB per stack (4 pages).
const STACK_SIZE: usize = 4096 * 4;

/// Double-fault uses IST index 0.
pub const DOUBLE_FAULT_IST_INDEX: u16 = 0;

/// The interrupt stack for double-fault handling.
static mut DOUBLE_FAULT_STACK: [u8; STACK_SIZE] = [0; STACK_SIZE];

/// Privilege-level-0 kernel stack used for ring 3 -> ring 0 transitions.
static mut PRIVILEGE_STACK: [u8; STACK_SIZE] = [0; STACK_SIZE];

/// The TSS lives in a mutable static so the GDT can point at it.
static mut TSS: TaskStateSegment = TaskStateSegment::new();

/// Raw GDT storage (7 u64 entries: null + 4 segments + TSS which is 2 u64s).
static mut GDT_ENTRIES: [u64; 7] = [0; 7];

static GDT_INITIALIZED: AtomicBool = AtomicBool::new(false);

// ---------------------------------------------------------------------------
// Task State Segment (64-bit)
// ---------------------------------------------------------------------------

/// 64-bit Task State Segment.  Layout must match the hardware spec exactly.
#[repr(C, packed)]
pub struct TaskStateSegment {
    _reserved0: u32,
    /// Privilege stack table (RSP0, RSP1, RSP2).
    pub privilege_stack_table: [u64; 3],
    _reserved1: u64,
    /// Interrupt Stack Table (IST1-IST7).  Index 0 = IST1, etc.
    pub interrupt_stack_table: [u64; 7],
    _reserved2: u64,
    _reserved3: u16,
    /// I/O Map Base Address.
    pub iomap_base: u16,
}

impl TaskStateSegment {
    pub const fn new() -> Self {
        Self {
            _reserved0: 0,
            privilege_stack_table: [0; 3],
            _reserved1: 0,
            interrupt_stack_table: [0; 7],
            _reserved2: 0,
            _reserved3: 0,
            iomap_base: size_of::<TaskStateSegment>() as u16,
        }
    }
}

// ---------------------------------------------------------------------------
// GDT pointer (passed to lgdt)
// ---------------------------------------------------------------------------

#[repr(C, packed)]
struct GdtPointer {
    limit: u16,
    base: u64,
}

// ---------------------------------------------------------------------------
// Helpers to build descriptors
// ---------------------------------------------------------------------------

/// Build a normal (non-system) segment descriptor with base=0, limit=0xFFFFF.
///
/// Layout (8 bytes):
///   Byte 0-1: limit 15:0  = 0xFFFF
///   Byte 2-3: base 15:0   = 0x0000
///   Byte 4:   base 23:16  = 0x00
///   Byte 5:   access byte
///   Byte 6:   flags(hi nibble) | limit 19:16 (lo nibble) = (flags & 0xF0) | 0x0F
///   Byte 7:   base 31:24  = 0x00
const fn segment_descriptor(access: u8, flags: u8) -> u64 {
    0xFFFF                                   // limit 15:0
    | ((access as u64) << 40)                // access byte
    | (0x0F_u64 << 48)                       // limit 19:16
    | (((flags & 0xF0) as u64) << 48)        // flags nibble (merged with limit bits)
}

/// Build a 64-bit TSS descriptor (16 bytes / 2 u64s).
fn tss_descriptor(tss_addr: u64, tss_size: u16) -> (u64, u64) {
    let limit = (tss_size - 1) as u64;
    let base = tss_addr;

    let low: u64 =
        (limit & 0xFFFF)                            // limit 15:0
        | ((base & 0xFFFF) << 16)                   // base 15:0
        | (((base >> 16) & 0xFF) << 32)             // base 23:16
        | ((TSS_ACCESS as u64) << 40)               // access byte
        | (((limit >> 16) & 0xF) << 48)             // limit 19:16
        | (((base >> 24) & 0xFF) << 56);            // base 31:24

    let high: u64 = (base >> 32) & 0xFFFF_FFFF;     // base 63:32

    (low, high)
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

/// Initialise the GDT, TSS, load them, and reload segment registers.
///
/// Safe to call multiple times (idempotent via AtomicBool).
pub fn init() {
    if GDT_INITIALIZED.swap(true, Ordering::SeqCst) {
        return;
    }
    {
        unsafe {
            // ---------------------------------------------------------------
            // 1. Set up the TSS
            // ---------------------------------------------------------------
            let df_stack_end = &DOUBLE_FAULT_STACK as *const _ as u64 + STACK_SIZE as u64;
            TSS.interrupt_stack_table[DOUBLE_FAULT_IST_INDEX as usize] = df_stack_end;

            let priv_stack_end = &PRIVILEGE_STACK as *const _ as u64 + STACK_SIZE as u64;
            TSS.privilege_stack_table[0] = priv_stack_end; // RSP0

            // ---------------------------------------------------------------
            // 2. Build GDT entries
            // ---------------------------------------------------------------

            // Index 0: Null descriptor
            GDT_ENTRIES[0] = 0;

            // Index 1 (0x08): Kernel Code — 64-bit, ring 0, readable
            GDT_ENTRIES[1] = segment_descriptor(
                ACCESS_PRESENT | ACCESS_DPL_RING0 | ACCESS_DESCRIPTOR
                    | ACCESS_EXECUTABLE | ACCESS_RW,
                FLAG_GRANULARITY | FLAG_LONG_MODE,
            );

            // Index 2 (0x10): Kernel Data — ring 0, writable
            GDT_ENTRIES[2] = segment_descriptor(
                ACCESS_PRESENT | ACCESS_DPL_RING0 | ACCESS_DESCRIPTOR | ACCESS_RW,
                FLAG_GRANULARITY | FLAG_SIZE_32,
            );

            // Index 3 (0x18): User Code — 64-bit, ring 3, readable
            GDT_ENTRIES[3] = segment_descriptor(
                ACCESS_PRESENT | ACCESS_DPL_RING3 | ACCESS_DESCRIPTOR
                    | ACCESS_EXECUTABLE | ACCESS_RW,
                FLAG_GRANULARITY | FLAG_LONG_MODE,
            );

            // Index 4 (0x20): User Data — ring 3, writable
            GDT_ENTRIES[4] = segment_descriptor(
                ACCESS_PRESENT | ACCESS_DPL_RING3 | ACCESS_DESCRIPTOR | ACCESS_RW,
                FLAG_GRANULARITY | FLAG_SIZE_32,
            );

            // Index 5-6 (0x28): TSS descriptor (occupies two u64 slots)
            let tss_addr = &TSS as *const _ as u64;
            let tss_size = size_of::<TaskStateSegment>() as u16;
            let (tss_low, tss_high) = tss_descriptor(tss_addr, tss_size);
            GDT_ENTRIES[5] = tss_low;
            GDT_ENTRIES[6] = tss_high;

            // ---------------------------------------------------------------
            // 3. Load the GDT
            // ---------------------------------------------------------------
            let gdt_ptr = GdtPointer {
                limit: (size_of::<[u64; 7]>() - 1) as u16,
                base: GDT_ENTRIES.as_ptr() as u64,
            };

            core::arch::asm!(
                "lgdt [{}]",
                in(reg) &gdt_ptr,
                options(readonly, nostack, preserves_flags),
            );

            // ---------------------------------------------------------------
            // 4. Reload segment registers
            // ---------------------------------------------------------------
            // We need a far return to reload CS.  DS/ES/SS can be loaded
            // with a simple mov.
            core::arch::asm!(
                // Push the new CS selector and the address of the label,
                // then do a far return.
                "push {kcs}",
                "lea {tmp}, [rip + 2f]",
                "push {tmp}",
                "retfq",
                "2:",
                // Reload data segment registers
                "mov ds, {kds:x}",
                "mov es, {kds:x}",
                "mov ss, {kds:x}",
                kcs = in(reg) KERNEL_CODE_SELECTOR as u64,
                kds = in(reg) KERNEL_DATA_SELECTOR as u64,
                tmp = lateout(reg) _,
            );

            // ---------------------------------------------------------------
            // 5. Load the TSS
            // ---------------------------------------------------------------
            core::arch::asm!(
                "ltr {0:x}",
                in(reg) TSS_SELECTOR,
                options(nostack, preserves_flags),
            );
        }

        serial::print(b"[gdt] GDT + TSS loaded\n");
    }
}
