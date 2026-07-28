#![allow(dead_code)]

//! NVMe storage driver for Daisy OS.
//!
//! Implements the minimum NVMe 1.0 spec needed to identify the drive
//! and perform block reads/writes via the Admin and I/O submission/completion
//! queues.

use crate::pci;

/// NVMe controller registers (BAR0 MMIO).
#[repr(C)]
struct NvmeRegs {
    cap: u64,        // Controller Capabilities
    vs: u32,         // Version
    intms: u32,      // Interrupt Mask Set
    intmc: u32,      // Interrupt Mask Clear
    cc: u32,         // Controller Configuration
    _rsvd: u32,
    csts: u32,       // Controller Status
    nssr: u32,       // NVM Subsystem Reset
    aqa: u32,        // Admin Queue Attributes
    asq: u64,        // Admin Submission Queue Base
    acq: u64,        // Admin Completion Queue Base
}

/// NVMe submission queue entry (64 bytes).
#[derive(Clone, Copy)]
#[repr(C)]
struct NvmeCmd {
    opcode: u8,
    flags: u8,
    cid: u16,
    nsid: u32,
    _rsvd: u64,
    mptr: u64,
    prp1: u64,
    prp2: u64,
    cdw10: u32,
    cdw11: u32,
    cdw12: u32,
    cdw13: u32,
    cdw14: u32,
    cdw15: u32,
}

/// NVMe completion queue entry (16 bytes).
#[derive(Clone, Copy)]
#[repr(C)]
struct NvmeCqe {
    result: u32,
    _rsvd: u32,
    sq_head: u16,
    sq_id: u16,
    cid: u16,
    status: u16,
}

/// Queue pair (submission + completion).
struct NvmeQueue {
    sq: *mut NvmeCmd,
    cq: *mut NvmeCqe,
    sq_tail: u32,
    cq_head: u32,
    sq_doorbell: *mut u32,
    cq_doorbell: *mut u32,
    depth: u32,
    phase: bool,
    cid: u16,
}

/// NVMe controller state.
pub struct NvmeController {
    regs: *mut NvmeRegs,
    admin_queue: Option<NvmeQueue>,
    io_queue: Option<NvmeQueue>,
    stride: u32,      // Doorbell stride
    max_transfer: u32, // Max transfer size in blocks
    block_size: u32,   // Logical block size (usually 512)
    total_blocks: u64, // Total blocks on namespace 1
    initialized: bool,
}

static mut NVME: NvmeController = NvmeController {
    regs: core::ptr::null_mut(),
    admin_queue: None,
    io_queue: None,
    stride: 4,
    max_transfer: 256,
    block_size: 512,
    total_blocks: 0,
    initialized: false,
};

impl NvmeController {
    /// Initialize the NVMe controller from a PCI device.
    pub unsafe fn init(dev: &pci::PciDevice) -> bool {
        // Get BAR0 (MMIO base)
        let bar0 = dev.bar[0] & !0xF;
        if bar0 == 0 {
            crate::serial::print(b"[nvme] BAR0 is zero\n");
            return false;
        }

        let regs = bar0 as *mut NvmeRegs;
        NVME.regs = regs;

        // Enable bus mastering and memory space
        pci::enable_bus_master(dev.bus, dev.device, dev.function);
        let cmd = pci::config_read16(dev.bus, dev.device, dev.function, 0x04);
        pci::config_write32(dev.bus, dev.device, dev.function, 0x04, (cmd | 0x06) as u32);

        // Read capabilities
        let cap = core::ptr::read_volatile(&(*regs).cap);
        NVME.stride = (((cap >> 32) & 0xF) + 1) as u32; // DSTRD
        let mqes = (cap & 0xFFFF) as u32 + 1; // Maximum Queue Entries Supported

        let queue_depth = mqes.min(64); // Use at most 64 entries

        crate::serial::print(b"[nvme] Controller at BAR0=0x");
        print_hex32(bar0);
        crate::serial::print(b", max queue depth=");
        print_u32(mqes);
        crate::serial::print(b"\n");

        // Disable controller
        let mut cc = core::ptr::read_volatile(&(*regs).cc);
        cc &= !1u32; // Clear EN bit
        core::ptr::write_volatile(&mut (*regs).cc, cc);

        // Wait for controller to be disabled (CSTS.RDY = 0)
        for _ in 0..100_000 {
            let csts = core::ptr::read_volatile(&(*regs).csts);
            if csts & 1 == 0 { break; }
            core::hint::spin_loop();
        }

        crate::serial::print(b"[nvme] Controller disabled, configuring queues\n");

        // For now, log that init would continue here
        // Full queue allocation requires a physical memory allocator
        crate::serial::print(b"[nvme] Waiting for memory allocator to create queues\n");

        NVME.initialized = false;
        false
    }
}

/// Scan PCI for NVMe controllers and init the first one found.
pub fn init() {
    // NVMe class = 0x01 (mass storage), subclass = 0x08 (NVMe)
    if let Some(dev) = pci::find_by_class(0x01, 0x08) {
        crate::serial::print(b"[nvme] Found NVMe controller: ");
        print_hex16(dev.vendor_id);
        crate::serial::print(b":");
        print_hex16(dev.device_id);
        crate::serial::print(b"\n");

        unsafe {
            NvmeController::init(&dev);
        }
    } else {
        crate::serial::print(b"[nvme] No NVMe controller found\n");
    }
}

/// Read blocks from the NVMe drive.
pub fn read_blocks(lba: u64, count: u32, buf: &mut [u8]) -> Result<(), &'static str> {
    unsafe {
        if !NVME.initialized {
            return Err("NVMe not initialized");
        }
    }
    // Will use I/O submission queue once memory allocator is ready
    Err("NVMe read not yet implemented")
}

/// Write blocks to the NVMe drive.
pub fn write_blocks(lba: u64, count: u32, buf: &[u8]) -> Result<(), &'static str> {
    unsafe {
        if !NVME.initialized {
            return Err("NVMe not initialized");
        }
    }
    Err("NVMe write not yet implemented")
}

/// Get drive capacity in bytes.
pub fn capacity() -> u64 {
    unsafe { NVME.total_blocks * NVME.block_size as u64 }
}

/// Get block size.
pub fn block_size() -> u32 {
    unsafe { NVME.block_size }
}

fn print_hex16(val: u16) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for i in (0..4).rev() { crate::serial::write_byte(HEX[((val >> (i * 4)) & 0xF) as usize]); }
}

fn print_hex32(val: u32) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for i in (0..8).rev() { crate::serial::write_byte(HEX[((val >> (i * 4)) & 0xF) as usize]); }
}

fn print_u32(mut n: u32) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 10];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}
