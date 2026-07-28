#![allow(dead_code)]

#[derive(Clone, Copy)]
struct BootInfo {
    version: [u8; 4],
    arch: [u8; 3],
}

const BANNER: [&[u8]; 7] = [
    b"   _____     _        ",
    b"  / ____|   | |       ",
    b" | (___   __| |_   _  ",
    b"  \\___ \\ / _` | | | | ",
    b"  ____) | (_| | |_| | ",
    b" |_____/ \\__,_|\\__, | ",
    b"                __/ |  ",
];

const VERSION: BootInfo = BootInfo {
    version: [0, 1, 0, 0],
    arch: *b"x86",
};

pub fn launch_init() {
    crate::vfs::init();
    let _ = crate::vfs::mount("/proc", 0);
    let _ = crate::vfs::mount("/sys", 1);
    let _ = crate::vfs::mount("/dev", 2);
    let _ = crate::vfs::mount("/tmp", 3);
    let _ = crate::vfs::mount("/run", 4);

    print_boot_banner();

    loop {
        crate::timer::sleep_ms(1000);
    }
}

pub fn print_boot_banner() {
    for line in BANNER.iter() {
        crate::serial::print(*line);
        crate::serial::write_byte(b'\n');
    }
    crate::serial::print(b"Version: 0.1.0.0\n");
    crate::serial::print(b"Arch: x86\n");
}
