//! Daisy OS UEFI Bootloader
//!
//! Initializes UEFI services, queries the GOP framebuffer, retrieves the
//! memory map, populates a BootInfo struct matching the kernel's boot.rs,
//! exits boot services, and jumps to the kernel at physical address 0x100000.

#![no_std]
#![no_main]

extern crate alloc;

use core::arch::asm;
use log::info;
use uefi::prelude::*;
use uefi::proto::console::gop::GraphicsOutput;
use uefi::table::boot::{MemoryType, SearchType};
use elf::ElfFile;
use goblin::elf;
use alloc::vec::Vec;

/// Physical address where the kernel is expected to be loaded.
const KERNEL_LOAD_ADDR: u64 = 0x100000;

/// Boot information passed from the bootloader to the kernel.
/// Layout must match `daisy-kernel/src/boot.rs` exactly.
#[repr(C)]
#[derive(Clone, Copy, Debug)]
struct BootInfo {
    memory_map_addr: usize,
    memory_map_byte_len: usize,
    memory_map_descriptor_size: usize,
    framebuffer_addr: usize,
    framebuffer_width: usize,
    framebuffer_height: usize,
    framebuffer_stride: usize,
}

/// UEFI application entry point.
#[entry]
fn main(image_handle: Handle, mut system_table: SystemTable<Boot>) -> Status {
    // Initialize UEFI services (logging, allocator, etc.).
    uefi_services::init(&mut system_table).expect("Failed to initialize UEFI services");
    info!("Daisy OS UEFI Bootloader v2.0.0");

    // ---------------------------------------------------------------
    // Step 1: Query GOP for framebuffer information
    // ---------------------------------------------------------------
    let (fb_addr, fb_width, fb_height, fb_stride) = query_gop(&system_table);
    info!(
        "GOP framebuffer: addr=0x{:X}, {}x{}, stride={}",
        fb_addr, fb_width, fb_height, fb_stride
    );

    // ---------------------------------------------------------------
    // Step 2: Exit boot services and retrieve the memory map
    // ---------------------------------------------------------------
    let (_runtime_table, memory_map) = system_table.exit_boot_services(MemoryType::LOADER_DATA);
    info!("Memory map retrieved");

    // ---------------------------------------------------------------
    // Step 3: Build the BootInfo struct
    // ---------------------------------------------------------------
    let boot_info = BootInfo {
        memory_map_addr: memory_map.memory_map as usize,
        memory_map_byte_len: memory_map.map_size as usize,
        memory_map_descriptor_size: memory_map.descriptor_size as usize,
        framebuffer_addr: fb_addr,
        framebuffer_width: fb_width,
        framebuffer_height: fb_height,
        framebuffer_stride: fb_stride,
    };
    info!("BootInfo assembled: {:?}", boot_info);

    // ---------------------------------------------------------------
    // Step 4: Place BootInfo in a known, safe memory location
    // ---------------------------------------------------------------
    // We write the BootInfo just below the kernel load address so the
    // kernel can find it at a fixed offset.  The struct is small (7
    // usizes = 56 bytes on x86-64), so this is safe as long as
    // nothing else occupies that region.
    let boot_info_addr = KERNEL_LOAD_ADDR - 0x1000; // 4 KiB below kernel
    unsafe {
        let dst = boot_info_addr as *mut BootInfo;
        core::ptr::write_volatile(dst, boot_info);
    }
    info!("BootInfo written to 0x{:X}", boot_info_addr);

    // ---------------------------------------------------------------
    // Step 5: Load the Kernel ELF and place it in memory
    // ---------------------------------------------------------------
    let file_system = system_table.boot_services().get_image_file_system(image_handle)
        .expect("Failed to get image file system");
    let mut root_dir = file_system.open_volume()
        .expect("Failed to open volume");
    let mut kernel_file = root_dir.open(b"kernel.elf", uefi::proto::media::file::FileMode::Read, 0)
        .expect("Failed to open kernel ELF file");

    // Read the kernel ELF into a buffer
    let mut buf: Vec<u8> = vec![0; kernel_file.get_info::<uefi::proto::media::file::FileInfo>().unwrap().file_size as usize];
    kernel_file.read(buf.as_mut_slice())
        .expect("Failed to read kernel ELF file");

    // Parse the kernel ELF and load it into memory
    let elf_file = ElfFile::new(&buf).expect("Failed to parse kernel ELF");
    for program_header in elf_file.program_headers.iter() {
        if program_header.p_type == elf::program_header::PT_LOAD {
            let dest_addr = KERNEL_LOAD_ADDR as *mut u8;
            unsafe {
                core::ptr::write_bytes(dest_addr.add(program_header.p_offset as usize), 0, program_header.p_memsz as usize);
                core::ptr::copy_nonoverlapping(buf.as_ptr().add(program_header.p_offset as usize), dest_addr.add(program_header.p_vaddr as usize - KERNEL_LOAD_ADDR as usize), program_header.p_filesz as usize);
            }
        }
    }

    // Zero the BSS section
    for segment in elf_file.sections.iter() {
        if segment.sh_type == elf::section_header::SHT_NOBITS && segment.sh_flags & elf::section_header::SHF_ALLOC != 0 {
            let dest_addr = KERNEL_LOAD_ADDR as *mut u8;
            unsafe {
                core::ptr::write_bytes(dest_addr.add(segment.sh_addr as usize - KERNEL_LOAD_ADDR as usize), 0, segment.sh_size as usize);
            }
        }
    }

    // ---------------------------------------------------------------
    // Step 6: Jump to the kernel entry point
    // ---------------------------------------------------------------
    // After exiting boot services we have no logging, no allocator,
    // and no UEFI boot-time services.  We pass a pointer to BootInfo
    // in RDI (System V AMD64 ABI first argument) so the kernel can
    // pick it up as `fn kernel_main(boot_info: *const BootInfo)`.
    unsafe {
        let kernel_entry: extern "sysv64" fn(boot_info: u64) -> ! =
            core::mem::transmute(KERNEL_LOAD_ADDR as *const ());
        kernel_entry(boot_info_addr);
    }
}

// -------------------------------------------------------------------
// Helper: query Graphics Output Protocol
// -------------------------------------------------------------------
/// Returns (framebuffer_base, width, height, stride) from the first
/// available GOP handle.
fn query_gop(st: &SystemTable<Boot>) -> (usize, usize, usize, usize) {
    let bt = st.boot_services();

    // Locate the GOP protocol handle.
    let gop_handle = bt
        .locate_handle_buffer(SearchType::ByProtocol(&GraphicsOutput::GUID))
        .expect("GOP not available -- headless systems are unsupported");

    // Open the protocol on the first handle.
    let mut gop = bt
        .open_protocol_exclusive::<GraphicsOutput>(gop_handle[0])
        .expect("Failed to open GOP protocol");

    // Read the current (or preferred) mode information.
    let mode_info = gop.current_mode_info();
    let (width, height) = mode_info.resolution();
    let stride = mode_info.stride();

    // The framebuffer base address is exposed through the mode structure.
    let fb_base = gop.frame_buffer().as_mut_ptr() as usize;

    (fb_base, width, height, stride)
}

