# scan.py — cloud-guardrails-scanner for Terraform

## Source

> @jp_mather: A $22K cloud bill because nobody knew how to secure production.
> AI can help you build faster. It cannot replace good DevOps.

No specific tool or technique was named — this builds the concrete
implication of the claim: a static scanner that catches the class of
Terraform misconfigurations (open security groups, public S3/RDS, IAM
wildcards, missing encryption/billing alarms) that most commonly cause both
security incidents and surprise cloud bills, especially in AI-generated
infra-as-code.

## What it does

Dependency-free regex/brace-matching scanner over `.tf` files. Checks:
open security groups on sensitive ports, wide-open security group rules,
public S3 ACLs, missing S3 encryption/versioning, IAM policies granting
`Action:"*"`/`Resource:"*"`, publicly-accessible/unencrypted RDS, unencrypted
EBS volumes, unbounded autoscaling groups, and missing billing alarms.

Not a replacement for tfsec/checkov — a small, readable, zero-dependency
starting point.

## Verified working (2026-07-20)

Tested against a deliberately vulnerable Terraform file (open SSH ingress,
public S3 bucket, public+unencrypted RDS, IAM policy with `Action="*"` /
`Resource="*"` via `jsonencode()`). Initially the IAM wildcard check missed
the `jsonencode({...})` HCL-map form (`Action = "*"` vs `"Action": "*"`) —
fixed to match both forms. All 7 expected findings now fire correctly.

## Usage

```bash
python3 scan.py <path-to-.tf-file-or-dir> [--format text|json] [--fail-on HIGH]
```

`--fail-on` makes it CI-friendly (non-zero exit if a finding at/above that
severity exists).

## Status

**built = true**, verified working, one real bug found and fixed during QA.
