"""Real git-project tracker — scans your actual repos and reports genuine
git state (branch, uncommitted changes, recent commits, last-touched file).
No fabricated hours or fake progress numbers: anything about "how long
you've been working" comes only from an actually-running CLI process's real
elapsed time (ps etime), cross-referenced against your actual open Terminal
tabs — never invented.
"""
import re
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
SCAN_ROOTS = [HOME / "Projects", HOME / "Projects" / "AI", HOME / "Projects" / "Human" / "Apps"]


def _git(repo: Path, *args, timeout=5):
    try:
        # GIT_OPTIONAL_LOCKS=0: `status` otherwise refreshes the index and
        # takes index.lock, which collides when repos in the same monorepo
        # are scanned in parallel.
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"},
                           text=True, timeout=timeout)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _git_root_and_subpath(repo: Path):
    if (repo / ".git").is_dir():
        return repo, None
    if (repo.parent / ".git").is_dir():
        return repo.parent, repo.name
    return repo, None

def _find_repos():
    repos, seen = [], set()
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        try:
            entries = list(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.name == "app-projects" and (entry / ".git").is_dir():
                for sub in entry.iterdir():
                    if sub.name.startswith(".") or not sub.is_dir():
                        continue
                    if str(sub) not in seen:
                        seen.add(str(sub))
                        repos.append(sub)
                continue
            if str(entry) in seen:
                continue
            if (entry / ".git").is_dir():
                seen.add(str(entry))
                repos.append(entry)
    return repos


def _sanitize_remote(url: str) -> str:
    # Strip any embedded credentials (https://user:token@host/...) before
    # this ever reaches the UI.
    return re.sub(r"://[^/@]+@", "://", url)


def _status_files(repo: Path):
    root, subpath = _git_root_and_subpath(repo)
    args = ["status", "--porcelain"]
    if subpath:
        args += ["--", subpath]
    out = _git(root, *args)
    files = []
    prefix = f"{subpath}/" if subpath else ""
    for line in out.split("\n"):
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
        files.append({"status": code.strip() or "??", "path": path})
    return files


def _recent_commits(repo: Path, n=5):
    root, subpath = _git_root_and_subpath(repo)
    args = ["log", f"-{n}", "--pretty=format:%h\x1f%ar\x1f%s"]
    if subpath:
        args += ["--", subpath]
    out = _git(root, *args)
    commits = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) == 3:
            commits.append({"hash": parts[0], "when": parts[1], "message": parts[2]})
    return commits


def _unpushed_count(repo: Path):
    root, _ = _git_root_and_subpath(repo)
    upstream = _git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if not upstream:
        return None  # no tracking branch configured — not "0", genuinely unknown
    out = _git(root, "log", "@{u}..HEAD", "--oneline")
    return len([l for l in out.split("\n") if l.strip()])


def _last_touched(repo: Path) -> str:
    """Newest mtime among top-level entries, formatted relative — mirrors
    apps_scanner's approach so 'last thing you're on' reflects uncommitted
    edits too, not just the last commit."""
    try:
        newest = repo.stat().st_mtime
        for entry in repo.iterdir():
            if entry.name in ("node_modules", ".git") or entry.name.startswith("."):
                continue
            try:
                m = entry.stat().st_mtime
                if m > newest:
                    newest = m
            except OSError:
                continue
    except OSError:
        return "unknown"
    delta = datetime.now().timestamp() - newest
    if delta < 3600: return f"{int(delta // 60)}m ago"
    if delta < 86400: return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def _match_active_session(repo_name: str, branch: str, terminal_tabs: list, cli_processes: list):
    """Real cross-reference only — a terminal tab whose title/task actually
    mentions this repo or branch, joined to a real running CLI process (via
    tty) for its actual elapsed time. Returns None if nothing genuinely
    matches; never guesses."""
    needle_repo = re.sub(r"[^a-z0-9]", "", repo_name.lower())
    needle_branch = re.sub(r"[^a-z0-9]", "", branch.lower()) if branch else ""
    for tab in terminal_tabs:
        hay = re.sub(r"[^a-z0-9]", "", (tab.get("title", "") + tab.get("task", "")).lower())
        if not hay:
            continue
        if (needle_repo and needle_repo in hay) or (needle_branch and len(needle_branch) > 3 and needle_branch in hay):
            # _terminal_tabs() reports tty as "/dev/ttys003"; `ps` (used by
            # _cli_processes()) reports the same tty as bare "ttys003" —
            # normalize both before joining or this never matches.
            tab_tty = (tab.get("tty") or "").replace("/dev/", "")
            proc = next((p for p in cli_processes
                        if p.get("tty") and p["tty"].replace("/dev/", "") == tab_tty), None)
            return {
                "engine": tab.get("engine", "Shell"),
                "task": tab.get("task", ""),
                "etime": proc["etime"] if proc else None,
            }
    return None


def _limited_glob(repo, patterns, limit=2000):
    """Walk at most `limit` entries (skip deps/build dirs) yielding matches."""
    import fnmatch
    seen = 0
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git", ".venv", "venv", "build", "dist", "reels-build", "DerivedData")]
        for f in filenames:
            seen += 1
            if seen > limit:
                return
            if any(fnmatch.fnmatch(f, p) for p in patterns):
                yield f


def _scan_one(repo, terminal_tabs, cli_processes):
    git_root, _ = _git_root_and_subpath(repo)
    branch = _git(git_root, "rev-parse", "--abbrev-ref", "HEAD") or "(detached)"
    remote = _sanitize_remote(_git(git_root, "config", "--get", "remote.origin.url"))
    uncommitted = _status_files(repo)
    recent = _recent_commits(repo)
    unpushed = _unpushed_count(repo)
    active = _match_active_session(repo.name, branch, terminal_tabs, cli_processes)
    last_touched = _last_touched(repo)
    # Facts for "what's missing to be perfect" — measured, not guessed.
    has_tests = any((repo / d).is_dir() for d in ("tests", "test", "Tests", "__tests__")) or any(
        True for _ in _limited_glob(repo, ("test_*.py", "*_test.py", "*.test.js", "*Tests.swift")))
    has_readme = any((repo / n).exists() for n in ("README.md", "README", "readme.md"))

    if active:
        status_label = "active now"
    elif uncommitted:
        status_label = "uncommitted work pending"
    elif recent:
        # last commit's relative time, e.g. "3 days ago" — flag as stale
        # if it looks like weeks/months/years back.
        when = recent[0]["when"]
        status_label = "stale" if any(u in when for u in ("week", "month", "year")) else "up to date"
    else:
        status_label = "no commits yet"

    return {
        "name": repo.name,
        "path": str(repo),
        "branch": branch,
        "remote": remote,
        "last_commit": recent[0] if recent else None,
        "recent_commits": recent,
        "uncommitted": uncommitted,
        "unpushed_count": unpushed,
        "last_touched": last_touched,
        "active_session": active,
        "status_label": status_label,
        "has_tests": has_tests,
        "has_readme": has_readme,
    }


def scan(terminal_tabs=None, cli_processes=None):
    terminal_tabs = terminal_tabs or []
    cli_processes = cli_processes or []
    # Repos are independent; ~5 git calls each ran serially (1.5s idle,
    # ~6s with the machine busy). Parallel, order restored by the sort below.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        projects = list(pool.map(lambda r: _scan_one(r, terminal_tabs, cli_processes), _find_repos()))

    # Active sessions first, then most recently touched.
    def sort_key(p):
        return (0 if p["active_session"] else 1, p["name"])
    return sorted(projects, key=lambda p: (p["active_session"] is None, p["name"].lower()))
