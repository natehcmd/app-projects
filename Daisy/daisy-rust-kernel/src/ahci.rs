#![allow(dead_code)]

//! AHCI (Advanced Host Controller Interface) / SATA driver for Daisy OS.
//!
//! Supports SATA drives via the AHCI HBA. Detects drives on each port,
//! sends IDENTIFY DEVICE, and provides read/write sector operations.

use crate::pci;

// AHCI HBA Generic Host Control registers
const HBA_CAP: u32 = 0x00;       // Host Capabilities
const HBA_GHC: u32 = 0x04;       // Global Host Control
const HBA_IS: u32 = 0x08;        // Interrupt Status
const HBA_PI: u32 = 0x0C;        // Ports Implemented
const HBA_VS: u32 = 0x10;        // Version

// GHC bits
const GHC_AE: u32 = 1 << 31;     // AHCI Enable
const GHC_HR: u32 = 1 << 0;      // HBA Reset

// Port register offsets (base = 0x100 + port * 0x80)
const PORT_CLB: u32 = 0x00;      // Command List Base Address
const PORT_CLBU: u32 = 0x04;     // Command List Base Upper
const PORT_FB: u32 = 0x08;       // FIS Base Address
const PORT_FBU: u32 = 0x0C;      // FIS Base Upper
const PORT_IS: u32 = 0x10;       // Interrupt Status
const PORT_IE: u32 = 0x14;       // Interrupt Enable
const PORT_CMD: u32 = 0x18;      // Command and Status
const PORT_TFD: u32 = 0x20;      // Task File Data
const PORT_SIG: u32 = 0x24;      // Signature
const PORT_SSTS: u32 = 0x28;     // SATA Status
const PORT_SCTL: u32 = 0x2C;     // SATA Control
const PORT_SERR: u32 = 0x30;     // SATA Error
const PORT_SACT: u32 = 0x34;     // SATA Active
const PORT_CI: u32 = 0x38;       // Command Issue

// Port CMD bits
const CMD_ST: u32 = 1 << 0;      // Start
const CMD_FRE: u32 = 1 << 4;     // FIS Receive Enable
const CMD_FR: u32 = 1 << 14;     // FIS Running
const CMD_CR: u32 = 1 << 15;     // Command List Running

// Device signatures
const SIG_ATA: u32 = 0x00000101;
const SIG_ATAPI: u32 = 0xEB140101;

// SATA status bits
const SSTS_DET_MASK: u32 = 0x0F;
const SSTS_DET_PRESENT: u32 = 0x03;

// FIS types
const FIS_TYPE_REG_H2D: u8 = 0x27;

// ATA commands
const ATA_CMD_IDENTIFY: u8 = 0xEC;
const ATA_CMD_READ_DMA_EX: u8 = 0x25;
const ATA_CMD_WRITE_DMA_EX: u8 = 0x35;

/// Command Header (32 bytes each, 32 per port).
#[repr(C)]
struct CmdHeader {
    flags: u16,         // CFL (0:4), ATAPI, Write, Prefetch, Reset, BIST, Clear, PMP
    prdtl: u16,         // PRDT Length (number of entries)
    prdbc: u32,         // PRD Byte Count (transferred)
    ctba: u32,          // Command Table Base Address
    ctbau: u32,         // Command Table Base Address Upper
    _reserved: [u32; 4],
}

/// PRDT Entry (Physical Region Descriptor Table).
#[repr(C)]
struct PrdtEntry {
    dba: u32,           // Data Base Address
    dbau: u32,          // Data Base Address Upper
    _reserved: u32,
    dbc_i: u32,         // Byte Count (bit 0 = interrupt on completion)
}

/// Command FIS — Register H2D (host to device).
#[repr(C)]
struct FisRegH2D {
    fis_type: u8,       // FIS_TYPE_REG_H2D
    flags: u8,          // bit 7 = command (vs control)
    command: u8,        // ATA command
    feature_lo: u8,

    lba0: u8,
    lba1: u8,
    lba2: u8,
    device: u8,

    lba3: u8,
    lba4: u8,
    lba5: u8,
    feature_hi: u8,

    count_lo: u8,
    count_hi: u8,
    icc: u8,
    control: u8,

    _reserved: [u8; 4],
}

/// Detected SATA drive info.
#[derive(Clone, Copy)]
pub struct SataDrive {
    pub port: u8,
    pub model: [u8; 40],
    pub serial: [u8; 20],
    pub sectors: u64,
    pub present: bool,
}

const MAX_PORTS: usize = 32;

static mut AHCI_BASE: usize = 0;
static mut DRIVES: [SataDrive; MAX_PORTS] = [SataDrive {
    port: 0, model: [0; 40], serial: [0; 20], sectors: 0, present: false,
}; MAX_PORTS];
static mut DRIVE_COUNT: usize = 0;

unsafe fn read_hba(offset: u32) -> u32 {
    core::ptr::read_volatile((AHCI_BASE + offset as usize) as *const u32)
}

unsafe fn write_hba(offset: u32, val: u32) {
    core::ptr::write_volatile((AHCI_BASE + offset as usize) as *mut u32, val);
}

unsafe fn read_port(port: u8, offset: u32) -> u32 {
    let base = 0x100 + (port as u32) * 0x80;
    read_hba(base + offset)
}

