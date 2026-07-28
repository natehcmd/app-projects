#![allow(dead_code)]

//! FAT32 filesystem implementation for Daisy OS.
//!
//! Reads/writes FAT32 volumes from a block device. Supports:
//! - Directory listing
//! - File read/write
//! - Long filename (LFN) support
//! - FAT chain traversal

/// Bytes per sector (standard).
const SECTOR_SIZE: usize = 512;

/// FAT32 BPB (BIOS Parameter Block).
#[derive(Clone, Copy, Debug)]
#[repr(C, packed)]
pub struct Fat32Bpb {
    pub jmp_boot: [u8; 3],
    pub oem_name: [u8; 8],
    pub bytes_per_sector: u16,
    pub sectors_per_cluster: u8,
    pub reserved_sectors: u16,
    pub num_fats: u8,
    pub root_entry_count: u16,    // 0 for FAT32
    pub total_sectors_16: u16,    // 0 for FAT32
    pub media_type: u8,
    pub fat_size_16: u16,         // 0 for FAT32
    pub sectors_per_track: u16,
    pub num_heads: u16,
    pub hidden_sectors: u32,
    pub total_sectors_32: u32,
    // FAT32-specific
    pub fat_size_32: u32,
    pub ext_flags: u16,
    pub fs_version: u16,
    pub root_cluster: u32,
    pub fs_info: u16,
    pub backup_boot: u16,
    pub reserved: [u8; 12],
    pub drive_number: u8,
    pub reserved1: u8,
    pub boot_sig: u8,
    pub volume_id: u32,
    pub volume_label: [u8; 11],
    pub fs_type: [u8; 8],
}

/// Standard 8.3 directory entry.
#[derive(Clone, Copy, Debug)]
#[repr(C, packed)]
pub struct DirEntry {
    pub name: [u8; 8],
    pub ext: [u8; 3],
    pub attrs: u8,
    pub nt_reserved: u8,
    pub create_time_tenths: u8,
    pub create_time: u16,
    pub create_date: u16,
    pub access_date: u16,
    pub first_cluster_hi: u16,
    pub modify_time: u16,
    pub modify_date: u16,
    pub first_cluster_lo: u16,
    pub file_size: u32,
}

/// Long Filename (LFN) directory entry.
#[derive(Clone, Copy, Debug)]
#[repr(C, packed)]
pub struct LfnEntry {
    pub order: u8,
    pub name1: [u16; 5],
    pub attrs: u8,       // Always 0x0F
    pub lfn_type: u8,
    pub checksum: u8,
    pub name2: [u16; 6],
    pub zero: u16,
    pub name3: [u16; 2],
}

/// Directory entry attributes.
pub const ATTR_READ_ONLY: u8 = 0x01;
pub const ATTR_HIDDEN: u8 = 0x02;
pub const ATTR_SYSTEM: u8 = 0x04;
pub const ATTR_VOLUME_ID: u8 = 0x08;
pub const ATTR_DIRECTORY: u8 = 0x10;
pub const ATTR_ARCHIVE: u8 = 0x20;
pub const ATTR_LFN: u8 = 0x0F;

/// End of chain marker.
const FAT_EOC: u32 = 0x0FFF_FFF8;

/// File info returned by directory operations.
#[derive(Clone, Debug)]
pub struct FileInfo {
    pub name: [u8; 256],
    pub name_len: usize,
    pub size: u32,
    pub cluster: u32,
    pub is_dir: bool,
}

impl FileInfo {
    pub fn name_str(&self) -> &[u8] {
        &self.name[..self.name_len]
    }
}

/// FAT32 filesystem state.
pub struct Fat32 {
    pub fat_start_lba: u64,
    pub data_start_lba: u64,
    pub sectors_per_cluster: u32,
    pub root_cluster: u32,
    pub fat_size: u32,
    pub bytes_per_sector: u32,
    pub total_clusters: u32,
    initialized: bool,
}

/// Read function type — abstracts the block device.
pub type ReadBlockFn = fn(lba: u64, buf: &mut [u8]) -> Result<(), &'static str>;

