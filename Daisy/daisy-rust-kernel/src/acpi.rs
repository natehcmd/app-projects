#![allow(dead_code)]

//! Basic ACPI table parsing for Daisy OS.
//!
//! Locates the RSDP, parses RSDT/XSDT, finds MADT (for APIC info)
//! and FADT (for power management).

/// RSDP signature: "RSD PTR "
const RSDP_SIGNATURE: &[u8; 8] = b"RSD PTR ";

#[derive(Clone, Copy, Debug)]
#[repr(C, packed)]
pub struct Rsdp {
    pub signature: [u8; 8],
    pub checksum: u8,
    pub oem_id: [u8; 6],
    pub revision: u8,
    pub rsdt_addr: u32,
}

#[derive(Clone, Copy, Debug)]
#[repr(C, packed)]
pub struct Rsdp2 {
    pub base: Rsdp,
    pub length: u32,
    pub xsdt_addr: u64,
    pub ext_checksum: u8,
    pub reserved: [u8; 3],
}

#[derive(Clone, Copy, Debug)]
#[repr(C, packed)]
pub struct SdtHeader {
    pub signature: [u8; 4],
    pub length: u32,
    pub revision: u8,
    pub checksum: u8,
    pub oem_id: [u8; 6],
    pub oem_table_id: [u8; 8],
    pub oem_revision: u32,
    pub creator_id: u32,
    pub creator_revision: u32,
}

/// MADT (Multiple APIC Description Table) entry types.
#[derive(Clone, Copy, Debug)]
pub enum MadtEntry {
    LocalApic { processor_id: u8, apic_id: u8, flags: u32 },
    IoApic { id: u8, addr: u32, gsi_base: u32 },
    InterruptOverride { bus: u8, source: u8, gsi: u32, flags: u16 },
}

/// Parsed ACPI info.
pub struct AcpiInfo {
    pub local_apic_addr: u32,
    pub io_apic_addr: u32,
    pub io_apic_id: u8,
    pub cpu_count: u8,
    /// SCI interrupt for ACPI events
    pub sci_interrupt: u16,
    /// PM1a control block port
    pub pm1a_control: u32,
    /// Sleep type values for S5 (shutdown)
    pub slp_typ_a: u16,
}

static mut ACPI: AcpiInfo = AcpiInfo {
    local_apic_addr: 0xFEE0_0000,
    io_apic_addr: 0xFEC0_0000,
    io_apic_id: 0,
    cpu_count: 1,
    sci_interrupt: 9,
    pm1a_control: 0,
    slp_typ_a: 0,
};

/// Search for RSDP in BIOS memory regions.
/// The RSDP is typically at:
///   1. First 1KB of EBDA (Extended BIOS Data Area)
///   2. 0x000E0000 - 0x000FFFFF (BIOS ROM)
pub fn find_rsdp() -> Option<usize> {
    // Search BIOS ROM area
    let start = 0x000E_0000usize;
    let end = 0x0010_0000usize;
    let mut addr = start;
    while addr < end {
        let ptr = addr as *const [u8; 8];
        unsafe {
            if *ptr == *RSDP_SIGNATURE {
                // Verify checksum
                let rsdp_bytes = core::slice::from_raw_parts(addr as *const u8, 20);
                let sum: u8 = rsdp_bytes.iter().fold(0u8, |a, &b| a.wrapping_add(b));
                if sum == 0 {
                    return Some(addr);
                }
            }
        }
        addr += 16; // RSDP is always 16-byte aligned
    }
    None
}

/// Initialize ACPI from a known RSDP address (e.g., from UEFI).
pub fn init_from_rsdp(rsdp_addr: usize) {
    unsafe {
        let rsdp = &*(rsdp_addr as *const Rsdp);
        crate::serial::print(b"[acpi] RSDP found, revision ");
        crate::serial::write_byte(b'0' + rsdp.revision);
        crate::serial::print(b"\n");

        if rsdp.revision >= 2 {
            let rsdp2 = &*(rsdp_addr as *const Rsdp2);
            parse_xsdt(rsdp2.xsdt_addr as usize);
        } else {
            parse_rsdt(rsdp.rsdt_addr as usize);
        }
    }
}

/// Parse the RSDT (Root System Description Table).
unsafe fn parse_rsdt(rsdt_addr: usize) {
    let hdr = &*(rsdt_addr as *const SdtHeader);
    let entry_count = (hdr.length as usize - core::mem::size_of::<SdtHeader>()) / 4;
    let entries = core::slice::from_raw_parts(
        (rsdt_addr + core::mem::size_of::<SdtHeader>()) as *const u32,
        entry_count,
    );

    for &entry_addr in entries {
        parse_table(entry_addr as usize);
    }
}

