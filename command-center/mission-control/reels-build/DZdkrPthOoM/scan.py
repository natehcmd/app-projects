#!/usr/bin/env python3
"""
cloud-guardrails-scanner
=========================

A small, dependency-free static scanner for Terraform (.tf) files that flags
the class of misconfigurations that turn into the two things the reel this
tool is based on calls out: a surprise 5-figure cloud bill and a security
incident. AI coding assistants are great at generating infrastructure-as-code
fast; they don't reliably remember to lock down security groups, encrypt
storage, cap IAM permissions, or wire up a billing alarm. This tool is a
cheap, deterministic guardrail you can run over anything (human- or
AI-generated) before it gets applied.

It is intentionally NOT a replacement for real tools like tfsec, checkov, or
AWS Config — it's a small, readable, single-file starting point that covers
the highest-signal checks with plain regexes over the raw HCL text, so it has
zero dependencies and runs anywhere Python 3 runs.

Usage:
    python3 scan.py <path-to-terraform-dir-or-file> [--format text|json] [--fail-on HIGH]

Exit code is non-zero only if --fail-on is set and a finding at or above that
severity is present (handy in CI).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# Ports that should essentially never be open to 0.0.0.0/0 in a security group.
SENSITIVE_PORTS = {
    22: "SSH",
    23: "Telnet",
    3389: "RDP",
    3306: "MySQL",
    5432: "PostgreSQL",
    6379: "Redis",
    27017: "MongoDB",
    9200: "Elasticsearch",
    5984: "CouchDB",
    11211: "Memcached",
}


@dataclass
class Finding:
    file: str
    line: int
    severity: str          # LOW | MEDIUM | HIGH
    category: str          # SECURITY | COST
    rule: str
    message: str
    remediation: str

    def to_dict(self):
        return asdict(self)


def iter_tf_blocks(text: str):
    """Yield (resource_type, resource_name, block_text, start_line) for each
    top-level `resource "..." "..." { ... }` block using brace matching.
    Good enough for well-formed HCL without needing a real parser."""
    pattern = re.compile(r'resource\s+"([^"]+)"\s+"([^"]+)"\s*\{')
    for m in pattern.finditer(text):
        start = m.end() - 1  # position of the opening brace
        depth = 0
        i = start
        while i < len(text):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    block = text[start:i + 1]
                    line_no = text.count("\n", 0, m.start()) + 1
                    yield m.group(1), m.group(2), block, line_no
                    break
            i += 1


def line_offset(block: str, sub_match_start: int) -> int:
    return block.count("\n", 0, sub_match_start)


def check_security_groups(rtype, rname, block, base_line, file_name, findings):
    if rtype not in ("aws_security_group", "aws_security_group_rule",
                      "aws_vpc_security_group_ingress_rule"):
        return

    if "0.0.0.0/0" not in block and "::/0" not in block:
        return

    # Try to find a from_port/to_port near an open cidr; if we can't tell,
    # flag generically.
    port_matches = list(re.finditer(r'(from_port|to_port)\s*=\s*(-?\d+)', block))
    ports_found = {int(m.group(2)) for m in port_matches if int(m.group(2)) >= 0}

    open_cidr_match = re.search(r'0\.0\.0\.0/0|::/0', block)
    line_no = base_line + line_offset(block, open_cidr_match.start())

    hit_ports = ports_found & set(SENSITIVE_PORTS)
    if hit_ports:
        names = ", ".join(f"{p}/{SENSITIVE_PORTS[p]}" for p in sorted(hit_ports))
        findings.append(Finding(
            file=file_name, line=line_no, severity="HIGH", category="SECURITY",
            rule="open-sensitive-port",
            message=f'{rtype} "{rname}" allows 0.0.0.0/0 on sensitive port(s): {names}.',
            remediation="Restrict the CIDR to known IP ranges / a bastion or VPN, "
                         "or use SSM Session Manager instead of exposing SSH/RDP directly.",
        ))
    elif ports_found and (0 in ports_found or -1 in ports_found or ports_found == {0, 65535}):
        findings.append(Finding(
            file=file_name, line=line_no, severity="HIGH", category="SECURITY",
            rule="open-all-ports",
            message=f'{rtype} "{rname}" opens ALL ports to 0.0.0.0/0.',
            remediation="Scope ingress to only the specific ports the service needs.",
        ))
    else:
        findings.append(Finding(
            file=file_name, line=line_no, severity="MEDIUM", category="SECURITY",
            rule="open-cidr",
            message=f'{rtype} "{rname}" has a rule open to the public internet (0.0.0.0/0).',
            remediation="Confirm this is intentional (e.g. a public web LB) and not "
                         "an accidental copy-paste from a tutorial or AI-generated example.",
        ))


def check_s3_public(rtype, rname, block, base_line, file_name, findings):
    if rtype != "aws_s3_bucket_acl" and rtype != "aws_s3_bucket":
        return
    m = re.search(r'acl\s*=\s*"(public-read|public-read-write)"', block)
    if m:
        line_no = base_line + line_offset(block, m.start())
        findings.append(Finding(
            file=file_name, line=line_no, severity="HIGH", category="SECURITY",
            rule="public-s3-acl",
            message=f'{rtype} "{rname}" sets ACL "{m.group(1)}" — bucket contents '
                     f'are readable/writable by anyone on the internet.',
            remediation='Use "private" ACL plus a scoped bucket policy, and enable '
                        "the account-level S3 Block Public Access settings.",
        ))


def check_s3_encryption_versioning(rtype, rname, block, base_line, file_name, findings, all_text):
    if rtype != "aws_s3_bucket":
        return
    # In modern provider versions, encryption/versioning are separate resources
    # referencing this bucket; a simple heuristic is to check whether the
    # bucket name is referenced by a matching *_versioning / *_encryption block
    # anywhere in the file, or configured inline for older provider syntax.
    has_inline_encryption = "server_side_encryption_configuration" in block
    has_inline_versioning = re.search(r'versioning\s*\{', block) is not None

    ref = f'aws_s3_bucket.{rname}.id'
    has_external_versioning = (
        has_inline_versioning or
        re.search(rf'aws_s3_bucket_versioning"\s*"[^"]+"\s*\{{[^}}]*{re.escape(ref)}', all_text, re.S) is not None
    )
    has_external_encryption = (
        has_inline_encryption or
        re.search(rf'aws_s3_bucket_server_side_encryption_configuration"\s*"[^"]+"\s*\{{[^}}]*{re.escape(ref)}', all_text, re.S) is not None
    )

    if not has_external_encryption:
        findings.append(Finding(
            file=file_name, line=base_line, severity="MEDIUM", category="SECURITY",
            rule="s3-no-encryption",
            message=f'aws_s3_bucket "{rname}" has no server-side encryption configured.',
            remediation="Add an aws_s3_bucket_server_side_encryption_configuration "
                        "resource (SSE-S3 or SSE-KMS) for this bucket.",
        ))
    if not has_external_versioning:
        findings.append(Finding(
            file=file_name, line=base_line, severity="LOW", category="SECURITY",
            rule="s3-no-versioning",
            message=f'aws_s3_bucket "{rname}" has no versioning configured.',
            remediation="Enable versioning so accidental deletes/overwrites (or "
                        "ransomware-style object tampering) are recoverable.",
        ))


def check_iam_wildcard(rtype, rname, block, base_line, file_name, findings):
    if rtype not in ("aws_iam_policy", "aws_iam_role_policy", "aws_iam_user_policy"):
        return
    # Look for Action = "*" / "Action": "*" (with or without a surrounding
    # array), covering both raw JSON policy strings/heredocs and HCL
    # jsonencode({...}) map syntax (unquoted keys, "=" instead of ":").
    action_re = r'"?Action"?\s*[:=]\s*(\[\s*)?"\*"'
    resource_re = r'"?Resource"?\s*[:=]\s*(\[\s*)?"\*"'
    has_wild_action = re.search(action_re, block) is not None
    has_wild_resource = re.search(resource_re, block) is not None
    if has_wild_action and has_wild_resource:
        m = re.search(action_re, block)
        line_no = base_line + line_offset(block, m.start())
        findings.append(Finding(
            file=file_name, line=line_no, severity="HIGH", category="SECURITY",
            rule="iam-wildcard-admin",
            message=f'{rtype} "{rname}" grants Action:"*" on Resource:"*" '
                     f'(full account admin).',
            remediation="Scope the policy to the specific actions and ARNs the "
                        "role actually needs (least privilege). AI-generated "
                        "policies default to this pattern surprisingly often.",
        ))


def check_rds_public(rtype, rname, block, base_line, file_name, findings):
    if rtype != "aws_db_instance":
        return
    m = re.search(r'publicly_accessible\s*=\s*true', block)
    if m:
        line_no = base_line + line_offset(block, m.start())
        findings.append(Finding(
            file=file_name, line=line_no, severity="HIGH", category="SECURITY",
            rule="rds-publicly-accessible",
            message=f'aws_db_instance "{rname}" has publicly_accessible = true.',
            remediation="Set publicly_accessible = false and reach the DB through "
                        "a VPN/bastion/private subnet instead.",
        ))
    if "storage_encrypted" not in block or re.search(r'storage_encrypted\s*=\s*false', block):
        findings.append(Finding(
            file=file_name, line=base_line, severity="MEDIUM", category="SECURITY",
            rule="rds-unencrypted",
            message=f'aws_db_instance "{rname}" does not have storage_encrypted = true.',
            remediation="Set storage_encrypted = true (must be done at creation time).",
        ))


def check_ebs_unencrypted(rtype, rname, block, base_line, file_name, findings):
    if rtype not in ("aws_ebs_volume", "aws_instance"):
        return
    # aws_instance root_block_device / ebs_block_device sub-blocks
    for sub in re.finditer(r'(root_block_device|ebs_block_device)\s*\{([^}]*)\}', block, re.S):
        subblock = sub.group(2)
        if not re.search(r'encrypted\s*=\s*true', subblock):
            line_no = base_line + line_offset(block, sub.start())
            findings.append(Finding(
                file=file_name, line=line_no, severity="MEDIUM", category="SECURITY",
                rule="ebs-unencrypted",
                message=f'{rtype} "{rname}" has a block device without encrypted = true.',
                remediation="Add encrypted = true to the device block (and set a "
                            "default EBS encryption policy account-wide as a backstop).",
            ))
    if rtype == "aws_ebs_volume" and not re.search(r'encrypted\s*=\s*true', block):
        findings.append(Finding(
            file=file_name, line=base_line, severity="MEDIUM", category="SECURITY",
            rule="ebs-unencrypted",
            message=f'aws_ebs_volume "{rname}" is not encrypted.',
            remediation="Add encrypted = true.",
        ))


def check_unbounded_autoscaling(rtype, rname, block, base_line, file_name, findings):
    if rtype != "aws_autoscaling_group":
        return
    m = re.search(r'max_size\s*=\s*(\d+)', block)
    if m and int(m.group(1)) >= 50:
        line_no = base_line + line_offset(block, m.start())
        findings.append(Finding(
            file=file_name, line=line_no, severity="MEDIUM", category="COST",
            rule="high-max-size-asg",
            message=f'aws_autoscaling_group "{rname}" allows scaling up to '
                     f'{m.group(1)} instances with no visible cap review.',
            remediation="Double check this max_size is intentional and that a "
                        "scale-down policy / target tracking policy exists so a "
                        "runaway loop or bad deploy can't scale you into a huge bill.",
        ))


def check_billing_alarm_present(all_text: str, files_scanned, findings):
    """Whole-project check: is there ANY budget/billing alarm defined at all?"""
    has_budget = "aws_budgets_budget" in all_text
    has_billing_alarm = bool(re.search(r'aws_cloudwatch_metric_alarm"\s*"[^"]*"\s*\{[^}]*EstimatedCharges', all_text, re.S))
    if not has_budget and not has_billing_alarm and files_scanned:
        findings.append(Finding(
            file="(project-wide)", line=0, severity="MEDIUM", category="COST",
            rule="no-billing-alarm",
            message="No aws_budgets_budget or billing CloudWatch alarm found anywhere "
                     "in the scanned files.",
            remediation="Add an aws_budgets_budget resource (or a CloudWatch alarm on "
                        "the EstimatedCharges metric) with an email/SNS notification "
                        "so a misconfiguration or runaway resource shows up as an "
                        "alert instead of a surprise invoice.",
        ))


CHECKS = [
    check_security_groups,
    check_s3_public,
    check_iam_wildcard,
    check_rds_public,
    check_ebs_unencrypted,
    check_unbounded_autoscaling,
]


def scan_file(path: Path, all_text_for_project: str, findings):
    text = path.read_text(errors="ignore")
    for rtype, rname, block, base_line in iter_tf_blocks(text):
        for check in CHECKS:
            check(rtype, rname, block, base_line, str(path), findings)
        # S3 encryption/versioning needs project-wide text to find companion resources
        check_s3_encryption_versioning(rtype, rname, block, base_line, str(path),
                                        findings, all_text_for_project)


def collect_tf_files(target: Path):
    if target.is_file():
        return [target]
    return sorted(target.rglob("*.tf"))


def main():
    parser = argparse.ArgumentParser(description="Static guardrail scanner for Terraform files.")
    parser.add_argument("path", help="Path to a .tf file or a directory to scan recursively.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--fail-on", choices=["LOW", "MEDIUM", "HIGH"], default=None,
                         help="Exit non-zero if any finding at or above this severity exists.")
    args = parser.parse_args()

    target = Path(args.path)
    if not target.exists():
        print(f"Path not found: {target}", file=sys.stderr)
        sys.exit(2)

    tf_files = collect_tf_files(target)
    if not tf_files:
        print(f"No .tf files found under {target}", file=sys.stderr)
        sys.exit(2)

    all_text = "\n".join(p.read_text(errors="ignore") for p in tf_files)

    findings: list[Finding] = []
    for f in tf_files:
        scan_file(f, all_text, findings)
    check_billing_alarm_present(all_text, tf_files, findings)

    findings.sort(key=lambda f: (-SEVERITY_ORDER[f.severity], f.file, f.line))

    if args.format == "json":
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        print_text_report(findings, tf_files)

    if args.fail_on:
        threshold = SEVERITY_ORDER[args.fail_on]
        if any(SEVERITY_ORDER[f.severity] >= threshold for f in findings):
            sys.exit(1)


def print_text_report(findings, tf_files):
    print(f"cloud-guardrails-scanner — scanned {len(tf_files)} file(s)\n")
    if not findings:
        print("No findings. (This checks a fixed set of common patterns — it is not "
              "a substitute for a full security review.)")
        return

    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        counts[f.severity] += 1

    print(f"Findings: {counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['LOW']} LOW\n")
    print("-" * 70)
    for f in findings:
        print(f"[{f.severity:6}] [{f.category:8}] {f.rule}")
        print(f"  {f.file}:{f.line}")
        print(f"  {f.message}")
        print(f"  Fix: {f.remediation}")
        print("-" * 70)


if __name__ == "__main__":
    main()
