"""Subscription watcher: how much of each AI subscription is used, when it resets.

Sources (nothing estimated that could be measured):
  * Claude  — Claude Code's own `/usage` (exact session / weekly % and reset
              times from Anthropic), run as `claude -p /usage` — local, 0 tokens.
  * Gemini  — the review pipeline's budget governor (~/.cache/code-review-
              pipeline): tokens it spent per agy model this window, capacity
              learned from real "quota reached · resets in …" errors, and the
              quota breaker's exhausted-until times. Nate's own interactive agy
              use shares that quota but is invisible here — said in the UI.
  * Local   — Ollama: free, shown for scale only.
"""
import glob
import json
import os
import threading
import time
from pathlib import Path

HOME = Path.home()
CLAUDE_DIR = HOME / ".claude" / "projects"
PIPE_DIR = HOME / ".cache" / "code-review-pipeline"
SESSION_S = 5 * 3600
WEEK_S = 7 * 86400
TARGET = 0.80

_cache = {"t": 0.0, "data": None}
_lock = threading.Lock()


def _pct(used, limit):
    return round(100 * used / limit) if limit else None


_usage_cache = {"t": 0.0, "data": None}


def claude_usage():
    """Exact plan usage from Claude Code's own /usage (runs locally: 0 tokens)."""
    import re
    import subprocess
    if _usage_cache["data"] and time.time() - _usage_cache["t"] < 120:
        return _usage_cache["data"]
    try:
        r = subprocess.run(["claude", "-p", "/usage", "--output-format", "json"],
                           capture_output=True, text=True, timeout=60)
        text = json.loads(r.stdout).get("result", "")
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return {"limits": [], "error": "couldn't run /usage: %s" % e}
    limits = [{"label": m.group(1).strip(), "pct": int(m.group(2)), "resets": m.group(3).strip()}
              for m in re.finditer(r"^(Current [^:]+):\s*(\d+)% used\s*·\s*resets ([^(\n]+)", text, re.M)]
    data = {"limits": limits, "error": None if limits else "no usage lines in /usage output"}
    _usage_cache.update(t=time.time(), data=data)
    return data


def claude_status(root, now):
    u = claude_usage()
    return {"id": "claude", "name": "Claude", "paid": True, "source": "/usage",
            "limits": u["limits"], "error": u["error"],
            "note": "Exact numbers from Claude Code's /usage."}


def gemini_status(now):
    try:
        budget = json.loads((PIPE_DIR / "budget.json").read_text())
    except (OSError, ValueError):
        budget = {}
    try:
        quota = json.loads((PIPE_DIR / "quota.json").read_text())
    except (OSError, ValueError):
        quota = {}
    spent = {}
    try:
        with open(PIPE_DIR / "usage.jsonl", errors="replace") as fh:
            for line in fh:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                spent.setdefault(e.get("k"), []).append((e.get("t") or 0, e.get("n") or 0))
    except OSError:
        pass
    names = {"agy_pro": "Gemini Pro", "agy_flash": "Gemini Flash", "agy_deep": "Gemini (agy default)"}
    models = []
    for key, name in names.items():
        b = budget.get(key, {})
        reset_at, cap = b.get("reset_at"), b.get("capacity")
        # current window = the 5h (default) before the known reset, or the last 5h
        win_start = (reset_at - SESSION_S) if reset_at and reset_at > now else now - SESSION_S
        used = sum(tok for t, tok in spent.get(key, []) if t >= win_start)
        out_until = quota.get(key) if (quota.get(key) or 0) > now else None
        models.append({"key": key, "name": name, "used": used, "limit": cap, "pct": _pct(used, cap),
                       "resets_at": reset_at if reset_at and reset_at > now else None,
                       "out_until": out_until})
    return {"id": "gemini", "name": "Gemini (Antigravity)", "paid": True, "models": models,
            "note": "What the pipeline spent. Your own agy chats use the same quota but aren't visible here."}


def local_status(now):
    """Local tokens aren't in the budget log; Arena's per-run ledgers have them
    (cumulative within a run, so take each run's largest figure)."""
    runs = HOME / ".local/share/review-pipeline/code-review-pipeline/scripts/arena_runs"
    used, seen_any = 0, False
    for f in glob.glob(str(runs / "*" / "events.jsonl")):
        try:
            if os.path.getmtime(f) < now - 86400:
                continue
            best = 0
            with open(f, errors="replace") as fh:
                for line in fh:
                    if '"ledger"' not in line:
                        continue
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("kind") == "ledger" and (e.get("t") or 0) >= now - 86400:
                        best = max(best, (e.get("by_provider") or {}).get("ollama", 0))
                        seen_any = True
            used += best
        except OSError:
            continue
    return {"id": "local", "name": "Local models (Ollama)", "paid": False,
            "day": {"label": "last 24 hours (code reviews)", "used": used if seen_any else None},
            "note": "Free — runs on this Mac. Counted from code-review runs; Team/Compare local calls aren't logged."}


def advice(claude, gemini):
    tips = []
    top = max((l["pct"] for l in claude["limits"]), default=None)
    if top is not None and top >= 80:
        tips.append("Claude is past 80% — send work to Sonnet/Haiku subagents and Gemini; keep Opus for review only.")
    for m in gemini["models"]:
        if m["out_until"]:
            tips.append("%s is out until %s — the pipeline uses the next model down." %
                        (m["name"], time.strftime("%-I:%M %p", time.localtime(m["out_until"]))))
        elif (m["pct"] or 0) >= 80:
            tips.append("%s is at %d%% — the pipeline slows it down to stay near 80%%." % (m["name"], m["pct"]))
    return tips


def status(root, max_age=120):
    """Cached: scanning a week of transcripts takes ~1-2 s."""
    with _lock:
        if _cache["data"] and time.time() - _cache["t"] < max_age:
            return _cache["data"]
    now = time.time()
    c, g, l = claude_status(root, now), gemini_status(now), local_status(now)
    data = {"subs": [c, g, l], "advice": advice(c, g), "target_pct": int(TARGET * 100),
            "generated": now}
    with _lock:
        _cache.update(t=time.time(), data=data)
    return data


if __name__ == "__main__":
    print(json.dumps(status(Path(__file__).resolve().parent, max_age=0), indent=1, default=str)[:3000])
