#![allow(dead_code)]

//! Intel e1000/e1000e Ethernet driver for Daisy OS.
//!
//! Supports the common Intel 82540EM (QEMU default) and similar.
//! Implements transmit and receive via descriptor rings.

use crate::pci;

// e1000 register offsets
const REG_CTRL: u32 = 0x0000;     // Device Control
const REG_STATUS: u32 = 0x0008;   // Device Status
const REG_EECD: u32 = 0x0010;     // EEPROM Control
const REG_EERD: u32 = 0x0014;     // EEPROM Read
const REG_ICR: u32 = 0x00C0;      // Interrupt Cause Read
const REG_IMS: u32 = 0x00D0;      // Interrupt Mask Set
const REG_IMC: u32 = 0x00D8;      // Interrupt Mask Clear
const REG_RCTL: u32 = 0x0100;     // Receive Control
const REG_TCTL: u32 = 0x0400;     // Transmit Control
const REG_RDBAL: u32 = 0x2800;    // RX Descriptor Base Low
const REG_RDBAH: u32 = 0x2804;    // RX Descriptor Base High
const REG_RDLEN: u32 = 0x2808;    // RX Descriptor Length
const REG_RDH: u32 = 0x2810;      // RX Descriptor Head
const REG_RDT: u32 = 0x2818;      // RX Descriptor Tail
const REG_TDBAL: u32 = 0x3800;    // TX Descriptor Base Low
const REG_TDBAH: u32 = 0x3804;    // TX Descriptor Base High
const REG_TDLEN: u32 = 0x3808;    // TX Descriptor Length
const REG_TDH: u32 = 0x3810;      // TX Descriptor Head
const REG_TDT: u32 = 0x3818;      // TX Descriptor Tail
const REG_MTA: u32 = 0x5200;      // Multicast Table Array
const REG_RAL: u32 = 0x5400;      // Receive Address Low
const REG_RAH: u32 = 0x5404;      // Receive Address High

// Control register bits
const CTRL_RST: u32 = 1 << 26;
const CTRL_SLU: u32 = 1 << 6;     // Set Link Up
const CTRL_ASDE: u32 = 1 << 5;    // Auto-Speed Detection Enable

// Receive control bits
const RCTL_EN: u32 = 1 << 1;
const RCTL_SBP: u32 = 1 << 2;     // Store Bad Packets
const RCTL_UPE: u32 = 1 << 3;     // Unicast Promisc
const RCTL_MPE: u32 = 1 << 4;     // Multicast Promisc
const RCTL_BAM: u32 = 1 << 15;    // Broadcast Accept
const RCTL_BSIZE_2048: u32 = 0;   // Buffer size 2048
const RCTL_SECRC: u32 = 1 << 26;  // Strip Ethernet CRC

// Transmit control bits
const TCTL_EN: u32 = 1 << 1;
const TCTL_PSP: u32 = 1 << 3;     // Pad Short Packets

// TX descriptor command bits
const TDESC_CMD_EOP: u8 = 1 << 0;  // End of Packet
const TDESC_CMD_IFCS: u8 = 1 << 1; // Insert FCS/CRC
const TDESC_CMD_RS: u8 = 1 << 3;   // Report Status

// TX descriptor status bits
const TDESC_STA_DD: u8 = 1 << 0;   // Descriptor Done

// RX descriptor status bits
const RDESC_STA_DD: u8 = 1 << 0;
const RDESC_STA_EOP: u8 = 1 << 1;

const NUM_RX_DESC: usize = 32;
const NUM_TX_DESC: usize = 32;
const RX_BUF_SIZE: usize = 2048;

/// Receive descriptor.
#[derive(Clone, Copy)]
#[repr(C)]
struct RxDesc {
    addr: u64,
    length: u16,
    checksum: u16,
    status: u8,
    errors: u8,
    special: u16,
}

/// Transmit descriptor.
#[derive(Clone, Copy)]
#[repr(C)]
struct TxDesc {
    addr: u64,
    length: u16,
    cso: u8,
    cmd: u8,
    status: u8,
    css: u8,
    special: u16,
}

/// e1000 driver state.
pub struct E1000 {
    mmio_base: *mut u32,
    mac: [u8; 6],
    rx_descs: *mut RxDesc,
    tx_descs: *mut TxDesc,
    rx_cur: usize,
    tx_cur: usize,
    initialized: bool,
}

static mut NIC: E1000 = E1000 {
    mmio_base: core::ptr::null_mut(),
    mac: [0; 6],
    rx_descs: core::ptr::null_mut(),
    tx_descs: core::ptr::null_mut(),
    rx_cur: 0,
    tx_cur: 0,
    initialized: false,
};

impl E1000 {
    /// Read a register.
    unsafe fn read_reg(&self, offset: u32) -> u32 {
        let ptr = (self.mmio_base as usize + offset as usize) as *const u32;
        core::ptr::read_volatile(ptr)
    }

    /// Write a register.
    unsafe fn write_reg(&self, offset: u32, val: u32) {
        let ptr = (self.mmio_base as usize + offset as usize) as *mut u32;
        core::ptr::write_volatile(ptr, val);
    }