/// Parse the XSDT (Extended System Description Table).
unsafe fn parse_xsdt(xsdt_addr: usize) {
    let hdr = &*(xsdt_addr as *const SdtHeader);
    let entry_count = (hdr.length as usize - core::mem::size_of::<SdtHeader>()) / 8;
    let entries = core::slice::from_raw_parts(
        (xsdt_addr + core::mem::size_of::<SdtHeader>()) as *const u64,
        entry_count,
    );

    for &entry_addr in entries {
        parse_table(entry_addr as usize);
    }
}

/// Parse a single ACPI table by its signature.
unsafe fn parse_table(addr: usize) {
    let hdr = &*(addr as *const SdtHeader);

    match &hdr.signature {
        b"APIC" => parse_madt(addr),
        b"FACP" => parse_fadt(addr),
        _ => {}
    }
}

/// Parse MADT for APIC information.
unsafe fn parse_madt(addr: usize) {
    let hdr = &*(addr as *const SdtHeader);
    let madt_base = addr + core::mem::size_of::<SdtHeader>();

    // Local APIC address (offset 0 after header)
    let lapic_addr = *((madt_base) as *const u32);
    ACPI.local_apic_addr = lapic_addr;

    // Parse MADT entries (start at offset 8 after header, after lapic_addr + flags)
    let mut offset = madt_base + 8;
    let end = addr + hdr.length as usize;
    let mut cpus = 0u8;

    while offset + 2 <= end {
        let entry_type = *(offset as *const u8);
        let entry_len = *((offset + 1) as *const u8) as usize;
        if entry_len < 2 { break; }

        match entry_type {
            0 => {
                // Local APIC
                let flags = *((offset + 4) as *const u32);
                if flags & 0x01 != 0 {
                    cpus += 1;
                }
            }
            1 => {
                // I/O APIC
                ACPI.io_apic_id = *((offset + 2) as *const u8);
                ACPI.io_apic_addr = *((offset + 4) as *const u32);
            }
            _ => {}
        }

        offset += entry_len;
    }

    ACPI.cpu_count = cpus;
    crate::serial::print(b"[acpi] MADT: ");
    print_u8(cpus);
    crate::serial::print(b" CPUs, LAPIC=0x");
    print_hex32(lapic_addr);
    crate::serial::print(b"\n");
}

/// Parse FADT for power management ports.
unsafe fn parse_fadt(addr: usize) {
    let base = addr + core::mem::size_of::<SdtHeader>();

    ACPI.sci_interrupt = *((base + 14) as *const u16); // SCI_INT at offset 46 of FADT
    ACPI.pm1a_control = *((base + 52) as *const u32); // PM1a_CNT_BLK

    crate::serial::print(b"[acpi] FADT: PM1a=0x");
    print_hex32(ACPI.pm1a_control);
    crate::serial::print(b", SCI=");
    print_u8(ACPI.sci_interrupt as u8);
    crate::serial::print(b"\n");
}

/// Get parsed ACPI info.
pub fn info() -> &'static AcpiInfo {
    unsafe { &ACPI }
}

/// Attempt to initialize from either UEFI-provided address or BIOS search.
pub fn init() {
    if let Some(rsdp) = find_rsdp() {
        init_from_rsdp(rsdp);
    } else {
        crate::serial::print(b"[acpi] RSDP not found (will use UEFI-provided address)\n");
    }
}

/// Power off via ACPI S5 sleep state.
pub fn shutdown() -> ! {
    unsafe {
        if ACPI.pm1a_control != 0 {
            crate::serial::print(b"[acpi] Shutting down via ACPI S5...\n");

            #[cfg(target_arch = "x86_64")]
            {
                let port = ACPI.pm1a_control as u16;
                let val = (ACPI.slp_typ_a << 10) | (1 << 13); // SLP_TYP | SLP_EN
                core::arch::asm!(
                    "out dx, ax",
                    in("dx") port,
                    in("ax") val,
                    options(nomem, nostack),
                );
            }
        }
    }

    // If ACPI shutdown failed, halt
    crate::serial::print(b"[acpi] Shutdown failed, halting\n");
    loop {
        #[cfg(target_arch = "x86_64")]
        unsafe { core::arch::asm!("hlt"); }
    }
}

fn print_hex32(val: u32) {
    for i in (0..8).rev() {
        let nib = ((val >> (i * 4)) & 0xF) as u8;
        crate::serial::write_byte(if nib < 10 { b'0' + nib } else { b'a' + nib - 10 });
    }
}

fn print_u8(val: u8) {
    if val >= 100 { crate::serial::write_byte(b'0' + val / 100); }
    if val >= 10  { crate::serial::write_byte(b'0' + (val / 10) % 10); }
    crate::serial::write_byte(b'0' + val % 10);
}
