"""Real 'apps you've built' scanner — a faithful Python port of my-apps'
Scanner.swift (Sources/MyApps/Scanner.swift), so Command Center's Apps tab
shows the exact same catalog the native my-apps launcher does, with no
placeholder data. Ported rather than shelled-out-to because my-apps has no
CLI/headless mode — it's a SwiftUI WindowGroup app only.
"""
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()

SCAN_ROOTS = [
    (HOME / "Projects" / "app-projects", "App Projects"),
    (HOME / "Projects" / "AI", "AI"),
    (HOME / "Projects" / "Human" / "Apps", "Human Apps"),
    (HOME / "Projects", "Projects"),
    (HOME, "Home"),
]

MARKERS = [".git", "package.json", "pyproject.toml", "Package.swift",
           "manifest.json", "Cargo.toml", "requirements.txt", "Makefile"]

HOME_EXCLUDES = {
    "Applications", "Desktop", "Documents", "Downloads", "Library",
    "Movies", "Music", "Pictures", "Public", "Sites", "Projects",
    "OneDrive", "audits", "chat-logs", "prompts", "bin",
}

# reels-build lives inside mission-control itself (see server.py's TOOLS_DIR)
MC_ROOT = Path(__file__).parent
REELS_MANIFEST = MC_ROOT / "reels-build" / "tools_manifest.json"

# Same curated third-party finds Scanner.swift hardcodes under "Inspo" —
# real tools verified during the reels research pass, kept for parity so
# the web tab matches the native app's catalog exactly.
INSPO_ITEMS = [
    ("skills", "Vercel Labs' open skills CLI — discover and install Claude Skills.",
     HOME / ".npm-global/lib/node_modules/skills", "skills find"),
    ("ruflo", "ruvnet/claude-flow — multi-agent orchestration CLI.",
     HOME / ".npm-global/lib/node_modules/ruflo", "ruflo --help"),
    ("jcode", "Rust coding-agent CLI, built from source (9.5k+ stars, organic growth).",
     HOME / "Projects/jcode", "jcode --version"),
    ("markitdown", "Microsoft's file-to-Markdown converter.",
     Path("/opt/homebrew/bin/markitdown"), "markitdown --help"),
    ("claude-cookbooks", "Official Anthropic example notebooks and recipes.",
     HOME / "Learning/claude-cookbooks", None),
    ("anthropic-courses", "Official Anthropic educational courses.",
     HOME / "Learning/anthropic-courses", None),
    ("Camoufox", "Anti-detect Playwright-based browser automation.",
     MC_ROOT / "reels-build/DanS4w5lcoZ",
     str(MC_ROOT / "reels-build/DanS4w5lcoZ/.venv/bin/camoufox") + " --help"),
    ("Hyperframes", "npm package discovered alongside Camoufox in the same reel.",
     Path("/opt/homebrew/lib/node_modules/hyperframes"), None),
    ("awesome-claude-skills", "Curated, actively-maintained list of real Claude Skills "
     "(14k+ stars, organic growth) — found during the deep web-research pass on reels "
     "with no direct link.", HOME / "Learning/awesome-claude-skills", None),
    ("ECC (everything-claude-code)", "119 skills/subagents/hooks framework, real "
     "Anthropic hackathon winner — installed project-scoped (not global) in ECC-eval "
     "to avoid touching your main Claude Code config.", HOME / "Projects/ECC-eval", None),
    ("Kickbacks", "Statusline and editor token monetization integration.",
     HOME / ".local/bin/kickbacks", "kickbacks --status"),
    ("Vayne Lead Finder", "Open-source compliant B2B lead finder CLI tool.",
     MC_ROOT / "reels-build/DYKSh1iv8nP",
     "python3 " + str(MC_ROOT / "reels-build/DYKSh1iv8nP/lead_finder.py") + " --help"),
    ("claude-ads", "33 ad auditing skills across Meta, Google, TikTok, YouTube, and LinkedIn.",
     MC_ROOT / "reels-build/DanS4w5lcoZ/claude-ads",
     "python3 " + str(MC_ROOT / "reels-build/DanS4w5lcoZ/claude-ads/claude_ads_core/cli.py") + " --help"),
    ("free-claude-code", "Routes Claude Code/Codex/Pi through free/local model backends — "
     "real, verified via GitHub Trending + community reports, not fake stars.",
     HOME / ".local/bin/fcc-server", "fcc-server --version"),
]


def _squash(s):
    return re.sub(r"[^a-z]", "", s.lower())


def _mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc).isoformat()


def _newest_change(path: Path) -> str:
    """Newest mtime among top-level entries — dir mtime alone misses edits in subfolders."""
    try:
        newest = path.stat().st_mtime
    except OSError:
        return datetime.fromtimestamp(0, tz=timezone.utc).isoformat()
    try:
        for entry in path.iterdir():
            if entry.name == "node_modules" or entry.name.startswith("."):
                continue
            try:
                m = entry.stat().st_mtime
                if m > newest:
                    newest = m
            except OSError:
                continue
    except OSError:
        pass
    return datetime.fromtimestamp(newest, tz=timezone.utc).isoformat()


