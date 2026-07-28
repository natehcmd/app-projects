#![allow(dead_code)]

//! CMOS Real-Time Clock driver for Daisy OS.
//! Reads date/time from the RTC via ports 0x70/0x71.

const CMOS_ADDR: u16 = 0x70;
const CMOS_DATA: u16 = 0x71;

#[derive(Clone, Copy, Debug)]
pub struct DateTime {
    pub year: u16,
    pub month: u8,
    pub day: u8,
    pub hour: u8,
    pub minute: u8,
    pub second: u8,
}

#[inline]
unsafe fn outb(port: u16, val: u8) {
    core::arch::asm!("out dx, al", in("dx") port, in("al") val, options(nomem, nostack));
}

#[inline]
unsafe fn inb(port: u16) -> u8 {
    let val: u8;
    core::arch::asm!("in al, dx", in("dx") port, out("al") val, options(nomem, nostack));
    val
}

fn cmos_read(reg: u8) -> u8 {
    unsafe {
        outb(CMOS_ADDR, reg);
        inb(CMOS_DATA)
    }
}

fn bcd_to_bin(bcd: u8) -> u8 {
    (bcd >> 4) * 10 + (bcd & 0x0F)
}

fn is_updating() -> bool {
    cmos_read(0x0A) & 0x80 != 0
}

/// Read the current date/time from the RTC.
pub fn read_rtc() -> DateTime {
    while is_updating() { core::hint::spin_loop(); }

    let reg_b = cmos_read(0x0B);
    let is_bcd = reg_b & 0x04 == 0;
    let is_24h = reg_b & 0x02 != 0;

    let mut sec = cmos_read(0x00);
    let mut min = cmos_read(0x02);
    let mut hour = cmos_read(0x04);
    let mut day = cmos_read(0x07);
    let mut month = cmos_read(0x08);
    let mut year = cmos_read(0x09);
    let century = cmos_read(0x32); // May not exist on all hardware

    if is_bcd {
        sec = bcd_to_bin(sec);
        min = bcd_to_bin(min);
        hour = bcd_to_bin(hour & 0x7F) | (hour & 0x80); // preserve PM bit
        day = bcd_to_bin(day);
        month = bcd_to_bin(month);
        year = bcd_to_bin(year);
    }

    if !is_24h && hour & 0x80 != 0 {
        hour = ((hour & 0x7F) + 12) % 24;
    }

    let full_year = if century > 0 {
        bcd_to_bin(century) as u16 * 100 + year as u16
    } else {
        2000 + year as u16
    };

    DateTime { year: full_year, month, day, hour, minute: min, second: sec }
}

/// Log the current time to serial.
pub fn init() {
    let dt = read_rtc();
    crate::serial::print(b"[rtc] ");
    print_u16(dt.year);
    crate::serial::print(b"-");
    print_u8_pad(dt.month);
    crate::serial::print(b"-");
    print_u8_pad(dt.day);
    crate::serial::print(b" ");
    print_u8_pad(dt.hour);
    crate::serial::print(b":");
    print_u8_pad(dt.minute);
    crate::serial::print(b":");
    print_u8_pad(dt.second);
    crate::serial::print(b"\n");
}

fn print_u8_pad(val: u8) {
    crate::serial::write_byte(b'0' + val / 10);
    crate::serial::write_byte(b'0' + val % 10);
}

fn print_u16(mut val: u16) {
    if val == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 5];
    let mut i = 0;
    while val > 0 { buf[i] = b'0' + (val % 10) as u8; val /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}
