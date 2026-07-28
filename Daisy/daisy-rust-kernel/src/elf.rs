#![allow(dead_code)]

//! ELF64 loader for Daisy OS.
//!
//! Parses and loads ELF64 executables into memory, returning the entry point.

/// ELF64 file header.
#[derive(Clone, Copy)]
#[repr(C)]
pub struct Elf64Header {
    pub e_ident: [u8; 16],
    pub e_type: u16,
    pub e_machine: u16,
    pub e_version: u32,
    pub e_entry: u64,
    pub e_phoff: u64,
    pub e_shoff: u64,
    pub e_flags: u32,
    pub e_ehsize: u16,
    pub e_phentsize: u16,
    pub e_phnum: u16,
    pub e_shentsize: u16,
    pub e_shnum: u16,
    pub e_shstrndx: u16,
}

/// ELF64 program header.
#[derive(Clone, Copy)]
#[repr(C)]
pub struct Elf64Phdr {
    pub p_type: u32,
    pub p_flags: u32,
    pub p_offset: u64,
    pub p_vaddr: u64,
    pub p_paddr: u64,
    pub p_filesz: u64,
    pub p_memsz: u64,
    pub p_align: u64,
}

// ELF magic
const ELF_MAGIC: [u8; 4] = [0x7F, b'E', b'L', b'F'];

// ELF identification indices
const EI_CLASS: usize = 4;
const EI_DATA: usize = 5;
const ELFCLASS64: u8 = 2;
const ELFDATA2LSB: u8 = 1;

// ELF type
const ET_EXEC: u16 = 2;

// ELF machine
const EM_X86_64: u16 = 62;

// Program header types
const PT_LOAD: u32 = 1;

// Program header flags
const PF_X: u32 = 1;
const PF_W: u32 = 2;
const PF_R: u32 = 4;

const ELF64_HDR_SIZE: usize = core::mem::size_of::<Elf64Header>();
const ELF64_PHDR_SIZE: usize = core::mem::size_of::<Elf64Phdr>();

/// Read a value from a byte slice at a given offset (little-endian).
/// Uses direct byte reads to avoid alignment issues.
#[inline]
fn read_u16(data: &[u8], off: usize) -> u16 {
    u16::from_le_bytes([data[off], data[off + 1]])
}

#[inline]
fn read_u32(data: &[u8], off: usize) -> u32 {
    u32::from_le_bytes([data[off], data[off + 1], data[off + 2], data[off + 3]])
}

#[inline]
fn read_u64(data: &[u8], off: usize) -> u64 {
    u64::from_le_bytes([
        data[off], data[off + 1], data[off + 2], data[off + 3],
        data[off + 4], data[off + 5], data[off + 6], data[off + 7],
    ])
}

/// Parse the ELF64 header from raw bytes.
fn parse_header(data: &[u8]) -> Result<Elf64Header, &'static str> {
    if data.len() < ELF64_HDR_SIZE {
        return Err("ELF data too short for header");
    }

    // Validate magic
    if data[0..4] != ELF_MAGIC {
        return Err("Invalid ELF magic");
    }

    // Must be 64-bit, little-endian
    if data[EI_CLASS] != ELFCLASS64 {
        return Err("Not ELF64");
    }
    if data[EI_DATA] != ELFDATA2LSB {
        return Err("Not little-endian");
    }

    let e_type = read_u16(data, 16);
    if e_type != ET_EXEC {
        return Err("Not an executable ELF");
    }

    let e_machine = read_u16(data, 18);
    if e_machine != EM_X86_64 {
        return Err("Not x86_64 ELF");
    }

    Ok(Elf64Header {
        e_ident: data[0..16].try_into().unwrap_or([0u8; 16]),
        e_type,
        e_machine,
        e_version: read_u32(data, 20),
        e_entry: read_u64(data, 24),
        e_phoff: read_u64(data, 32),
        e_shoff: read_u64(data, 40),
        e_flags: read_u32(data, 48),
        e_ehsize: read_u16(data, 52),
        e_phentsize: read_u16(data, 54),
        e_phnum: read_u16(data, 56),
        e_shentsize: read_u16(data, 58),
        e_shnum: read_u16(data, 60),
        e_shstrndx: read_u16(data, 62),
    })
}

