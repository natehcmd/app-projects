#!/usr/bin/env python3
"""
vibecheck.py — a small static "pre-launch security" scanner for vibe-coded apps.

Turns the 5 generic checklist items from the source reel into 5 actual,
automated checks you can run against a codebase before you ship it:

  1. Hardcoded secrets / API keys / tokens / passwords
  2. Sensitive values that leak into frontend-reachable code
  3. Auth-ish routes that don't appear to have any rate limiting nearby
  4. Dangerous / unsanitized input handling (eval, shell=True, raw SQL, etc.)
  5. A rolled-up pass/fail summary you can paste into a PR description

This is a heuristic, regex/keyword-based scanner — not a substitute for a
real SAST tool, a security audit, or a human. It has no network access,
does not execute or import any of the code it scans, and never sends your
code anywhere. It just reads text files on disk and reports patterns.

Usage:
    python3 vibecheck.py [path]            # scan a directory (default: cwd)
    python3 vibecheck.py [path] --json out.json
    python3 vibecheck.py [path] --fail-on-warn   # exit 1 if anything is flagged

No dependencies beyond the Python 3 standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "dist", "build",
    "__pycache__", ".next", ".nuxt", "target", "vendor", ".idea", ".vscode",
    "coverage", ".pytest_cache", "out",
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".rb", ".go", ".php", ".java", ".env", ".yml", ".yaml", ".json", ".html",
    ".sh", ".toml", ".ini", ".cfg", ".txt",
}

MAX_FILE_BYTES = 2_000_000  # skip anything absurdly large (binaries etc.)

FRONTEND_HINT_DIRS = {"src", "client", "frontend", "public", "web", "app", "pages", "components"}
FRONTEND_EXTENSIONS = {".jsx", ".tsx", ".vue", ".svelte", ".html", ".js"}

AUTH_ROUTE_KEYWORDS = re.compile(
    r"(login|signin|sign-in|signup|sign-up|register|reset-?password|forgot-?password|"
    r"auth|token|otp|verify)", re.IGNORECASE
)

RATE_LIMIT_HINTS = re.compile(
    r"(rate[-_]?limit|ratelimit|throttle|slowdown|express-rate-limit|"
    r"flask-limiter|Limiter\(|slowapi|django-ratelimit|@limiter)", re.IGNORECASE
)

ROUTE_DEF_PATTERNS = [
    # Express / Fastify / Koa style: app.post('/login', ...)
    re.compile(r"""\.\s*(get|post|put|patch|delete)\s*\(\s*['"`]([^'"`]+)['"`]""", re.IGNORECASE),
    # Flask style: @app.route('/login', methods=['POST'])
    re.compile(r"""@\w*\.?route\s*\(\s*['"]([^'"]+)['"]""", re.IGNORECASE),
    # FastAPI style: @app.post("/login")
    re.compile(r"""@\w+\.(get|post|put|patch|delete)\s*\(\s*['"]([^'"]+)['"]""", re.IGNORECASE),
]

# Secret-scanning patterns: (name, regex). Kept broad but reasonably specific
# to avoid flagging every variable named "token".
SECRET_PATTERNS = [
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("AWS Secret Key (heuristic)", re.compile(r"aws_secret_access_key\s*[:=]\s*['\"][A-Za-z0-9/+=]{30,}['\"]", re.IGNORECASE)),
    ("Stripe Secret Key", re.compile(r"\bsk_(live|test)_[0-9a-zA-Z]{16,}\b")),
    ("OpenAI API Key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("Anthropic API Key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b")),
    ("Slack Token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("Generic Private Key Block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("JWT-looking literal", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        "Hardcoded secret/password/api_key assignment",
        re.compile(
            r"""\b(api[_-]?key|secret|password|passwd|pwd|access[_-]?token|auth[_-]?token)\s*[:=]\s*['"]([^'"\s]{6,})['"]""",
            re.IGNORECASE,
        ),
    ),
]

# Values that are obviously placeholders, not real secrets — suppress noise.
PLACEHOLDER_RE = re.compile(
    r"^(your[_-]?|xxx|placeholder|changeme|example|test|dummy|fake|<|\$\{|process\.env|os\.environ)",
    re.IGNORECASE,
)

DANGEROUS_PATTERNS = [
    ("Python eval()/exec()", re.compile(r"\b(eval|exec)\s*\(")),
    ("Python os.system()", re.compile(r"\bos\.system\s*\(")),
    ("Python subprocess shell=True", re.compile(r"subprocess\.\w+\([^)]*shell\s*=\s*True")),
    ("JS eval() / new Function()", re.compile(r"\b(eval\s*\(|new\s+Function\s*\()")),
    ("child_process exec() with concatenation", re.compile(r"child_process\.\w*exec\w*\s*\([^)]*\+")),
    ("Possible raw SQL string concatenation", re.compile(
        r"""(SELECT|INSERT|UPDATE|DELETE)\s+.*['"]\s*\+\s*\w+""", re.IGNORECASE
    )),
    ("Possible raw SQL f-string/format interpolation", re.compile(
        r"""(execute|cursor\.execute)\s*\(\s*f?['"].*\{.*\}.*['"]""", re.IGNORECASE
    )),
    ("innerHTML assignment (possible XSS)", re.compile(r"\.innerHTML\s*=")),
    ("dangerouslySetInnerHTML", re.compile(r"dangerouslySetInnerHTML")),
]

SANITIZATION_HINTS = re.compile(
    r"(sanitize|validator|joi\.|zod\.|yup\.|pydantic|marshmallow|escape\(|"
    r"parameterize|prepared[_ ]?statement|\?\s*,\s*\[|express-validator|"
    r"class-validator|schema\.validate)",
    re.IGNORECASE,
)

ENV_FILE_NAMES = {".env", ".env.local", ".env.production", ".env.development"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    check: str
    severity: str  # "high" | "medium" | "low" | "info"
    file: str
    line: int
    message: str
    snippet: str = ""


@dataclass
class Report:
    root: str
    files_scanned: int = 0
    findings: list = field(default_factory=list)

    def add(self, f: Finding):
        self.findings.append(f)

    def by_check(self):
        grouped = {}
        for f in self.findings:
            grouped.setdefault(f.check, []).append(f)
        return grouped


# ---------------------------------------------------------------------------
# File walking helpers
# ---------------------------------------------------------------------------

def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            path = Path(dirpath) / name
            yield path


def is_scannable(path: Path) -> bool:
    # Never scan ourselves — our own source is full of the regex patterns we
    # search for (as string literals), which would self-match as findings.
    if path.resolve() == Path(__file__).resolve():
        return False
    if path.name in ENV_FILE_NAMES:
        return True
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return False
    except OSError:
        return False
    return True


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return ""


def looks_frontend(path: Path, root: Path) -> bool:
    rel_parts = {p.lower() for p in path.relative_to(root).parts[:-1]}
    if rel_parts & FRONTEND_HINT_DIRS:
        return True
    return path.suffix.lower() in {".jsx", ".tsx", ".vue", ".svelte", ".html"}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_secrets(report: Report, path: Path, rel: str, text: str, lines: list):
    for i, line in enumerate(lines, start=1):
        for name, pattern in SECRET_PATTERNS:
            m = pattern.search(line)
            if not m:
                continue
            # For the generic assignment pattern, filter out obvious placeholders.
            if name.startswith("Hardcoded secret"):
                value = m.group(2)
                if PLACEHOLDER_RE.match(value):
                    continue
            report.add(Finding(
                check="1. hardcoded_secrets",
                severity="high",
                file=rel,
                line=i,
                message=f"Possible {name} found in source",
                snippet=line.strip()[:160],
            ))


def check_env_exposure(report: Report, root: Path, path: Path, rel: str, text: str, lines: list):
    # .env files that are NOT excluded by any .gitignore we can find are a real risk.
    if path.name in ENV_FILE_NAMES:
        gitignore = root / ".gitignore"
        ignored = False
        if gitignore.exists():
            gi_text = read_text(gitignore)
            for pat in (path.name, "*.env", ".env*", ".env"):
                if pat in gi_text:
                    ignored = True
                    break
        if not ignored:
            report.add(Finding(
                check="2. env_var_exposure",
                severity="high",
                file=rel,
                line=1,
                message=(
                    f"{path.name} exists but doesn't appear to be excluded by .gitignore "
                    "— it may get committed to git."
                ),
            ))
        return

    # Frontend-reachable files that reference secret-ish env vars directly.
    if looks_frontend(path, root):
        for i, line in enumerate(lines, start=1):
            if re.search(r"(process\.env|import\.meta\.env)\.\w*(SECRET|PRIVATE|API_KEY|TOKEN|PASSWORD)\w*", line, re.IGNORECASE):
                # NEXT_PUBLIC_/VITE_ prefixed vars are meant to be public — skip those.
                if re.search(r"(NEXT_PUBLIC_|VITE_|REACT_APP_)", line):
                    continue
                report.add(Finding(
                    check="2. env_var_exposure",
                    severity="medium",
                    file=rel,
                    line=i,
                    message="A non-public-prefixed secret-looking env var is referenced from frontend code",
                    snippet=line.strip()[:160],
                ))


def check_rate_limiting(report: Report, project_has_rate_limit_hint: bool, rel: str, text: str, lines: list):
    for i, line in enumerate(lines, start=1):
        for pattern in ROUTE_DEF_PATTERNS:
            m = pattern.search(line)
            if not m:
                continue
            route_path = m.group(m.lastindex)
            if not AUTH_ROUTE_KEYWORDS.search(route_path):
                continue
            if not project_has_rate_limit_hint:
                report.add(Finding(
                    check="3. rate_limiting",
                    severity="medium",
                    file=rel,
                    line=i,
                    message=(
                        f"Auth-related route '{route_path}' found, but no rate-limiting "
                        "library/middleware was detected anywhere in the project."
                    ),
                    snippet=line.strip()[:160],
                ))


def check_dangerous_input_handling(report: Report, rel: str, text: str, lines: list):
    file_has_sanitization = bool(SANITIZATION_HINTS.search(text))
    for i, line in enumerate(lines, start=1):
        for name, pattern in DANGEROUS_PATTERNS:
            if pattern.search(line):
                severity = "high" if not file_has_sanitization else "low"
                report.add(Finding(
                    check="4. input_sanitization",
                    severity=severity,
                    file=rel,
                    line=i,
                    message=(
                        f"{name} found"
                        + ("" if file_has_sanitization else " and no validation/sanitization library reference exists in this file")
                    ),
                    snippet=line.strip()[:160],
                ))


# ---------------------------------------------------------------------------
# Main scan
# ---------------------------------------------------------------------------

def scan(root: Path) -> Report:
    report = Report(root=str(root))
    all_text_blob = []
    files = [p for p in iter_files(root) if is_scannable(p)]

    # First pass: figure out whether the project has ANY rate-limiting
    # dependency/import anywhere, so route-level findings aren't all noise.
    project_has_rate_limit_hint = False
    file_cache = {}
    for path in files:
        text = read_text(path)
        file_cache[path] = text
        if RATE_LIMIT_HINTS.search(text):
            project_has_rate_limit_hint = True

    for path in files:
        text = file_cache.get(path, "")
        if not text:
            continue
        rel = str(path.relative_to(root))
        lines = text.splitlines()
        report.files_scanned += 1

        check_secrets(report, path, rel, text, lines)
        check_env_exposure(report, root, path, rel, text, lines)
        check_rate_limiting(report, project_has_rate_limit_hint, rel, text, lines)
        check_dangerous_input_handling(report, rel, text, lines)

    return report


CHECK_TITLES = {
    "1. hardcoded_secrets": "Hardcoded API keys / tokens / passwords",
    "2. env_var_exposure": "Sensitive data exposed via env vars / git / frontend",
    "3. rate_limiting": "Rate limiting on auth routes",
    "4. input_sanitization": "Input sanitization / dangerous execution patterns",
}


def print_report(report: Report):
    print(f"\nvibecheck — scanned {report.files_scanned} files under {report.root}\n")
    grouped = report.by_check()

    for key in ["1. hardcoded_secrets", "2. env_var_exposure", "3. rate_limiting", "4. input_sanitization"]:
        title = CHECK_TITLES[key]
        findings = grouped.get(key, [])
        status = "FAIL" if findings else "PASS"
        print(f"[{status}] {title} ({len(findings)} finding(s))")
        for f in findings[:25]:
            print(f"    - {f.severity.upper():6} {f.file}:{f.line}  {f.message}")
            if f.snippet:
                print(f"             {f.snippet}")
        if len(findings) > 25:
            print(f"    ... and {len(findings) - 25} more")
        print()

    total = len(report.findings)
    print("5. Summary")
    if total == 0:
        print("    No issues flagged by these 5 heuristic checks. Nice — still get a human/real audit before shipping anything sensitive.")
    else:
        high = sum(1 for f in report.findings if f.severity == "high")
        med = sum(1 for f in report.findings if f.severity == "medium")
        low = sum(1 for f in report.findings if f.severity == "low")
        print(f"    {total} total finding(s) — {high} high, {med} medium, {low} low. See details above.")
    print()


def main():
    parser = argparse.ArgumentParser(description="Pre-launch security checklist scanner for vibe-coded apps.")
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("--json", metavar="FILE", help="Also write findings as JSON to FILE")
    parser.add_argument("--fail-on-warn", action="store_true", help="Exit with code 1 if any findings were reported")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: '{root}' is not a directory", file=sys.stderr)
        sys.exit(2)

    report = scan(root)
    print_report(report)

    if args.json:
        with open(args.json, "w") as f:
            json.dump(
                {
                    "root": report.root,
                    "files_scanned": report.files_scanned,
                    "findings": [asdict(x) for x in report.findings],
                },
                f,
                indent=2,
            )
        print(f"Wrote JSON report to {args.json}")

    if args.fail_on_warn and report.findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
