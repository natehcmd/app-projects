"""Subscription watcher: how much of each AI subscription is used, when it resets.

Sources (nothing estimated that could be measured):
  * Claude  — Nate's own Claude Code sessions: every assistant message's usage
              in ~/.claude/projects/**/*.jsonl (deduped by message id). Claude
              has no "tokens left" API, so the 5-hour session window is rebuilt
              from message times, and limits are LEARNED: when Nate presses
              "I just hit the limit", what was used in that window/week becomes
              the limit (data/subs.json).
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


def _parse_iso_utc(s):
    # "2026-09-23T15:50:48.585Z" -> epoch seconds (UTC)
    try:
        import calendar
        return calendar.timegm(time.strptime(s[:19], "%Y-%m-%dT%H:%M:%S"))
    except (TypeError, ValueError):
        return None


def _family(model):
    m = (model or "").lower()
    for f in ("opus", "sonnet", "haiku", "fable"):
        if f in m:
            return f
    return "other"


def claude_messages(now):
    """[(epoch, family, work_tokens, cache_read_tokens)] for the last 7 days, deduped."""
    seen, out = set(), []
    cutoff = now - WEEK_S
    for path in glob.glob(str(CLAUDE_DIR / "**" / "*.jsonl"), recursive=True):
        try:
            if os.path.getmtime(path) < cutoff:
                continue
            with open(path, errors="replace") as fh:
                for line in fh:
                    if '"usage"' not in line or '"assistant"' not in line:
                        continue
                    try:
                        d = json.loads(line)
                    except ValueError:
                        continue
                    msg = d.get("message") or {}
                    u = msg.get("usage") or {}
                    key = (msg.get("id"), d.get("requestId"))
                    if not u or key in seen:
                        continue
                    seen.add(key)
                    t = _parse_iso_utc(d.get("timestamp"))
                    if not t or t < cutoff:
                        continue
                    work = (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) \
                        + (u.get("output_tokens") or 0)
                    out.append((t, _family(msg.get("model")), work, u.get("cache_read_input_tokens") or 0))
        except OSError:
            continue
    out.sort()
    return out


def session_window(msgs, now):
    """Claude's 5-hour window starts at the first message after the last one expired."""
    start = None
    for t, *_ in msgs:
        if start is None or t >= start + SESSION_S:
            start = t
    if start is None or now >= start + SESSION_S:
        return None, None
    return start, start + SESSION_S


def _limits_file(root):
    return Path(root) / "data" / "subs.json"


def load_limits(root):
    try:
        return json.loads(_limits_file(root).read_text())
    except (OSError, ValueError):
        return {}


def _pct(used, limit):
    return round(100 * used / limit) if limit else None


def claude_status(root, now):
    msgs = claude_messages(now)
    start, reset = session_window(msgs, now)
    in_win = [m for m in msgs if start and m[0] >= start]
    lim = load_limits(root).get("claude", {})
    used_w = sum(m[2] for m in in_win)
    used_wk = sum(m[2] for m in msgs)
    by_model = {}
    for t, fam, work, _ in in_win:
        by_model[fam] = by_model.get(fam, 0) + work
    return {
        "id": "claude", "name": "Claude", "paid": True,
        "window": {"label": "this 5-hour session", "used": used_w, "limit": lim.get("window"),
                   "pct": _pct(used_w, lim.get("window")), "resets_at": reset,
                   "started_at": start},
        "week": {"label": "last 7 days", "used": used_wk, "limit": lim.get("week"),
                 "pct": _pct(used_wk, lim.get("week"))},
        "by_model": by_model,
        "cache_reads_window": sum(m[3] for m in in_win),
        "learned_at": lim.get("learned_at"),
        "note": "Your Claude Code sessions on this Mac. Limits are learned when you press 'I just hit the limit'.",
    }


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
    cw, ck = claude["window"]["pct"], claude["week"]["pct"]
    if (cw or 0) >= 80 or (ck or 0) >= 80:
        tips.append("Claude is past 80% — send work to Sonnet/Haiku subagents and Gemini; keep Opus for review only.")
    out = [m for m in gemini["models"] if m["out_until"]]
    for m in out:
        tips.append("%s is out until %s — the pipeline uses the next model down." %
                    (m["name"], time.strftime("%-I:%M %p", time.localtime(m["out_until"]))))
    hot = [m for m in gemini["models"] if (m["pct"] or 0) >= 80 and not m["out_until"]]
    for m in hot:
        tips.append("%s is at %d%% — the pipeline slows it down to stay near 80%%." % (m["name"], m["pct"]))
    if cw is None and ck is None:
        tips.append("Claude's limits aren't learned yet — press 'I just hit the limit' next time Claude stops you.")
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


def learn_limit(root, which):
    """Nate just got stopped by Claude: what was used becomes the limit."""
    now = time.time()
    c = claude_status(root, now)
    lim = load_limits(root)
    cl = lim.setdefault("claude", {})
    if which == "window":
        cl["window"] = max(c["window"]["used"], 1)
    elif which == "week":
        cl["week"] = max(c["week"]["used"], 1)
    else:
        raise ValueError("which must be window or week")
    cl["learned_at"] = now
    f = _limits_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(lim, indent=1))
    with _lock:
        _cache["data"] = None
    return cl


if __name__ == "__main__":
    print(json.dumps(status(Path(__file__).resolve().parent, max_age=0), indent=1, default=str)[:3000])
