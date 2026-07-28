#![allow(dead_code)]

//! Minimal IP/TCP/UDP network stack for Daisy OS.
//!
//! Implements: Ethernet frame parsing, ARP, IPv4, ICMP echo,
//! UDP send/recv, TCP connect/listen (simplified).

/// Ethernet frame header.
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct EthHeader {
    pub dst: [u8; 6],
    pub src: [u8; 6],
    pub ethertype: u16, // big-endian
}

/// EtherType constants.
pub const ETH_IPV4: u16 = 0x0800;
pub const ETH_ARP: u16  = 0x0806;

/// IPv4 header (no options).
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct Ipv4Header {
    pub ver_ihl: u8,      // version (4) + IHL (5 = 20 bytes)
    pub tos: u8,
    pub total_len: u16,   // big-endian
    pub id: u16,
    pub flags_frag: u16,
    pub ttl: u8,
    pub protocol: u8,
    pub checksum: u16,
    pub src: [u8; 4],
    pub dst: [u8; 4],
}

/// IP protocols.
pub const PROTO_ICMP: u8 = 1;
pub const PROTO_TCP: u8  = 6;
pub const PROTO_UDP: u8  = 17;

/// UDP header.
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct UdpHeader {
    pub src_port: u16,    // big-endian
    pub dst_port: u16,
    pub length: u16,
    pub checksum: u16,
}

/// TCP header (no options).
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct TcpHeader {
    pub src_port: u16,
    pub dst_port: u16,
    pub seq: u32,
    pub ack: u32,
    pub data_off_flags: u16, // data offset (4 bits) + reserved + flags
    pub window: u16,
    pub checksum: u16,
    pub urgent: u16,
}

/// TCP flags.
pub const TCP_FIN: u16 = 0x01;
pub const TCP_SYN: u16 = 0x02;
pub const TCP_RST: u16 = 0x04;
pub const TCP_PSH: u16 = 0x08;
pub const TCP_ACK: u16 = 0x10;

/// ARP header.
#[derive(Clone, Copy)]
#[repr(C, packed)]
pub struct ArpHeader {
    pub hw_type: u16,
    pub proto_type: u16,
    pub hw_len: u8,
    pub proto_len: u8,
    pub operation: u16,   // 1=request, 2=reply
    pub sender_mac: [u8; 6],
    pub sender_ip: [u8; 4],
    pub target_mac: [u8; 6],
    pub target_ip: [u8; 4],
}

/// Network interface configuration.
pub struct NetConfig {
    pub ip: [u8; 4],
    pub netmask: [u8; 4],
    pub gateway: [u8; 4],
    pub dns: [u8; 4],
    pub mac: [u8; 6],
    pub configured: bool,
}

static mut NET_CONFIG: NetConfig = NetConfig {
    ip: [0; 4],
    netmask: [255, 255, 255, 0],
    gateway: [0; 4],
    dns: [8, 8, 8, 8],
    mac: [0; 6],
    configured: false,
};

/// ARP cache (simple, 16 entries).
const ARP_CACHE_SIZE: usize = 16;
struct ArpEntry {
    ip: [u8; 4],
    mac: [u8; 6],
    valid: bool,
}

static mut ARP_CACHE: [ArpEntry; ARP_CACHE_SIZE] = {
    const EMPTY: ArpEntry = ArpEntry { ip: [0; 4], mac: [0; 6], valid: false };
    [EMPTY; ARP_CACHE_SIZE]
};

/// UDP receive buffer (simple ring of packets).
const UDP_BUF_COUNT: usize = 16;
const UDP_BUF_SIZE: usize = 1500;

struct UdpPacket {
    data: [u8; UDP_BUF_SIZE],
    len: usize,
    src_ip: [u8; 4],
    src_port: u16,
    dst_port: u16,
    valid: bool,
}

