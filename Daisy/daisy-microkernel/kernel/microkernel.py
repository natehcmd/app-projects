#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-2-Clause
# Copyright (c) 2026 Daisy OS Contributors
from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Any, Optional

log = logging.getLogger("daisy.kernel")

MAX_REGION_BYTES = 64 * 1024 * 1024  # 64 MB hard cap per region


class KernelError(Exception):
    def __init__(self, msg: str, code: int = 1):
        super().__init__(msg)
        self.code = code


class Err(IntEnum):
    OK = 0
    INVALID_TASK = auto()
    INVALID_ENDPOINT = auto()
    INVALID_CAP = auto()
    INVALID_REGION = auto()
    PERMISSION_DENIED = auto()
    TIMEOUT = auto()
    TASK_DEAD = auto()
    RESOURCE_LIMIT = auto()
    ALREADY_EXISTS = auto()


class TaskState(IntEnum):
    READY = 0
    RUNNING = 1
    BLOCKED = 2
    DEAD = 3


@dataclass
class Task:
    id: int
    name: str
    state: TaskState = TaskState.READY
    parent_id: int = 0
    priority: int = 5
    caps: list[str] = field(default_factory=list)


@dataclass
class Capability:
    id: str
    resource_type: str  # "endpoint" | "memory" | "task" | "irq"
    resource_id: int
    permissions: set[str] = field(default_factory=set)  # "send" | "recv" | "read" | "write" | "destroy"
    owner_task_id: int = 0


@dataclass
class Endpoint:
    id: int
    name: str
    owner_task_id: int
    q: queue.Queue = field(default_factory=lambda: queue.Queue(maxsize=64))


@dataclass
class MemoryRegion:
    id: int
    size: int
    owner_task_id: int
    data: bytearray = field(default_factory=bytearray)
    mapped_tasks: set[int] = field(default_factory=set)

    def __post_init__(self):
        if not self.data:
            self.data = bytearray(self.size)


@dataclass
class Message:
    type: str
    sender: int
    payload: dict = field(default_factory=dict)
    caps: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    seq: int = 0