def _readme_summary(path: Path):
    for candidate in ("README.md", "readme.md", "README.txt", "CLAUDE.md"):
        f = path / candidate
        if not f.exists():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for raw in text.split("\n"):
            line = raw.strip()
            if not line or line.startswith(("#", "!", "[", "---", "<", "|", "```", "*")):
                continue
            return line[:160]
    return None


def _default_summary(path: Path) -> str:
    try:
        count = sum(1 for _ in path.iterdir())
    except OSError:
        count = 0
    return f"{count} items"


def _kind(path: Path, name: str) -> str:
    if (path / "Package.swift").exists():
        return "Mac App"
    if (path / "manifest.json").exists():
        return "Chrome Extension"
    if (path / "Cargo.toml").exists():
        return "Rust"
    has_py = False
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        has_py = True
    else:
        try:
            has_py = any(p.suffix == ".py" for p in path.iterdir())
        except OSError:
            has_py = False
    if has_py:
        return "Python"
    if (path / "package.json").exists():
        return "Web / Node"
    if (path / "index.html").exists():
        return "Website"
    if name == "scripts":
        return "Scripts"
    return "Project"


def _category(kind: str, has_bundle: bool, explicit=None) -> str:
    if explicit:
        return explicit
    if kind == "Claude Skill":
        return "Skills"
    if kind == "Website":
        return "Websites"
    if has_bundle:
        return "Apps"
    return "Projects"


def _skill_description(skill_file: Path):
    try:
        lines = skill_file.read_text(encoding="utf-8", errors="ignore").split("\n")
    except OSError:
        return None
    for i, raw in enumerate(lines):
        if raw.startswith("description:"):
            value = raw[len("description:"):].strip()
            if value in (">", "|", ""):
                for later in lines[i + 1:]:
                    if later.strip():
                        value = later.strip()
                        break
            return value[:160] if value else None
    return None


def _describe(path: Path, name: str, area: str) -> dict:
    kind = _kind(path, name)
    return {
        "id": str(path), "name": name, "path": str(path), "kind": kind,
        "summary": _readme_summary(path) or _default_summary(path),
        "modified": _newest_change(path), "area": area,
        "appBundle": None, "category": _category(kind, False),
        "terminalCommand": None,
    }


def _match_app_bundle(name: str, bundles_squashed: dict):
    squashed = _squash(name)
    for b_squashed, b_path in bundles_squashed.items():
        if b_squashed == squashed or (len(squashed) > 3 and squashed in b_squashed):
            return b_path
    return None


