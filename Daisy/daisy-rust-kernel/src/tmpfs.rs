#![allow(dead_code)]

//! In-memory temporary filesystem (tmpfs) for Daisy OS.
//!
//! Provides 64 inodes and a 256 KB flat data pool.
//! Implements the crate::vfs::Filesystem trait.

use crate::vfs::{
    DirEntry, FileStat, FileType, Filesystem, OpenFlags, VfsError, VfsResult,
};

const INODES_COUNT: usize = 64;
const DATA_POOL_SIZE: usize = 262144; // 256 KB
const MAX_NAME: usize = 64;

/// On-disk (in-memory) inode.
#[derive(Clone, Copy)]
struct Inode {
    name: [u8; MAX_NAME],
    name_len: usize,
    file_type: FileType,
    size: usize,
    parent: usize,
    data_offset: usize,
    mode: u16,
    active: bool,
}

impl Inode {
    const fn empty() -> Self {
        Self {
            name: [0u8; MAX_NAME],
            name_len: 0,
            file_type: FileType::Regular,
            size: 0,
            parent: 0,
            data_offset: 0,
            mode: 0o644,
            active: false,
        }
    }
}

/// Root inode (index 0) is always an active directory.
const fn make_root_inode() -> Inode {
    Inode {
        name: [0u8; MAX_NAME],
        name_len: 0,
        file_type: FileType::Directory,
        size: 0,
        parent: 0,
        data_offset: 0,
        mode: 0o755,
        active: true,
    }
}

static mut INODES: [Inode; INODES_COUNT] = {
    let mut arr = [Inode::empty(); INODES_COUNT];
    arr[0] = make_root_inode();
    arr
};

static mut DATA: [u8; DATA_POOL_SIZE] = [0u8; DATA_POOL_SIZE];
static mut NEXT_DATA: usize = 0;

// ── Path resolution helpers ─────────────────────────────────────────

/// Walk a path like "/foo/bar" and return the inode index, or NotFound.
fn find_inode_by_path(path: &str) -> VfsResult<usize> {
    let bytes = path.as_bytes();
    if bytes.is_empty() {
        return Ok(0); // root
    }

    let mut current = 0usize; // start at root
    let mut seg_start = 0usize;
    let total = bytes.len();

    // Skip leading slash.
    if bytes[0] == b'/' {
        seg_start = 1;
    }

    loop {
        // Skip consecutive slashes.
        while seg_start < total && bytes[seg_start] == b'/' {
            seg_start += 1;
        }
        if seg_start >= total {
            break;
        }

        // Find end of this segment.
        let mut seg_end = seg_start;
        while seg_end < total && bytes[seg_end] != b'/' {
            seg_end += 1;
        }

        let seg = &bytes[seg_start..seg_end];
        let mut found = false;

        unsafe {
            let mut ino = 0;
            while ino < INODES_COUNT {
                if INODES[ino].active
                    && INODES[ino].parent == current
                    && ino != current
                    && INODES[ino].name_len == seg.len()
                    && bytes_eq(&INODES[ino].name[..INODES[ino].name_len], seg)
                {
                    current = ino;
                    found = true;
                    break;
                }
                ino += 1;
            }
        }

        if !found {
            return Err(VfsError::NotFound);
        }
        seg_start = seg_end;
    }

    Ok(current)
}

fn find_free_inode() -> VfsResult<usize> {
    unsafe {
        (1..INODES_COUNT)
            .find(|&i| !INODES[i].active)
            .ok_or(VfsError::NoSpace)
    }
}

/// Allocate `size` bytes from the flat data pool.
fn alloc_data(size: usize) -> VfsResult<usize> {
    unsafe {
        if NEXT_DATA + size > DATA_POOL_SIZE {
            return Err(VfsError::NoSpace);
        }
        let off = NEXT_DATA;
        NEXT_DATA += size;
        Ok(off)
    }
}

#[inline]
fn bytes_eq(a: &[u8], b: &[u8]) -> bool {
    a == b
}

/// Extract the last path segment and the parent path from a full path.
/// Returns (parent_path_end_index, name_start, name_end) into the byte slice.
/// E.g. "/foo/bar" -> parent="/foo", name="bar"
fn split_parent_name(path: &[u8]) -> Option<(usize, usize, usize)> {
    // Find last slash.
    let mut last_slash = 0;
    let mut i = 0;
    let mut found_slash = false;
    while i < path.len() {
        if path[i] == b'/' {
            last_slash = i;
            found_slash = true;
        }
        i += 1;
    }
    if !found_slash {
        return None;
    }
    let name_start = last_slash + 1;
    if name_start >= path.len() {
        return None; // trailing slash, no name
    }
    Some((last_slash, name_start, path.len()))
}

// ── TmpFs struct ────────────────────────────────────────────────────

pub struct TmpFs;

impl TmpFs {
    pub const fn new() -> Self {
        Self
    }
}

static mut TMP_FS: TmpFs = TmpFs::new();

pub fn get_tmpfs() -> &'static TmpFs {
    unsafe { &TMP_FS }
}

// ── Filesystem trait impl ───────────────────────────────────────────

impl Filesystem for TmpFs {
    fn fs_type(&self) -> &str {
        "tmpfs"
    }

    fn open(&self, path: &str, _flags: OpenFlags) -> VfsResult<u64> {
        let ino = find_inode_by_path(path)?;
        Ok(ino as u64)
    }

