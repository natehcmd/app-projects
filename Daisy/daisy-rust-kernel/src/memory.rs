#![allow(dead_code)]

//! Physical and virtual memory management for the Daisy kernel.
//!
//! - `BitmapAllocator`: bitmap-based physical frame allocator (4KB frames, up to 4GB)
//! - `MemoryRegion` / `MemoryKind`: memory map descriptors
//! - `PageAllocator` / `PageTable`: 4-level x86-64 page table management

use core::sync::atomic::{AtomicBool, Ordering};
use spin::Mutex;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// 4 KiB page/frame size.
pub const PAGE_SIZE: usize = 4096;

/// Maximum supported physical memory (4 GiB).
pub const MAX_PHYS_MEMORY: usize = 4 * 1024 * 1024 * 1024;

/// Total number of 4 KiB frames in 4 GiB.
pub const MAX_FRAMES: usize = MAX_PHYS_MEMORY / PAGE_SIZE; // 1_048_576

/// Number of u64 words needed to hold the bitmap (1 bit per frame).
pub const BITMAP_WORDS: usize = MAX_FRAMES / 64; // 16_384

/// Number of entries in a single page table level.
pub const PAGE_TABLE_ENTRIES: usize = 512;

// ---------------------------------------------------------------------------
// Type aliases
// ---------------------------------------------------------------------------

pub type PhysAddr = u64;
pub type VirtAddr = u64;

// ---------------------------------------------------------------------------
// MemoryKind / MemoryRegion
// ---------------------------------------------------------------------------

/// Classification of a physical memory region as reported by the bootloader.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum MemoryKind {
    /// Normal RAM, free for use.
    Usable = 0,
    /// Reserved by firmware or hardware -- do not touch.
    Reserved = 1,
    /// ACPI tables that may be reclaimed after parsing.
    AcpiReclaimable = 2,
    /// Occupied by the kernel image.
    Kernel = 3,
    /// Occupied by the bootloader; reclaimable later.
    Bootloader = 4,
}

/// A contiguous region of physical memory with a usage tag.
#[derive(Debug, Clone, Copy)]
pub struct MemoryRegion {
    pub base: u64,
    pub size: u64,
    pub kind: MemoryKind,
}

impl MemoryRegion {
    pub const fn new(base: u64, size: u64, kind: MemoryKind) -> Self {
        Self { base, size, kind }
    }

    /// Past-the-end address.
    pub const fn end(&self) -> u64 {
        self.base + self.size
    }
}

// ---------------------------------------------------------------------------
// BitmapAllocator
// ---------------------------------------------------------------------------

/// A bitmap-based physical frame allocator.
///
/// Each bit in `bitmap` corresponds to a single 4 KiB physical frame.
/// A set bit (1) means the frame is **used**; a clear bit (0) means **free**.
pub struct BitmapAllocator {
    /// 1 bit per frame.  Index `i` bit `b` => frame `i*64 + b`.
    bitmap: [u64; BITMAP_WORDS],
    /// How many frames are within addressable physical memory.
    total_frames: usize,
    /// Cached count of used frames (avoids scanning the whole bitmap).
    used_frames: usize,
    /// Whether `init_from_memory_map` has been called.
    initialized: bool,
}

impl BitmapAllocator {
    /// Create a new allocator for `total_memory` bytes of physical RAM.
    ///
    /// All frames start **used** (bits set to 1). Call `init_from_memory_map`
    /// to mark usable regions as free.
    pub const fn new(total_memory: usize) -> Self {
        let frames = total_memory / PAGE_SIZE;
        let capped = if frames > MAX_FRAMES { MAX_FRAMES } else { frames };
        Self {
            // Mark everything used by default -- conservative & safe.
            bitmap: [!0u64; BITMAP_WORDS],
            total_frames: capped,
            used_frames: capped,
            initialized: false,
        }
    }