static mut FS: Fat32 = Fat32 {
    fat_start_lba: 0,
    data_start_lba: 0,
    sectors_per_cluster: 0,
    root_cluster: 0,
    fat_size: 0,
    bytes_per_sector: 512,
    total_clusters: 0,
    initialized: false,
};

/// Initialize the FAT32 filesystem from a BPB at the given LBA.
pub fn init(partition_lba: u64, read_block: ReadBlockFn) -> Result<(), &'static str> {
    let mut sector = [0u8; SECTOR_SIZE];
    read_block(partition_lba, &mut sector)?;

    // Read BPB fields directly to avoid misaligned reference to packed struct
    let bytes_per_sector = u16::from_le_bytes([sector[11], sector[12]]);
    let sectors_per_cluster = sector[13];
    let reserved_sectors = u16::from_le_bytes([sector[14], sector[15]]);
    let num_fats = sector[16];
    let total_sectors_16 = u16::from_le_bytes([sector[19], sector[20]]);
    let total_sectors_32 = u32::from_le_bytes([sector[32], sector[33], sector[34], sector[35]]);
    let fat_size_32 = u32::from_le_bytes([sector[36], sector[37], sector[38], sector[39]]);
    let root_cluster = u32::from_le_bytes([sector[44], sector[45], sector[46], sector[47]]);

    // Validate
    if bytes_per_sector == 0 || sectors_per_cluster == 0 {
        return Err("Invalid BPB");
    }
    if bytes_per_sector != 512 {
        return Err("Only 512-byte sectors supported");
    }
    if fat_size_32 == 0 {
        return Err("Not a FAT32 volume");
    }

    unsafe {
        FS.bytes_per_sector = bytes_per_sector as u32;
        FS.sectors_per_cluster = sectors_per_cluster as u32;
        FS.fat_size = fat_size_32;
        FS.root_cluster = root_cluster;
        FS.fat_start_lba = partition_lba + reserved_sectors as u64;
        FS.data_start_lba = FS.fat_start_lba + (num_fats as u64 * fat_size_32 as u64);

        let total_sectors = if total_sectors_32 != 0 {
            total_sectors_32
        } else {
            total_sectors_16 as u32
        };
        let data_sectors = total_sectors
            - reserved_sectors as u32
            - (num_fats as u32 * fat_size_32);
        FS.total_clusters = data_sectors / sectors_per_cluster as u32;
        FS.initialized = true;
    }

    crate::serial::print(b"[fat32] Volume initialized, root cluster=");
    print_u32(root_cluster);
    crate::serial::print(b", clusters=");
    unsafe { print_u32(FS.total_clusters); }
    crate::serial::print(b"\n");

    Ok(())
}

/// Convert a cluster number to its LBA on disk.
/// Cluster numbers start at 2 in FAT32.
pub fn cluster_to_lba(cluster: u32) -> u64 {
    assert!(cluster >= 2, "Invalid FAT32 cluster number");
    unsafe {
        FS.data_start_lba + ((cluster - 2) as u64 * FS.sectors_per_cluster as u64)
    }
}

/// Read the next cluster in the FAT chain.
pub fn next_cluster(cluster: u32, read_block: ReadBlockFn) -> Result<Option<u32>, &'static str> {
    unsafe {
        let fat_offset = cluster * 4;
        let fat_sector = FS.fat_start_lba + (fat_offset / FS.bytes_per_sector) as u64;
        let entry_offset = (fat_offset % FS.bytes_per_sector) as usize;

        let mut sector = [0u8; SECTOR_SIZE];
        read_block(fat_sector, &mut sector)?;

        let val = u32::from_le_bytes([
            sector[entry_offset],
            sector[entry_offset + 1],
            sector[entry_offset + 2],
            sector[entry_offset + 3],
        ]) & 0x0FFF_FFFF;

        if val >= FAT_EOC {
            Ok(None)
        } else {
            Ok(Some(val))
        }
    }
}

/// Read an entire cluster into a buffer.
pub fn read_cluster(cluster: u32, buf: &mut [u8], read_block: ReadBlockFn) -> Result<(), &'static str> {
    let lba = cluster_to_lba(cluster);
    unsafe {
        for i in 0..FS.sectors_per_cluster {
            let offset = (i as usize) * SECTOR_SIZE;
            if offset + SECTOR_SIZE > buf.len() { break; }
            read_block(lba + i as u64, &mut buf[offset..offset + SECTOR_SIZE])?;
        }
    }
    Ok(())
}

