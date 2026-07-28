#![allow(dead_code)]

//! /proc virtual filesystem for Daisy OS.
//!
//! Exposes kernel state as readable virtual files:
//! /proc/cpuinfo, /proc/meminfo, /proc/uptime, /proc/version,
//! /proc/loadavg, /proc/stat, /proc/[pid]/stat, /proc/[pid]/status

use crate::vfs::{Filesystem, OpenFlags, FileStat, FileType, DirEntry, VfsResult, VfsError};

/// ProcFS implementation.
pub struct ProcFs;

impl ProcFs {
    pub const fn new() -> Self {
        Self
    }

    /// Generate /proc/cpuinfo content.
    fn gen_cpuinfo(&self, buf: &mut [u8]) -> usize {
        let content = b"processor\t: 0\nvendor_id\t: DaisyOS\nmodel name\t: Daisy Virtual CPU\ncpu MHz\t\t: 1000.000\ncache size\t: 256 KB\nflags\t\t: fpu vme de pse tsc msr pae mce cx8 apic\nbogomips\t: 2000.00\n";
        let len = content.len().min(buf.len());
        buf[..len].copy_from_slice(&content[..len]);
        len
    }

    fn gen_meminfo(&self, buf: &mut [u8]) -> usize {
        let (total_kb, free_kb) = {
            let g = crate::memory::FRAME_ALLOCATOR.lock();
            (g.total_frames() as u64 * 4, g.free_count() as u64 * 4)
        };

        let mut w = BufWriter::new(buf);
        w.write_str("MemTotal:       "); w.write_u64(total_kb);
        w.write_str(" kB\nMemFree:        "); w.write_u64(free_kb);
        w.write_str(" kB\nMemAvailable:   "); w.write_u64(free_kb);
        w.write_str(" kB\nBuffers:        0 kB\nCached:         0 kB\nSwapTotal:      0 kB\nSwapFree:       0 kB\n");
        w.pos
    }

    /// Generate /proc/uptime content.
    fn gen_uptime(&self, buf: &mut [u8]) -> usize {
        let ms = crate::timer::uptime_ms();
        let secs = ms / 1000;
        let frac = (ms % 1000) / 10;

        let mut w = BufWriter::new(buf);
        w.write_u64(secs);
        w.write_byte(b'.');
        if frac < 10 { w.write_byte(b'0'); }
        w.write_u64(frac);
        w.write_str(" 0.00\n"); // idle time (not tracked yet)
        w.pos
    }

    /// Generate /proc/version content.
    fn gen_version(&self, buf: &mut [u8]) -> usize {
        let content = b"Daisy OS version 2.0 (bloom) (rustc nightly) #1 SMP PREEMPT daisy-rust-kernel\n";
        let len = content.len().min(buf.len());
        buf[..len].copy_from_slice(&content[..len]);
        len
    }

    /// Generate /proc/loadavg content.
    fn gen_loadavg(&self, buf: &mut [u8]) -> usize {
        // Placeholder — real load tracking needs scheduler integration
        let content = b"0.00 0.00 0.00 1/1 1\n";
        let len = content.len().min(buf.len());
        buf[..len].copy_from_slice(&content[..len]);
        len
    }

    /// Generate /proc/stat content.
    fn gen_stat(&self, buf: &mut [u8]) -> usize {
        let ticks = crate::timer::ticks();
        let mut w = BufWriter::new(buf);
        w.write_str("cpu  ");
        w.write_u64(ticks); // user
        w.write_str(" 0 0 ");
        w.write_u64(ticks); // idle (approximate)
        w.write_str(" 0 0 0 0 0 0\n");
        w.write_str("processes 1\n");
        w.write_str("procs_running 1\n");
        w.write_str("procs_blocked 0\n");
        w.pos
    }

