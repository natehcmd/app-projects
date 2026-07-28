#![allow(dead_code)]

//! Virtual Filesystem (VFS) layer for Daisy OS.
//!
//! Provides a unified interface for mounting filesystems and performing
//! file operations (open, read, write, close, stat, readdir).

use core::fmt;

/// Maximum open file descriptors per process.
pub const MAX_FDS: usize = 256;
/// Maximum mounted filesystems.
pub const MAX_MOUNTS: usize = 16;
/// Maximum path length.
pub const MAX_PATH: usize = 256;

/// File types.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum FileType {
    Regular,
    Directory,
    CharDevice,
    BlockDevice,
    Pipe,
    Socket,
    Symlink,
}

/// File open flags.
#[derive(Debug, Clone, Copy)]
pub struct OpenFlags(u32);

impl OpenFlags {
    pub const READ: Self = Self(1 << 0);
    pub const WRITE: Self = Self(1 << 1);
    pub const CREATE: Self = Self(1 << 2);
    pub const APPEND: Self = Self(1 << 3);
    pub const TRUNCATE: Self = Self(1 << 4);
    pub const DIRECTORY: Self = Self(1 << 5);

    pub fn contains(&self, flag: Self) -> bool {
        self.0 & flag.0 != 0
    }

    pub fn bits(&self) -> u32 {
        self.0
    }

    pub fn from_bits(bits: u32) -> Self {
        Self(bits)
    }
}

/// File metadata (stat).
#[derive(Debug, Clone, Copy)]
pub struct FileStat {
    pub file_type: FileType,
    pub size: u64,
    pub block_size: u32,
    pub blocks: u64,
    pub mode: u16,       // permissions
    pub uid: u32,
    pub gid: u32,
    pub inode: u64,
    pub nlinks: u32,
    pub atime: u64,      // access time (unix timestamp)
    pub mtime: u64,      // modify time
    pub ctime: u64,      // change time
}

impl FileStat {
    pub const fn zeroed() -> Self {
        Self {
            file_type: FileType::Regular,
            size: 0,
            block_size: 512,
            blocks: 0,
            mode: 0o644,
            uid: 0,
            gid: 0,
            inode: 0,
            nlinks: 1,
            atime: 0,
            mtime: 0,
            ctime: 0,
        }
    }
}

/// Directory entry.
#[derive(Clone)]
pub struct DirEntry {
    pub name: [u8; 256],
    pub name_len: usize,
    pub inode: u64,
    pub file_type: FileType,
}

impl DirEntry {
    pub fn name_str(&self) -> &str {
        core::str::from_utf8(&self.name[..self.name_len]).unwrap_or("???")
    }
}

/// VFS error codes.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum VfsError {
    NotFound,
    PermissionDenied,
    AlreadyExists,
    NotADirectory,
    IsADirectory,
    NotEmpty,
    InvalidPath,
    NoSpace,
    IoError,
    TooManyOpenFiles,
    BadFileDescriptor,
    NotMounted,
    NotSupported,
    MountFull,
    BusyDevice,
}

impl fmt::Display for VfsError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::NotFound => write!(f, "not found"),
            Self::PermissionDenied => write!(f, "permission denied"),
            Self::AlreadyExists => write!(f, "already exists"),
            Self::NotADirectory => write!(f, "not a directory"),
            Self::IsADirectory => write!(f, "is a directory"),
            Self::NotEmpty => write!(f, "directory not empty"),
            Self::InvalidPath => write!(f, "invalid path"),
            Self::NoSpace => write!(f, "no space left"),
            Self::IoError => write!(f, "I/O error"),
            Self::TooManyOpenFiles => write!(f, "too many open files"),
            Self::BadFileDescriptor => write!(f, "bad file descriptor"),
            Self::NotMounted => write!(f, "not mounted"),
            Self::NotSupported => write!(f, "not supported"),
            Self::MountFull => write!(f, "mount table full"),
            Self::BusyDevice => write!(f, "device busy"),
        }
    }
}

