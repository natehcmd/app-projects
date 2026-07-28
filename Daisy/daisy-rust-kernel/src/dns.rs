#![allow(dead_code)]
#![allow(static_mut_refs)]

/// DNS resolver for bare-metal kernel
/// Builds A-record queries, parses responses, maintains a static cache.

#[derive(Clone, Copy)]
struct CacheEntry {
    hostname: [u8; 64],
    hostname_len: usize,
    ip: [u8; 4],
    valid: bool,
}

const CACHE_SIZE: usize = 16;

static mut DNS_CACHE: [CacheEntry; CACHE_SIZE] = [CacheEntry {
    hostname: [0; 64],
    hostname_len: 0,
    ip: [0; 4],
    valid: false,
}; CACHE_SIZE];

const QTYPE_A: u8 = 1;
const QCLASS_IN: u8 = 1;

/// Build a DNS A-record query for `hostname[..hostname_len]`.
/// Returns (buffer, length).
pub fn build_query(hostname: &[u8], hostname_len: usize, tx_id: u16) -> ([u8; 512], usize) {
    let mut buf = [0u8; 512];
    let mut i: usize = 0;

    // Transaction ID
    buf[i] = (tx_id >> 8) as u8;
    buf[i + 1] = tx_id as u8;
    i += 2;

    // Flags: standard query, RD=1
    buf[i] = 0x01;
    buf[i + 1] = 0x00;
    i += 2;

    // QDCOUNT = 1
    buf[i] = 0x00;
    buf[i + 1] = 0x01;
    i += 2;

    // ANCOUNT, NSCOUNT, ARCOUNT = 0
    buf[i] = 0; buf[i + 1] = 0; i += 2;
    buf[i] = 0; buf[i + 1] = 0; i += 2;
    buf[i] = 0; buf[i + 1] = 0; i += 2;

    // Encode hostname as DNS labels: "www.example.com" -> 3www7example3com0
    let mut label_start = i; // position where we will write label length
    i += 1; // skip past the length byte, fill in later
    let mut label_len: u8 = 0;

    let mut h: usize = 0;
    while h < hostname_len {
        let b = hostname[h];
        if b == b'.' {
            buf[label_start] = label_len;
            label_start = i;
            i += 1;
            label_len = 0;
        } else {
            buf[i] = b;
            i += 1;
            label_len += 1;
        }
        h += 1;
    }
    // Write final label length
    buf[label_start] = label_len;
    // Null terminator
    buf[i] = 0x00;
    i += 1;

    buf[i] = 0x00; buf[i + 1] = QTYPE_A; i += 2;
    buf[i] = 0x00; buf[i + 1] = QCLASS_IN; i += 2;

    (buf, i)
}

/// Parse a DNS response and extract the first A-record IP address.
pub fn parse_response(data: &[u8]) -> Option<[u8; 4]> {
    if data.len() < 12 {
        return None;
    }

    // Check QR=1 (response), OPCODE=0, RCODE=0
    let qr = (data[2] & 0x80) != 0;
    let opcode = (data[2] & 0x78) >> 3;
    let rcode = data[3] & 0x0F;
    if !qr || opcode != 0 || rcode != 0 {
        return None;
    }

    let ancount = ((data[6] as u16) << 8) | (data[7] as u16);
    if ancount == 0 {
        return None;
    }

    // Skip the question section
    let mut idx: usize = 12;
    // Skip QNAME
    while idx < data.len() {
        let len = data[idx];
        if len == 0 {
            idx += 1;
            break;
        }
        if len & 0xC0 == 0xC0 {
            idx += 2; // compressed pointer
            break;
        }
        idx += 1 + len as usize;
    }
    // Skip QTYPE + QCLASS
    idx += 4;

    // Parse answer records
    let mut ans: u16 = 0;
    while ans < ancount && idx + 2 <= data.len() {
        // Skip NAME (may be compressed)
        if idx >= data.len() {
            return None;
        }
        if data[idx] & 0xC0 == 0xC0 {
            idx += 2;
        } else {
            while idx < data.len() {
                let len = data[idx];
                if len == 0 {
                    idx += 1;
                    break;
                }
                idx += 1 + len as usize;
            }
        }

        // Need TYPE(2) + CLASS(2) + TTL(4) + RDLENGTH(2) = 10 bytes
        if idx + 10 > data.len() {
            return None;
        }

        let atype = ((data[idx] as u16) << 8) | (data[idx + 1] as u16);
        let aclass = ((data[idx + 2] as u16) << 8) | (data[idx + 3] as u16);
        let rdlength = ((data[idx + 8] as u16) << 8) | (data[idx + 9] as u16);
        idx += 10;

        if atype == QTYPE_A as u16
            && aclass == QCLASS_IN as u16
            && rdlength == 4
            && idx + 4 <= data.len()
        {
            return Some([data[idx], data[idx + 1], data[idx + 2], data[idx + 3]]);
        }

        idx += rdlength as usize;
        ans += 1;
    }

    None
}

/// Look up a hostname in the cache. Returns the IP if found.
pub fn cache_lookup(hostname: &[u8], len: usize) -> Option<[u8; 4]> {
    // SAFETY: single-core kernel; DNS_CACHE is not shared concurrently.
    unsafe {
        DNS_CACHE[..CACHE_SIZE].iter().find(|e| {
            e.valid && e.hostname_len == len && &e.hostname[..len] == &hostname[..len]
        }).map(|e| e.ip)
    }
}

/// Store a hostname -> IP mapping in the cache.
pub fn cache_store(hostname: &[u8], len: usize, ip: [u8; 4]) {
    if len > 64 { return; }
    // SAFETY: single-core kernel.
    unsafe {
        let slot = DNS_CACHE[..CACHE_SIZE].iter().position(|e| !e.valid).unwrap_or(0);
        DNS_CACHE[slot].hostname = [0; 64];
        DNS_CACHE[slot].hostname[..len].copy_from_slice(&hostname[..len]);
        DNS_CACHE[slot].hostname_len = len;
        DNS_CACHE[slot].ip = ip;
        DNS_CACHE[slot].valid = true;
    }
}

/// Resolve a hostname: check cache first, otherwise return None
/// (caller is responsible for sending the query and calling cache_store).
pub fn resolve(hostname: &[u8], len: usize) -> Option<[u8; 4]> {
    cache_lookup(hostname, len)
}