/// Parse a single program header from raw bytes.
fn parse_phdr(data: &[u8], offset: usize) -> Result<Elf64Phdr, &'static str> {
    if offset + ELF64_PHDR_SIZE > data.len() {
        return Err("ELF data too short for program header");
    }

    Ok(Elf64Phdr {
        p_type: read_u32(data, offset),
        p_flags: read_u32(data, offset + 4),
        p_offset: read_u64(data, offset + 8),
        p_vaddr: read_u64(data, offset + 16),
        p_paddr: read_u64(data, offset + 24),
        p_filesz: read_u64(data, offset + 32),
        p_memsz: read_u64(data, offset + 40),
        p_align: read_u64(data, offset + 48),
    })
}

/// Load an ELF64 executable from a byte slice.
///
/// Copies PT_LOAD segments to their specified virtual addresses and
/// returns the entry point address on success.
///
/// # Safety
/// This function writes directly to the virtual addresses specified in the ELF.
/// The caller must ensure that those addresses are mapped and writable.
pub unsafe fn load_elf(elf_data: &[u8]) -> Result<u64, &'static str> {
    let hdr = parse_header(elf_data)?;

    if hdr.e_phoff == 0 || hdr.e_phnum == 0 {
        return Err("No program headers");
    }

    let ph_off = hdr.e_phoff as usize;
    let ph_size = hdr.e_phentsize as usize;
    let ph_num = hdr.e_phnum as usize;

    if ph_size < ELF64_PHDR_SIZE {
        return Err("Program header entry too small");
    }

    let mut loaded = 0u32;

    for i in 0..ph_num {
        let offset = ph_off + i * ph_size;
        let phdr = parse_phdr(elf_data, offset)?;

        if phdr.p_type != PT_LOAD {
            continue;
        }

        // Validate segment bounds within the ELF data
        let file_off = phdr.p_offset as usize;
        let file_sz = phdr.p_filesz as usize;
        let mem_sz = phdr.p_memsz as usize;

        if file_off.checked_add(file_sz).map_or(true, |end| end > elf_data.len()) {
            return Err("Segment extends beyond ELF data");
        }

        if mem_sz == 0 {
            continue;
        }

        // Validate virtual address range
        let vaddr = phdr.p_vaddr as *mut u8;
        if vaddr as usize % core::mem::align_of::<u8>() != 0 {
            return Err("Invalid virtual address alignment");
        }

        // Check for overlapping program headers
        for j in 0..i {
            let other_phdr = parse_phdr(elf_data, ph_off + j * ph_size)?;
            if phdr.p_vaddr == other_phdr.p_vaddr && phdr.p_memsz > 0 {
                return Err("Overlapping program headers");
            }
        }

        // Copy file contents to virtual address
        if file_sz > 0 {
            core::ptr::copy_nonoverlapping(
                elf_data.as_ptr().add(file_off),
                vaddr,
                file_sz,
            );
        }

        // Zero BSS (memsz > filesz)
        if mem_sz > file_sz {
            core::ptr::write_bytes(vaddr.add(file_sz), 0, mem_sz - file_sz);
        }

        loaded += 1;

        crate::serial::print(b"[elf] Loaded segment at 0x");
        print_hex64(phdr.p_vaddr);
        crate::serial::print(b" (");
        print_u64(mem_sz as u64);
        crate::serial::print(b" bytes)\n");
    }

    if loaded == 0 {
        return Err("No loadable segments found");
    }

    crate::serial::print(b"[elf] Entry point: 0x");
    print_hex64(hdr.e_entry);
    crate::serial::print(b"\n");

    Ok(hdr.e_entry)
}

fn print_hex64(val: u64) {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut buf = [0u8; 16];
    for (i, slot) in buf.iter_mut().enumerate().rev() {
        *slot = HEX[((val >> (i * 4)) & 0xF) as usize];
    }
    crate::serial::print(&buf);
}

fn print_u64(mut n: u64) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 20];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}
