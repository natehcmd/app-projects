#![allow(dead_code)]

pub struct FrameBuffer {
    pub buffer: *mut u32,
    pub width: usize,
    pub height: usize,
    pub stride: usize, // pixels per scanline
}

impl FrameBuffer {
    pub fn new(buffer: *mut u32, width: usize, height: usize, stride: usize) -> Self {
        Self { buffer, width, height, stride }
    }

    pub fn clear(&mut self, color: u32) {
        // SAFETY: buffer covers width * height pixels; stride >= width.
        unsafe {
            for row in 0..self.height {
                let row_ptr = self.buffer.add(row * self.stride);
                for col in 0..self.width {
                    core::ptr::write_volatile(row_ptr.add(col), color);
                }
            }
        }
    }

    pub fn put_pixel(&mut self, x: usize, y: usize, color: u32) {
        if x < self.width && y < self.height {
            unsafe {
                let offset = y * self.stride + x;
                *self.buffer.add(offset) = color;
            }
        }
    }

    pub fn draw_rect(&mut self, x: usize, y: usize, w: usize, h: usize, color: u32) {
        let x_end = (x + w).min(self.width);
        let y_end = (y + h).min(self.height);
        // SAFETY: clamped coordinates are within buffer bounds.
        unsafe {
            for row in y..y_end {
                let row_ptr = self.buffer.add(row * self.stride + x);
                for col in 0..x_end - x {
                    core::ptr::write_volatile(row_ptr.add(col), color);
                }
            }
        }
    }

    pub fn print_str(&mut self, x: usize, y: usize, text: &[u8], color: u32) {
        let mut cx = x;
        for &ch in text {
            if ch == b'\n' {
                // newline — skip
                continue;
            }
            self.draw_char(cx, y, ch, color);
            cx += 9; // 8px wide + 1px gap
        }
    }

    pub fn draw_char(&mut self, x: usize, y: usize, ch: u8, color: u32) {
        // Simple 8x16 font — each char is 16 bytes (1 bit per pixel, 8 wide)
        let glyph = BASIC_FONT.get(ch as usize).unwrap_or(&[0u8; 16]);
        for row in 0..16 {
            for col in 0..8 {
                if glyph[row] & (0x80 >> col) != 0 {
                    self.put_pixel(x + col, y + row, color);
                }
            }
        }
    }
}

// Minimal ASCII font (space through ~, 8x16)
// Only including a few chars for bootstrap — full font loaded from disk later
static BASIC_FONT: [[u8; 16]; 128] = {
    let mut font = [[0u8; 16]; 128];
    // Space
    // A
    font[b'A' as usize] = [0x00,0x18,0x3C,0x66,0x66,0xC3,0xC3,0xFF,0xC3,0xC3,0xC3,0xC3,0x00,0x00,0x00,0x00];
    // D
    font[b'D' as usize] = [0x00,0xFC,0x66,0x63,0x63,0x63,0x63,0x63,0x63,0x63,0x66,0xFC,0x00,0x00,0x00,0x00];
    // a
    font[b'a' as usize] = [0x00,0x00,0x00,0x00,0x3C,0x66,0x06,0x3E,0x66,0x66,0x66,0x3B,0x00,0x00,0x00,0x00];
    // i
    font[b'i' as usize] = [0x00,0x00,0x18,0x18,0x00,0x38,0x18,0x18,0x18,0x18,0x18,0x3C,0x00,0x00,0x00,0x00];
    // s
    font[b's' as usize] = [0x00,0x00,0x00,0x00,0x3E,0x63,0x60,0x3E,0x03,0x63,0x63,0x3E,0x00,0x00,0x00,0x00];
    // y
    font[b'y' as usize] = [0x00,0x00,0x00,0x00,0xC3,0xC3,0xC3,0xC3,0x66,0x3C,0x18,0x30,0x60,0xC0,0x00,0x00];
    font
};
