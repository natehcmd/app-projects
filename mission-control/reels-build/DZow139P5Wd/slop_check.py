#!/usr/bin/env python3
"""
slop_check.py — a small, local, dependency-free "fix your slop" linter.

Scans a directory of source code for common signs of rushed / AI-generated
"slop" — leftover placeholders, empty error handling, copy-pasted blocks,
debug prints, suspicious hardcoded secrets, giant functions, generic
variable names, etc. — and prints a prioritized report.

This is NOT a wrapper around any third-party code-review API (e.g.
CodeRabbit). It's a standalone, offline static-analysis pass you can run on
any repo with nothing but the Python standard library. No network calls,
no credentials, no external services.

Usage:
    python3 slop_check.py [PATH] [--ext .py,.js,.ts] [--json out.json] [--top N]

Examples:
    python3 slop_check.py .                     # scan current directory
    python3 slop_check.py src/ --ext .py         # only .py files
    python3 slop_check.py . --json report.json   # also write machine-readable report
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rb", ".java", ".c", ".cpp", ".h"}

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".next", ".turbo", "target", ".mypy_cache", ".pytest_cache", "vendor",
}

PLACEHOLDER_PATTERNS = [
    r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"\bHACK\b",
    r"your code here", r"implement (this|me)", r"placeholder",
    r"not implemented", r"do something", r"\bstub\b",
]

DEBUG_PATTERNS = [
    r"\bconsole\.log\(", r"\bprint\(\s*['\"]?debug", r"\bpdb\.set_trace\(",
    r"\bdebugger;", r"\balert\(",
]

SECRET_PATTERNS = [
    r"(api[_-]?key|secret|token|password)\s*=\s*['\"][A-Za-z0-9_\-]{8,}['\"]",
    r"AKIA[0-9A-Z]{16}",  # AWS access key id shape
    r"sk-[A-Za-z0-9]{20,}",  # generic "sk-" style API key shape
]

GENERIC_NAMES = {"data", "temp", "tmp", "foo", "bar", "baz", "result", "res",
                  "obj", "thing", "stuff", "val", "val2", "x1", "x2"}

LONG_FUNCTION_LINES = 60          # a function/method body longer than this = smell
MAX_NESTING_DEPTH = 5             # indentation-derived nesting deeper than this = smell
DUPLICATE_LINE_MIN_LEN = 40       # only flag duplicate lines longer than this (real logic, not braces)
DUPLICATE_LINE_MIN_COUNT = 4      # how many repeats before it's "copy-paste slop"

FUNC_DEF_RE = re.compile(
    r"^\s*(def\s+\w+\s*\(|function\s+\w*\s*\(|const\s+\w+\s*=\s*(\([^)]*\)|)\s*=>|"
    r"\w+\s*\([^)]*\)\s*\{)"
)
EMPTY_CATCH_RE = re.compile(
    r"(except[^:]*:\s*\n\s*pass\b)|(catch\s*\([^)]*\)\s*\{\s*\}\s*)", re.MULTILINE
)


@dataclass
class Finding:
    file: str
    line: int
    category: str
    severity: str  # "high" | "medium" | "low"
    message: str
    snippet: str = ""


@dataclass
class Report:
    files_scanned: int = 0
    findings: list = field(default_factory=list)

    def add(self, f: Finding):
        self.findings.append(f)


def iter_source_files(root: Path, exts: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in exts:
                yield p


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def check_placeholders(path: Path, lines: list[str], report: Report):
    pat = re.compile("|".join(PLACEHOLDER_PATTERNS), re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        if pat.search(line):
            report.add(Finding(str(path), i, "placeholder", "medium",
                                "Leftover placeholder / TODO-style marker.", line.strip()[:120]))


def check_debug_statements(path: Path, lines: list[str], report: Report):
    pat = re.compile("|".join(DEBUG_PATTERNS))
    for i, line in enumerate(lines, 1):
        if pat.search(line):
            report.add(Finding(str(path), i, "debug-leftover", "low",
                                "Debug statement left in code (console.log/print/pdb/debugger).",
                                line.strip()[:120]))


def check_secrets(path: Path, lines: list[str], report: Report):
    pat = re.compile("|".join(SECRET_PATTERNS), re.IGNORECASE)
    for i, line in enumerate(lines, 1):
        if pat.search(line):
            report.add(Finding(str(path), i, "possible-secret", "high",
                                "Looks like a hardcoded credential/API key/token. "
                                "Move to an environment variable or secret manager.",
                                line.strip()[:80] + " …"))


def check_empty_error_handling(path: Path, text: str, report: Report):
    for m in EMPTY_CATCH_RE.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        report.add(Finding(str(path), line_no, "swallowed-error", "high",
                            "Empty except/catch block — errors are being silently swallowed.",
                            m.group(0).strip()[:80]))


def check_generic_names(path: Path, lines: list[str], report: Report):
    ident_re = re.compile(r"\b(?:let|const|var|def|self\.)?\s*([a-zA-Z_]\w*)\s*=(?!=)")
    for i, line in enumerate(lines, 1):
        for m in ident_re.finditer(line):
            name = m.group(1).lower()
            if name in GENERIC_NAMES:
                report.add(Finding(str(path), i, "generic-name", "low",
                                    f"Generic/uninformative variable name '{m.group(1)}'.",
                                    line.strip()[:100]))
                break  # one flag per line is enough


def check_long_functions(path: Path, lines: list[str], report: Report):
    start = None
    start_indent = None
    for i, line in enumerate(lines, 1):
        if FUNC_DEF_RE.match(line):
            if start is not None and i - start > LONG_FUNCTION_LINES:
                report.add(Finding(str(path), start, "long-function", "medium",
                                    f"Function body is {i - start} lines long — consider splitting it up.",
                                    lines[start - 1].strip()[:100]))
            start = i
    if start is not None and len(lines) - start > LONG_FUNCTION_LINES:
        report.add(Finding(str(path), start, "long-function", "medium",
                            f"Function body runs to end of file (~{len(lines) - start} lines) — consider splitting it up.",
                            lines[start - 1].strip()[:100]))


def _strip_strings(line: str) -> str:
    """Best-effort removal of string-literal contents so bracket counting
    below isn't thrown off by parens/braces/quotes inside strings."""
    return re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', '""', line)