class DaisyKernel:
    """Daisy OS Microkernel — capability-based, message-passing, minimal."""

    VERSION = "2.0.0"
    CODENAME = "bloom"

    def __init__(self, max_tasks: int = 256, max_endpoints: int = 1024,
                 max_regions: int = 512):
        self._lock = threading.RLock()
        self._running = False
        self._max_tasks = max_tasks
        self._max_endpoints = max_endpoints
        self._max_regions = max_regions

        self._tasks: dict[int, Task] = {}
        self._caps: dict[str, Capability] = {}
        self._endpoints: dict[int, Endpoint] = {}
        self._regions: dict[int, MemoryRegion] = {}

        self._next_task_id = 0
        self._next_endpoint_id = 0
        self._next_region_id = 0
        self._seq = 0

        # priority → [task_id, ...]
        self._ready_queues: dict[int, list[int]] = {p: [] for p in range(10)}

    # ── Boot / Shutdown ──────────────────────────────────────────────────

    def boot(self) -> int:
        with self._lock:
            if self._running:
                raise KernelError("Kernel already running", Err.ALREADY_EXISTS)
            self._running = True
            root = self._alloc_task("root", parent_id=-1, priority=0)
            self._grant_cap(root, "task", 0, {"create", "destroy"})
            log.info("Daisy Kernel %s (%s) booted. Root task: %d",
                     self.VERSION, self.CODENAME, root)
            return root

    def shutdown(self):
        with self._lock:
            self._running = False
            for t in self._tasks.values():
                t.state = TaskState.DEAD
            log.info("Kernel shutdown. %d tasks terminated.", len(self._tasks))

    @property
    def is_running(self) -> bool:
        return self._running

    def info(self) -> dict:
        with self._lock:
            return {
                "version": self.VERSION,
                "codename": self.CODENAME,
                "running": self._running,
                "tasks": len(self._tasks),
                "endpoints": len(self._endpoints),
                "regions": len(self._regions),
            }

    def task_list(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "id": t.id,
                    "name": t.name,
                    "state": t.state.name,
                    "priority": t.priority,
                    "caps": len(t.caps),
                }
                for t in self._tasks.values()
            ]

    # ── Scheduler ───────────────────────────────────────────────────────

    def scheduler_next(self) -> Optional[int]:
        with self._lock:
            for p in range(10):
                for tid in self._ready_queues[p]:
                    if self._tasks.get(tid) and self._tasks[tid].state == TaskState.READY:
                        return tid
            return None

    # ── Internal helpers ─────────────────────────────────────────────────

    def _alloc_task(self, name: str, parent_id: int, priority: int) -> int:
        if len(self._tasks) >= self._max_tasks:
            raise KernelError("Task limit reached", Err.RESOURCE_LIMIT)
        tid = self._next_task_id
        self._next_task_id += 1
        self._tasks[tid] = Task(id=tid, name=name, parent_id=parent_id, priority=priority)
        self._ready_queues[priority].append(tid)
        return tid

    def _grant_cap(self, task_id: int, res_type: str, res_id: int,
                   perms: set[str]) -> str:
        cap_id = str(uuid.uuid4())
        self._caps[cap_id] = Capability(
            id=cap_id, resource_type=res_type, resource_id=res_id,
            permissions=perms, owner_task_id=task_id,
        )
        self._tasks[task_id].caps.append(cap_id)
        return cap_id

    def _has_cap(self, task_id: int, res_type: str, res_id: int, perm: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        for cid in task.caps:
            cap = self._caps.get(cid)
            if cap and cap.resource_type == res_type and cap.resource_id == res_id and perm in cap.permissions:
                return True
        return False

    def _require_task(self, task_id: int):
        if task_id not in self._tasks:
            raise KernelError(f"Invalid task {task_id}", Err.INVALID_TASK)

    # ── Task Syscalls ─────────────────────────────────────────────────────

    def syscall_task_create(self, parent_id: int, name: str, priority: int = 5) -> int:
        with self._lock:
            self._require_task(parent_id)
            if not (0 <= priority <= 9):
                raise KernelError("Invalid priority", Err.INVALID_TASK)
            tid = self._alloc_task(name, parent_id, priority)
            self._grant_cap(tid, "task", tid, {"yield", "destroy"})
            log.debug("Task %d '%s' created by %d pri=%d", tid, name, parent_id, priority)
            return tid

    def syscall_task_destroy(self, caller: int, task_id: int) -> None:
        with self._lock:
            self._require_task(caller)
            self._require_task(task_id)
            task = self._tasks[task_id]
            if task.state == TaskState.DEAD:
                raise KernelError("Task already dead", Err.INVALID_TASK)
            task.state = TaskState.DEAD
            # clean up owned caps
            for cid in list(task.caps):
                cap = self._caps.pop(cid, None)
                if cap:
                    for t in self._tasks.values():
                        if cid in t.caps:
                            t.caps.remove(cid)
            # clean up owned endpoints
            for ep in list(self._endpoints.values()):
                if ep.owner_task_id == task_id:
                    del self._endpoints[ep.id]
            # clean up owned regions
            for reg in list(self._regions.values()):
                if reg.owner_task_id == task_id:
                    del self._regions[reg.id]
            q = self._ready_queues[task.priority]
            if task_id in q:
                q.remove(task_id)
            del self._tasks[task_id]

    def syscall_task_yield(self, task_id: int) -> None:
        with self._lock:
            self._require_task(task_id)
            # Rotate this task to the back of its priority queue
            q = self._ready_queues[self._tasks[task_id].priority]
            if task_id in q:
                q.remove(task_id)
                q.append(task_id)

    # ── Capability Syscalls ───────────────────────────────────────────────

    def syscall_cap_copy(self, caller: int, cap_id: str, target: int) -> str:
        with self._lock:
            self._require_task(caller)
            self._require_task(target)
            cap = self._caps.get(cap_id)
            if not cap or cap_id not in self._tasks[caller].caps:
                raise KernelError("Invalid capability", Err.INVALID_CAP)
            return self._grant_cap(target, cap.resource_type, cap.resource_id, set(cap.permissions))

    def syscall_cap_revoke(self, caller: int, cap_id: str) -> None:
        with self._lock:
            self._require_task(caller)
            cap = self._caps.get(cap_id)
            if not cap or cap.owner_task_id != caller:
                raise KernelError("Capability not owned by caller", Err.INVALID_CAP)
            for t in self._tasks.values():
                if cap_id in t.caps:
                    t.caps.remove(cap_id)
            del self._caps[cap_id]

    def syscall_cap_revoke_all(self, caller: int) -> None:
        with self._lock:
            self._require_task(caller)
            owned = [cid for cid, c in self._caps.items() if c.owner_task_id == caller]
            for cid in owned:
                del self._caps[cid]
            for t in self._tasks.values():
                t.caps = [c for c in t.caps if c not in owned]

    def syscall_cap_transfer(self, caller: int, target: int, cap_id: str) -> str:
        with self._lock:
            self._require_task(caller)
            self._require_task(target)
            cap = self._caps.get(cap_id)
            if not cap or cap.owner_task_id != caller:
                raise KernelError("Capability not owned by caller", Err.INVALID_CAP)
            # Remove from caller, add to target
            if cap_id in self._tasks[caller].caps:
                self._tasks[caller].caps.remove(cap_id)
            cap.owner_task_id = target
            self._tasks[target].caps.append(cap_id)
            return cap_id

    # ── Endpoint Syscalls ─────────────────────────────────────────────────

    def syscall_endpoint_create(self, owner: int, name: str) -> int:
        with self._lock:
            self._require_task(owner)
            if len(self._endpoints) >= self._max_endpoints:
                raise KernelError("Endpoint limit reached", Err.RESOURCE_LIMIT)
            eid = self._next_endpoint_id
            self._next_endpoint_id += 1
            self._endpoints[eid] = Endpoint(id=eid, name=name, owner_task_id=owner)
            self._grant_cap(owner, "endpoint", eid, {"send", "recv"})
            return eid

    def syscall_endpoint_send(self, sender: int, endpoint_id: int, payload: dict) -> None:
        with self._lock:
            self._require_task(sender)
            ep = self._endpoints.get(endpoint_id)
            if not ep:
                raise KernelError("Invalid endpoint", Err.INVALID_ENDPOINT)
            if not self._has_cap(sender, "endpoint", endpoint_id, "send"):
                raise KernelError("No send capability", Err.PERMISSION_DENIED)
            msg = Message(type="call", sender=sender, payload=payload, seq=self._seq)
            self._seq += 1
        ep.q.put(msg)

    def syscall_endpoint_recv(self, receiver: int, endpoint_id: int,
                               timeout: Optional[float] = None) -> Optional[Message]:
        with self._lock:
            self._require_task(receiver)
            ep = self._endpoints.get(endpoint_id)
            if not ep:
                raise KernelError("Invalid endpoint", Err.INVALID_ENDPOINT)
            if not self._has_cap(receiver, "endpoint", endpoint_id, "recv"):
                raise KernelError("No recv capability", Err.PERMISSION_DENIED)
        try:
            return ep.q.get(timeout=timeout)
        except queue.Empty:
            return None

    # ── Memory Syscalls ──────────────────────────────────────────────────

    def syscall_memory_create(self, owner: int, size: int) -> int:
        with self._lock:
            self._require_task(owner)
            if size <= 0 or size > MAX_REGION_BYTES:
                raise KernelError(f"Invalid region size (max {MAX_REGION_BYTES})", Err.INVALID_REGION)
            if len(self._regions) >= self._max_regions:
                raise KernelError("Memory region limit reached", Err.RESOURCE_LIMIT)
            rid = self._next_region_id
            self._next_region_id += 1
            self._regions[rid] = MemoryRegion(id=rid, size=size, owner_task_id=owner,
                                               mapped_tasks={owner})
            self._grant_cap(owner, "memory", rid, {"read", "write"})
            return rid

    def syscall_memory_map(self, task_id: int, region_id: int) -> None:
        with self._lock:
            self._require_task(task_id)
            reg = self._regions.get(region_id)
            if not reg:
                raise KernelError("Invalid region", Err.INVALID_REGION)
            if not self._has_cap(task_id, "memory", region_id, "read"):
                raise KernelError("No read capability for region", Err.PERMISSION_DENIED)
            reg.mapped_tasks.add(task_id)

    def syscall_memory_read(self, task_id: int, region_id: int,
                             offset: int, length: int) -> bytes:
        with self._lock:
            self._require_task(task_id)
            reg = self._regions.get(region_id)
            if not reg or task_id not in reg.mapped_tasks:
                raise KernelError("Region not mapped for task", Err.PERMISSION_DENIED)
            if offset < 0 or length < 0 or offset + length > len(reg.data):
                raise KernelError("Out-of-bounds read", Err.INVALID_REGION)
            return bytes(reg.data[offset:offset + length])

    def syscall_memory_write(self, task_id: int, region_id: int,
                              offset: int, data: bytes) -> None:
        with self._lock:
            self._require_task(task_id)
            reg = self._regions.get(region_id)
            if not reg or task_id not in reg.mapped_tasks:
                raise KernelError("Region not mapped for task", Err.PERMISSION_DENIED)
            if offset < 0 or offset + len(data) > len(reg.data):
                raise KernelError("Out-of-bounds write", Err.INVALID_REGION)
            reg.data[offset:offset + len(data)] = data
