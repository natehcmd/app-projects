#![allow(dead_code)]
#![allow(static_mut_refs)]

/// Service manager (init daemon) for bare-metal kernel
/// Register, start, stop services and check health with restart policies.

#[derive(Clone, Copy, PartialEq)]
pub enum ServiceState {
    Stopped,
    Starting,
    Running,
    Failed,
}

#[derive(Clone, Copy, PartialEq)]
pub enum RestartPolicy {
    Never,
    OnFailure,
    Always,
}

#[derive(Clone, Copy)]
pub struct Service {
    name: [u8; 32],
    name_len: usize,
    task_id: u64,
    state: ServiceState,
    restart: RestartPolicy,
    active: bool,
}

const MAX_SERVICES: usize = 32;

static mut SERVICES: [Service; MAX_SERVICES] = [Service {
    name: [0; 32],
    name_len: 0,
    task_id: 0,
    state: ServiceState::Stopped,
    restart: RestartPolicy::Never,
    active: false,
}; MAX_SERVICES];

static mut NEXT_TASK_ID: u64 = 1;

/// Register a new service. Returns its slot index on success.
pub fn register(name: &[u8], _entry_addr: u64, restart: RestartPolicy) -> Option<usize> {
    if name.len() > 32 {
        crate::serial::print(b"[initd] service name too long\n");
        return None;
    }

    // SAFETY: single-core kernel.
    unsafe {
        for i in 0..MAX_SERVICES {
            if !SERVICES[i].active {
                let mut sname = [0u8; 32];
                sname[..name.len()].copy_from_slice(name);
                SERVICES[i] = Service {
                    name: sname,
                    name_len: name.len(),
                    task_id: NEXT_TASK_ID,
                    state: ServiceState::Stopped,
                    restart,
                    active: true,
                };
                NEXT_TASK_ID += 1;
                crate::serial::print(b"[initd] service registered\n");
                return Some(i);
            }
        }
    }

    crate::serial::print(b"[initd] no free service slots\n");
    None
}

/// Start a registered service by slot index.
pub fn start(id: usize) -> bool {
    unsafe {
        if id >= MAX_SERVICES || !SERVICES[id].active {
            return false;
        }
        if SERVICES[id].state != ServiceState::Stopped
            && SERVICES[id].state != ServiceState::Failed
        {
            return false;
        }
        SERVICES[id].state = ServiceState::Starting;
        // In a real kernel this would spawn the task at entry_addr
        SERVICES[id].state = ServiceState::Running;
        crate::serial::print(b"[initd] service started\n");
        true
    }
}

/// Stop a running service by slot index.
pub fn stop(id: usize) -> bool {
    unsafe {
        if id >= MAX_SERVICES || !SERVICES[id].active {
            return false;
        }
        if SERVICES[id].state != ServiceState::Running {
            return false;
        }
        SERVICES[id].state = ServiceState::Stopped;
        crate::serial::print(b"[initd] service stopped\n");
        true
    }
}

/// Query the state of a service.
pub fn status(id: usize) -> Option<ServiceState> {
    unsafe {
        if id < MAX_SERVICES && SERVICES[id].active {
            Some(SERVICES[id].state)
        } else {
            None
        }
    }
}

/// Check all services and restart failed ones according to their policy.
pub fn check_health() {
    // SAFETY: single-core kernel.
    unsafe {
        for i in 0..MAX_SERVICES {
            if SERVICES[i].active && SERVICES[i].state == ServiceState::Failed {
                match SERVICES[i].restart {
                    RestartPolicy::Never => {
                        crate::serial::print(b"[initd] service failed, no restart\n");
                    }
                    RestartPolicy::OnFailure | RestartPolicy::Always => {
                        crate::serial::print(b"[initd] restarting failed service\n");
                        SERVICES[i].state = ServiceState::Stopped;
                        start(i);
                    }
                }
            }
        }
    }
}