    /// Populate the bitmap from a boot-supplied memory map.
    ///
    /// Every `Usable` region has its frames marked free.  Everything else
    /// stays marked as used (the bitmap was initialised that way).
    pub fn init_from_memory_map(&mut self, entries: &[MemoryRegion]) {
        for entry in entries.iter().filter(|e| e.kind == MemoryKind::Usable) {
            let start_frame = ((entry.base as usize) + PAGE_SIZE - 1) / PAGE_SIZE;
            let end_frame = ((entry.end() as usize) / PAGE_SIZE).min(self.total_frames);
            if end_frame > start_frame {
                for frame in start_frame..end_frame {
                    self.clear_bit(frame);
                }
            }
        }
        self.used_frames = self.count_used();
        self.initialized = true;
    }

    /// Allocate a single 4 KiB frame.  Returns its physical address.
    pub fn alloc_frame(&mut self) -> Option<PhysAddr> {
        let frame = self.find_first_free()?;
        self.set_bit(frame);
        self.used_frames += 1;
        Some((frame * PAGE_SIZE) as PhysAddr)
    }

    /// Free a previously allocated frame by its physical address.
    pub fn free_frame(&mut self, addr: PhysAddr) {
        let frame = (addr as usize) / PAGE_SIZE;
        if frame >= self.total_frames {
            return;
        }
        if self.is_used(frame) {
            self.clear_bit(frame);
            if self.used_frames > 0 {
                self.used_frames -= 1;
            }
        }
    }

    /// Allocate `count` physically contiguous frames.
    ///
    /// Returns the physical address of the first frame, or `None` if a
    /// contiguous run of the requested size cannot be found.
    pub fn alloc_contiguous(&mut self, count: usize) -> Option<PhysAddr> {
        if count == 0 {
            return None;
        }
        if count == 1 {
            return self.alloc_frame();
        }

        let mut run_start: usize = 0;
        let mut run_len: usize = 0;

        for frame in 0..self.total_frames {
            if self.is_free(frame) {
                if run_len == 0 {
                    run_start = frame;
                }
                run_len += 1;
                if run_len == count {
                    // Mark the whole run as used.
                    for f in run_start..run_start + count {
                        self.set_bit(f);
                    }
                    self.used_frames += count;
                    return Some((run_start * PAGE_SIZE) as PhysAddr);
                }
            } else {
                run_len = 0;
            }
        }

        None
    }

    /// Number of free frames.
    pub fn free_count(&self) -> usize {
        self.total_frames.saturating_sub(self.used_frames)
    }

    /// Number of used frames.
    pub fn used_count(&self) -> usize {
        self.used_frames
    }

    /// Total number of tracked frames.
    pub fn total_frames(&self) -> usize {
        self.total_frames
    }

    /// Whether the allocator has been initialised from a memory map.
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }

    // -- private helpers ----------------------------------------------------

    #[inline]
    fn word_and_bit(frame: usize) -> (usize, u64) {
        (frame / 64, 1u64 << (frame % 64))
    }

    #[inline]
    fn set_bit(&mut self, frame: usize) {
        let (w, b) = Self::word_and_bit(frame);
        self.bitmap[w] |= b;
    }

    #[inline]
    fn clear_bit(&mut self, frame: usize) {
        let (w, b) = Self::word_and_bit(frame);
        self.bitmap[w] &= !b;
    }

    #[inline]
    fn is_used(&self, frame: usize) -> bool {
        let (w, b) = Self::word_and_bit(frame);
        self.bitmap[w] & b != 0
    }

    #[inline]
    fn is_free(&self, frame: usize) -> bool {
        !self.is_used(frame)
    }

    /// Scan the bitmap for the first free (0) bit.
    fn find_first_free(&self) -> Option<usize> {
        let total_words = (self.total_frames + 63) / 64;
        for i in 0..total_words {
            if self.bitmap[i] != !0u64 {
                // At least one bit is clear in this word.
                let bit = (!self.bitmap[i]).trailing_zeros() as usize;
                let frame = i * 64 + bit;
                if frame < self.total_frames {
                    return Some(frame);
                }
            }
        }
        None
    }

    fn count_used(&self) -> usize {
        let full_words = self.total_frames / 64;
        let remaining = self.total_frames % 64;
        let mut count: usize = self.bitmap[..full_words]
            .iter()
            .map(|w| w.count_ones() as usize)
            .sum();
        if remaining > 0 && full_words < BITMAP_WORDS {
            let mask = (1u64 << remaining) - 1;
            count += (self.bitmap[full_words] & mask).count_ones() as usize;
        }
        count
    }
}

