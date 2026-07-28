#![no_std]
#![no_main]
#![feature(abi_x86_interrupt)]

extern crate alloc;

pub mod capability;
pub mod task;
pub mod ipc;
pub mod scheduler;
pub mod framebuffer;
pub mod serial;
pub mod memory;
pub mod boot;
pub mod drivers;
pub mod gdt;
pub mod idt;
pub mod pic;
pub mod timer;
pub mod keyboard;
pub mod pci;
pub mod acpi;
pub mod nvme;
pub mod fat32;
pub mod e1000;
pub mod xhci;
pub mod ahci;
pub mod rtc;
pub mod vga;
pub mod syscall;
pub mod heap;
pub mod elf;
pub mod apic;
pub mod vfs;
pub mod procfs;
pub mod sysfs;
pub mod context;
pub mod pipe;
pub mod signal;
pub mod netstack;
pub mod syscall_table;
pub mod devfs;
pub mod tmpfs;
pub mod socket;
pub mod gpu;
pub mod smp;
pub mod boot_bridge;
pub mod dhcp;
pub mod dns;
pub mod nft;
pub mod panic;
pub mod power;
pub mod initd;
pub mod wifi;

use spin::Mutex;

pub static KERNEL: Mutex<Option<DaisyKernel>> = Mutex::new(None);

pub struct DaisyKernel {
    pub caps: capability::CapabilitySystem,
    pub tasks: task::TaskManager,
    pub ipc: ipc::IPCSystem,
    pub scheduler: scheduler::Scheduler,
    running: bool,
}

impl Default for DaisyKernel {
    fn default() -> Self {
        Self::new()
    }
}

impl DaisyKernel {
    pub fn new() -> Self {
        Self {
            caps: capability::CapabilitySystem::new(),
            tasks: task::TaskManager::new(),
            ipc: ipc::IPCSystem::new(),
            scheduler: scheduler::Scheduler::new(),
            running: false,
        }
    }

    pub fn boot(&mut self) -> u64 {
        self.running = true;
        let root = self.tasks.create_task("root", 0, 0);
        self.caps.grant(root, capability::ResType::Task, 0, capability::Perms::all());
        serial::print(b"[kernel] Daisy Kernel 2.0 booted\n");
        root
    }

    pub fn shutdown(&mut self) {
        self.running = false;
        serial::print(b"[kernel] shutdown\n");
    }

    pub fn is_running(&self) -> bool {
        self.running
    }
}