def check_deep_nesting(path: Path, lines: list[str], report: Report):
    # Track open-bracket depth across lines so continuation lines inside a
    # multi-line function call (e.g. keyword args each on their own indented
    # line) aren't mistaken for real control-flow nesting — indentation
    # alone can't tell those apart.
    bracket_depth = 0
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith(("#", "//", "*")):
            continue
        leading = len(line) - len(stripped)
        depth = leading // 4  # rough heuristic assuming 4-space indent
        if depth > MAX_NESTING_DEPTH and bracket_depth == 0:
            report.add(Finding(str(path), i, "deep-nesting", "medium",
                                f"Deeply nested code (~{depth} levels). Consider early returns/guard clauses.",
                                line.strip()[:100]))
        cleaned = _strip_strings(line)
        bracket_depth += cleaned.count("(") + cleaned.count("[") + cleaned.count("{")
        bracket_depth -= cleaned.count(")") + cleaned.count("]") + cleaned.count("}")
        bracket_depth = max(bracket_depth, 0)


def check_duplicate_lines(path: Path, lines: list[str], report: Report):
    counts = Counter()
    first_seen = {}
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if len(s) < DUPLICATE_LINE_MIN_LEN or s.startswith(("#", "//", "*", "/*")):
            continue
        counts[s] += 1
        first_seen.setdefault(s, i)
    for s, n in counts.items():
        if n >= DUPLICATE_LINE_MIN_COUNT:
            report.add(Finding(str(path), first_seen[s], "copy-paste", "medium",
                                f"Same non-trivial line repeated {n} times in this file — "
                                "possible copy-paste slop; consider extracting a function.",
                                s[:100]))


CHECKS = [
    check_placeholders,
    check_debug_statements,
    check_secrets,
    check_generic_names,
    check_long_functions,
    check_deep_nesting,
    check_duplicate_lines,
]


def scan_file(path: Path, report: Report):
    text = safe_read(path)
    if not text:
        return
    lines = text.splitlines()
    for check in CHECKS:
        if check in (check_secrets,):
            check(path, lines, report)
        elif check is check_empty_error_handling:
            continue
        else:
            check(path, lines, report)
    check_empty_error_handling(path, text, report)


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_LABEL = {"high": "🔴 HIGH", "medium": "🟡 MED ", "low": "⚪ low "}


def print_report(report: Report, top: int | None):
    if not report.findings:
        print(f"Scanned {report.files_scanned} file(s). No slop found — nice.")
        return

    by_cat = Counter(f.category for f in report.findings)
    by_sev = Counter(f.severity for f in report.findings)

    print(f"Scanned {report.files_scanned} file(s), {len(report.findings)} finding(s).\n")
    print("By severity: " + ", ".join(f"{k}={v}" for k, v in sorted(
        by_sev.items(), key=lambda kv: SEVERITY_ORDER[kv[0]])))
    print("By category: " + ", ".join(f"{k}={v}" for k, v in by_cat.most_common()))
    print()

    findings = sorted(report.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.file, f.line))
    if top:
        findings = findings[:top]

    for f in findings:
        print(f"{SEVERITY_LABEL[f.severity]}  {f.file}:{f.line}  [{f.category}]")
        print(f"          {f.message}")
        if f.snippet:
            print(f"          > {f.snippet}")
        print()


def main():
    ap = argparse.ArgumentParser(description="Find 'slop' in your codebase — offline, no API keys.")
    ap.add_argument("path", nargs="?", default=".", help="Directory to scan (default: current dir)")
    ap.add_argument("--ext", default=None,
                     help="Comma-separated extensions to include, e.g. .py,.js (default: common source exts)")
    ap.add_argument("--json", default=None, help="Also write a JSON report to this path")
    ap.add_argument("--top", type=int, default=None, help="Only print the N highest-severity findings")
    args = ap.parse_args()

    exts = DEFAULT_EXTS
    if args.ext:
        exts = {e if e.startswith(".") else f".{e}" for e in args.ext.split(",")}

    root = Path(args.path)
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        sys.exit(1)

    report = Report()
    for f in iter_source_files(root, exts):
        report.files_scanned += 1
        scan_file(f, report)

    print_report(report, args.top)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({
                "files_scanned": report.files_scanned,
                "findings": [asdict(f) for f in report.findings],
            }, fh, indent=2)
        print(f"JSON report written to {args.json}")


if __name__ == "__main__":
    main()