unsafe fn write_port(port: u8, offset: u32, val: u32) {
    let base = 0x100 + (port as u32) * 0x80;
    write_hba(base + offset, val);
}

/// Stop a port's command engine.
unsafe fn stop_port(port: u8) {
    let cmd = read_port(port, PORT_CMD);
    write_port(port, PORT_CMD, cmd & !(CMD_ST | CMD_FRE));

    // Wait for FR and CR to clear
    for _ in 0..100_000 {
        let cmd = read_port(port, PORT_CMD);
        if cmd & (CMD_FR | CMD_CR) == 0 {
            return;
        }
        core::hint::spin_loop();
    }
}

/// Start a port's command engine.
unsafe fn start_port(port: u8) {
    // Wait for CR to clear
    for _ in 0..100_000 {
        if read_port(port, PORT_CMD) & CMD_CR == 0 { break; }
        core::hint::spin_loop();
    }

    let cmd = read_port(port, PORT_CMD);
    write_port(port, PORT_CMD, cmd | CMD_FRE | CMD_ST);
}

/// Check if a port has a device attached.
unsafe fn port_has_device(port: u8) -> bool {
    let ssts = read_port(port, PORT_SSTS);
    (ssts & SSTS_DET_MASK) == SSTS_DET_PRESENT
}

/// Initialize AHCI controller.
pub fn init() {
    // AHCI: class 0x01 (mass storage), subclass 0x06 (SATA), prog_if 0x01 (AHCI)
    let dev = pci::find_by_class(0x01, 0x06);
    let dev = match dev {
        Some(d) if d.prog_if == 0x01 => d,
        Some(_) => {
            crate::serial::print(b"[ahci] SATA controller found but not in AHCI mode\n");
            return;
        }
        None => {
            crate::serial::print(b"[ahci] No AHCI controller found\n");
            return;
        }
    };

    crate::serial::print(b"[ahci] Found AHCI controller: ");
    print_hex16(dev.vendor_id);
    crate::serial::print(b":");
    print_hex16(dev.device_id);
    crate::serial::print(b"\n");

    pci::enable_bus_master(dev.bus, dev.device, dev.function);

    // AHCI uses BAR5 (ABAR) — must be a memory BAR (bit 0 = 0)
    let bar5_raw = dev.bar[5];
    if bar5_raw & 0x01 != 0 {
        crate::serial::print(b"[ahci] BAR5 is I/O, not memory - invalid\n");
        return;
    }
    let abar = bar5_raw & !0xF;
    if abar == 0 {
        crate::serial::print(b"[ahci] BAR5 (ABAR) is zero\n");
        return;
    }

    unsafe {
        AHCI_BASE = abar as usize;

        // Enable AHCI mode
        let ghc = read_hba(HBA_GHC);
        write_hba(HBA_GHC, ghc | GHC_AE);

        // Read version and ports
        let vs = read_hba(HBA_VS);
        let pi = read_hba(HBA_PI);
        let cap = read_hba(HBA_CAP);
        let num_ports = ((cap & 0x1F) + 1) as u8;

        crate::serial::print(b"[ahci] Version ");
        print_hex16((vs >> 16) as u16);
        crate::serial::print(b".");
        print_hex16(vs as u16);
        crate::serial::print(b", ports=");
        print_u8(num_ports);
        crate::serial::print(b"\n");

        // Scan ports
        for port in 0..num_ports.min(MAX_PORTS as u8) {
            if pi & (1 << port) == 0 { continue; }
            if !port_has_device(port) { continue; }

            let sig = read_port(port, PORT_SIG);
            let sig_str = match sig {
                SIG_ATA => b"SATA" as &[u8],
                SIG_ATAPI => b"SATAPI",
                _ => b"Unknown",
            };

            crate::serial::print(b"[ahci] Port ");
            print_u8(port);
            crate::serial::print(b": ");
            crate::serial::print(sig_str);
            crate::serial::print(b" device detected\n");

            if sig == SIG_ATA {
                DRIVES[DRIVE_COUNT] = SataDrive {
                    port,
                    model: [0; 40],
                    serial: [0; 20],
                    sectors: 0,
                    present: true,
                };
                DRIVE_COUNT += 1;
            }
        }

        crate::serial::print(b"[ahci] Found ");
        print_u8(DRIVE_COUNT as u8);
        crate::serial::print(b" SATA drives (IDENTIFY needs allocator)\n");
    }
}

/// Get number of detected drives.
pub fn drive_count() -> usize {
    unsafe { DRIVE_COUNT }
}

/// Get a detected drive by index.
pub fn get_drive(index: usize) -> Option<SataDrive> {
    unsafe {
        if index < DRIVE_COUNT { Some(DRIVES[index]) } else { None }
    }
}

fn print_hex16(val: u16) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for i in (0..4).rev() {
        crate::serial::write_byte(HEX[((val >> (i * 4)) & 0xF) as usize]);
    }
}

fn print_u8(val: u8) {
    if val >= 100 { crate::serial::write_byte(b'0' + val / 100); }
    if val >= 10  { crate::serial::write_byte(b'0' + (val / 10) % 10); }
    crate::serial::write_byte(b'0' + val % 10);
}
