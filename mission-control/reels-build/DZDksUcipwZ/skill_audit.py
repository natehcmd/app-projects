#!/usr/bin/env python3
"""
skill_audit.py — a safety auditor for Claude "Agent Skills" before you install them.

The reel this tool is based on made one genuinely good point buried in the
hype: skill packages can run arbitrary code on your machine (shell commands,
file access, network calls) and marketplaces generally don't vet that code
for you. So: audit before you install.

This script does NOT install, download, or evade anything. Point it at a
local folder (a skill you already downloaded/cloned/unzipped) and it will:

  1. Find the SKILL.md (or skill.md) manifest and any bundled scripts.
  2. Grep those files for patterns commonly associated with risky behavior:
     shell execution, network calls, credential/secret file access,
     dynamic code eval, obfuscation, and "curl | bash"-style installers.
  3. Print a plain-English risk report with file:line citations so you can
     make an informed decision — the report never auto-installs or auto-runs
     anything.

Usage:
    python3 skill_audit.py /path/to/downloaded-skill-folder
    python3 skill_audit.py /path/to/skill.zip
    python3 skill_audit.py /path/to/skill-folder --json report.json

This tool intentionally only reads files you already have locally. It does
not fetch skills from any marketplace, bypass any download restriction, or
scrape any site. You are responsible for how you obtained the skill folder
you point it at.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --- Risk pattern catalogue -------------------------------------------------
# Each entry: (severity, label, regex, why-it-matters)
# Severity: HIGH / MEDIUM / LOW

PATTERNS: list[tuple[str, str, re.Pattern, str]] = [
    ("HIGH", "shell-exec",
     re.compile(r"\b(os\.system|subprocess\.(run|Popen|call|check_output)|child_process|execSync|exec\()"),
     "Runs arbitrary shell/OS commands — can do anything your user account can do."),
    ("HIGH", "curl-pipe-shell",
     re.compile(r"(curl|wget)[^\n]*\|\s*(sh|bash|zsh)"),
     "Classic 'curl | bash' pattern — downloads and executes code with no review step."),
    ("HIGH", "credential-file-access",
     re.compile(r"(\.ssh/id_|\.aws/credentials|\.netrc|\.npmrc|\.env\b|api_key|API_KEY|secret_key|SECRET_KEY|\.pem\b)"),
     "References SSH keys, cloud credentials, .env files, or API/secret keys."),
    ("HIGH", "eval-dynamic-code",
     re.compile(r"\b(eval\(|exec\(|new Function\(|Function\(['\"])"),
     "Executes dynamically constructed code — hard to audit, easy to hide payloads in."),
    ("HIGH", "reverse-shell-ish",
     re.compile(r"(nc\s+-e|/dev/tcp/|bash\s+-i\s+>&)"),
     "Pattern associated with reverse shells / remote command execution."),
    ("MEDIUM", "network-call",
     re.compile(r"\b(requests\.(get|post)|fetch\(|axios\.|urllib\.request|http\.client|socket\.socket)"),
     "Makes outbound network calls — fine for many legitimate skills, but note *where* it sends data."),
    ("MEDIUM", "env-var-read",
     re.compile(r"\bos\.environ|process\.env\b"),
     "Reads environment variables — check it isn't scooping up unrelated secrets."),
    ("MEDIUM", "file-write-outside-cwd",
     re.compile(r"(open\(['\"]/|Path\(['\"]/|writeFile\(['\"]/)(?!tmp)"),
     "Writes to an absolute path outside the skill's own folder."),
    ("MEDIUM", "base64-blob",
     re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"),
     "Long base64-looking blob — could be a legitimate asset, or could be hiding a payload."),
    ("LOW", "sudo-or-elevated",
     re.compile(r"\bsudo\b"),
     "Requests elevated privileges."),
    ("LOW", "delete-recursive",
     re.compile(r"(rm\s+-rf|shutil\.rmtree|fs\.rmSync)"),
     "Performs recursive/destructive deletes — make sure the target path is sane."),
]

SCRIPT_EXTS = {".py", ".sh", ".js", ".ts", ".mjs", ".cjs", ".rb", ".pl", ".ps1"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


@dataclass
class Finding:
    severity: str
    label: str
    file: str
    line: int
    snippet: str
    why: str


@dataclass
class Report:
    skill_path: str
    manifest_found: bool
    manifest_name: str | None
    files_scanned: int
    findings: list[Finding] = field(default_factory=list)

    def risk_level(self) -> str:
        sevs = {f.severity for f in self.findings}
        if "HIGH" in sevs:
            return "HIGH RISK — review carefully before installing"
        if "MEDIUM" in sevs:
            return "MEDIUM RISK — worth a quick read-through"
        if "LOW" in sevs:
            return "LOW RISK — minor notes only"
        return "NO FLAGS — nothing matched known risky patterns (not a guarantee of safety)"


def find_manifest(root: Path) -> Path | None:
    for name in ("SKILL.md", "skill.md", "Skill.md"):
        candidates = list(root.rglob(name))
        if candidates:
            return candidates[0]
    return None


def iter_scannable_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in SCRIPT_EXTS or path.name.lower() in ("skill.md",):
            yield path


def scan_file(path: Path, root: Path) -> list[Finding]:
    findings = []
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return findings
    lines = text.splitlines()
    for severity, label, pattern, why in PATTERNS:
        for i, line in enumerate(lines, start=1):
            m = pattern.search(line)
            if m:
                snippet = line.strip()
                if len(snippet) > 140:
                    snippet = snippet[:137] + "..."
                findings.append(Finding(
                    severity=severity,
                    label=label,
                    file=str(path.relative_to(root)),
                    line=i,
                    snippet=snippet,
                    why=why,
                ))
    return findings


def audit(skill_path: Path) -> Report:
    tmpdir = None
    root = skill_path
    if skill_path.is_file() and skill_path.suffix.lower() == ".zip":
        tmpdir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(skill_path) as zf:
            zf.extractall(tmpdir.name)
        root = Path(tmpdir.name)

    if not root.is_dir():
        raise SystemExit(f"Not a directory or zip of a skill: {skill_path}")

    manifest = find_manifest(root)
    findings: list[Finding] = []
    scanned = 0
    for f in iter_scannable_files(root):
        scanned += 1
        findings.extend(scan_file(f, root))

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    findings.sort(key=lambda fnd: (order[fnd.severity], fnd.file, fnd.line))

    report = Report(
        skill_path=str(skill_path),
        manifest_found=manifest is not None,
        manifest_name=str(manifest.relative_to(root)) if manifest else None,
        files_scanned=scanned,
        findings=findings,
    )

    if tmpdir is not None:
        tmpdir.cleanup()

    return report


def print_report(report: Report) -> None:
    print(f"\nSkill Audit Report — {report.skill_path}")
    print("=" * 60)
    if report.manifest_found:
        print(f"Manifest: {report.manifest_name} (found)")
    else:
        print("Manifest: SKILL.md NOT FOUND — this may not be a valid skill package.")
    print(f"Files scanned: {report.files_scanned}")
    print(f"\nOverall: {report.risk_level()}\n")

    if not report.findings:
        print("No risky patterns matched. Still read SKILL.md yourself before installing —")
        print("this tool catches known patterns, not intent.")
        return

    for sev in ("HIGH", "MEDIUM", "LOW"):
        group = [f for f in report.findings if f.severity == sev]
        if not group:
            continue
        print(f"--- {sev} ({len(group)}) ---")
        for f in group:
            print(f"  [{f.label}] {f.file}:{f.line}")
            print(f"    {f.snippet}")
            print(f"    why: {f.why}")
        print()

    print("Reminder: this is a heuristic scan, not a guarantee. Read the flagged")
    print("lines in context, and never install a skill you don't understand.")


def main():
    ap = argparse.ArgumentParser(description="Audit a downloaded Claude Agent Skill for risky code before installing it.")
    ap.add_argument("path", help="Path to a skill folder or a .zip of one")
    ap.add_argument("--json", metavar="FILE", help="Also write the report as JSON to this file")
    args = ap.parse_args()

    skill_path = Path(args.path).expanduser().resolve()
    if not skill_path.exists():
        print(f"Error: path does not exist: {skill_path}", file=sys.stderr)
        sys.exit(1)

    report = audit(skill_path)
    print_report(report)

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(asdict(report), fh, indent=2)
        print(f"\nJSON report written to {args.json}")

    # Exit code reflects risk so this can gate a CI/pre-install step if wanted.
    sevs = {f.severity for f in report.findings}
    if "HIGH" in sevs:
        sys.exit(2)
    if "MEDIUM" in sevs:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