// ---------------------------------------------------------------------------
// Global allocator instance (behind a spin lock)
// ---------------------------------------------------------------------------

/// Global physical frame allocator.
///
/// Initialised for 4 GiB but all frames marked used until
/// `init_from_memory_map` is called during boot.
pub static FRAME_ALLOCATOR: Mutex<BitmapAllocator> =
    Mutex::new(BitmapAllocator::new(MAX_PHYS_MEMORY));

// ---------------------------------------------------------------------------
// PageFlags (bitflags)
// ---------------------------------------------------------------------------

bitflags::bitflags! {
    /// Flags for a single page-table entry (x86-64).
    #[derive(Debug, Clone, Copy, PartialEq, Eq)]
    pub struct PageFlags: u64 {
        const PRESENT       = 1 << 0;
        const WRITABLE      = 1 << 1;
        const USER          = 1 << 2;
        const WRITE_THROUGH = 1 << 3;
        const CACHE_DISABLE = 1 << 4;
        const ACCESSED      = 1 << 5;
        const DIRTY         = 1 << 6;
        const HUGE_PAGE     = 1 << 7;
        const GLOBAL        = 1 << 8;
        const NO_EXECUTE    = 1 << 63;
    }
}

// ---------------------------------------------------------------------------
// PageTableEntry
// ---------------------------------------------------------------------------

/// A single entry in any level of the page table hierarchy.
#[derive(Clone, Copy)]
#[repr(transparent)]
pub struct PageTableEntry(u64);

impl PageTableEntry {
    pub const fn empty() -> Self {
        Self(0)
    }

    /// Raw value.
    #[inline]
    pub fn raw(&self) -> u64 {
        self.0
    }

    /// Physical address stored in this entry (bits 12..51).
    #[inline]
    pub fn addr(&self) -> PhysAddr {
        self.0 & 0x000F_FFFF_FFFF_F000
    }

    /// Flags portion of the entry.
    #[inline]
    pub fn flags(&self) -> PageFlags {
        PageFlags::from_bits_truncate(self.0)
    }

    /// Whether the PRESENT flag is set.
    #[inline]
    pub fn is_present(&self) -> bool {
        self.flags().contains(PageFlags::PRESENT)
    }

    /// Whether this is a huge (2 MiB / 1 GiB) page entry.
    #[inline]
    pub fn is_huge(&self) -> bool {
        self.flags().contains(PageFlags::HUGE_PAGE)
    }

    /// Set this entry to point at `addr` with `flags`.
    #[inline]
    pub fn set(&mut self, addr: PhysAddr, flags: PageFlags) {
        self.0 = (addr & 0x000F_FFFF_FFFF_F000) | flags.bits();
    }

    /// Clear the entry (mark not-present).
    #[inline]
    pub fn clear(&mut self) {
        self.0 = 0;
    }

    // Individual flag accessors for convenience.
    #[inline]
    pub fn is_writable(&self) -> bool {
        self.flags().contains(PageFlags::WRITABLE)
    }
    #[inline]
    pub fn is_user(&self) -> bool {
        self.flags().contains(PageFlags::USER)
    }
    #[inline]
    pub fn is_write_through(&self) -> bool {
        self.flags().contains(PageFlags::WRITE_THROUGH)
    }
    #[inline]
    pub fn is_cache_disabled(&self) -> bool {
        self.flags().contains(PageFlags::CACHE_DISABLE)
    }
    #[inline]
    pub fn is_accessed(&self) -> bool {
        self.flags().contains(PageFlags::ACCESSED)
    }
    #[inline]
    pub fn is_dirty(&self) -> bool {
        self.flags().contains(PageFlags::DIRTY)
    }
    #[inline]
    pub fn is_global(&self) -> bool {
        self.flags().contains(PageFlags::GLOBAL)
    }
    #[inline]
    pub fn is_no_execute(&self) -> bool {
        self.flags().contains(PageFlags::NO_EXECUTE)
    }
}

// ---------------------------------------------------------------------------
// PageTable
// ---------------------------------------------------------------------------

/// A single page table (used at every level: PML4, PDPT, PD, PT).
///
/// Must be page-aligned in memory.
#[repr(C, align(4096))]
pub struct PageTable {
    pub entries: [PageTableEntry; PAGE_TABLE_ENTRIES],
}