pub type VfsResult<T> = Result<T, VfsError>;

/// Filesystem operations trait — each filesystem (FAT32, procfs, sysfs, etc.) implements this.
pub trait Filesystem {
    /// Filesystem type name (e.g., "fat32", "procfs", "sysfs").
    fn fs_type(&self) -> &str;

    /// Open a file by path relative to mount point.
    fn open(&self, path: &str, flags: OpenFlags) -> VfsResult<u64>; // returns inode/handle

    /// Read from an open file.
    fn read(&self, handle: u64, buf: &mut [u8], offset: u64) -> VfsResult<usize>;

    /// Write to an open file.
    fn write(&self, handle: u64, buf: &[u8], offset: u64) -> VfsResult<usize>;

    /// Close an open file.
    fn close(&self, handle: u64) -> VfsResult<()>;

    /// Get file metadata.
    fn stat(&self, path: &str) -> VfsResult<FileStat>;

    /// Read directory entries.
    fn readdir(&self, path: &str, entries: &mut [DirEntry]) -> VfsResult<usize>;

    /// Create a file.
    fn create(&self, path: &str, file_type: FileType, mode: u16) -> VfsResult<()> {
        let _ = (path, file_type, mode);
        Err(VfsError::NotSupported)
    }

    /// Remove a file or empty directory.
    fn remove(&self, path: &str) -> VfsResult<()> {
        let _ = path;
        Err(VfsError::NotSupported)
    }
}

/// A mounted filesystem.
struct MountPoint {
    path: [u8; MAX_PATH],   // mount path (e.g., "/", "/proc", "/sys")
    path_len: usize,
    fs_index: usize,         // index into filesystem table
    active: bool,
}

/// File descriptor.
#[derive(Clone, Copy)]
pub struct FileDescriptor {
    pub mount_index: usize,  // which mount point
    pub handle: u64,         // filesystem-internal handle
    pub offset: u64,         // current read/write position
    pub flags: OpenFlags,
    pub active: bool,
}

impl FileDescriptor {
    const fn empty() -> Self {
        Self {
            mount_index: 0,
            handle: 0,
            offset: 0,
            flags: OpenFlags(0),
            active: false,
        }
    }
}

/// Global mount table.
static mut MOUNTS: [MountPoint; MAX_MOUNTS] = {
    const EMPTY: MountPoint = MountPoint {
        path: [0; MAX_PATH],
        path_len: 0,
        fs_index: 0,
        active: false,
    };
    [EMPTY; MAX_MOUNTS]
};

/// Per-process file descriptor table (for now, global single-process).
static mut FD_TABLE: [FileDescriptor; MAX_FDS] = [FileDescriptor::empty(); MAX_FDS];

/// Mount a filesystem at a path.
pub fn mount(path: &str, fs_index: usize) -> VfsResult<()> {
    if path.is_empty() || !path.starts_with('/') {
        return Err(VfsError::InvalidPath);
    }

    unsafe {
        for i in 0..MAX_MOUNTS {
            if !MOUNTS[i].active {
                let bytes = path.as_bytes();
                let len = bytes.len().min(MAX_PATH);
                MOUNTS[i].path[..len].copy_from_slice(&bytes[..len]);
                MOUNTS[i].path_len = len;
                MOUNTS[i].fs_index = fs_index;
                MOUNTS[i].active = true;

                crate::serial::print(b"[vfs] Mounted fs ");
                print_usize(fs_index);
                crate::serial::print(b" at ");
                crate::serial::print(bytes);
                crate::serial::print(b"\n");
                return Ok(());
            }
        }
    }
    Err(VfsError::MountFull)
}

/// Unmount a filesystem at a path.
pub fn umount(path: &str) -> VfsResult<()> {
    unsafe {
        for i in 0..MAX_MOUNTS {
            if MOUNTS[i].active && &MOUNTS[i].path[..MOUNTS[i].path_len] == path.as_bytes() {
                MOUNTS[i].active = false;
                return Ok(());
            }
        }
    }
    Err(VfsError::NotMounted)
}

