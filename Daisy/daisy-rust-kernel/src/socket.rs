#![allow(dead_code)]

//! Unix-domain socket implementation for Daisy OS.
//!
//! Supports create/bind/listen/accept/connect/send/recv/close
//! on up to 32 concurrent sockets with 4 KB ring buffers.

const MAX_SOCKETS: usize = 32;
const PATH_MAX: usize = 108;
const BUF_SIZE: usize = 4096;

/// Socket lifecycle states.
#[derive(Clone, Copy, PartialEq)]
pub enum SocketState {
    Free,
    Created,
    Bound,
    Listening,
    Connected,
    Closed,
}

/// Error codes returned by socket operations.
#[derive(Clone, Copy, PartialEq)]
pub enum SocketError {
    InvalidId,
    WrongState,
    PeerNotConnected,
    BufferFull,
    BufferEmpty,
    NoFreeSocket,
    PathTooLong,
    NotFound,
}

/// A single socket with a ring buffer for received data.
#[derive(Clone, Copy)]
struct Socket {
    path: [u8; PATH_MAX],
    path_len: usize,
    peer: usize,          // index of the connected peer
    state: SocketState,
    rx_buf: [u8; BUF_SIZE],
    rx_read: usize,
    rx_write: usize,
}

impl Socket {
    const fn empty() -> Self {
        Self {
            path: [0; PATH_MAX],
            path_len: 0,
            peer: usize::MAX,
            state: SocketState::Free,
            rx_buf: [0; BUF_SIZE],
            rx_read: 0,
            rx_write: 0,
        }
    }

    /// Number of bytes available to read in the ring buffer.
    fn rx_available(&self) -> usize {
        if self.rx_write >= self.rx_read {
            self.rx_write - self.rx_read
        } else {
            BUF_SIZE - self.rx_read + self.rx_write
        }
    }

    /// Free space in the ring buffer.
    fn rx_free(&self) -> usize {
        BUF_SIZE - 1 - self.rx_available()
    }
}

static mut SOCKETS: [Socket; MAX_SOCKETS] = [Socket::empty(); MAX_SOCKETS];

// ── Helpers ─────────────────────────────────────────────────────────

fn validate(id: usize) -> Result<(), SocketError> {
    if id >= MAX_SOCKETS {
        Err(SocketError::InvalidId)
    } else {
        Ok(())
    }
}


// ── Public API ──────────────────────────────────────────────────────

/// Allocate a new socket. Returns the socket id.
pub fn create() -> Result<usize, SocketError> {
    // SAFETY: single-core kernel; no concurrent access to SOCKETS.
    unsafe {
        for i in 0..MAX_SOCKETS {
            if SOCKETS[i].state == SocketState::Free {
                SOCKETS[i] = Socket::empty();
                SOCKETS[i].state = SocketState::Created;
                return Ok(i);
            }
        }
    }
    Err(SocketError::NoFreeSocket)
}

/// Bind a socket to a path (up to 108 bytes).
pub fn bind(id: usize, path: &[u8]) -> Result<(), SocketError> {
    validate(id)?;
    if path.len() > PATH_MAX { return Err(SocketError::PathTooLong); }
    // SAFETY: single-core kernel.
    unsafe {
        if SOCKETS[id].state != SocketState::Created { return Err(SocketError::WrongState); }
        SOCKETS[id].path[..path.len()].copy_from_slice(path);
        SOCKETS[id].path_len = path.len();
        SOCKETS[id].state = SocketState::Bound;
    }
    Ok(())
}

/// Mark a bound socket as listening.
pub fn listen(id: usize) -> Result<(), SocketError> {
    validate(id)?;
    unsafe {
        if SOCKETS[id].state != SocketState::Bound {
            return Err(SocketError::WrongState);
        }
        SOCKETS[id].state = SocketState::Listening;
    }
    crate::serial::print(b"[socket] listening\n");
    Ok(())
}