    /// Read MAC address from EEPROM.
    unsafe fn read_mac(&mut self) {
        // Try reading from RAL/RAH first (may already be set)
        let ral = self.read_reg(REG_RAL);
        let rah = self.read_reg(REG_RAH);
        if rah & (1 << 31) != 0 {
            // Address valid bit set
            self.mac[0] = (ral & 0xFF) as u8;
            self.mac[1] = ((ral >> 8) & 0xFF) as u8;
            self.mac[2] = ((ral >> 16) & 0xFF) as u8;
            self.mac[3] = ((ral >> 24) & 0xFF) as u8;
            self.mac[4] = (rah & 0xFF) as u8;
            self.mac[5] = ((rah >> 8) & 0xFF) as u8;
        } else {
            // Read from EEPROM
            for i in 0..3u32 {
                self.write_reg(REG_EERD, (i << 8) | 1);
                // Wait for read to complete
                let mut timeout = 100_000u32;
                loop {
                    let val = self.read_reg(REG_EERD);
                    if val & (1 << 4) != 0 {
                        let data = (val >> 16) as u16;
                        self.mac[(i * 2) as usize] = (data & 0xFF) as u8;
                        self.mac[(i * 2 + 1) as usize] = ((data >> 8) & 0xFF) as u8;
                        break;
                    }
                    timeout -= 1;
                    if timeout == 0 {
                        crate::serial::print(b"[e1000] EEPROM read timeout\n");
                        return;
                    }
                    core::hint::spin_loop();
                }
            }
        }

        const HEX: &[u8; 16] = b"0123456789abcdef";
        crate::serial::print(b"[e1000] MAC: ");
        for (i, &byte) in self.mac.iter().enumerate() {
            crate::serial::write_byte(HEX[(byte >> 4) as usize]);
            crate::serial::write_byte(HEX[(byte & 0xF) as usize]);
            if i < 5 { crate::serial::write_byte(b':'); }
        }
        crate::serial::print(b"\n");
    }
}

/// Scan PCI for an Intel e1000 and initialize it.
pub fn init() {
    // Common e1000 device IDs
    let ids: &[(u16, u16)] = &[
        (0x8086, 0x100E), // 82540EM (QEMU)
        (0x8086, 0x100F), // 82545EM
        (0x8086, 0x10D3), // 82574L
        (0x8086, 0x153A), // I217-LM
        (0x8086, 0x1539), // I211
    ];

    for &(vendor, device) in ids {
        if let Some(dev) = pci::find_by_id(vendor, device) {
            crate::serial::print(b"[e1000] Found NIC: ");
            print_hex16(dev.vendor_id);
            crate::serial::print(b":");
            print_hex16(dev.device_id);
            crate::serial::print(b"\n");

            // Enable bus mastering
            pci::enable_bus_master(dev.bus, dev.device, dev.function);

            let bar0 = dev.bar[0] & !0xF;
            unsafe {
                NIC.mmio_base = bar0 as *mut u32;

                // Reset the device
                NIC.write_reg(REG_CTRL, NIC.read_reg(REG_CTRL) | CTRL_RST);
                // Wait for reset
                for _ in 0..100_000 { core::hint::spin_loop(); }

                // Set link up
                let ctrl = NIC.read_reg(REG_CTRL);
                NIC.write_reg(REG_CTRL, ctrl | CTRL_SLU | CTRL_ASDE);

                // Clear multicast table
                for i in 0..128 {
                    NIC.write_reg(REG_MTA + i * 4, 0);
                }

                // Disable interrupts for now
                NIC.write_reg(REG_IMC, 0xFFFF_FFFF);

                // Read MAC address
                NIC.read_mac();

                // Note: RX/TX descriptor ring setup requires physical memory allocation
                // which needs the frame allocator to be fully operational
                crate::serial::print(b"[e1000] NIC initialized (descriptor rings need allocator)\n");
                NIC.initialized = true;
            }
            return;
        }
    }

    crate::serial::print(b"[e1000] No compatible NIC found\n");
}

/// Get the MAC address.
pub fn mac_address() -> [u8; 6] {
    unsafe { NIC.mac }
}

/// Check if NIC is initialized.
pub fn is_initialized() -> bool {
    unsafe { NIC.initialized }
}

/// Send a packet (requires descriptor rings to be set up).
pub fn send_packet(data: &[u8]) -> Result<(), &'static str> {
    unsafe {
        if !NIC.initialized { return Err("NIC not initialized"); }
        if NIC.tx_descs.is_null() { return Err("TX descriptors not allocated"); }
    }
    Err("TX not yet fully implemented")
}

/// Receive a packet (requires descriptor rings to be set up).
pub fn receive_packet(buf: &mut [u8]) -> Result<usize, &'static str> {
    unsafe {
        if !NIC.initialized { return Err("NIC not initialized"); }
        if NIC.rx_descs.is_null() { return Err("RX descriptors not allocated"); }
    }
    Err("RX not yet fully implemented")
}

fn print_hex16(val: u16) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    for i in (0..4).rev() {
        crate::serial::write_byte(HEX[((val >> (i * 4)) & 0xF) as usize]);
    }
}
