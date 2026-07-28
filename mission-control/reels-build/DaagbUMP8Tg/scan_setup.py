#!/usr/bin/env python3
"""
Claude Code Setup Advisor
==========================

The Instagram reel this was built from ("Claude Code Setup" plugin) is pure
comment-for-link engagement bait -- it never discloses what the alleged
plugin actually does beyond "it scans your codebase and suggests stuff."
There's no official Anthropic plugin behind this, and no algorithm was
disclosed to reproduce.

This script builds the most reasonable, honest, standalone version of that
idea: a local, offline codebase scanner that looks at the signals actually
present in your project (manifests, config files, folder layout) and prints
a plain-language report suggesting which Claude Code building blocks --
hooks, skills, subagents, and MCP servers -- are a good fit. It makes no
network calls, installs nothing, and doesn't claim to be an official
Anthropic product. You review its suggestions and wire up whatever you like
by hand.

Usage
-----
    python3 scan_setup.py [path]

If [path] is omitted, the current directory is scanned.

No dependencies beyond the Python 3 standard library.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Findings:
    signals: list[str] = field(default_factory=list)
    suggestions: dict[str, list[str]] = field(
        default_factory=lambda: {
            "hooks": [],
            "skills": [],
            "subagents": [],
            "mcp_servers": [],
        }
    )

    def note(self, signal: str):
        if signal not in self.signals:
            self.signals.append(signal)

    def suggest(self, category: str, item: str):
        bucket = self.suggestions[category]
        if item not in bucket:
            bucket.append(item)


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return ""


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def scan(root: Path) -> Findings:
    f = Findings()

    # --- JavaScript / TypeScript stack -------------------------------
    pkg_path = root / "package.json"
    if pkg_path.exists():
        f.note("Node project (package.json found)")
        pkg = read_json(pkg_path)
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        if "typescript" in deps:
            f.note("TypeScript in use")
            f.suggest("hooks", "pre-commit: run `tsc --noEmit` to block type errors before commit")

        if any(k in deps for k in ("next",)):
            f.note("Next.js framework detected")
            f.suggest("skills", "next-js-app-router-helper: scaffold routes/loaders following App Router conventions")
            f.suggest("mcp_servers", "vercel (if deploying on Vercel — manage envs/deploys from chat)")

        if any(k in deps for k in ("react", "react-dom")) and "next" not in deps:
            f.note("React (non-Next) detected")
            f.suggest("skills", "component-scaffolder: generate React components with your existing conventions")

        if "express" in deps or "fastify" in deps or "koa" in deps:
            f.note("Node backend framework detected")
            f.suggest("subagents", "api-review: reviews new/changed endpoints for auth, input validation, error handling")

        if "prisma" in deps or (root / "prisma" / "schema.prisma").exists():
            f.note("Prisma ORM detected")
            f.suggest("mcp_servers", "postgres (or your Prisma datasource) — inspect schema/data from chat")
            f.suggest("subagents", "db-migration-reviewer: checks new Prisma migrations for destructive changes")

        if "jest" in deps or "vitest" in deps or "mocha" in deps:
            f.note("JS test runner detected")
            f.suggest("hooks", "pre-push: run test suite before pushing")
            f.suggest("subagents", "test-writer: drafts unit tests for new/changed functions")

        if "eslint" in deps:
            f.suggest("hooks", "pre-commit: run `eslint --fix` on staged files")

        if "stripe" in deps:
            f.note("Stripe SDK detected")
            f.suggest("mcp_servers", "stripe — look up charges/customers/webhooks from chat")

    # --- Python stack --------------------------------------------------
    req_files = [root / "requirements.txt", root / "pyproject.toml", root / "Pipfile"]
    py_manifest = next((p for p in req_files if p.exists()), None)
    if py_manifest:
        f.note(f"Python project ({py_manifest.name} found)")
        text = read_text(py_manifest).lower()

        if "django" in text:
            f.note("Django framework detected")
            f.suggest("subagents", "migration-reviewer: checks Django migrations before they're applied")
            f.suggest("mcp_servers", "postgres (Django's usual datastore) — query/inspect from chat")

        if "flask" in text:
            f.note("Flask framework detected")
            f.suggest("subagents", "api-review: checks new Flask routes for auth/input validation")

        if "fastapi" in text:
            f.note("FastAPI framework detected")
            f.suggest("skills", "pydantic-model-helper: keep request/response models in sync with routes")

        if "pytest" in text:
            f.note("pytest detected")
            f.suggest("hooks", "pre-push: run `pytest` before pushing")
            f.suggest("subagents", "test-writer: drafts pytest cases for new/changed functions")

        if "sqlalchemy" in text or "alembic" in text:
            f.suggest("mcp_servers", "postgres (or your SQLAlchemy datastore) — inspect schema from chat")

    # --- Infra / ops -----------------------------------------------------
    if (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists() or (root / "docker-compose.yaml").exists():
        f.note("Docker setup detected")
        f.suggest("skills", "container-debug-helper: reason about Dockerfile/compose changes")

        compose_text = ""
        for name in ("docker-compose.yml", "docker-compose.yaml"):
            p = root / name
            if p.exists():
                compose_text += read_text(p).lower()
        if "postgres" in compose_text:
            f.suggest("mcp_servers", "postgres — query the containerized DB from chat")
        if "redis" in compose_text:
            f.suggest("mcp_servers", "redis — inspect keys/queues from chat")
        if "mongo" in compose_text:
            f.suggest("mcp_servers", "mongodb — query collections from chat")

    if (root / ".github" / "workflows").is_dir():
        f.note("GitHub Actions CI detected")
        f.suggest("mcp_servers", "github — check PR/CI status and open issues from chat")
        f.suggest("subagents", "ci-triage: investigates failing workflow runs")

    if (root / "terraform").is_dir() or any(root.glob("*.tf")):
        f.note("Terraform IaC detected")
        f.suggest("subagents", "infra-review: sanity-checks Terraform plans for destructive changes")

    # --- Repo hygiene ------------------------------------------------------
    if not (root / ".git").exists():
        f.note("No .git directory found at this path — is this the repo root?")

    has_tests = any(root.glob("**/test_*.py")) or any(root.glob("**/*.test.js")) or \
        any(root.glob("**/*.test.ts")) or (root / "tests").is_dir() or (root / "test").is_dir()
    if not has_tests:
        f.note("No obvious test directory/files found")
        f.suggest("skills", "test-scaffolder: bootstrap an initial test suite for this project")

    env_example = root / ".env.example"
    if env_example.exists():
        f.note(".env.example found — checking referenced services (keys only, values ignored)")
        for line in read_text(env_example).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key = line.split("=", 1)[0].upper()
            if "STRIPE" in key:
                f.suggest("mcp_servers", "stripe — referenced in .env.example")
            if "SLACK" in key:
                f.suggest("mcp_servers", "slack — referenced in .env.example")
            if "AWS" in key or "S3" in key:
                f.suggest("mcp_servers", "aws (or filesystem-adjacent) — referenced in .env.example")

    if not f.signals:
        f.note("No recognizable manifests or config files found at this path")

    return f


def render_report(root: Path, f: Findings) -> str:
    lines = []
    lines.append(f"# Claude Code Setup Report — {root}\n")
    lines.append(
        "This is a local, offline scan of files actually present in your project. "
        "Nothing was sent anywhere. Review each suggestion before acting on it — "
        "this is a starting point, not an installer.\n"
    )

    lines.append("## What was detected\n")
    if f.signals:
        for s in f.signals:
            lines.append(f"- {s}")
    else:
        lines.append("- Nothing recognizable")
    lines.append("")

    labels = {
        "hooks": "Suggested hooks (pre-commit / pre-push automation)",
        "skills": "Suggested skills (packaged instructions for repeatable tasks)",
        "subagents": "Suggested subagents (focused reviewers you can invoke)",
        "mcp_servers": "Suggested MCP servers (connect Claude to live services)",
    }
    any_suggestions = False
    for key, label in labels.items():
        items = f.suggestions[key]
        if not items:
            continue
        any_suggestions = True
        lines.append(f"## {label}\n")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    if not any_suggestions:
        lines.append(
            "## No specific suggestions\n\n"
            "Nothing in this scan matched a known pattern. That's fine — not every "
            "project needs extra tooling. Run again from your actual project root "
            "if this looks wrong.\n"
        )

    lines.append(
        "---\n"
        "Note: this tool does not install, configure, or download anything on your "
        "behalf, and it is not an official Anthropic product. It only reads files "
        "already on disk and prints suggestions for you to act on manually.\n"
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scan a project for signals (manifests, frameworks, config) and "
                    "suggest Claude Code hooks/skills/subagents/MCP servers that fit. "
                    "Fully local and offline — reads files, makes no network calls, "
                    "installs nothing."
    )
    parser.add_argument("path", nargs="?", default=".",
                        help="Project directory to scan (default: current directory)")
    args = parser.parse_args()

    target = Path(args.path).resolve()
    if not target.is_dir():
        parser.error(f"{target} is not a directory")

    findings = scan(target)
    print(render_report(target, findings))


if __name__ == "__main__":
    main()