/// Find the best-matching mount point for a path.
/// Returns (mount_index, relative_path).
fn resolve_mount(path: &str) -> VfsResult<(usize, &str)> {
    let mut best_idx = usize::MAX;
    let mut best_len = 0;

    unsafe {
        for i in 0..MAX_MOUNTS {
            if !MOUNTS[i].active {
                continue;
            }
            let mp = core::str::from_utf8(&MOUNTS[i].path[..MOUNTS[i].path_len])
                .map_err(|_| VfsError::InvalidPath)?;

            if path.starts_with(mp) && MOUNTS[i].path_len > best_len {
                // Ensure mount path is a proper prefix (ends at / boundary)
                if MOUNTS[i].path_len == path.len()
                    || path.as_bytes()[MOUNTS[i].path_len] == b'/'
                    || mp == "/"
                {
                    best_idx = i;
                    best_len = MOUNTS[i].path_len;
                }
            }
        }
    }

    if best_idx == usize::MAX {
        return Err(VfsError::NotMounted);
    }

    // Compute relative path
    let rel = if best_len >= path.len() {
        "/"
    } else {
        &path[best_len..]
    };

    Ok((best_idx, if rel.is_empty() { "/" } else { rel }))
}

/// Allocate a file descriptor.
pub fn fd_alloc(mount_index: usize, handle: u64, flags: OpenFlags) -> VfsResult<usize> {
    unsafe {
        // FDs 0-2 are stdin/stdout/stderr by convention
        for i in 3..MAX_FDS {
            if !FD_TABLE[i].active {
                FD_TABLE[i] = FileDescriptor {
                    mount_index,
                    handle,
                    offset: 0,
                    flags,
                    active: true,
                };
                return Ok(i);
            }
        }
    }
    Err(VfsError::TooManyOpenFiles)
}

/// Free a file descriptor.
pub fn fd_free(fd: usize) -> VfsResult<()> {
    if fd >= MAX_FDS {
        return Err(VfsError::BadFileDescriptor);
    }
    unsafe {
        if !FD_TABLE[fd].active {
            return Err(VfsError::BadFileDescriptor);
        }
        FD_TABLE[fd].active = false;
    }
    Ok(())
}

/// Get a file descriptor.
pub fn fd_get(fd: usize) -> VfsResult<FileDescriptor> {
    if fd >= MAX_FDS {
        return Err(VfsError::BadFileDescriptor);
    }
    unsafe {
        if !FD_TABLE[fd].active {
            return Err(VfsError::BadFileDescriptor);
        }
        Ok(FD_TABLE[fd])
    }
}

/// Update the offset of a file descriptor.
pub fn fd_set_offset(fd: usize, offset: u64) -> VfsResult<()> {
    if fd >= MAX_FDS {
        return Err(VfsError::BadFileDescriptor);
    }
    unsafe {
        if !FD_TABLE[fd].active {
            return Err(VfsError::BadFileDescriptor);
        }
        FD_TABLE[fd].offset = offset;
    }
    Ok(())
}

/// Initialize the VFS with stdin/stdout/stderr.
pub fn init() {
    unsafe {
        // FD 0 = stdin (keyboard)
        FD_TABLE[0] = FileDescriptor {
            mount_index: 0,
            handle: 0,
            offset: 0,
            flags: OpenFlags::READ,
            active: true,
        };
        // FD 1 = stdout (serial/vga)
        FD_TABLE[1] = FileDescriptor {
            mount_index: 0,
            handle: 1,
            offset: 0,
            flags: OpenFlags::WRITE,
            active: true,
        };
        // FD 2 = stderr (serial)
        FD_TABLE[2] = FileDescriptor {
            mount_index: 0,
            handle: 2,
            offset: 0,
            flags: OpenFlags::WRITE,
            active: true,
        };
    }
    crate::serial::print(b"[vfs] Initialized (stdin/stdout/stderr)\n");
}

fn print_usize(mut n: usize) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 20];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}
