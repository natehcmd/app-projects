#![allow(dead_code)]

//! Unix-style pipes for Daisy OS.
//!
//! Provides unidirectional byte streams between tasks.
//! pipe() returns (read_fd, write_fd).

use core::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

const PIPE_BUF_SIZE: usize = 4096;
const MAX_PIPES: usize = 32;

struct PipeBuffer {
    data: [u8; PIPE_BUF_SIZE],
    read_pos: AtomicUsize,
    write_pos: AtomicUsize,
    reader_open: AtomicBool,
    writer_open: AtomicBool,
    active: AtomicBool,
}

impl PipeBuffer {
    const fn new() -> Self {
        Self {
            data: [0; PIPE_BUF_SIZE],
            read_pos: AtomicUsize::new(0),
            write_pos: AtomicUsize::new(0),
            reader_open: AtomicBool::new(false),
            writer_open: AtomicBool::new(false),
            active: AtomicBool::new(false),
        }
    }

    fn available(&self) -> usize {
        let w = self.write_pos.load(Ordering::Acquire);
        let r = self.read_pos.load(Ordering::Acquire);
        if w >= r { w - r } else { PIPE_BUF_SIZE - r + w }
    }

    fn free_space(&self) -> usize {
        PIPE_BUF_SIZE - 1 - self.available()
    }
}

static mut PIPES: [PipeBuffer; MAX_PIPES] = {
    const P: PipeBuffer = PipeBuffer::new();
    [P; MAX_PIPES]
};

/// Create a new pipe. Returns (pipe_id, read_end, write_end) or None.
pub fn create() -> Option<(usize, usize, usize)> {
    unsafe {
        for i in 0..MAX_PIPES {
            if !PIPES[i].active.load(Ordering::Relaxed) {
                PIPES[i].active.store(true, Ordering::Relaxed);
                PIPES[i].reader_open.store(true, Ordering::Relaxed);
                PIPES[i].writer_open.store(true, Ordering::Relaxed);
                PIPES[i].read_pos.store(0, Ordering::Relaxed);
                PIPES[i].write_pos.store(0, Ordering::Relaxed);

                // Allocate two FDs via VFS
                let read_fd = i * 2;      // even = read end
                let write_fd = i * 2 + 1; // odd = write end

                crate::serial::print(b"[pipe] Created pipe ");
                print_usize(i);
                crate::serial::print(b"\n");

                return Some((i, read_fd, write_fd));
            }
        }
    }
    None
}

/// Write to a pipe. Returns bytes written.
pub fn write(pipe_id: usize, data: &[u8]) -> Result<usize, &'static str> {
    if pipe_id >= MAX_PIPES {
        return Err("invalid pipe");
    }
    // SAFETY: single-core kernel; no concurrent access to PIPES.
    unsafe {
        let pipe = &mut PIPES[pipe_id];
        if !pipe.active.load(Ordering::Relaxed) { return Err("pipe closed"); }
        if !pipe.reader_open.load(Ordering::Relaxed) { return Err("broken pipe"); }
        let mut written = 0;
        for &byte in data {
            if pipe.free_space() == 0 { break; }
            let pos = pipe.write_pos.load(Ordering::Relaxed);
            pipe.data[pos] = byte;
            pipe.write_pos.store((pos + 1) % PIPE_BUF_SIZE, Ordering::Release);
            written += 1;
        }
        Ok(written)
    }
}

/// Read from a pipe. Returns bytes read.
pub fn read(pipe_id: usize, buf: &mut [u8]) -> Result<usize, &'static str> {
    if pipe_id >= MAX_PIPES {
        return Err("invalid pipe");
    }
    // SAFETY: single-core kernel; no concurrent access to PIPES.
    unsafe {
        let pipe = &mut PIPES[pipe_id];
        if !pipe.active.load(Ordering::Relaxed) { return Err("pipe closed"); }
        let mut count = 0;
        for slot in buf.iter_mut() {
            if pipe.available() == 0 {
                if !pipe.writer_open.load(Ordering::Relaxed) && count == 0 {
                    return Ok(0); // EOF
                }
                break;
            }
            let pos = pipe.read_pos.load(Ordering::Relaxed);
            *slot = pipe.data[pos];
            pipe.read_pos.store((pos + 1) % PIPE_BUF_SIZE, Ordering::Release);
            count += 1;
        }
        Ok(count)
    }
}

/// Close the read end of a pipe.
pub fn close_read(pipe_id: usize) {
    if pipe_id < MAX_PIPES {
        unsafe {
            PIPES[pipe_id].reader_open.store(false, Ordering::Relaxed);
            maybe_destroy(pipe_id);
        }
    }
}

/// Close the write end of a pipe.
pub fn close_write(pipe_id: usize) {
    if pipe_id < MAX_PIPES {
        unsafe {
            PIPES[pipe_id].writer_open.store(false, Ordering::Relaxed);
            maybe_destroy(pipe_id);
        }
    }
}

unsafe fn maybe_destroy(pipe_id: usize) {
    let pipe = &PIPES[pipe_id];
    if !pipe.reader_open.load(Ordering::Relaxed) && !pipe.writer_open.load(Ordering::Relaxed) {
        pipe.active.store(false, Ordering::Relaxed);
    }
}

fn print_usize(mut n: usize) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 20];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    while i > 0 { i -= 1; crate::serial::write_byte(buf[i]); }
}
