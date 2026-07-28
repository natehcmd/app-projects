# Daisy Microkernel — Design Specification

## Goals
A capability-based microkernel that can run as either:
1. A userspace simulator on Linux (current mode — for development)
2. A native kernel (future — when hardware support is ready)

## Core Concepts

### Capabilities
Every resource access requires a capability (unforgeable token).
No capability = no access. This is the security model.

### Tasks (Processes)
- Each task has its own address space (simulated with dicts)
- Tasks communicate ONLY through IPC
- Tasks hold capabilities to endpoints, memory regions, and devices

### IPC (Inter-Process Communication)
- Synchronous message passing through endpoints
- Endpoints are capability-protected
- Messages are typed: Call, Reply, Notification

### Memory Regions
- Explicitly mapped memory objects
- Shared memory through capability transfer
- No implicit shared state

### Syscalls
Minimal set — only what's needed:
- task_create, task_destroy, task_yield
- endpoint_create, endpoint_send, endpoint_recv
- memory_create, memory_map, memory_unmap
- cap_copy, cap_revoke, cap_delete
- irq_register, irq_wait (for device drivers)
- log (debug output)

## Architecture

```
┌─────────────────────────────────────┐
│           User Space                │
│  ┌──────┐ ┌──────┐ ┌──────┐       │
│  │daisy │ │file  │ │net   │  ...   │
│  │  d   │ │ srv  │ │ srv  │       │
│  └──┬───┘ └──┬───┘ └──┬───┘       │
│     │        │        │            │
│  ───┴────────┴────────┴──── IPC ── │
│                                     │
├─────────────────────────────────────┤
│         Microkernel                 │
│  ┌────────┐ ┌─────┐ ┌──────────┐  │
│  │Scheduler│ │ IPC │ │Cap System│  │
│  └────────┘ └─────┘ └──────────┘  │
│  ┌──────────┐ ┌─────────────────┐  │
│  │Memory Mgr│ │ IRQ Dispatcher  │  │
│  └──────────┘ └─────────────────┘  │
└─────────────────────────────────────┘
```

## Implementation Rules
- Pure Python (for simulator mode)
- No external dependencies
- Thread-safe (each task is a thread in simulator)
- All state in the kernel object — no globals
- Every public method is a syscall
- Every syscall checks capabilities first
- Comprehensive logging for debugging
- Type hints everywhere
