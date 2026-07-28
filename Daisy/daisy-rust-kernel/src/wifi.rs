#![allow(dead_code)]
#![allow(static_mut_refs)]

/// WiFi management for bare-metal kernel
/// Scan, connect, disconnect, saved profiles, auto-connect.

#[derive(Clone, Copy, PartialEq)]
pub enum WifiState {
    Disconnected,
    Scanning,
    Connecting,
    Connected,
}

#[derive(Clone, Copy, PartialEq)]
pub enum WifiSecurity {
    Open,
    Wpa2,
    Wpa3,
}

#[derive(Clone, Copy)]
pub struct WifiNetwork {
    pub ssid: [u8; 32],
    pub ssid_len: usize,
    pub bssid: [u8; 6],
    pub signal: i8,
    pub security: WifiSecurity,
    pub channel: u8,
    pub valid: bool,
}

#[derive(Clone, Copy)]
pub struct WifiProfile {
    pub ssid: [u8; 32],
    pub ssid_len: usize,
    pub password: [u8; 64],
    pub pass_len: usize,
    pub active: bool,
}

const MAX_NETWORKS: usize = 16;
const MAX_PROFILES: usize = 8;

static mut NETWORKS: [WifiNetwork; MAX_NETWORKS] = [WifiNetwork {
    ssid: [0; 32],
    ssid_len: 0,
    bssid: [0; 6],
    signal: 0,
    security: WifiSecurity::Open,
    channel: 0,
    valid: false,
}; MAX_NETWORKS];

static mut PROFILES: [WifiProfile; MAX_PROFILES] = [WifiProfile {
    ssid: [0; 32],
    ssid_len: 0,
    password: [0; 64],
    pass_len: 0,
    active: false,
}; MAX_PROFILES];

static mut CURRENT_STATE: WifiState = WifiState::Disconnected;
static mut NETWORK_COUNT: usize = 0;

/// Trigger a scan. In a real driver this would issue commands to the
/// WiFi hardware; here we just set state to Scanning.
pub fn scan() {
    unsafe {
        CURRENT_STATE = WifiState::Scanning;
        // Clear previous results
        let mut i = 0;
        while i < MAX_NETWORKS {
            NETWORKS[i].valid = false;
            i += 1;
        }
        NETWORK_COUNT = 0;
        crate::serial::print(b"[wifi] scanning\n");
        // Hardware driver would populate NETWORKS asynchronously.
        // For now, mark scan complete.
        CURRENT_STATE = WifiState::Disconnected;
    }
}

/// Add a discovered network to the scan results (called by driver).
pub fn add_scan_result(
    ssid: &[u8],
    bssid: [u8; 6],
    signal: i8,
    security: WifiSecurity,
    channel: u8,
) -> bool {
    if ssid.len() > 32 {
        return false;
    }
    unsafe {
        if NETWORK_COUNT >= MAX_NETWORKS {
            return false;
        }
        let idx = NETWORK_COUNT;
        let mut s = [0u8; 32];
        s[..ssid.len()].copy_from_slice(ssid);
        NETWORKS[idx] = WifiNetwork {
            ssid: s,
            ssid_len: ssid.len(),
            bssid,
            signal,
            security,
            channel,
            valid: true,
        };
        NETWORK_COUNT += 1;
        true
    }
}

/// Connect to a network by SSID with the given password.
pub fn connect(ssid: &[u8], password: &[u8]) -> bool {
    // SAFETY: single-core kernel.
    unsafe {
        let net = (0..MAX_NETWORKS).find(|&i| {
            NETWORKS[i].valid && &NETWORKS[i].ssid[..NETWORKS[i].ssid_len] == ssid
        });
        let Some(idx) = net else {
            crate::serial::print(b"[wifi] network not found\n");
            return false;
        };
        CURRENT_STATE = WifiState::Connecting;
        if NETWORKS[idx].security == WifiSecurity::Open || !password.is_empty() {
            CURRENT_STATE = WifiState::Connected;
            crate::serial::print(b"[wifi] connected\n");
            return true;
        }
        CURRENT_STATE = WifiState::Disconnected;
        crate::serial::print(b"[wifi] connection failed\n");
        false
    }
}

/// Disconnect from the current network.
pub fn disconnect() {
    unsafe {
        CURRENT_STATE = WifiState::Disconnected;
        crate::serial::print(b"[wifi] disconnected\n");
    }
}

/// Return the current WiFi state.
pub fn status() -> WifiState {
    unsafe { CURRENT_STATE }
}

/// Save a network profile (SSID + password) for auto-connect.
pub fn save_profile(ssid: &[u8], password: &[u8]) -> bool {
    if ssid.len() > 32 || password.len() > 64 {
        crate::serial::print(b"[wifi] profile data too long\n");
        return false;
    }
    unsafe {
        let mut i = 0;
        while i < MAX_PROFILES {
            if !PROFILES[i].active {
                let mut s = [0u8; 32];
                s[..ssid.len()].copy_from_slice(ssid);
                let mut p = [0u8; 64];
                p[..password.len()].copy_from_slice(password);
                PROFILES[i] = WifiProfile {
                    ssid: s,
                    ssid_len: ssid.len(),
                    password: p,
                    pass_len: password.len(),
                    active: true,
                };
                crate::serial::print(b"[wifi] profile saved\n");
                return true;
            }
            i += 1;
        }
    }
    crate::serial::print(b"[wifi] no free profile slots\n");
    false
}

/// Try to auto-connect using saved profiles against scan results.
pub fn auto_connect() -> bool {
    unsafe {
        let mut pi = 0;
        while pi < MAX_PROFILES {
            if PROFILES[pi].active && PROFILES[pi].ssid_len > 0 {
                let mut ni = 0;
                while ni < MAX_NETWORKS {
                    if NETWORKS[ni].valid && NETWORKS[ni].ssid_len == PROFILES[pi].ssid_len {
                        let mut match_ok = true;
                        let mut j = 0;
                        while j < PROFILES[pi].ssid_len {
                            if NETWORKS[ni].ssid[j] != PROFILES[pi].ssid[j] {
                                match_ok = false;
                                break;
                            }
                            j += 1;
                        }
                        if match_ok {
                            let slen = PROFILES[pi].ssid_len;
                            let plen = PROFILES[pi].pass_len;
                            // Copy data to local arrays to avoid borrow issues
                            let mut ssid_buf = [0u8; 32];
                            ssid_buf[..slen].copy_from_slice(&PROFILES[pi].ssid[..slen]);
                            let mut pass_buf = [0u8; 64];
                            pass_buf[..plen].copy_from_slice(&PROFILES[pi].password[..plen]);
                            return connect(&ssid_buf[..slen], &pass_buf[..plen]);
                        }
                    }
                    ni += 1;
                }
            }
            pi += 1;
        }
    }
    crate::serial::print(b"[wifi] no matching network for auto-connect\n");
    false
}
