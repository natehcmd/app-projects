#![allow(dead_code)]

//! Simple bump allocator for early kernel heap.
//! Uses a fixed-size static buffer. This is temporary until the
//! frame allocator can back a proper slab/buddy allocator.

use core::alloc::{GlobalAlloc, Layout};
use core::sync::atomic::{AtomicUsize, Ordering};

/// 256 KB heap for early boot allocations.
const HEAP_SIZE: usize = 256 * 1024;

#[repr(C, align(4096))]
struct HeapStorage([u8; HEAP_SIZE]);

static mut HEAP: HeapStorage = HeapStorage([0; HEAP_SIZE]);
static HEAP_POS: AtomicUsize = AtomicUsize::new(0);

pub struct BumpAllocator;

unsafe impl GlobalAlloc for BumpAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let size = layout.size();
        let align = layout.align();
        loop {
            let pos = HEAP_POS.load(Ordering::Relaxed);
            let Some(aligned) = pos.checked_add(align - 1).map(|a| a & !(align - 1)) else {
                return core::ptr::null_mut();
            };
            let Some(new_pos) = aligned.checked_add(size) else {
                return core::ptr::null_mut();
            };
            if new_pos > HEAP_SIZE {
                return core::ptr::null_mut();
            }
            if HEAP_POS
                .compare_exchange_weak(pos, new_pos, Ordering::AcqRel, Ordering::Relaxed)
                .is_ok()
            {
                // SAFETY: aligned is within HEAP bounds (checked above).
                return HEAP.0.as_mut_ptr().add(aligned);
            }
        }
    }

    #[inline]
    unsafe fn dealloc(&self, _ptr: *mut u8, _layout: Layout) {}
}

#[global_allocator]
static ALLOCATOR: BumpAllocator = BumpAllocator;

/// How many bytes have been allocated.
pub fn used() -> usize {
    HEAP_POS.load(Ordering::Relaxed)
}

/// How many bytes remain.
pub fn free() -> usize {
    HEAP_SIZE - used()
}
