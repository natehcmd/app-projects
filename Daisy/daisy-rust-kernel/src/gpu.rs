#![allow(dead_code)]

use core::ptr::write_volatile;
use core::sync::atomic::{AtomicBool, Ordering};

static mut FB_ADDR: u64 = 0;
static mut FB_WIDTH: u32 = 0;
static mut FB_HEIGHT: u32 = 0;
static mut FB_STRIDE: u32 = 0; // bytes per row
static INITIALIZED: AtomicBool = AtomicBool::new(false);

pub fn init(addr: u64, width: u32, height: u32, stride: u32) {
    unsafe {
        FB_ADDR = addr;
        FB_WIDTH = width;
        FB_HEIGHT = height;
        FB_STRIDE = stride;
        INITIALIZED.store(true, Ordering::SeqCst);
    }
    crate::serial::print(b"[gpu] Framebuffer at 0x");
    print_hex(addr);
    crate::serial::print(b" ");
    print_dec(width);
    crate::serial::print(b"x");
    print_dec(height);
    crate::serial::print(b"\n");
}

fn print_hex(mut num: u64) {
    const HEX_CHARS: [u8; 16] = *b"0123456789abcdef";
    let mut buf = [0u8; 16];
    for i in (0..16).rev() {
        buf[i] = HEX_CHARS[(num & 0xF) as usize];
        num >>= 4;
    }
    crate::serial::print(&buf);
}

fn print_dec(mut num: u32) {
    let mut buf = [0u8; 10];
    let mut i = 9;
    if num == 0 {
        buf[i] = b'0';
        i -= 1;
    } else {
        while num > 0 {
            buf[i] = (num % 10) as u8 + b'0';
            num /= 10;
            i -= 1;
        }
    }
    crate::serial::print(&buf[i+1..]);
}

pub fn set_pixel(x: u32, y: u32, color: u32) {
    if x < unsafe { FB_WIDTH } && y < unsafe { FB_HEIGHT } {
        let offset = (y * unsafe { FB_STRIDE } + x * 4) as u64;
        unsafe { write_volatile((FB_ADDR + offset) as *mut u32, color) }
    }
}

pub fn fill_rect(x: u32, y: u32, w: u32, h: u32, color: u32) {
    // SAFETY: single-core; reads once, then uses clamped bounds.
    unsafe {
        let (fw, fh, stride, addr) = (FB_WIDTH, FB_HEIGHT, FB_STRIDE, FB_ADDR);
        if !INITIALIZED.load(core::sync::atomic::Ordering::Relaxed) { return; }
        let x_end = (x + w).min(fw);
        let y_end = (y + h).min(fh);
        for row in y..y_end {
            let row_base = addr + (row * stride) as u64;
            for col in x..x_end {
                write_volatile((row_base + (col * 4) as u64) as *mut u32, color);
            }
        }
    }
}

pub fn clear(color: u32) {
    let (w, h) = unsafe { (FB_WIDTH, FB_HEIGHT) };
    fill_rect(0, 0, w, h, color);
}

pub fn get_resolution() -> (u32, u32) {
    unsafe { (FB_WIDTH, FB_HEIGHT) }
}