def scan() -> list[dict]:
    apps: dict[str, dict] = {}

    for root, area in SCAN_ROOTS:
        if not root.is_dir():
            continue
        try:
            names = [p.name for p in root.iterdir()]
        except OSError:
            continue
        for name in names:
            if name.startswith(".") or name.startswith("junk"):
                continue
            if "Google Drive" in name or "Nexus-Vault" in name:
                continue
            if area == "Home" and name in HOME_EXCLUDES:
                continue
            if area == "Projects" and name in ("AI", "Human", "app-projects"):
                continue
            path = root / name
            if not path.is_dir():
                continue
            if not any((path / m).exists() for m in MARKERS):
                continue
            if str(path) in apps:
                continue
            apps[str(path)] = _describe(path, name, area)

    # Built .app bundles in ~/Applications
    apps_dir = HOME / "Applications"
    if apps_dir.is_dir():
        bundles_squashed = {}
        try:
            bundle_names = [p.name for p in apps_dir.iterdir() if p.name.endswith(".app")]
        except OSError:
            bundle_names = []
        for bundle in bundle_names:
            base = bundle[:-4]
            match = None
            squashed = _squash(base)
            for a in apps.values():
                a_squashed = _squash(a["name"])
                if a_squashed == squashed or squashed in a_squashed:
                    match = a
                    break
            bundle_path = apps_dir / bundle
            if match:
                match["appBundle"] = str(bundle_path)
                match["category"] = _category(match["kind"], True)
            else:
                apps[str(bundle_path)] = {
                    "id": str(bundle_path), "name": base, "path": str(bundle_path),
                    "kind": "Built App", "summary": "Standalone app bundle",
                    "modified": _mtime(bundle_path), "area": "Built Apps",
                    "appBundle": str(bundle_path), "category": "Apps",
                    "terminalCommand": None,
                }
            bundles_squashed[squashed] = str(bundle_path)

    # Claude skills
    skills_dir = HOME / ".claude" / "skills"
    if skills_dir.is_dir():
        try:
            skill_names = [p.name for p in skills_dir.iterdir()]
        except OSError:
            skill_names = []
        for name in skill_names:
            path = skills_dir / name
            skill_file = path / "SKILL.md"
            if not skill_file.exists():
                continue
            apps[str(path)] = {
                "id": str(path), "name": name, "path": str(path), "kind": "Claude Skill",
                "summary": _skill_description(skill_file) or "Claude skill",
                "modified": _mtime(skill_file), "area": "Skills",
                "appBundle": None, "category": "Skills", "terminalCommand": None,
            }

    # Registered Reel Build tools (also surfaced in the dedicated Reel Tools
    # tab via /api/tools — included here too so Apps mirrors my-apps exactly)
    try:
        manifest = json.loads(REELS_MANIFEST.read_text())
    except (OSError, json.JSONDecodeError):
        manifest = []
    apps_dir_bundles = {}
    if apps_dir.is_dir():
        try:
            apps_dir_bundles = {p.name: p for p in apps_dir.iterdir() if p.name.endswith(".app")}
        except OSError:
            pass
    for tool in manifest:
        tid = tool.get("id"); name = tool.get("name")
        script = tool.get("script"); desc = tool.get("desc")
        if not (tid and name and script and desc):
            continue
        usage = tool.get("usage") or f"python3 {script} --help"
        tool_path = MC_ROOT / "reels-build" / tid
        bundle_match = None
        squashed = _squash(name)
        for bname, bpath in apps_dir_bundles.items():
            b_squashed = _squash(bname[:-4])
            if tid in bname or b_squashed == squashed or squashed in b_squashed or b_squashed in squashed:
                bundle_match = str(bpath)
                break
        mod_time = _newest_change(tool_path) if tool_path.exists() else _mtime(REELS_MANIFEST)
        apps[f"reel:{tid}"] = {
            "id": f"reel:{tid}", "name": name, "path": str(tool_path), "kind": "Built App",
            "summary": desc, "modified": mod_time,
            "area": "Reel Apps", "appBundle": bundle_match, "category": "Apps",
            "terminalCommand": f'cd "{tool_path}" && {usage}',
        }

    # Inspo — real third-party tools found during reels research
    for name, summary, path, cmd in INSPO_ITEMS:
        cmd_path = None
        if cmd:
            parts = cmd.split()
            cmd_path = parts[1] if parts[0] in ("python", "python3") and len(parts) > 1 else parts[0]

        p = Path(path)
        if cmd_path and (cmd_path.startswith("/") or "/" in cmd_path):
            if not Path(cmd_path).exists():
                continue
        elif cmd_path:
            import shutil
            if not shutil.which(cmd_path) and not p.exists():
                continue
        elif not p.exists():
            continue

        mod_time = _newest_change(p) if p.is_dir() else (_mtime(p) if p.exists() else _mtime(REELS_MANIFEST))
        apps[f"inspo:{name}"] = {
            "id": f"inspo:{name}", "name": name, "path": str(path), "kind": "Project",
            "summary": summary, "modified": mod_time,
            "area": "Inspo", "appBundle": None, "category": "Inspo",
            "terminalCommand": cmd,
        }

    return sorted(apps.values(), key=lambda a: a["modified"], reverse=True)


def open_app(app: dict):
    """Mirrors AppScanner.open(_:) — launch bundle, else terminal command, else reveal in Finder."""
    bundle = app.get("appBundle")
    if bundle and Path(bundle).exists():
        subprocess.Popen(["open", bundle])
        return {"action": "launched", "bundle": bundle}

    apps_dir = HOME / "Applications"
    if apps_dir.is_dir():
        clean_id = app.get("id", "").replace("reel:", "").replace("inspo:", "")
        squashed = _squash(app.get("name", ""))
        try:
            for b in apps_dir.iterdir():
                if not b.name.endswith(".app"):
                    continue
                b_squashed = _squash(b.name[:-4])
                if (clean_id and clean_id in b.name) or b_squashed == squashed or \
                   (len(squashed) > 3 and squashed in b_squashed):
                    subprocess.Popen(["open", str(b)])
                    return {"action": "launched", "bundle": str(b)}
        except OSError:
            pass

    cmd = app.get("terminalCommand")
    if cmd:
        # Backslashes first — otherwise a trailing "\" in cmd would combine
        # with the quote-escape below into "\\\"", breaking back out of the
        # AppleScript string literal.
        clean_cmd = cmd.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')
        script = (f'tell application "Terminal" to activate\n'
                  f'tell application "Terminal" to do script "{clean_cmd}"')
        subprocess.Popen(["osascript", "-e", script])
        return {"action": "terminal", "command": cmd}

    path = app.get("path")
    if path and Path(path).exists():
        subprocess.Popen(["open", "-R", path])
        return {"action": "revealed", "path": path}

    return {"action": "none"}