static mut UDP_RX_BUF: [UdpPacket; UDP_BUF_COUNT] = {
    const EMPTY: UdpPacket = UdpPacket {
        data: [0; UDP_BUF_SIZE], len: 0,
        src_ip: [0; 4], src_port: 0, dst_port: 0, valid: false,
    };
    [EMPTY; UDP_BUF_COUNT]
};

/// Configure the network interface.
pub fn configure(ip: [u8; 4], netmask: [u8; 4], gateway: [u8; 4], mac: [u8; 6]) {
    unsafe {
        NET_CONFIG.ip = ip;
        NET_CONFIG.netmask = netmask;
        NET_CONFIG.gateway = gateway;
        NET_CONFIG.mac = mac;
        NET_CONFIG.configured = true;
    }
    crate::serial::print(b"[net] Configured: ");
    print_ip(&ip);
    crate::serial::print(b"\n");
}

/// Process a received Ethernet frame.
pub fn process_frame(frame: &[u8]) {
    if frame.len() < 14 {
        return;
    }

    let ethertype = u16::from_be_bytes([frame[12], frame[13]]);

    match ethertype {
        ETH_ARP => process_arp(&frame[14..]),
        ETH_IPV4 => process_ipv4(&frame[14..]),
        _ => {} // ignore unknown
    }
}

fn process_arp(data: &[u8]) {
    if data.len() < 28 {
        return;
    }

    let op = u16::from_be_bytes([data[6], data[7]]);
    let sender_mac: [u8; 6] = data[8..14].try_into().unwrap_or([0; 6]);
    let sender_ip: [u8; 4] = data[14..18].try_into().unwrap_or([0; 4]);
    let target_ip: [u8; 4] = data[24..28].try_into().unwrap_or([0; 4]);

    // Update ARP cache
    arp_cache_update(sender_ip, sender_mac);

    unsafe {
        if op == 1 && target_ip == NET_CONFIG.ip && NET_CONFIG.configured {
            // ARP request for us — send reply
            crate::serial::print(b"[net] ARP request from ");
            print_ip(&sender_ip);
            crate::serial::print(b"\n");
            // TODO: send ARP reply via e1000 driver
        }
    }
}

fn process_ipv4(data: &[u8]) {
    if data.len() < 20 {
        return;
    }

    let protocol = data[9];
    let src_ip: [u8; 4] = data[12..16].try_into().unwrap_or([0; 4]);
    let dst_ip: [u8; 4] = data[16..20].try_into().unwrap_or([0; 4]);
    let ihl = (data[0] & 0x0F) as usize * 4;

    if ihl > data.len() {
        return;
    }

    let payload = &data[ihl..];

    match protocol {
        PROTO_ICMP => process_icmp(payload, src_ip),
        PROTO_UDP => process_udp(payload, src_ip),
        PROTO_TCP => process_tcp(payload, src_ip),
        _ => {}
    }
}

fn process_icmp(data: &[u8], src_ip: [u8; 4]) {
    if data.len() < 8 {
        return;
    }
    let icmp_type = data[0];
    if icmp_type == 8 {
        // Echo request (ping) — we should reply
        crate::serial::print(b"[net] ICMP echo from ");
        print_ip(&src_ip);
        crate::serial::print(b"\n");
        // TODO: send echo reply
    }
}

fn process_udp(data: &[u8], src_ip: [u8; 4]) {
    if data.len() < 8 {
        return;
    }
    let src_port = u16::from_be_bytes([data[0], data[1]]);
    let dst_port = u16::from_be_bytes([data[2], data[3]]);
    let length = u16::from_be_bytes([data[4], data[5]]) as usize;
    let payload_len = if length > 8 { length - 8 } else { 0 };

    if data.len() < 8 + payload_len {
        return;
    }

    // Store in UDP receive buffer
    // SAFETY: single-core kernel.
    unsafe {
        if let Some(slot) = UDP_RX_BUF[..UDP_BUF_COUNT].iter_mut().find(|p| !p.valid) {
            let copy_len = payload_len.min(UDP_BUF_SIZE);
            slot.data[..copy_len].copy_from_slice(&data[8..8 + copy_len]);
            slot.len = copy_len;
            slot.src_ip = src_ip;
            slot.src_port = src_port;
            slot.dst_port = dst_port;
            slot.valid = true;
        }
    }
}