impl PageTable {
    pub const fn new() -> Self {
        Self {
            entries: [PageTableEntry::empty(); PAGE_TABLE_ENTRIES],
        }
    }

    /// Zero out every entry.
    pub fn zero(&mut self) {
        for e in self.entries.iter_mut() {
            e.clear();
        }
    }
}

// ---------------------------------------------------------------------------
// PageAllocator  (4-level page table walker)
// ---------------------------------------------------------------------------

/// Virtual-memory page allocator operating over 4-level x86-64 page tables.
///
/// Holds a pointer to the PML4 and uses `FRAME_ALLOCATOR` to get physical
/// frames for intermediate page-table pages when mapping.
pub struct PageAllocator {
    /// Physical address of the PML4 table.
    pml4_phys: PhysAddr,
}

// Indices into the four levels, extracted from a 48-bit virtual address.
#[inline]
fn pml4_index(virt: VirtAddr) -> usize {
    ((virt >> 39) & 0x1FF) as usize
}
#[inline]
fn pdpt_index(virt: VirtAddr) -> usize {
    ((virt >> 30) & 0x1FF) as usize
}
#[inline]
fn pd_index(virt: VirtAddr) -> usize {
    ((virt >> 21) & 0x1FF) as usize
}
#[inline]
fn pt_index(virt: VirtAddr) -> usize {
    ((virt >> 12) & 0x1FF) as usize
}

impl PageAllocator {
    /// Create a `PageAllocator` that manages the page tables rooted at
    /// the given PML4 physical address.
    pub const fn new(pml4_phys: PhysAddr) -> Self {
        Self { pml4_phys }
    }

    /// Physical address of the PML4 root table.
    pub fn pml4_phys(&self) -> PhysAddr {
        self.pml4_phys
    }

    // -- Helpers to convert phys -> mut ptr (identity-mapped assumption) ----