    fn read(&self, handle: u64, buf: &mut [u8], offset: u64) -> VfsResult<usize> {
        let ino = handle as usize;
        // SAFETY: single-core kernel; no concurrent mutation.
        unsafe {
            if ino >= INODES_COUNT || !INODES[ino].active {
                return Err(VfsError::BadFileDescriptor);
            }
            if INODES[ino].file_type == FileType::Directory {
                return Err(VfsError::IsADirectory);
            }
            let off = offset as usize;
            if off >= INODES[ino].size { return Ok(0); }
            let avail = INODES[ino].size - off;
            let to_read = buf.len().min(avail);
            let src_start = INODES[ino].data_offset + off;
            buf[..to_read].copy_from_slice(&DATA[src_start..src_start + to_read]);
            Ok(to_read)
        }
    }

    fn write(&self, handle: u64, buf: &[u8], offset: u64) -> VfsResult<usize> {
        let ino = handle as usize;
        // SAFETY: single-core kernel; no concurrent mutation.
        unsafe {
            if ino >= INODES_COUNT || !INODES[ino].active {
                return Err(VfsError::BadFileDescriptor);
            }
            if INODES[ino].file_type == FileType::Directory {
                return Err(VfsError::IsADirectory);
            }
            let off = offset as usize;
            let end = off + buf.len();
            let data_end = INODES[ino].data_offset + end;
            if data_end > DATA_POOL_SIZE { return Err(VfsError::NoSpace); }
            let dst_start = INODES[ino].data_offset + off;
            DATA[dst_start..dst_start + buf.len()].copy_from_slice(buf);
            if end > INODES[ino].size { INODES[ino].size = end; }
            Ok(buf.len())
        }
    }

    fn close(&self, handle: u64) -> VfsResult<()> {
        let ino = handle as usize;
        unsafe {
            if ino >= INODES_COUNT || !INODES[ino].active {
                return Err(VfsError::BadFileDescriptor);
            }
        }
        Ok(())
    }

    fn stat(&self, path: &str) -> VfsResult<FileStat> {
        let ino = find_inode_by_path(path)?;
        unsafe {
            if !INODES[ino].active {
                return Err(VfsError::NotFound);
            }
            let mut st = FileStat::zeroed();
            st.file_type = INODES[ino].file_type;
            st.size = INODES[ino].size as u64;
            st.mode = INODES[ino].mode;
            st.inode = ino as u64;
            st.nlinks = 1;
            Ok(st)
        }
    }

    fn readdir(&self, path: &str, entries: &mut [DirEntry]) -> VfsResult<usize> {
        let dir_ino = find_inode_by_path(path)?;
        // SAFETY: single-core kernel; no concurrent mutation.
        unsafe {
            if !INODES[dir_ino].active || INODES[dir_ino].file_type != FileType::Directory {
                return Err(VfsError::NotADirectory);
            }
            let mut count = 0usize;
            for i in 0..INODES_COUNT {
                if count >= entries.len() { break; }
                if INODES[i].active && INODES[i].parent == dir_ino && i != dir_ino {
                    let nlen = INODES[i].name_len;
                    entries[count].name = [0u8; 256];
                    entries[count].name[..nlen].copy_from_slice(&INODES[i].name[..nlen]);
                    entries[count].name_len = nlen;
                    entries[count].inode = i as u64;
                    entries[count].file_type = INODES[i].file_type;
                    count += 1;
                }
            }
            Ok(count)
        }
    }

    fn create(&self, path: &str, file_type: FileType, mode: u16) -> VfsResult<()> {
        let bytes = path.as_bytes();
        let (parent_end, name_start, name_end) =
            split_parent_name(bytes).ok_or(VfsError::InvalidPath)?;

        // Resolve parent directory.
        let parent_path = if parent_end == 0 { "/" } else {
            // Safety: path was valid &str so the sub-slice is also valid UTF-8
            // because we only split on ASCII '/'.
            unsafe { core::str::from_utf8_unchecked(&bytes[..parent_end]) }
        };
        let parent_ino = find_inode_by_path(parent_path)?;

        let name_bytes = &bytes[name_start..name_end];
        let name_len = name_bytes.len();
        if name_len == 0 || name_len > MAX_NAME {
            return Err(VfsError::InvalidPath);
        }

        // Check for duplicate.
        // SAFETY: single-core kernel; no concurrent mutation.
        unsafe {
            for i in 0..INODES_COUNT {
                if INODES[i].active
                    && INODES[i].parent == parent_ino
                    && bytes_eq(&INODES[i].name[..INODES[i].name_len], name_bytes)
                {
                    return Err(VfsError::AlreadyExists);
                }
            }
        }

        let new_ino = find_free_inode()?;
        let data_off = if file_type == FileType::Regular { alloc_data(0)? } else { 0 };

        // SAFETY: new_ino was found to be inactive above.
        unsafe {
            let node = &mut INODES[new_ino];
            node.name = [0u8; MAX_NAME];
            node.name[..name_len].copy_from_slice(name_bytes);
            node.name_len = name_len;
            node.file_type = file_type;
            node.size = 0;
            node.parent = parent_ino;
            node.data_offset = data_off;
            node.mode = mode;
            node.active = true;
        }

        crate::serial::print(b"[tmpfs] created inode\n");
        Ok(())
    }

    fn remove(&self, path: &str) -> VfsResult<()> {
        let ino = find_inode_by_path(path)?;
        if ino == 0 {
            return Err(VfsError::PermissionDenied); // can't remove root
        }
        unsafe {
            if !INODES[ino].active {
                return Err(VfsError::NotFound);
            }
            // If directory, check it's empty.
            if INODES[ino].file_type == FileType::Directory {
                let mut i = 0;
                while i < INODES_COUNT {
                    if INODES[i].active && INODES[i].parent == ino && i != ino {
                        return Err(VfsError::NotEmpty);
                    }
                    i += 1;
                }
            }
            INODES[ino].active = false;
        }
        Ok(())
    }
}
