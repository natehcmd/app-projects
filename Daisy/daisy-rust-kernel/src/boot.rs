#![allow(dead_code)]

/// Minimal boot information passed from the loader to the kernel.
#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct BootInfo {
    pub memory_map_entries: usize,
    pub framebuffer_addr: usize,
    pub framebuffer_width: usize,
    pub framebuffer_height: usize,
    pub framebuffer_stride: usize,
}

impl BootInfo {
    pub const fn new() -> Self {
        Self {
            memory_map_entries: 0,
            framebuffer_addr: 0,
            framebuffer_width: 0,
            framebuffer_height: 0,
            framebuffer_stride: 0,
        }
    }
}
