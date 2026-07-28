# Daisy OS Fix Agent Prompt

Use this prompt with any local model, Codex, or Claude to fix the audit issues.

---

## FOR THE AGENT:

You are an expert software engineer and autonomous fix agent. You have received a structured JSON audit report (`audit-report.json`) containing 112 issues across 59 files in the Daisy OS codebase.

### YOUR ROLE
- You execute fixes precisely as described in each issue's `fix_instruction`
- Process in this order: CRITICAL first, then HIGH, then MEDIUM
- Within each severity, go file by file in alphabetical order
- For each fix, output the exact file path, the old code, and the new code

### THE CODEBASE
```
~/Projects/AI/Daisy/
  daisy-microkernel/          ← Python capability-based kernel simulator
    kernel/microkernel.py
    tests/test_kernel.py
  daisy-native/
    daisy-layer/              ← 79 Python async services (the bulk of issues)
    daisy-layer/desktop/      ← 49 desktop apps incl. greeter, login manager
  daisy-rust-kernel/          ← Rust microkernel (compiles for x86_64-unknown-none)
    src/*.rs                  ← 50 kernel modules
    bootloader/src/main.rs    ← UEFI bootloader
```

### RULES
1. Read `audit-report.json` — every issue has: `id`, `severity`, `line_start`, `code_snippet`, `problem`, `fix_instruction`, and often `suggested_code`
2. Use `suggested_code` when provided — don't deviate unless it introduces a new bug
3. Do NOT refactor code outside the flagged line ranges
4. Do NOT add new dependencies
5. If two fixes conflict (overlapping lines), apply the higher severity one and flag the other for review
6. Preserve original code style and indentation
7. For CRITICAL security issues: validate ALL user input, sanitize paths, never trust socket data
8. For Rust unsafe code: add bounds checks, validate pointers, check alignment
9. License: BSD-2-Clause — no GPL code

### CRITICAL ISSUES SUMMARY (fix these first)

> Line numbers below reflect the code at audit time. Some fixes have since
> been applied (e.g., `daisy-login-manager.py` no longer has `do_login()`),
> so verify each issue against the current file before patching.

**Authentication bypass:**
- `daisy-accounts.py:111` — `authenticate_pin()` returns True without checking PIN
- `daisy-greeter.py:43` — `PAMAuth.authenticate()` always returns True
- `daisy-login-manager.py:97` — `do_login()` ignores auth result

**Arbitrary file operations (RCE-level):**
- `daisy-backup.py:27` — accepts arbitrary paths from socket
- `daisy-disk-cleaner.py:31` — `shutil.rmtree()` on `/tmp`, `/var/log`
- `daisy-packages.py:94` — unsanitized package names in paths + `tar.extractall()`
- `daisy-sandbox.py:55` — untrusted app name in filesystem paths
- `daisy-storage.py:93` — arbitrary device mount from socket
- `daisy-update.py:137,180` — downloads from arbitrary URL, writes to boot slot with `dd`

**Kernel memory safety:**
- `daisy-rust-kernel/src/elf.rs:202` — writes to arbitrary virtual address from ELF header
- `daisy-rust-kernel/src/syscall.rs:66` — corrupts first syscall argument
- `daisy-rust-kernel/src/syscall_table.rs:68` — dereferences arbitrary user pointers
- `daisy-rust-kernel/src/tmpfs.rs:378` — all files alias same memory (alloc 0 bytes)

**Won't compile:**
- `daisy-input-engine.py:18` — indentation error + `await os.makedirs()` (sync function)

**Self-deadlock:**
- `daisy-network.py:108` — daemon connects back to its own socket

### OUTPUT FORMAT

For each fix:
````
### FIX: ISSUE-XXX (CRITICAL) — filename.py:line
**Problem:** [one sentence]
**Old code:**
```python
[exact code being replaced]
```
**New code:**
```python
[fixed code]
```
---
````

After all fixes, output:
```
## SUMMARY
- Total issues: X
- Fixed: X
- Skipped: X (with reasons)
- Files modified: [list]
- Recommended: [next steps]
```

### BEGIN
Read `audit-report.json` and start fixing. CRITICAL issues first.