/// Accept an incoming connection on a listening socket.
/// Returns the new server-side socket id.
pub fn accept(id: usize) -> Result<usize, SocketError> {
    validate(id)?;
    unsafe {
        if SOCKETS[id].state != SocketState::Listening {
            return Err(SocketError::WrongState);
        }

        // Find a client socket that connected to us (peer == id, state == Connected).
        let mut ci = 0;
        while ci < MAX_SOCKETS {
            if SOCKETS[ci].state == SocketState::Connected
                && SOCKETS[ci].peer == id
            {
                // Create a new server-side socket linked to this client.
                let srv = create()?;
                SOCKETS[srv].state = SocketState::Connected;
                SOCKETS[srv].peer = ci;
                // Point the client at the new server socket.
                SOCKETS[ci].peer = srv;
                crate::serial::print(b"[socket] accepted\n");
                return Ok(srv);
            }
            ci += 1;
        }
    }
    Err(SocketError::NotFound)
}

/// Connect a created socket to a listening socket by path.
pub fn connect(id: usize, path: &[u8]) -> Result<(), SocketError> {
    validate(id)?;
    if path.len() > PATH_MAX { return Err(SocketError::PathTooLong); }
    // SAFETY: single-core kernel.
    unsafe {
        if SOCKETS[id].state != SocketState::Created { return Err(SocketError::WrongState); }
        for i in 0..MAX_SOCKETS {
            if SOCKETS[i].state == SocketState::Listening
                && &SOCKETS[i].path[..SOCKETS[i].path_len] == path
            {
                SOCKETS[id].path[..path.len()].copy_from_slice(path);
                SOCKETS[id].path_len = path.len();
                SOCKETS[id].peer = i;
                SOCKETS[id].state = SocketState::Connected;
                return Ok(());
            }
        }
    }
    Err(SocketError::NotFound)
}

/// Send data to the peer's receive buffer.
pub fn send(id: usize, data: &[u8]) -> Result<usize, SocketError> {
    validate(id)?;
    // SAFETY: single-core kernel.
    unsafe {
        if SOCKETS[id].state != SocketState::Connected { return Err(SocketError::WrongState); }
        let peer = SOCKETS[id].peer;
        if peer >= MAX_SOCKETS || SOCKETS[peer].state != SocketState::Connected {
            return Err(SocketError::PeerNotConnected);
        }
        if data.len() > SOCKETS[peer].rx_free() { return Err(SocketError::BufferFull); }
        for &byte in data {
            let w = SOCKETS[peer].rx_write;
            SOCKETS[peer].rx_buf[w] = byte;
            SOCKETS[peer].rx_write = (w + 1) % BUF_SIZE;
        }
        Ok(data.len())
    }
}

/// Receive data from our own ring buffer.
pub fn recv(id: usize, buf: &mut [u8]) -> Result<usize, SocketError> {
    validate(id)?;
    // SAFETY: single-core kernel.
    unsafe {
        if SOCKETS[id].state != SocketState::Connected { return Err(SocketError::WrongState); }
        let avail = SOCKETS[id].rx_available();
        let to_read = buf.len().min(avail);
        for slot in buf[..to_read].iter_mut() {
            let r = SOCKETS[id].rx_read;
            *slot = SOCKETS[id].rx_buf[r];
            SOCKETS[id].rx_read = (r + 1) % BUF_SIZE;
        }
        Ok(to_read)
    }
}

/// Close a socket and notify the peer.
pub fn close(id: usize) -> Result<(), SocketError> {
    validate(id)?;
    unsafe {
        if SOCKETS[id].state == SocketState::Free {
            return Err(SocketError::WrongState);
        }

        let peer = SOCKETS[id].peer;
        SOCKETS[id].state = SocketState::Closed;

        // Notify peer.
        if peer < MAX_SOCKETS && SOCKETS[peer].state == SocketState::Connected {
            SOCKETS[peer].state = SocketState::Closed;
        }

        crate::serial::print(b"[socket] closed\n");
    }
    Ok(())
}
