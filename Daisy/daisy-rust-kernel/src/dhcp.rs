#![allow(dead_code)]
#![allow(static_mut_refs)]

/// DHCP client for bare-metal kernel
/// Builds DHCP Discover/Request packets, parses Offer/Ack responses.

#[derive(Clone, Copy)]
pub struct DhcpLease {
    pub ip: [u8; 4],
    pub mask: [u8; 4],
    pub gateway: [u8; 4],
    pub dns: [u8; 4],
    pub lease_secs: u32,
}

const BOOTP_MIN_LEN: usize = 236;
const DHCP_MAGIC: [u8; 4] = [99, 130, 83, 99];

// BOOTP op codes
const BOOTREQUEST: u8 = 1;
const BOOTREPLY: u8 = 2;

// DHCP message types (option 53 values)
const DHCP_DISCOVER: u8 = 1;
const DHCP_OFFER: u8 = 2;
const DHCP_REQUEST: u8 = 3;
const DHCP_ACK: u8 = 5;

#[inline]
fn write_u16_be(buf: &mut [u8], off: usize, v: u16) {
    buf[off..off + 2].copy_from_slice(&v.to_be_bytes());
}

#[inline]
fn write_u32_be(buf: &mut [u8], off: usize, v: u32) {
    buf[off..off + 4].copy_from_slice(&v.to_be_bytes());
}

#[inline]
fn read_u32_be(buf: &[u8], off: usize) -> u32 {
    u32::from_be_bytes([buf[off], buf[off + 1], buf[off + 2], buf[off + 3]])
}

fn copy4(buf: &mut [u8], off: usize, src: &[u8; 4]) {
    buf[off..off + 4].copy_from_slice(src);
}

fn copy6(buf: &mut [u8], off: usize, src: &[u8; 6]) {
    buf[off..off + 6].copy_from_slice(src);
}

/// Fill the BOOTP header common to Discover and Request.
/// Returns the offset just past the magic cookie (ready for DHCP options).
fn fill_bootp_header(buf: &mut [u8; 576], mac: &[u8; 6], xid: u32) -> usize {
    buf[0] = BOOTREQUEST;
    buf[1] = 1;  // htype: Ethernet
    buf[2] = 6;  // hlen: MAC length
    buf[3] = 0;  // hops
    write_u32_be(buf, 4, xid);
    write_u16_be(buf, 8, 0);      // secs
    write_u16_be(buf, 10, 0x8000); // flags: broadcast
    // ciaddr, yiaddr, siaddr, giaddr all zero (already)
    copy6(buf, 28, mac); // chaddr

    // Magic cookie at offset 236
    let off = BOOTP_MIN_LEN;
    buf[off..off + 4].copy_from_slice(&DHCP_MAGIC);
    off + 4
}

/// Build a DHCP Discover packet. Returns (buffer, length).
pub fn build_discover(mac: &[u8; 6], xid: u32) -> ([u8; 576], usize) {
    let mut buf = [0u8; 576];
    let mut off = fill_bootp_header(&mut buf, mac, xid);

    // Option 53: DHCP Message Type = Discover
    buf[off] = 53;
    buf[off + 1] = 1;
    buf[off + 2] = DHCP_DISCOVER;
    off += 3;

    // Option 61: Client Identifier
    buf[off] = 61;
    buf[off + 1] = 7;
    buf[off + 2] = 1; // hw type ethernet
    copy6(&mut buf, off + 3, mac);
    off += 9;

    // Option 55: Parameter Request List
    buf[off] = 55;
    buf[off + 1] = 3;
    buf[off + 2] = 1; // Subnet Mask
    buf[off + 3] = 3; // Router
    buf[off + 4] = 6; // DNS
    off += 5;

    // End
    buf[off] = 255;
    off += 1;

    (buf, off)
}

/// Build a DHCP Request packet. Returns (buffer, length).
pub fn build_request(
    mac: &[u8; 6],
    xid: u32,
    offered_ip: [u8; 4],
    server_ip: [u8; 4],
) -> ([u8; 576], usize) {
    let mut buf = [0u8; 576];
    let mut off = fill_bootp_header(&mut buf, mac, xid);

    // Option 53: DHCP Message Type = Request
    buf[off] = 53;
    buf[off + 1] = 1;
    buf[off + 2] = DHCP_REQUEST;
    off += 3;

    // Option 61: Client Identifier
    buf[off] = 61;
    buf[off + 1] = 7;
    buf[off + 2] = 1;
    copy6(&mut buf, off + 3, mac);
    off += 9;

    // Option 50: Requested IP Address
    buf[off] = 50;
    buf[off + 1] = 4;
    copy4(&mut buf, off + 2, &offered_ip);
    off += 6;

    // Option 54: Server Identifier
    buf[off] = 54;
    buf[off + 1] = 4;
    copy4(&mut buf, off + 2, &server_ip);
    off += 6;

    // End
    buf[off] = 255;
    off += 1;

    (buf, off)
}

/// Parse a DHCP Offer or Ack response. Returns a lease on success.
pub fn parse_response(data: &[u8]) -> Option<DhcpLease> {
    // Need at least BOOTP header + magic cookie + 1 option byte
    if data.len() < BOOTP_MIN_LEN + 5 {
        return None;
    }

    // Must be a BOOTREPLY
    if data[0] != BOOTREPLY {
        return None;
    }

    // Verify magic cookie
    if data[BOOTP_MIN_LEN..BOOTP_MIN_LEN + 4] != DHCP_MAGIC {
        return None;
    }

    let yiaddr = [data[16], data[17], data[18], data[19]];
    let mut mask = [0u8; 4];
    let mut gateway = [0u8; 4];
    let mut dns = [0u8; 4];
    let mut lease_secs: u32 = 3600; // default 1 hour
    let mut msg_type: u8 = 0;

    // Walk DHCP options starting after the magic cookie
    let mut off = BOOTP_MIN_LEN + 4;
    while off < data.len() {
        let tag = data[off];
        if tag == 255 {
            break; // End option
        }
        if tag == 0 {
            off += 1; // Pad option
            continue;
        }
        if off + 1 >= data.len() {
            break;
        }
        let len = data[off + 1] as usize;
        let val_start = off + 2;
        if val_start + len > data.len() {
            break;
        }

        match tag {
            53 => {
                if len >= 1 {
                    msg_type = data[val_start];
                }
            }
            1 => {
                if len >= 4 {
                    mask.copy_from_slice(&data[val_start..val_start + 4]);
                }
            }
            3 => {
                if len >= 4 {
                    gateway.copy_from_slice(&data[val_start..val_start + 4]);
                }
            }
            6 => {
                if len >= 4 {
                    dns.copy_from_slice(&data[val_start..val_start + 4]);
                }
            }
            51 => {
                if len >= 4 {
                    lease_secs = read_u32_be(data, val_start);
                }
            }
            _ => {}
        }
        off = val_start + len;
    }

    // Only accept Offer or Ack
    if msg_type != DHCP_OFFER && msg_type != DHCP_ACK {
        return None;
    }

    Some(DhcpLease {
        ip: yiaddr,
        mask,
        gateway,
        dns,
        lease_secs,
    })
}