    /// Convert a physical address to a mutable reference to a `PageTable`.
    ///
    /// # Safety
    /// Caller guarantees:
    ///   - Physical memory is identity-mapped (phys == virt).
    ///   - The address points to a valid, aligned `PageTable`.
    #[inline]
    unsafe fn table_at(phys: PhysAddr) -> &'static mut PageTable {
        &mut *(phys as *mut PageTable)
    }

    /// Walk (or create) intermediate tables, returning a mutable reference
    /// to the level-1 page table (PT) that covers `virt`.
    ///
    /// If `allocate` is true, missing intermediate tables are allocated via
    /// `FRAME_ALLOCATOR`; otherwise `None` is returned when a table is
    /// missing.
    unsafe fn walk_to_pt(
        &self,
        virt: VirtAddr,
        allocate: bool,
    ) -> Option<&'static mut PageTable> {
        let pml4 = Self::table_at(self.pml4_phys);

        // Level 4 -> 3
        let pdpt = Self::next_table(&mut pml4.entries[pml4_index(virt)], allocate)?;
        // Level 3 -> 2
        let pd = Self::next_table(&mut pdpt.entries[pdpt_index(virt)], allocate)?;
        // Level 2 -> 1
        let pt = Self::next_table(&mut pd.entries[pd_index(virt)], allocate)?;

        Some(pt)
    }

    /// Follow (or create) a page-table entry to the next-level table.
    unsafe fn next_table(
        entry: &mut PageTableEntry,
        allocate: bool,
    ) -> Option<&'static mut PageTable> {
        if entry.is_present() {
            return Some(Self::table_at(entry.addr()));
        }

        if !allocate {
            return None;
        }

        // Allocate a new frame for the intermediate table.
        let frame = {
            let mut alloc = FRAME_ALLOCATOR.lock();
            alloc.alloc_frame()?
        };

        // Zero the fresh table.
        let table = Self::table_at(frame);
        table.zero();

        // Point the entry at the new table (present + writable + user).
        entry.set(
            frame,
            PageFlags::PRESENT | PageFlags::WRITABLE | PageFlags::USER,
        );

        Some(table)
    }

    /// Map a single 4 KiB virtual page to a physical frame.
    ///
    /// # Safety
    /// Caller must ensure `virt` is page-aligned and identity mapping is
    /// active for page-table physical addresses.
    pub unsafe fn map_page(
        &self,
        virt: VirtAddr,
        phys: PhysAddr,
        flags: PageFlags,
    ) -> Result<(), &'static str> {
        let pt = self
            .walk_to_pt(virt, true)
            .ok_or("map_page: failed to allocate intermediate table")?;

        let idx = pt_index(virt);
        if pt.entries[idx].is_present() {
            return Err("map_page: page already mapped");
        }

        pt.entries[idx].set(phys, flags | PageFlags::PRESENT);
        // Flush TLB for this page (x86 `invlpg`).
        Self::invlpg(virt);
        Ok(())
    }

    /// Unmap a single 4 KiB virtual page. Does **not** free the physical
    /// frame -- the caller decides if that should happen.
    ///
    /// # Safety
    /// Identity mapping must be active for page-table addresses.
    pub unsafe fn unmap_page(&self, virt: VirtAddr) -> Result<PhysAddr, &'static str> {
        let pt = self
            .walk_to_pt(virt, false)
            .ok_or("unmap_page: page not mapped (no PT)")?;

        let idx = pt_index(virt);
        if !pt.entries[idx].is_present() {
            return Err("unmap_page: page not present");
        }

        let phys = pt.entries[idx].addr();
        pt.entries[idx].clear();
        Self::invlpg(virt);
        Ok(phys)
    }

    /// Translate a virtual address to its physical address, if mapped.
    ///
    /// # Safety
    /// Identity mapping assumed for page-table addresses.
    pub unsafe fn translate(&self, virt: VirtAddr) -> Option<PhysAddr> {
        let pml4 = Self::table_at(self.pml4_phys);

        let pml4e = &pml4.entries[pml4_index(virt)];
        if !pml4e.is_present() {
            return None;
        }

        let pdpt = Self::table_at(pml4e.addr());
        let pdpte = &pdpt.entries[pdpt_index(virt)];
        if !pdpte.is_present() {
            return None;
        }
        // 1 GiB huge page
        if pdpte.is_huge() {
            let offset = virt & 0x3FFF_FFFF; // 30-bit offset
            return Some(pdpte.addr() + offset);
        }

        let pd = Self::table_at(pdpte.addr());
        let pde = &pd.entries[pd_index(virt)];
        if !pde.is_present() {
            return None;
        }
        // 2 MiB huge page
        if pde.is_huge() {
            let offset = virt & 0x1F_FFFF; // 21-bit offset
            return Some(pde.addr() + offset);
        }

        let pt = Self::table_at(pde.addr());
        let pte = &pt.entries[pt_index(virt)];
        if !pte.is_present() {
            return None;
        }

        let offset = virt & 0xFFF; // 12-bit offset
        Some(pte.addr() + offset)
    }

    /// Issue an `invlpg` instruction to flush a single TLB entry.
    #[inline]
    fn invlpg(virt: VirtAddr) {
        #[cfg(target_arch = "x86_64")]
        unsafe {
            core::arch::asm!("invlpg [{}]", in(reg) virt, options(nostack, preserves_flags));
        }
    }
}

// ---------------------------------------------------------------------------
// Convenience functions (lock the global allocator)
// ---------------------------------------------------------------------------

/// Allocate one physical frame from the global allocator.
pub fn alloc_frame() -> Option<PhysAddr> {
    FRAME_ALLOCATOR.lock().alloc_frame()
}

/// Free a physical frame back to the global allocator.
pub fn free_frame(addr: PhysAddr) {
    FRAME_ALLOCATOR.lock().free_frame(addr);
}

/// Allocate `count` contiguous physical frames.
pub fn alloc_contiguous(count: usize) -> Option<PhysAddr> {
    FRAME_ALLOCATOR.lock().alloc_contiguous(count)
}

/// Number of free frames globally.
pub fn free_count() -> usize {
    FRAME_ALLOCATOR.lock().free_count()
}

/// Number of used frames globally.
pub fn used_count() -> usize {
    FRAME_ALLOCATOR.lock().used_count()
}

/// Initialise the global frame allocator from a memory map.
pub fn init(entries: &[MemoryRegion]) {
    FRAME_ALLOCATOR.lock().init_from_memory_map(entries);
}
