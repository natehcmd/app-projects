#![allow(dead_code)]

//! VGA text-mode driver for Daisy OS.
//! 80x25 character display at 0xB8000.

use core::fmt;
use spin::Mutex;

const VGA_BUFFER: usize = 0xB8000;
const WIDTH: usize = 80;
const HEIGHT: usize = 25;

#[repr(u8)]
#[derive(Clone, Copy)]
pub enum Color {
    Black = 0, Blue = 1, Green = 2, Cyan = 3,
    Red = 4, Magenta = 5, Brown = 6, LightGray = 7,
    DarkGray = 8, LightBlue = 9, LightGreen = 10, LightCyan = 11,
    LightRed = 12, Pink = 13, Yellow = 14, White = 15,
}

fn color_code(fg: Color, bg: Color) -> u8 {
    (bg as u8) << 4 | (fg as u8)
}

pub struct Writer {
    col: usize,
    row: usize,
    color: u8,
}

impl Writer {
    pub const fn new() -> Self {
        Self { col: 0, row: 0, color: 0x0F } // white on black
    }

    pub fn set_color(&mut self, fg: Color, bg: Color) {
        self.color = color_code(fg, bg);
    }

    pub fn put_char(&mut self, c: u8) {
        match c {
            b'\n' => self.newline(),
            c => {
                if self.col >= WIDTH { self.newline(); }
                let offset = self.row * WIDTH + self.col;
                unsafe {
                    let ptr = VGA_BUFFER as *mut u16;
                    *ptr.add(offset) = (self.color as u16) << 8 | c as u16;
                }
                self.col += 1;
            }
        }
    }

    pub fn print(&mut self, s: &[u8]) {
        for &c in s { self.put_char(c); }
    }

    fn newline(&mut self) {
        self.col = 0;
        self.row += 1;
        if self.row >= HEIGHT {
            self.scroll();
            self.row = HEIGHT - 1;
        }
    }

    fn scroll(&mut self) {
        unsafe {
            let buf = VGA_BUFFER as *mut u16;
            // Move rows 1..HEIGHT up by one
            core::ptr::copy(buf.add(WIDTH), buf, WIDTH * (HEIGHT - 1));
            // Clear last row
            let blank = (self.color as u16) << 8 | b' ' as u16;
            for x in 0..WIDTH {
                *buf.add((HEIGHT - 1) * WIDTH + x) = blank;
            }
        }
    }

    pub fn clear(&mut self) {
        let blank = (self.color as u16) << 8 | b' ' as u16;
        unsafe {
            let buf = VGA_BUFFER as *mut u16;
            for i in 0..WIDTH * HEIGHT {
                *buf.add(i) = blank;
            }
        }
        self.col = 0;
        self.row = 0;
    }
}

impl fmt::Write for Writer {
    fn write_str(&mut self, s: &str) -> fmt::Result {
        self.print(s.as_bytes());
        Ok(())
    }
}

pub static WRITER: Mutex<Writer> = Mutex::new(Writer::new());

pub fn init() {
    WRITER.lock().clear();
    WRITER.lock().print(b"[vga] Text mode initialized (80x25)\n");
}

pub fn print(s: &[u8]) {
    WRITER.lock().print(s);
}

pub fn clear() {
    WRITER.lock().clear();
}
