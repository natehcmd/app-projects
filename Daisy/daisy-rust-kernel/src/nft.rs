#![allow(dead_code)]

//! Packet filter (nftables equivalent) for Daisy OS.

use core::sync::atomic::{AtomicBool, Ordering};

#[derive(Clone, Copy, PartialEq)]
pub enum Direction { In, Out }

#[derive(Clone, Copy, PartialEq)]
pub enum Proto { Tcp, Udp, Icmp, Any }

#[derive(Clone, Copy, PartialEq)]
pub enum Action { Allow, Deny }

#[derive(Clone, Copy)]
pub struct Rule {
    pub dir: Direction,
    pub proto: Proto,
    pub port: u16,
    pub action: Action,
    pub active: bool,
}

impl Rule {
    fn matches(&self, dir: Direction, proto_num: u8, port: u16) -> bool {
        if !self.active { return false; }
        let proto_match = match self.proto {
            Proto::Tcp => proto_num == 6,
            Proto::Udp => proto_num == 17,
            Proto::Icmp => proto_num == 1,
            Proto::Any => true,
        };
        dir == self.dir && proto_match && (self.port == 0 || self.port == port)
    }
}

const MAX_RULES: usize = 64;
static mut RULES: [Rule; MAX_RULES] = [Rule { dir: Direction::Out, proto: Proto::Any, port: 0, action: Action::Allow, active: false }; MAX_RULES];
static mut RULE_COUNT: usize = 0;
static INITIALIZED: AtomicBool = AtomicBool::new(false);

pub fn add_rule(dir: Direction, proto: Proto, port: u16, action: Action) -> bool {
    unsafe {
        if RULE_COUNT >= MAX_RULES { return false; }
        RULES[RULE_COUNT] = Rule { dir, proto, port, action, active: true };
        RULE_COUNT += 1;
        true
    }
}

pub fn remove_rule(index: usize) -> bool {
    unsafe {
        if index >= RULE_COUNT { return false; }
        for i in index..RULE_COUNT - 1 {
            RULES[i] = RULES[i + 1];
        }
        RULES[RULE_COUNT - 1].active = false;
        RULE_COUNT -= 1;
        true
    }
}

pub fn check_packet(dir: Direction, proto_num: u8, port: u16) -> bool {
    // SAFETY: single-core kernel; RULES and RULE_COUNT are not concurrently modified.
    unsafe {
        for i in 0..RULE_COUNT {
            if RULES[i].matches(dir, proto_num, port) {
                return RULES[i].action == Action::Allow;
            }
        }
        match dir {
            Direction::Out => true,
            Direction::In => port == 22 || port == 80 || port == 443,
        }
    }
}

pub fn list_rules() {
    // SAFETY: single-core kernel.
    unsafe {
        for i in 0..RULE_COUNT {
            let r = &RULES[i];
            crate::serial::print(b"[nft] Rule ");
            print_usize(i);
            crate::serial::print(b": ");
            crate::serial::print(match r.dir { Direction::In => b"IN " as &[u8], Direction::Out => b"OUT " });
            crate::serial::print(match r.proto {
                Proto::Tcp => b"TCP" as &[u8], Proto::Udp => b"UDP",
                Proto::Icmp => b"ICMP", Proto::Any => b"ANY",
            });
            crate::serial::print(b" port=");
            print_usize(r.port as usize);
            crate::serial::print(b" -> ");
            crate::serial::print(match r.action { Action::Allow => b"ALLOW" as &[u8], Action::Deny => b"DENY" });
            crate::serial::print(b"\n");
        }
    }
}

pub fn init() {
    if INITIALIZED.swap(true, Ordering::SeqCst) { return; }
    add_rule(Direction::In, Proto::Tcp, 22, Action::Allow);
    add_rule(Direction::In, Proto::Tcp, 80, Action::Allow);
    add_rule(Direction::In, Proto::Tcp, 443, Action::Allow);
    add_rule(Direction::Out, Proto::Any, 0, Action::Allow);
    crate::serial::print(b"[nft] Packet filter initialized (4 default rules)\n");
}

fn print_usize(mut n: usize) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 20];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    while i > 0 { i -= 1; crate::serial::write_byte(buf[i]); }
}
