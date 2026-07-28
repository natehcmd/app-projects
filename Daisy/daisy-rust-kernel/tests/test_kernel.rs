use daisy_kernel::capability::{CapabilitySystem, Perms, ResType};
use daisy_kernel::ipc::{IPCSystem, Message};
use daisy_kernel::scheduler::Scheduler;
use daisy_kernel::task::{TaskManager, TaskState};

// ── Capability tests ──────────────────────────────────────────────────────────

#[test]
fn cap_grant_check_correct_task() {
    let mut caps = CapabilitySystem::new();
    caps.grant(1, ResType::Task, 0, Perms::CREATE | Perms::DESTROY);
    assert!(caps.check(1, ResType::Task, 0, Perms::CREATE));
    assert!(caps.check(1, ResType::Task, 0, Perms::DESTROY));
}

#[test]
fn cap_check_wrong_task_denied() {
    let mut caps = CapabilitySystem::new();
    caps.grant(1, ResType::Task, 0, Perms::CREATE);
    assert!(!caps.check(2, ResType::Task, 0, Perms::CREATE));
}

#[test]
fn cap_check_wrong_perm_denied() {
    let mut caps = CapabilitySystem::new();
    caps.grant(1, ResType::Endpoint, 5, Perms::SEND);
    assert!(!caps.check(1, ResType::Endpoint, 5, Perms::RECV));
}

#[test]
fn cap_copy_grants_same_access() {
    let mut caps = CapabilitySystem::new();
    let cid = caps.grant(1, ResType::Endpoint, 5, Perms::SEND);
    caps.copy_cap(cid, 2);
    assert!(caps.check(2, ResType::Endpoint, 5, Perms::SEND));
}

#[test]
fn cap_revoke_all_clears_task() {
    let mut caps = CapabilitySystem::new();
    let _cid = caps.grant(2, ResType::Endpoint, 5, Perms::SEND);
    caps.revoke_all(2);
    assert!(!caps.check(2, ResType::Endpoint, 5, Perms::SEND));
}

#[test]
fn cap_copy_then_revoke_only_removes_copy() {
    let mut caps = CapabilitySystem::new();
    let cid = caps.grant(1, ResType::Endpoint, 5, Perms::SEND);
    caps.copy_cap(cid, 2);
    caps.revoke_all(2);
    // Original owner still has access
    assert!(caps.check(1, ResType::Endpoint, 5, Perms::SEND));
    assert!(!caps.check(2, ResType::Endpoint, 5, Perms::SEND));
}

// ── Task tests ────────────────────────────────────────────────────────────────

#[test]
fn task_create_is_alive() {
    let mut tm = TaskManager::new();
    let t = tm.create_task("test", 0, 5);
    assert!(tm.is_alive(t));
    assert_eq!(tm.count_alive(), 1);
}

#[test]
fn task_destroy_is_no_longer_alive() {
    let mut tm = TaskManager::new();
    let t = tm.create_task("victim", 0, 5);
    tm.destroy_task(t);
    assert!(!tm.is_alive(t));
    assert_eq!(tm.count_alive(), 0);
}

#[test]
fn task_multiple_alive_count() {
    let mut tm = TaskManager::new();
    let t1 = tm.create_task("a", 0, 5);
    let t2 = tm.create_task("b", 0, 3);
    let t3 = tm.create_task("c", 0, 1);
    assert_eq!(tm.count_alive(), 3);
    tm.destroy_task(t2);
    assert_eq!(tm.count_alive(), 2);
    assert!(tm.is_alive(t1));
    assert!(!tm.is_alive(t2));
    assert!(tm.is_alive(t3));
}

// ── IPC tests ─────────────────────────────────────────────────────────────────

#[test]
fn ipc_send_recv_roundtrip() {
    let mut ipc = IPCSystem::new();
    let ep = ipc.create_endpoint(1, b"test");
    let msg = Message { sender: 1, msg_type: 0, payload: b"hello".to_vec(), caps: vec![] };
    ipc.send(ep, msg).unwrap();
    let got = ipc.recv(ep).unwrap();
    assert_eq!(got.payload, b"hello");
    assert_eq!(got.sender, 1);
}

#[test]
fn ipc_recv_empty_returns_none() {
    let mut ipc = IPCSystem::new();
    let ep = ipc.create_endpoint(1, b"empty");
    assert!(ipc.try_recv(ep).is_none());
}

#[test]
fn ipc_messages_ordered_fifo() {
    let mut ipc = IPCSystem::new();
    let ep = ipc.create_endpoint(1, b"fifo");
    for i in 0u8..5 {
        let msg = Message { sender: 1, msg_type: 0, payload: vec![i], caps: vec![] };
        ipc.send(ep, msg).unwrap();
    }
    for i in 0u8..5 {
        let got = ipc.recv(ep).unwrap();
        assert_eq!(got.payload[0], i);
    }
}

// ── Scheduler tests ───────────────────────────────────────────────────────────

#[test]
fn scheduler_higher_priority_first() {
    let mut s = Scheduler::new();
    s.add(10, 9); // low priority
    s.add(20, 0); // high priority
    assert_eq!(s.next().unwrap(), 20);
}

#[test]
fn scheduler_equal_priority_fifo() {
    let mut s = Scheduler::new();
    s.add(1, 5);
    s.add(2, 5);
    assert_eq!(s.next().unwrap(), 1);
}

#[test]
fn scheduler_empty_returns_none() {
    let mut s = Scheduler::new();
    assert!(s.next().is_none());
}

#[test]
fn scheduler_add_remove_cycles() {
    let mut s = Scheduler::new();
    s.add(42, 3);
    assert_eq!(s.next().unwrap(), 42);
    s.remove(42);
    assert!(s.next().is_none());
}