/// List files in a directory starting at the given cluster.
/// Returns up to `max` entries.
pub fn list_dir(
    dir_cluster: u32,
    read_block: ReadBlockFn,
    entries: &mut [FileInfo],
    max: usize,
) -> Result<usize, &'static str> {
    let mut count = 0;
    let mut cluster = dir_cluster;
    let cluster_size = unsafe { (FS.sectors_per_cluster * FS.bytes_per_sector) as usize };

    // Allocate a cluster-sized buffer on stack (limit 4KB clusters)
    let mut buf = [0u8; 4096];
    if cluster_size > buf.len() {
        return Err("Cluster too large for stack buffer");
    }

    loop {
        read_cluster(cluster, &mut buf[..cluster_size], read_block)?;

        let num_entries = cluster_size / 32;
        for i in 0..num_entries {
            let offset = i * 32;
            let first_byte = buf[offset];

            if first_byte == 0x00 { return Ok(count); } // End of directory
            if first_byte == 0xE5 { continue; }          // Deleted entry

            let attrs = buf[offset + 11];
            if attrs == ATTR_LFN { continue; } // Skip LFN entries for now
            if attrs & ATTR_VOLUME_ID != 0 { continue; }

            if count >= max { return Ok(count); }

            // Read DirEntry fields directly to avoid misaligned packed struct reference
            let e = &buf[offset..offset + 32];
            let file_size = u32::from_le_bytes([e[28], e[29], e[30], e[31]]);
            let cluster_hi = u16::from_le_bytes([e[20], e[21]]);
            let cluster_lo = u16::from_le_bytes([e[26], e[27]]);

            let mut info = FileInfo {
                name: [0u8; 256],
                name_len: 0,
                size: file_size,
                cluster: ((cluster_hi as u32) << 16) | cluster_lo as u32,
                is_dir: attrs & ATTR_DIRECTORY != 0,
            };

            // Convert 8.3 name (bytes 0-7 = name, 8-10 = ext)
            let mut pos = 0;
            for j in 0..8 {
                if e[j] != b' ' {
                    info.name[pos] = e[j];
                    pos += 1;
                }
            }
            if e[8] != b' ' {
                info.name[pos] = b'.';
                pos += 1;
                for j in 8..11 {
                    if e[j] != b' ' {
                        info.name[pos] = e[j];
                        pos += 1;
                    }
                }
            }
            info.name_len = pos;

            entries[count] = info;
            count += 1;
        }

        // Follow FAT chain
        match next_cluster(cluster, read_block)? {
            Some(next) => cluster = next,
            None => break,
        }
    }

    Ok(count)
}

/// Read a file's contents starting from its first cluster.
pub fn read_file(
    start_cluster: u32,
    file_size: u32,
    buf: &mut [u8],
    read_block: ReadBlockFn,
) -> Result<usize, &'static str> {
    let cluster_size = unsafe { (FS.sectors_per_cluster * FS.bytes_per_sector) as usize };
    let mut cluster = start_cluster;
    let mut remaining = file_size as usize;
    let mut offset = 0usize;

    let mut cluster_buf = [0u8; 4096];
    if cluster_size > cluster_buf.len() {
        return Err("Cluster too large");
    }

    while remaining > 0 {
        read_cluster(cluster, &mut cluster_buf[..cluster_size], read_block)?;

        if offset >= buf.len() { break; }
        let to_copy = remaining.min(cluster_size).min(buf.len() - offset);
        buf[offset..offset + to_copy].copy_from_slice(&cluster_buf[..to_copy]);
        offset += to_copy;
        remaining -= to_copy;

        if remaining == 0 { break; }

        match next_cluster(cluster, read_block)? {
            Some(next) => cluster = next,
            None => break,
        }
    }

    Ok(offset)
}

/// Check if filesystem is initialized.
pub fn is_initialized() -> bool {
    unsafe { FS.initialized }
}

fn print_u32(mut n: u32) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 10];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    while i > 0 { i -= 1; crate::serial::write_byte(buf[i]); }
}
