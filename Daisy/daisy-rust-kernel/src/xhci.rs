#![allow(dead_code)]

//! USB XHCI Host Controller driver for Daisy OS.
//!
//! Implements the minimum XHCI spec to enumerate USB devices and
//! set up control/bulk/interrupt transfers.

use crate::pci;

// XHCI Capability Register offsets
const CAP_CAPLENGTH: u32 = 0x00;
const CAP_HCSPARAMS1: u32 = 0x04;
const CAP_HCSPARAMS2: u32 = 0x08;
const CAP_HCSPARAMS3: u32 = 0x0C;
const CAP_HCCPARAMS1: u32 = 0x10;
const CAP_DBOFF: u32 = 0x14;
const CAP_RTSOFF: u32 = 0x18;

// XHCI Operational Register offsets (relative to op_base = base + cap_length)
const OP_USBCMD: u32 = 0x00;
const OP_USBSTS: u32 = 0x04;
const OP_PAGESIZE: u32 = 0x08;
const OP_DNCTRL: u32 = 0x14;
const OP_CRCR: u32 = 0x18;
const OP_DCBAAP: u32 = 0x30;
const OP_CONFIG: u32 = 0x38;

// USBCMD bits
const CMD_RUN: u32 = 1 << 0;
const CMD_HCRST: u32 = 1 << 1;
const CMD_INTE: u32 = 1 << 2;

// USBSTS bits
const STS_HCH: u32 = 1 << 0;   // HCHalted
const STS_CNR: u32 = 1 << 11;  // Controller Not Ready

// Port status/control register
const PORTSC_CCS: u32 = 1 << 0;    // Current Connect Status
const PORTSC_PED: u32 = 1 << 1;    // Port Enabled
const PORTSC_PR: u32 = 1 << 4;     // Port Reset
const PORTSC_PLS_MASK: u32 = 0xF << 5;
const PORTSC_PP: u32 = 1 << 9;     // Port Power
const PORTSC_SPEED_MASK: u32 = 0xF << 10;

/// TRB (Transfer Request Block) — 16 bytes.
#[derive(Clone, Copy, Default)]
#[repr(C)]
pub struct Trb {
    pub param: u64,
    pub status: u32,
    pub control: u32,
}

/// XHCI controller state.
pub struct XhciController {
    mmio_base: usize,
    op_base: usize,
    db_base: usize,
    rt_base: usize,
    max_ports: u8,
    max_slots: u8,
    initialized: bool,
}

static mut XHCI: XhciController = XhciController {
    mmio_base: 0,
    op_base: 0,
    db_base: 0,
    rt_base: 0,
    max_ports: 0,
    max_slots: 0,
    initialized: false,
};

impl XhciController {
    unsafe fn read_cap(&self, offset: u32) -> u32 {
        core::ptr::read_volatile((self.mmio_base + offset as usize) as *const u32)
    }

    unsafe fn read_op(&self, offset: u32) -> u32 {
        core::ptr::read_volatile((self.op_base + offset as usize) as *const u32)
    }

    unsafe fn write_op(&self, offset: u32, val: u32) {
        core::ptr::write_volatile((self.op_base + offset as usize) as *mut u32, val);
    }

    unsafe fn read_op64(&self, offset: u32) -> u64 {
        core::ptr::read_volatile((self.op_base + offset as usize) as *const u64)
    }

    unsafe fn write_op64(&self, offset: u32, val: u64) {
        core::ptr::write_volatile((self.op_base + offset as usize) as *mut u64, val);
    }

    /// Read a port status/control register.
    unsafe fn read_portsc(&self, port: u8) -> u32 {
        let offset = 0x400 + (port as u32 - 1) * 0x10;
        self.read_op(offset)
    }

    /// Write a port status/control register.
    unsafe fn write_portsc(&self, port: u8, val: u32) {
        let offset = 0x400 + (port as u32 - 1) * 0x10;
        self.write_op(offset, val);
    }
}

