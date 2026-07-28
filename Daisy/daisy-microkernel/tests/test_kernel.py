"""Tests for Daisy OS Microkernel."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from kernel.microkernel import DaisyKernel, KernelError, Err, TaskState


@pytest.fixture
def kernel():
    k = DaisyKernel()
    k.boot()
    yield k
    if k.is_running:
        k.shutdown()


class TestBoot:
    def test_boot_creates_root_task(self, kernel):
        tasks = kernel.task_list()
        assert len(tasks) == 1
        assert tasks[0]["name"] == "root"
        assert tasks[0]["id"] == 0

    def test_info(self, kernel):
        info = kernel.info()
        assert info["version"] == "2.0.0"
        assert info["running"] is True
        assert info["tasks"] == 1
        assert info["endpoints"] == 0

    def test_double_boot_raises(self, kernel):
        with pytest.raises(KernelError) as exc:
            kernel.boot()
        assert exc.value.code == Err.ALREADY_EXISTS

    def test_shutdown(self, kernel):
        kernel.shutdown()
        assert kernel.is_running is False


class TestTaskManagement:
    def test_create_task_returns_sequential_id(self, kernel):
        tid = kernel.syscall_task_create(0, "worker")
        assert tid == 1
        assert kernel.info()["tasks"] == 2

    def test_create_with_priority(self, kernel):
        tid = kernel.syscall_task_create(0, "hi-pri", priority=1)
        t = next(x for x in kernel.task_list() if x["id"] == tid)
        assert t["priority"] == 1

    def test_create_many_tasks(self, kernel):
        for i in range(5):
            kernel.syscall_task_create(0, f"t{i}")
        assert kernel.info()["tasks"] == 6

    def test_invalid_priority_raises(self, kernel):
        with pytest.raises(KernelError) as exc:
            kernel.syscall_task_create(0, "bad", priority=10)
        assert exc.value.code == Err.INVALID_TASK

    def test_destroy_task(self, kernel):
        tid = kernel.syscall_task_create(0, "doomed")
        kernel.syscall_task_destroy(0, tid)
        assert kernel.info()["tasks"] == 1

    def test_destroy_nonexistent_raises(self, kernel):
        with pytest.raises(KernelError) as exc:
            kernel.syscall_task_destroy(0, 999)
        assert exc.value.code == Err.INVALID_TASK

    def test_yield_rotates_queue(self, kernel):
        t1 = kernel.syscall_task_create(0, "t1", priority=5)
        t2 = kernel.syscall_task_create(0, "t2", priority=5)
        # After yield, t1 moves to back so t2 should be next in that priority slot
        kernel.syscall_task_yield(t1)
        q = kernel._ready_queues[5]
        assert q[-1] == t1


class TestCapabilities:
    def test_new_task_has_caps(self, kernel):
        tid = kernel.syscall_task_create(0, "capped")
        t = next(x for x in kernel.task_list() if x["id"] == tid)
        assert t["caps"] > 0

    def test_cap_copy_grants_access(self, kernel):
        t1 = kernel.syscall_task_create(0, "t1")
        t2 = kernel.syscall_task_create(0, "t2")
        ep = kernel.syscall_endpoint_create(t1, "shared")
        send_cap = next(
            cid for cid in kernel._tasks[t1].caps
            if (c := kernel._caps.get(cid)) and c.resource_type == "endpoint" and c.resource_id == ep
        )
        new_cap = kernel.syscall_cap_copy(t1, send_cap, t2)
        assert new_cap in kernel._tasks[t2].caps

    def test_cap_revoke_removes_access(self, kernel):
        tid = kernel.syscall_task_create(0, "r")
        cap_id = kernel._tasks[tid].caps[0]
        # Adjust owner so revoke check passes
        kernel._caps[cap_id].owner_task_id = tid
        before = len(kernel._tasks[tid].caps)
        kernel.syscall_cap_revoke(tid, cap_id)
        assert len(kernel._tasks[tid].caps) == before - 1

    def test_cap_transfer_changes_owner(self, kernel):
        t1 = kernel.syscall_task_create(0, "t1")
        t2 = kernel.syscall_task_create(0, "t2")
        ep = kernel.syscall_endpoint_create(t1, "ep")
        cap_id = next(
            cid for cid in kernel._tasks[t1].caps
            if (c := kernel._caps.get(cid)) and c.resource_type == "endpoint"
        )
        kernel.syscall_cap_transfer(t1, t2, cap_id)
        assert kernel._caps[cap_id].owner_task_id == t2
        assert cap_id in kernel._tasks[t2].caps

    def test_no_send_cap_denied(self, kernel):
        t1 = kernel.syscall_task_create(0, "owner")
        t2 = kernel.syscall_task_create(0, "intruder")
        ep = kernel.syscall_endpoint_create(t1, "private")
        with pytest.raises(KernelError) as exc:
            kernel.syscall_endpoint_send(t2, ep, {"x": 1})
        assert exc.value.code == Err.PERMISSION_DENIED

    def test_no_recv_cap_denied(self, kernel):
        t1 = kernel.syscall_task_create(0, "owner")
        t2 = kernel.syscall_task_create(0, "intruder")
        ep = kernel.syscall_endpoint_create(t1, "private")
        with pytest.raises(KernelError) as exc:
            kernel.syscall_endpoint_recv(t2, ep, timeout=0.0)
        assert exc.value.code == Err.PERMISSION_DENIED


class TestIPC:
    def test_create_endpoint_increments_count(self, kernel):
        tid = kernel.syscall_task_create(0, "ipc")
        kernel.syscall_endpoint_create(tid, "ep")
        assert kernel.info()["endpoints"] == 1

    def test_send_and_recv(self, kernel):
        tid = kernel.syscall_task_create(0, "ipc")
        ep = kernel.syscall_endpoint_create(tid, "ep")
        kernel.syscall_endpoint_send(tid, ep, {"msg": "hello"})
        msg = kernel.syscall_endpoint_recv(tid, ep, timeout=1)
        assert msg is not None
        assert msg.payload["msg"] == "hello"
        assert msg.sender == tid

    def test_send_between_tasks(self, kernel):
        t1 = kernel.syscall_task_create(0, "sender")
        t2 = kernel.syscall_task_create(0, "recv")
        ep = kernel.syscall_endpoint_create(t2, "inbox")
        send_cap = next(
            cid for cid in kernel._tasks[t2].caps
            if (c := kernel._caps.get(cid)) and c.resource_type == "endpoint" and "send" in c.permissions
        )
        kernel.syscall_cap_copy(t2, send_cap, t1)
        kernel.syscall_endpoint_send(t1, ep, {"data": "ping"})
        msg = kernel.syscall_endpoint_recv(t2, ep, timeout=1)
        assert msg.payload["data"] == "ping"
        assert msg.sender == t1

    def test_recv_empty_returns_none(self, kernel):
        tid = kernel.syscall_task_create(0, "empty")
        ep = kernel.syscall_endpoint_create(tid, "empty")
        result = kernel.syscall_endpoint_recv(tid, ep, timeout=0.05)
        assert result is None

    def test_messages_are_ordered(self, kernel):
        tid = kernel.syscall_task_create(0, "ord")
        ep = kernel.syscall_endpoint_create(tid, "ep")
        for i in range(5):
            kernel.syscall_endpoint_send(tid, ep, {"i": i})
        for i in range(5):
            msg = kernel.syscall_endpoint_recv(tid, ep, timeout=0.1)
            assert msg.payload["i"] == i


class TestMemory:
    def test_create_region_increments_count(self, kernel):
        tid = kernel.syscall_task_create(0, "mem")
        kernel.syscall_memory_create(tid, 1024)
        assert kernel.info()["regions"] == 1

    def test_write_and_read(self, kernel):
        tid = kernel.syscall_task_create(0, "mem")
        rid = kernel.syscall_memory_create(tid, 1024)
        kernel.syscall_memory_write(tid, rid, 0, b"hello daisy")
        assert kernel.syscall_memory_read(tid, rid, 0, 11) == b"hello daisy"

    def test_partial_write_at_offset(self, kernel):
        tid = kernel.syscall_task_create(0, "mem")
        rid = kernel.syscall_memory_create(tid, 64)
        kernel.syscall_memory_write(tid, rid, 10, b"XY")
        assert kernel.syscall_memory_read(tid, rid, 10, 2) == b"XY"
        assert kernel.syscall_memory_read(tid, rid, 0, 1) == b"\x00"

    def test_shared_memory(self, kernel):
        t1 = kernel.syscall_task_create(0, "writer")
        t2 = kernel.syscall_task_create(0, "reader")
        rid = kernel.syscall_memory_create(t1, 256)
        read_cap = next(
            cid for cid in kernel._tasks[t1].caps
            if (c := kernel._caps.get(cid)) and c.resource_type == "memory" and "read" in c.permissions
        )
        kernel.syscall_cap_copy(t1, read_cap, t2)
        kernel.syscall_memory_map(t2, rid)
        kernel.syscall_memory_write(t1, rid, 0, b"shared")
        assert kernel.syscall_memory_read(t2, rid, 0, 6) == b"shared"

    def test_out_of_bounds_read_raises(self, kernel):
        tid = kernel.syscall_task_create(0, "oob")
        rid = kernel.syscall_memory_create(tid, 64)
        with pytest.raises(KernelError) as exc:
            kernel.syscall_memory_read(tid, rid, 60, 10)
        assert exc.value.code == Err.INVALID_REGION

    def test_unmapped_task_denied(self, kernel):
        t1 = kernel.syscall_task_create(0, "owner")
        t2 = kernel.syscall_task_create(0, "outsider")
        rid = kernel.syscall_memory_create(t1, 64)
        with pytest.raises(KernelError) as exc:
            kernel.syscall_memory_read(t2, rid, 0, 4)
        assert exc.value.code == Err.PERMISSION_DENIED

    def test_oversized_region_raises(self, kernel):
        tid = kernel.syscall_task_create(0, "big")
        with pytest.raises(KernelError) as exc:
            kernel.syscall_memory_create(tid, 100 * 1024 * 1024)
        assert exc.value.code == Err.INVALID_REGION


class TestScheduler:
    def test_returns_ready_task(self, kernel):
        kernel.syscall_task_create(0, "worker")
        assert kernel.scheduler_next() is not None

    def test_higher_priority_scheduled_first(self, kernel):
        lo = kernel.syscall_task_create(0, "low", priority=9)
        hi = kernel.syscall_task_create(0, "high", priority=0)
        nxt = kernel.scheduler_next()
        assert nxt in (0, hi)  # root is also pri=0

    def test_no_ready_tasks_returns_none(self, kernel):
        root_tid = 0
        kernel._tasks[root_tid].state = TaskState.DEAD
        kernel._ready_queues[0].remove(root_tid)
        assert kernel.scheduler_next() is None


class TestResourceLimits:
    def test_task_limit(self):
        k = DaisyKernel(max_tasks=3)
        k.boot()
        k.syscall_task_create(0, "t1")
        k.syscall_task_create(0, "t2")
        with pytest.raises(KernelError) as exc:
            k.syscall_task_create(0, "overflow")
        assert exc.value.code == Err.RESOURCE_LIMIT
        k.shutdown()

    def test_endpoint_limit(self):
        k = DaisyKernel(max_endpoints=2)
        k.boot()
        tid = k.syscall_task_create(0, "t1")
        k.syscall_endpoint_create(tid, "e1")
        k.syscall_endpoint_create(tid, "e2")
        with pytest.raises(KernelError) as exc:
            k.syscall_endpoint_create(tid, "overflow")
        assert exc.value.code == Err.RESOURCE_LIMIT
        k.shutdown()

    def test_region_limit(self):
        k = DaisyKernel(max_regions=2)
        k.boot()
        tid = k.syscall_task_create(0, "t1")
        k.syscall_memory_create(tid, 64)
        k.syscall_memory_create(tid, 64)
        with pytest.raises(KernelError) as exc:
            k.syscall_memory_create(tid, 64)
        assert exc.value.code == Err.RESOURCE_LIMIT
        k.shutdown()