    /// Generate content for a virtual proc file.
    fn generate(&self, path: &str, buf: &mut [u8]) -> VfsResult<usize> {
        match path {
            "/cpuinfo" | "cpuinfo" => Ok(self.gen_cpuinfo(buf)),
            "/meminfo" | "meminfo" => Ok(self.gen_meminfo(buf)),
            "/uptime" | "uptime" => Ok(self.gen_uptime(buf)),
            "/version" | "version" => Ok(self.gen_version(buf)),
            "/loadavg" | "loadavg" => Ok(self.gen_loadavg(buf)),
            "/stat" | "stat" => Ok(self.gen_stat(buf)),
            "/" => {
                // Root directory of /proc
                let content = b"cpuinfo\nmeminfo\nuptime\nversion\nloadavg\nstat\ndaisy\n";
                let len = content.len().min(buf.len());
                buf[..len].copy_from_slice(&content[..len]);
                Ok(len)
            }
            "/daisy" | "daisy" => {
                // Daisy-specific kernel info
                let mut w = BufWriter::new(buf);
                w.write_str("kernel: daisy-rust-kernel 2.0\n");
                w.write_str("arch: x86_64\n");
                w.write_str("tasks: ");
                w.write_u64(1); // TODO: get from task manager
                w.write_str("\ncapabilities: enabled\n");
                w.write_str("ipc_endpoints: ");
                w.write_u64(0); // TODO: get from IPC
                w.write_str("\n");
                Ok(w.pos)
            }
            _ => Err(VfsError::NotFound),
        }
    }
}

impl Filesystem for ProcFs {
    fn fs_type(&self) -> &str {
        "procfs"
    }

    fn open(&self, path: &str, _flags: OpenFlags) -> VfsResult<u64> {
        // Verify the file exists by trying to generate it
        let mut tmp = [0u8; 16];
        self.generate(path, &mut tmp)?;
        // Return a hash of the path as handle (stateless)
        Ok(simple_hash(path))
    }

    fn read(&self, _handle: u64, buf: &mut [u8], _offset: u64) -> VfsResult<usize> {
        // For procfs, we regenerate content on every read
        // In a real implementation, we'd cache based on handle
        // For now, return full content (offset handling TODO)
        Ok(0)
    }

    fn write(&self, _handle: u64, _buf: &[u8], _offset: u64) -> VfsResult<usize> {
        Err(VfsError::PermissionDenied) // procfs is read-only
    }

    fn close(&self, _handle: u64) -> VfsResult<()> {
        Ok(()) // stateless
    }

    fn stat(&self, path: &str) -> VfsResult<FileStat> {
        let file_type = if path == "/" {
            FileType::Directory
        } else {
            FileType::Regular
        };

        Ok(FileStat {
            file_type,
            size: 0, // virtual files have no fixed size
            mode: 0o444, // read-only
            ..FileStat::zeroed()
        })
    }

    fn readdir(&self, path: &str, entries: &mut [DirEntry]) -> VfsResult<usize> {
        if !path.is_empty() && path != "/" {
            return Err(VfsError::NotADirectory);
        }
        const NAMES: &[&str] = &["cpuinfo", "meminfo", "uptime", "version", "loadavg", "stat", "daisy"];
        let count = entries.len().min(NAMES.len());
        for (i, name) in NAMES.iter().take(count).enumerate() {
            let bytes = name.as_bytes();
            entries[i].name[..bytes.len()].copy_from_slice(bytes);
            entries[i].name_len = bytes.len();
            entries[i].inode = i as u64 + 1;
            entries[i].file_type = FileType::Regular;
        }
        Ok(count)
    }
}

/// Read a procfs file's full content into a buffer.
pub fn read_file(path: &str, buf: &mut [u8]) -> VfsResult<usize> {
    let fs = ProcFs::new();
    fs.generate(path, buf)
}

/// Simple non-crypto hash for handles.
fn simple_hash(s: &str) -> u64 {
    let mut h: u64 = 5381;
    for b in s.bytes() {
        h = h.wrapping_mul(33).wrapping_add(b as u64);
    }
    h
}

/// Tiny buffer writer helper (no alloc needed).
struct BufWriter<'a> {
    buf: &'a mut [u8],
    pos: usize,
}

impl<'a> BufWriter<'a> {
    fn new(buf: &'a mut [u8]) -> Self {
        Self { buf, pos: 0 }
    }

    fn write_byte(&mut self, b: u8) {
        if self.pos < self.buf.len() {
            self.buf[self.pos] = b;
            self.pos += 1;
        }
    }

    fn write_str(&mut self, s: &str) {
        let bytes = s.as_bytes();
        let len = bytes.len().min(self.buf.len() - self.pos);
        self.buf[self.pos..self.pos + len].copy_from_slice(&bytes[..len]);
        self.pos += len;
    }

    fn write_u64(&mut self, mut n: u64) {
        if n == 0 {
            self.write_byte(b'0');
            return;
        }
        let mut tmp = [0u8; 20];
        let mut i = 0;
        while n > 0 {
            tmp[i] = b'0' + (n % 10) as u8;
            n /= 10;
            i += 1;
        }
        while i > 0 {
            i -= 1;
            self.write_byte(tmp[i]);
        }
    }
}
