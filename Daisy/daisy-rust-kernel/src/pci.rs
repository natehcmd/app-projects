#![allow(dead_code)]

//! PCI configuration space access and bus enumeration for Daisy OS.
//!
//! Uses the standard x86 I/O port mechanism (CONFIG_ADDRESS + CONFIG_DATA)
//! to scan all buses, devices, and functions.

const PCI_CONFIG_ADDR: u16 = 0xCF8;
const PCI_CONFIG_DATA: u16 = 0xCFC;

/// Maximum devices we track.
const MAX_DEVICES: usize = 64;

/// PCI device information.
#[derive(Clone, Copy, Debug)]
pub struct PciDevice {
    pub bus: u8,
    pub device: u8,
    pub function: u8,
    pub vendor_id: u16,
    pub device_id: u16,
    pub class_code: u8,
    pub subclass: u8,
    pub prog_if: u8,
    pub revision: u8,
    pub header_type: u8,
    pub bar: [u32; 6],
    pub interrupt_line: u8,
    pub interrupt_pin: u8,
}

impl PciDevice {
    const fn empty() -> Self {
        Self {
            bus: 0, device: 0, function: 0,
            vendor_id: 0xFFFF, device_id: 0xFFFF,
            class_code: 0, subclass: 0, prog_if: 0, revision: 0,
            header_type: 0, bar: [0; 6],
            interrupt_line: 0, interrupt_pin: 0,
        }
    }
}

/// Static device list.
static mut DEVICES: [PciDevice; MAX_DEVICES] = [PciDevice::empty(); MAX_DEVICES];
static mut DEVICE_COUNT: usize = 0;

#[inline]
unsafe fn outl(port: u16, val: u32) {
    core::arch::asm!("out dx, eax", in("dx") port, in("eax") val, options(nomem, nostack));
}

#[inline]
unsafe fn inl(port: u16) -> u32 {
    let val: u32;
    core::arch::asm!("in eax, dx", in("dx") port, out("eax") val, options(nomem, nostack));
    val
}

/// Build a PCI config address for bus/device/function/offset.
fn config_addr(bus: u8, device: u8, function: u8, offset: u8) -> u32 {
    0x8000_0000
        | ((bus as u32) << 16)
        | (((device & 0x1F) as u32) << 11)
        | (((function & 0x07) as u32) << 8)
        | ((offset & 0xFC) as u32)
}

/// Read a 32-bit value from PCI configuration space.
pub fn config_read32(bus: u8, device: u8, function: u8, offset: u8) -> u32 {
    unsafe {
        outl(PCI_CONFIG_ADDR, config_addr(bus, device, function, offset));
        inl(PCI_CONFIG_DATA)
    }
}

/// Write a 32-bit value to PCI configuration space.
pub fn config_write32(bus: u8, device: u8, function: u8, offset: u8, val: u32) {
    unsafe {
        outl(PCI_CONFIG_ADDR, config_addr(bus, device, function, offset));
        outl(PCI_CONFIG_DATA, val);
    }
}

/// Read a 16-bit value from PCI configuration space.
pub fn config_read16(bus: u8, device: u8, function: u8, offset: u8) -> u16 {
    let val = config_read32(bus, device, function, offset & 0xFC);
    ((val >> ((offset & 2) * 8)) & 0xFFFF) as u16
}

/// Read an 8-bit value from PCI configuration space.
pub fn config_read8(bus: u8, device: u8, function: u8, offset: u8) -> u8 {
    let val = config_read32(bus, device, function, offset & 0xFC);
    ((val >> ((offset & 3) * 8)) & 0xFF) as u8
}