/// Initialize XHCI from PCI.
pub fn init() {
    // XHCI class = 0x0C (serial bus), subclass = 0x03 (USB), prog_if = 0x30 (XHCI)
    let dev = pci::find_by_class(0x0C, 0x03);
    let dev = match dev {
        Some(d) if d.prog_if == 0x30 => d,
        _ => {
            crate::serial::print(b"[xhci] No XHCI controller found\n");
            return;
        }
    };

    crate::serial::print(b"[xhci] Found XHCI controller: ");
    print_hex16(dev.vendor_id);
    crate::serial::print(b":");
    print_hex16(dev.device_id);
    crate::serial::print(b"\n");

    // Enable bus mastering and memory space
    pci::enable_bus_master(dev.bus, dev.device, dev.function);

    let bar0 = (dev.bar[0] & !0xF) as usize;
    if bar0 == 0 {
        crate::serial::print(b"[xhci] BAR0 is zero\n");
        return;
    }

    unsafe {
        XHCI.mmio_base = bar0;

        // Read capability length
        let cap_length = XHCI.read_cap(CAP_CAPLENGTH) & 0xFF;
        XHCI.op_base = bar0 + cap_length as usize;

        // Read doorbell and runtime offsets
        let dboff = XHCI.read_cap(CAP_DBOFF);
        XHCI.db_base = bar0 + dboff as usize;
        let rtsoff = XHCI.read_cap(CAP_RTSOFF);
        XHCI.rt_base = bar0 + rtsoff as usize;

        // Read structural params
        let hcsparams1 = XHCI.read_cap(CAP_HCSPARAMS1);
        XHCI.max_ports = ((hcsparams1 >> 24) & 0xFF) as u8;
        XHCI.max_slots = (hcsparams1 & 0xFF) as u8;

        crate::serial::print(b"[xhci] Max ports=");
        print_u8(XHCI.max_ports);
        crate::serial::print(b", max slots=");
        print_u8(XHCI.max_slots);
        crate::serial::print(b"\n");

        // Reset the controller
        XHCI.write_op(OP_USBCMD, CMD_HCRST);

        // Wait for reset complete (CNR = 0)
        for _ in 0..100_000 {
            if XHCI.read_op(OP_USBSTS) & STS_CNR == 0 {
                break;
            }
            core::hint::spin_loop();
        }

        if XHCI.read_op(OP_USBSTS) & STS_CNR != 0 {
            crate::serial::print(b"[xhci] Controller reset timeout\n");
            return;
        }

        // Set max device slots
        XHCI.write_op(OP_CONFIG, XHCI.max_slots as u32);

        crate::serial::print(b"[xhci] Controller reset complete\n");

        // Scan ports for connected devices
        for port in 1..=XHCI.max_ports {
            let portsc = XHCI.read_portsc(port);
            if portsc & PORTSC_CCS != 0 {
                let speed = (portsc & PORTSC_SPEED_MASK) >> 10;
                let speed_str = match speed {
                    1 => b"Full-Speed" as &[u8],
                    2 => b"Low-Speed",
                    3 => b"High-Speed",
                    4 => b"SuperSpeed",
                    _ => b"Unknown",
                };
                crate::serial::print(b"[xhci] Port ");
                print_u8(port);
                crate::serial::print(b": device connected (");
                crate::serial::print(speed_str);
                crate::serial::print(b")\n");
            }
        }

        // Note: full initialization (DCBAA, command ring, event ring)
        // requires the memory allocator
        crate::serial::print(b"[xhci] Basic init done (needs allocator for full setup)\n");
        XHCI.initialized = true;
    }
}

/// Get number of ports on the controller.
pub fn port_count() -> u8 {
    unsafe { XHCI.max_ports }
}

/// Check if a device is connected on a given port (1-based).
pub fn port_connected(port: u8) -> bool {
    unsafe {
        if !XHCI.initialized || port == 0 || port > XHCI.max_ports {
            return false;
        }
        XHCI.read_portsc(port) & PORTSC_CCS != 0
    }
}

fn print_hex16(val: u16) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for i in (0..4).rev() { crate::serial::write_byte(HEX[((val >> (i * 4)) & 0xF) as usize]); }
}

fn print_u8(val: u8) {
    if val >= 100 { crate::serial::write_byte(b'0' + val / 100); }
    if val >= 10  { crate::serial::write_byte(b'0' + (val / 10) % 10); }
    crate::serial::write_byte(b'0' + val % 10);
}
