#![allow(dead_code)]

//! /sys virtual filesystem for Daisy OS.
//!
//! Exposes device and driver information:
//! /sys/class/net/     - network interfaces
//! /sys/class/block/   - block devices
//! /sys/class/input/   - input devices
//! /sys/devices/system/cpu/ - CPU info
//! /sys/power/state    - power management

use crate::vfs::{Filesystem, OpenFlags, FileStat, FileType, DirEntry, VfsResult, VfsError};

pub struct SysFs;

impl Default for SysFs {
    fn default() -> Self { Self::new() }
}

impl SysFs {
    pub const fn new() -> Self {
        Self
    }

    fn generate(&self, path: &str, buf: &mut [u8]) -> VfsResult<usize> {
        match path {
            "/" => {
                let c = b"class\ndevices\npower\nkernel\n";
                let l = c.len().min(buf.len());
                buf[..l].copy_from_slice(&c[..l]);
                Ok(l)
            }
            "/class" | "class" => {
                let c = b"net\nblock\ninput\nthermal\n";
                let l = c.len().min(buf.len());
                buf[..l].copy_from_slice(&c[..l]);
                Ok(l)
            }
            "/devices/system/cpu/online" => {
                let c = b"0\n"; // single CPU for now
                buf[..c.len()].copy_from_slice(c);
                Ok(c.len())
            }
            "/devices/system/cpu/cpu0/cpufreq/scaling_governor" => {
                let c = b"performance\n";
                let l = c.len().min(buf.len());
                buf[..l].copy_from_slice(&c[..l]);
                Ok(l)
            }
            "/power/state" => {
                let c = b"freeze mem disk\n";
                let l = c.len().min(buf.len());
                buf[..l].copy_from_slice(&c[..l]);
                Ok(l)
            }
            "/kernel/hostname" => {
                let c = b"daisy\n";
                buf[..c.len()].copy_from_slice(c);
                Ok(c.len())
            }
            "/kernel/osrelease" => {
                let c = b"2.0.0-daisy\n";
                buf[..c.len()].copy_from_slice(c);
                Ok(c.len())
            }
            "/class/thermal/thermal_zone0/temp" => {
                // CPU temperature (placeholder — real impl reads ACPI)
                let c = b"45000\n"; // 45.0°C in millidegrees
                buf[..c.len()].copy_from_slice(c);
                Ok(c.len())
            }
            _ => Err(VfsError::NotFound),
        }
    }
}

impl Filesystem for SysFs {
    fn fs_type(&self) -> &str { "sysfs" }

    fn open(&self, path: &str, _flags: OpenFlags) -> VfsResult<u64> {
        let mut tmp = [0u8; 16];
        self.generate(path, &mut tmp)?;
        Ok(simple_hash(path))
    }

    fn read(&self, _handle: u64, buf: &mut [u8], _offset: u64) -> VfsResult<usize> {
        Ok(0) // content generated on demand via generate()
    }

    fn write(&self, _handle: u64, buf: &[u8], _offset: u64) -> VfsResult<usize> {
        // Some sysfs files are writable (e.g., power/state, scaling_governor)
        // For now, accept writes but don't act on them
        Ok(buf.len())
    }

    fn close(&self, _handle: u64) -> VfsResult<()> { Ok(()) }

    fn stat(&self, path: &str) -> VfsResult<FileStat> {
        let ft = match path {
            "/" | "/class" | "/devices" | "/power" | "/kernel" => FileType::Directory,
            _ => FileType::Regular,
        };
        Ok(FileStat { file_type: ft, mode: 0o644, ..FileStat::zeroed() })
    }

    fn readdir(&self, path: &str, entries: &mut [DirEntry]) -> VfsResult<usize> {
        let names: &[&str] = match path {
            "/" => &["class", "devices", "power", "kernel"],
            "/class" => &["net", "block", "input", "thermal"],
            _ => return Err(VfsError::NotADirectory),
        };
        let count = names.len().min(entries.len());
        for (i, name) in names.iter().take(count).enumerate() {
            let b = name.as_bytes();
            entries[i].name[..b.len()].copy_from_slice(b);
            entries[i].name_len = b.len();
            entries[i].inode = i as u64 + 1;
            entries[i].file_type = FileType::Directory;
        }
        Ok(count)
    }
}

pub fn read_file(path: &str, buf: &mut [u8]) -> VfsResult<usize> {
    SysFs::new().generate(path, buf)
}

fn simple_hash(s: &str) -> u64 {
    let mut h: u64 = 5381;
    for b in s.bytes() { h = h.wrapping_mul(33).wrapping_add(b as u64); }
    h
}