/// Scan a single PCI function and record it if valid.
fn scan_function(bus: u8, device: u8, function: u8) {
    let vendor_id = config_read16(bus, device, function, 0x00);
    if vendor_id == 0xFFFF {
        return;
    }

    let device_id = config_read16(bus, device, function, 0x02);
    let class_rev = config_read32(bus, device, function, 0x08);
    let header_type = config_read8(bus, device, function, 0x0E);

    let dev = PciDevice {
        bus,
        device,
        function,
        vendor_id,
        device_id,
        class_code: ((class_rev >> 24) & 0xFF) as u8,
        subclass: ((class_rev >> 16) & 0xFF) as u8,
        prog_if: ((class_rev >> 8) & 0xFF) as u8,
        revision: (class_rev & 0xFF) as u8,
        header_type: header_type & 0x7F,
        bar: [
            config_read32(bus, device, function, 0x10),
            config_read32(bus, device, function, 0x14),
            config_read32(bus, device, function, 0x18),
            config_read32(bus, device, function, 0x1C),
            config_read32(bus, device, function, 0x20),
            config_read32(bus, device, function, 0x24),
        ],
        interrupt_line: config_read8(bus, device, function, 0x3C),
        interrupt_pin: config_read8(bus, device, function, 0x3D),
    };

    unsafe {
        if DEVICE_COUNT < MAX_DEVICES {
            DEVICES[DEVICE_COUNT] = dev;
            DEVICE_COUNT += 1;
        }
    }

    // Log the device
    crate::serial::print(b"[pci] ");
    print_hex8(bus);
    crate::serial::print(b":");
    print_hex8(device);
    crate::serial::print(b".");
    crate::serial::write_byte(b'0' + function);
    crate::serial::print(b" vendor=");
    print_hex16(vendor_id);
    crate::serial::print(b" device=");
    print_hex16(device_id);
    crate::serial::print(b" class=");
    print_hex8(dev.class_code);
    crate::serial::print(b":");
    print_hex8(dev.subclass);
    crate::serial::print(b"\n");
}

/// Enumerate all PCI devices on all buses.
pub fn init() {
    crate::serial::print(b"[pci] Scanning PCI bus...\n");

    for bus in 0u8..=255 {
        for device in 0u8..32 {
            if config_read16(bus, device, 0, 0x00) == 0xFFFF { continue; }
            scan_function(bus, device, 0);
            if config_read8(bus, device, 0, 0x0E) & 0x80 != 0 {
                for func in 1u8..8 {
                    scan_function(bus, device, func);
                }
            }
        }
    }

    unsafe {
        crate::serial::print(b"[pci] Found ");
        print_u32(DEVICE_COUNT as u32);
        crate::serial::print(b" devices\n");
    }
}

/// Get the number of discovered PCI devices.
pub fn device_count() -> usize {
    unsafe { DEVICE_COUNT }
}

/// Get a discovered device by index.
pub fn get_device(index: usize) -> Option<PciDevice> {
    unsafe {
        if index < DEVICE_COUNT {
            Some(DEVICES[index])
        } else {
            None
        }
    }
}

/// Find the first device matching a given class and subclass.
pub fn find_by_class(class: u8, subclass: u8) -> Option<PciDevice> {
    unsafe {
        for i in 0..DEVICE_COUNT {
            if DEVICES[i].class_code == class && DEVICES[i].subclass == subclass {
                return Some(DEVICES[i]);
            }
        }
    }
    None
}

/// Find a device by vendor and device ID.
pub fn find_by_id(vendor: u16, device: u16) -> Option<PciDevice> {
    unsafe {
        for i in 0..DEVICE_COUNT {
            if DEVICES[i].vendor_id == vendor && DEVICES[i].device_id == device {
                return Some(DEVICES[i]);
            }
        }
    }
    None
}

/// Enable bus mastering for a PCI device (needed for DMA).
/// Only modifies the 16-bit command register, preserving the status register.
pub fn enable_bus_master(bus: u8, device: u8, function: u8) {
    let full = config_read32(bus, device, function, 0x04);
    let cmd = (full & 0xFFFF) as u16;
    let status = full & 0xFFFF_0000;
    config_write32(bus, device, function, 0x04, status | (cmd | 0x04) as u32);
}

// Helper print functions
fn print_hex8(val: u8) {
    let hi = (val >> 4) & 0xF;
    let lo = val & 0xF;
    crate::serial::write_byte(if hi < 10 { b'0' + hi } else { b'a' + hi - 10 });
    crate::serial::write_byte(if lo < 10 { b'0' + lo } else { b'a' + lo - 10 });
}

fn print_hex16(val: u16) {
    print_hex8((val >> 8) as u8);
    print_hex8(val as u8);
}

fn print_u32(mut n: u32) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 10];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    while i > 0 { i -= 1; crate::serial::write_byte(buf[i]); }
}