fn process_tcp(data: &[u8], src_ip: [u8; 4]) {
    if data.len() < 20 {
        return;
    }
    let src_port = u16::from_be_bytes([data[0], data[1]]);
    let dst_port = u16::from_be_bytes([data[2], data[3]]);
    let flags = u16::from_be_bytes([data[12], data[13]]) & 0x3F;

    crate::serial::print(b"[net] TCP ");
    print_ip(&src_ip);
    crate::serial::print(b":");
    print_u16(src_port);
    crate::serial::print(b" -> :");
    print_u16(dst_port);
    if flags & TCP_SYN != 0 { crate::serial::print(b" SYN"); }
    if flags & TCP_ACK != 0 { crate::serial::print(b" ACK"); }
    if flags & TCP_FIN != 0 { crate::serial::print(b" FIN"); }
    if flags & TCP_RST != 0 { crate::serial::print(b" RST"); }
    crate::serial::print(b"\n");

    // TODO: TCP state machine
}

/// Receive a UDP packet for a given port. Returns (data_len, src_ip, src_port).
pub fn udp_recv(port: u16, buf: &mut [u8]) -> Option<(usize, [u8; 4], u16)> {
    // SAFETY: single-core kernel.
    unsafe {
        let slot = UDP_RX_BUF[..UDP_BUF_COUNT].iter_mut()
            .find(|p| p.valid && p.dst_port == port)?;
        let len = slot.len.min(buf.len());
        buf[..len].copy_from_slice(&slot.data[..len]);
        let src_ip = slot.src_ip;
        let src_port = slot.src_port;
        slot.valid = false;
        Some((len, src_ip, src_port))
    }
}

/// Compute IPv4 header checksum.
pub fn ipv4_checksum(header: &[u8]) -> u16 {
    let mut sum: u32 = header.chunks_exact(2)
        .map(|c| u16::from_be_bytes([c[0], c[1]]) as u32)
        .sum();
    if header.len() % 2 == 1 {
        sum += (*header.last().unwrap() as u32) << 8;
    }
    while sum > 0xFFFF { sum = (sum & 0xFFFF) + (sum >> 16); }
    !(sum as u16)
}

fn arp_cache_update(ip: [u8; 4], mac: [u8; 6]) {
    // SAFETY: single-core kernel.
    unsafe {
        if let Some(e) = ARP_CACHE[..ARP_CACHE_SIZE].iter_mut().find(|e| e.valid && e.ip == ip) {
            e.mac = mac;
            return;
        }
        let slot = ARP_CACHE[..ARP_CACHE_SIZE].iter().position(|e| !e.valid).unwrap_or(0);
        ARP_CACHE[slot] = ArpEntry { ip, mac, valid: true };
    }
}

/// Look up a MAC address in the ARP cache.
pub fn arp_lookup(ip: [u8; 4]) -> Option<[u8; 6]> {
    // SAFETY: single-core kernel.
    unsafe {
        ARP_CACHE[..ARP_CACHE_SIZE].iter()
            .find(|e| e.valid && e.ip == ip)
            .map(|e| e.mac)
    }
}

pub fn init() {
    crate::serial::print(b"[net] Network stack initialized\n");
}

fn print_ip(ip: &[u8; 4]) {
    for (i, octet) in ip.iter().enumerate() {
        if i > 0 { crate::serial::write_byte(b'.'); }
        print_u16(*octet as u16);
    }
}

fn print_u16(mut n: u16) {
    if n == 0 { crate::serial::write_byte(b'0'); return; }
    let mut buf = [0u8; 5];
    let mut i = 0;
    while n > 0 { buf[i] = b'0' + (n % 10) as u8; n /= 10; i += 1; }
    for &b in buf[..i].iter().rev() { crate::serial::write_byte(b); }
}
