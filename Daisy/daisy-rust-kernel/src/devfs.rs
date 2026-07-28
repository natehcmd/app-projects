#![allow(dead_code)]

//! /dev virtual filesystem for Daisy OS.
//!
//! Provides character devices: null, zero, random, console, serial0.
//! Implements the crate::vfs::Filesystem trait.

use core::sync::atomic::{AtomicU32, Ordering};
use crate::vfs::{
    DirEntry, FileStat, FileType, Filesystem, OpenFlags, VfsError, VfsResult,
};

/// Device types available under /dev.
#[derive(Clone, Copy, PartialEq)]
enum DeviceKind {
    Null,
    Zero,
    Random,
    Console,
    Serial0,
}

const NUM_DEVICES: usize = 5;

/// Device name bytes and lengths (stored as fixed arrays).
static DEVICE_NAMES: [[u8; 8]; NUM_DEVICES] = [
    *b"null\0\0\0\0",
    *b"zero\0\0\0\0",
    *b"random\0\0",
    *b"console\0",
    *b"serial0\0",
];
static DEVICE_NAME_LENS: [usize; NUM_DEVICES] = [4, 4, 6, 7, 7];
static DEVICE_KINDS: [DeviceKind; NUM_DEVICES] = [
    DeviceKind::Null,
    DeviceKind::Zero,
    DeviceKind::Random,
    DeviceKind::Console,
    DeviceKind::Serial0,
];

/// PRNG seed for /dev/random.
static SEED: AtomicU32 = AtomicU32::new(12345);

/// Maximum simultaneously open handles.
const MAX_HANDLES: usize = 16;

/// An open handle: maps a handle id to a device index.
#[derive(Clone, Copy)]
struct OpenHandle {
    active: bool,
    device_idx: usize,
}

/// The devfs instance (lives in a static).
pub struct DevFs {
    handles: [OpenHandle; MAX_HANDLES],
    next_handle: u64,
}

impl DevFs {
    pub const fn new() -> Self {
        Self {
            handles: [OpenHandle { active: false, device_idx: 0 }; MAX_HANDLES],
            next_handle: 1,
        }
    }

    #[inline]
    fn find_device(name: &str) -> Option<usize> {
        let name_bytes = name.as_bytes();
        (0..NUM_DEVICES).find(|&i| {
            &DEVICE_NAMES[i][..DEVICE_NAME_LENS[i]] == name_bytes
        })
    }

    /// Find the slot index for a given handle id.
    fn slot_for_handle(&self, handle: u64) -> Option<usize> {
        // handle id is stored as next_handle at allocation time; we store
        // slot index + 1 as the handle id actually. Simpler: iterate.
        // Actually we just use slot index as handle for simplicity.
        let idx = handle as usize;
        if idx < MAX_HANDLES && self.handles[idx].active {
            Some(idx)
        } else {
            None
        }
    }
}

static mut DEV_FS: DevFs = DevFs::new();

/// Get a reference to the global DevFs instance.
pub fn get_devfs() -> &'static DevFs {
    unsafe { &DEV_FS }
}

impl Filesystem for DevFs {
    fn fs_type(&self) -> &str {
        "devfs"
    }

    fn open(&self, path: &str, _flags: OpenFlags) -> VfsResult<u64> {
        // Strip leading slash if present.
        let name = if path.as_bytes().first() == Some(&b'/') {
            &path[1..]
        } else {
            path
        };

        let dev_idx = DevFs::find_device(name).ok_or(VfsError::NotFound)?;

        unsafe {
            let mut i = 0;
            while i < MAX_HANDLES {
                if !DEV_FS.handles[i].active {
                    DEV_FS.handles[i] = OpenHandle {
                        active: true,
                        device_idx: dev_idx,
                    };
                    return Ok(i as u64);
                }
                i += 1;
            }
        }
        Err(VfsError::TooManyOpenFiles)
    }

    fn read(&self, handle: u64, buf: &mut [u8], _offset: u64) -> VfsResult<usize> {
        let slot = handle as usize;
        let dev_idx = unsafe {
            if slot >= MAX_HANDLES || !DEV_FS.handles[slot].active {
                return Err(VfsError::BadFileDescriptor);
            }
            DEV_FS.handles[slot].device_idx
        };

        match DEVICE_KINDS[dev_idx] {
            DeviceKind::Null => Ok(0),
            DeviceKind::Zero => {
                buf.fill(0);
                Ok(buf.len())
            }
            DeviceKind::Random => {
                let mut seed = SEED.load(Ordering::Relaxed);
                let mut i = 0;
                while i < buf.len() {
                    seed = seed.wrapping_mul(1103515245).wrapping_add(12345);
                    buf[i] = (seed >> 16) as u8;
                    i += 1;
                }
                SEED.store(seed, Ordering::Relaxed);
                Ok(buf.len())
            }
            DeviceKind::Console => Ok(0), // console read not implemented
            DeviceKind::Serial0 => Ok(0), // serial read not implemented here
        }
    }

    fn write(&self, handle: u64, buf: &[u8], _offset: u64) -> VfsResult<usize> {
        let slot = handle as usize;
        let dev_idx = unsafe {
            if slot >= MAX_HANDLES || !DEV_FS.handles[slot].active {
                return Err(VfsError::BadFileDescriptor);
            }
            DEV_FS.handles[slot].device_idx
        };

        match DEVICE_KINDS[dev_idx] {
            DeviceKind::Null | DeviceKind::Zero | DeviceKind::Random => Ok(buf.len()),
            DeviceKind::Console => {
                crate::vga::print(buf);
                Ok(buf.len())
            }
            DeviceKind::Serial0 => {
                for &b in buf { crate::serial::write_byte(b); }
                Ok(buf.len())
            }
        }
    }

    fn close(&self, handle: u64) -> VfsResult<()> {
        let slot = handle as usize;
        unsafe {
            if slot >= MAX_HANDLES || !DEV_FS.handles[slot].active {
                return Err(VfsError::BadFileDescriptor);
            }
            DEV_FS.handles[slot].active = false;
        }
        Ok(())
    }

    fn stat(&self, path: &str) -> VfsResult<FileStat> {
        // If path is "/" or empty, stat the directory itself.
        let name = if path.as_bytes().first() == Some(&b'/') {
            &path[1..]
        } else {
            path
        };

        if name.is_empty() {
            // Root of /dev is a directory.
            let mut st = FileStat::zeroed();
            st.file_type = FileType::Directory;
            st.mode = 0o755;
            return Ok(st);
        }

        let _dev_idx = DevFs::find_device(name).ok_or(VfsError::NotFound)?;
        let mut st = FileStat::zeroed();
        st.file_type = FileType::CharDevice;
        st.mode = 0o666;
        Ok(st)
    }

    fn readdir(&self, _path: &str, entries: &mut [DirEntry]) -> VfsResult<usize> {
        let count = entries.len().min(NUM_DEVICES);
        for i in 0..count {
            let nlen = DEVICE_NAME_LENS[i];
            entries[i].name = [0u8; 256];
            entries[i].name[..nlen].copy_from_slice(&DEVICE_NAMES[i][..nlen]);
            entries[i].name_len = nlen;
            entries[i].inode = i as u64;
            entries[i].file_type = FileType::CharDevice;
        }
        Ok(count)
    }
}
