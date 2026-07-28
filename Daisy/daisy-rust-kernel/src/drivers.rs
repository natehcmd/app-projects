#![allow(dead_code)]

/// Shared driver traits for the first hardware bring-up pass.
pub trait BlockDevice {
    fn read_block(&mut self, block: u64, buf: &mut [u8]) -> Result<(), &'static str>;
    fn write_block(&mut self, block: u64, buf: &[u8]) -> Result<(), &'static str>;
}

pub trait NetworkDevice {
    fn mac_address(&self) -> [u8; 6];
    fn send_packet(&mut self, packet: &[u8]) -> Result<(), &'static str>;
}

pub trait InputDevice {
    fn poll(&mut self) -> Option<u16>;
}

/// Tiny device registry placeholder so later drivers have somewhere to register.
pub struct DriverRegistry {
    devices: usize,
}

impl Default for DriverRegistry {
    fn default() -> Self { Self::new() }
}

impl DriverRegistry {
    pub const fn new() -> Self {
        Self { devices: 0 }
    }

    pub fn register(&mut self) {
        self.devices += 1;
    }

    pub fn count(&self) -> usize {
        self.devices
    }
}
