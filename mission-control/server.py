"""Mission Control — local agentic OS dashboard. Runs on http://localhost:8450"""
import json, os, re, shutil, sqlite3, subprocess, datetime, threading, urllib.request
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).parent
DB = ROOT / "data" / "mission.db"
OLLAMA = "http://localhost:11434"
BRIEF_MODEL = "qwen2.5-coder:32b"

app = FastAPI(title="Mission Control")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS reels(id TEXT PRIMARY KEY, uploader TEXT, caption TEXT,
      transcript TEXT, url TEXT, added TEXT, topic TEXT, verdict TEXT, notes TEXT);
    CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT,
      done INTEGER DEFAULT 0, urgent INTEGER DEFAULT 0, created TEXT, completed TEXT);
    CREATE TABLE IF NOT EXISTS subscriptions(id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT, monthly REAL, note TEXT);
    CREATE TABLE IF NOT EXISTS networth(id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT, assets REAL, liabilities REAL, note TEXT);
    CREATE TABLE IF NOT EXISTS checkins(id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT UNIQUE, energy INTEGER, focus INTEGER, mood INTEGER, note TEXT, score INTEGER);
    CREATE TABLE IF NOT EXISTS flows(id TEXT PRIMARY KEY, name TEXT, steps TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY AUTOINCREMENT,
      ts TEXT, kind TEXT, detail TEXT);
    """)
    c.commit(); c.close()

def seed_reels():
    curated = {  # id: (topic, verdict)
      "DaagbUMP8Tg": ("claude-setup", "installed"), "DaNjtbcFSLE": ("claude-md", "applied"),
      "DXmWHzIExeq": ("free-backends", "skipped"), "DYXFtTFsbLt": ("local-models", "done"),
      "DXxQS0AO1Km": ("multi-agent", "skipped"), "DY_SoPGKv2A": ("multi-agent", "skipped"),
      "DZsup8Lx6yQ": ("multi-agent", "skipped"), "DZCzO6GE0y7": ("mega-repo", "skipped"),
      "DZDksUcipwZ": ("skills", "installed"), "DaSwegFCZO7": ("skills", "installed"),
      "DXUJ1zdCJaa": ("learning", "reference"), "DY2GRVfN4bZ": ("markitdown", "installed"),
      "DXAshxEDM5m": ("memory-graph", "skipped"), "DZpgTfBioe6": ("design", "partial"),
      "DZue1ksxHGF": ("design", "partial"), "DaI3LY3tLYn": ("career", "tracked"),
      "DZLHHJuOPVs": ("career", "saved"), "DaWVAIrh_EB": ("career", "saved"),
      "DWwLhCEAtV_": ("security", "noted"), "DYkjSXcA45p": ("security", "noted"),
      "DYSUqcsuGX9": ("saves-organizer", "rebuilt"), "DYC5WI6AU_N": ("jarvis", "rebuilt"),
      "DZAr26ugm5H": ("jarvis", "rebuilt"), "DZ1BSCyRtD0": ("agent-team", "rebuilt"),
      "DZDUd0kS7lw": ("agents-marketplace", "installed"), "DYKSh1iv8nP": ("leadgen", "skipped"),
      "DZY4CWVPiXl": ("jarvis", "skipped"), "DZoJOLQoQY2": ("ads", "skipped"),
      "DZcSLefuxRU": ("jarvis", "skipped"), "DXUHZ5SDVs-": ("jarvis", "skipped"),
      "DaSw8Balfqk": ("jarvis", "skipped"), "DYnFlSKK-Qg": ("learning", "noted"),
      # comment-bait funnels (DM/comment-for-link, no installable tool) — auto-skipped
      "DZ0rP21xg1V": ("content-bait", "skipped"), "DZ5xhLYvGpT": ("content-bait", "skipped"),
      "DZAtd2JTvT9": ("content-bait", "skipped"), "DZn-G9wvwgX": ("content-bait", "skipped"),
      "DZxUGClNzi_": ("content-bait", "skipped"), "DaMauuPAzao": ("content-bait", "skipped"),
      "DaQ1XDsycZP": ("content-bait", "skipped"), "DaWjATqpBjL": ("content-bait", "skipped"),
    }
    c = db()
    meta_dir = ROOT / "data" / "reels" / "meta"
    for f in sorted(meta_dir.glob("*.json")):
        rid = f.stem
        try:
            d = json.loads(f.read_text())
            assert d and d.get("id")
        except Exception:
            continue
        tx_file = ROOT / "data" / "reels" / "tx" / f"{rid}.txt"
        tx = tx_file.read_text().strip() if tx_file.exists() else ""
        topic, verdict = curated.get(rid, ("uncategorized", "review"))
        c.execute("""INSERT OR IGNORE INTO reels(id,uploader,caption,transcript,url,added,topic,verdict)
          VALUES(?,?,?,?,?,?,?,?)""", (rid, d.get("uploader") or d.get("channel") or "?",
          (d.get("description") or "")[:2000], tx[:6000],
          f"https://www.instagram.com/reel/{rid}/", "2026-07-06", topic, verdict))
    c.commit(); c.close()

init_db(); seed_reels()

# ---------- helpers ----------
def ollama_gen(prompt, model=BRIEF_MODEL, timeout=300):
    req = urllib.request.Request(f"{OLLAMA}/api/generate", method="POST",
        data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["response"]

def sh(cmd):
    try:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15).stdout.strip()
    except Exception:
        return ""

def log_activity(kind, detail="", conn=None):
    """Append one row to the activity feed. Never raises — logging must not break the action.
    Pass conn to reuse a connection that already holds the write lock (caller commits)."""
    try:
        c = conn or db()
        c.execute("INSERT INTO activity(ts,kind,detail) VALUES(?,?,?)",
                  (datetime.datetime.now().isoformat(timespec="seconds"), kind, (detail or "")[:300]))
        if conn is None:
            c.commit(); c.close()
    except Exception:
        pass

def ollama_loaded():
    """Names of models currently loaded in ollama memory (via /api/ps)."""
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/ps", timeout=3) as r:
            return [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return None  # ollama unreachable

# ---------- status / toolbox ----------
@app.get("/api/status")
def status():
    models = []
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=3) as r:
            models = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        pass
    skills_dir = Path.home() / ".claude" / "skills"
    skills = sorted([p.name for p in skills_dir.iterdir() if (p / "SKILL.md").exists()
                     or (p.is_symlink() and p.exists())]) if skills_dir.exists() else []
    cron = sh("crontab -l 2>/dev/null | grep -v '^#'")
    briefs = sorted((ROOT / "data" / "briefs").glob("*.md"), reverse=True)
    return {"ollama_models": models, "skills": skills, "cron": cron.splitlines(),
            "latest_brief": briefs[0].name if briefs else None,
            "ollama_loaded": ollama_loaded(),
            "links": {"Agent Deck": "http://localhost:8444", "File Graph": "http://localhost:8437"}}

@app.get("/api/vitals")
def vitals():
    """System vitals — no psutil: os.getloadavg + vm_stat + shutil.disk_usage."""
    load1, load5, load15 = os.getloadavg()
    ncpu = os.cpu_count() or 1
    vm = sh("/usr/bin/vm_stat")
    page = 16384
    m = re.search(r"page size of (\d+)", vm)
    if m:
        page = int(m.group(1))
    pages = {}
    for line in vm.splitlines():
        k, _, v = line.partition(":")
        v = v.strip().rstrip(".")
        if v.isdigit():
            pages[k.strip()] = int(v)
    mem_used = (pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
                + pages.get("Pages occupied by compressor", 0)) * page
    mem_total = int(sh("sysctl -n hw.memsize") or 0)
    du = shutil.disk_usage("/")
    up = re.search(r"up\s+(.*?),\s+\d+ users?", sh("uptime"))
    return {"cpu": {"load1": round(load1, 2), "load5": round(load5, 2),
                    "load15": round(load15, 2), "cores": ncpu,
                    "pct": min(100, round(load1 / ncpu * 100))},
            "mem": {"used": mem_used, "total": mem_total,
                    "pct": round(mem_used / mem_total * 100) if mem_total else 0},
            "disk": {"used": du.used, "total": du.total,
                     "pct": round(du.used / du.total * 100)},
            "uptime": up.group(1) if up else "",
            "ollama_loaded": ollama_loaded()}

@app.get("/api/activity")
def activity(limit: int = 40):
    c = db()
    rows = [dict(r) for r in c.execute("SELECT * FROM activity ORDER BY id DESC LIMIT ?",
                                       (max(1, min(limit, 200)),))]
    c.close()
    return rows

@app.get("/api/search")
def search(q: str = ""):
    q = q.strip()
    if len(q) < 2:
        return {"q": q, "results": []}
    like = f"%{q}%"
    results = []
    c = db()
    for r in c.execute("""SELECT id,uploader,caption,topic,verdict FROM reels
        WHERE uploader LIKE ? OR caption LIKE ? OR transcript LIKE ? OR topic LIKE ? LIMIT 8""", (like,) * 4):
        results.append({"type": "reel", "view": "reels", "title": f"@{r['uploader']} · {r['topic']}",
                        "detail": (r["caption"] or "").replace("\n", " ")[:110], "id": r["id"]})
    for r in c.execute("SELECT id,text,done,urgent FROM goals WHERE text LIKE ? ORDER BY done, id DESC LIMIT 8", (like,)):
        tag = "done" if r["done"] else ("urgent" if r["urgent"] else "open")
        results.append({"type": "goal", "view": "life", "title": r["text"], "detail": f"goal · {tag}"})
    for r in c.execute("SELECT id,name,steps FROM flows WHERE name LIKE ? OR steps LIKE ? LIMIT 5", (like, like)):
        results.append({"type": "flow", "view": "flows", "title": r["name"],
                        "detail": f"flow · {len(json.loads(r['steps']))} steps"})
    for r in c.execute("SELECT name,monthly FROM subscriptions WHERE name LIKE ? LIMIT 5", (like,)):
        results.append({"type": "subscription", "view": "life", "title": r["name"],
                        "detail": f"subscription · ${r['monthly'] or 0:.2f}/mo"})
    for r in c.execute("SELECT ts,kind,detail FROM activity WHERE detail LIKE ? OR kind LIKE ? ORDER BY id DESC LIMIT 5", (like, like)):
        results.append({"type": "activity", "view": "home", "title": r["detail"] or r["kind"],
                        "detail": f"activity · {r['kind']} · {r['ts'].replace('T', ' ')}"})
    c.close()
    ql = q.lower()
    for f in sorted((ROOT / "data" / "briefs").glob("*.md"), reverse=True)[:30]:
        try:
            text = f.read_text()
        except Exception:
            continue
        i = text.lower().find(ql)
        if i >= 0 or ql in f.stem.lower():
            snip = text[max(0, i - 40):i + 70].replace("\n", " ").strip() if i >= 0 else ""
            results.append({"type": "brief", "view": "briefs", "title": f"Brief {f.stem}", "detail": snip[:110]})
            if sum(1 for x in results if x["type"] == "brief") >= 4:
                break
    return {"q": q, "results": results[:30]}

# ---------- chat: talks through your actual CLIs (claude / codex / local ollama via claude cli) ----------
CHAT_SYSTEM = ("You are the assistant living inside Nate's Mission Control dashboard — a local, "
    "no-cloud command center for his goals, reels, briefs, and agent runs. Be direct, concise, "
    "and a little warm. No markdown headers, keep replies conversational unless code is requested.")
CHAT_CWD = ROOT / "sandbox"

def _clean_cli_output(text):
    lines = [l for l in text.splitlines() if "claude.ai connectors are disabled" not in l]
    text = "\n".join(lines).strip()
    if text.lower().startswith("assistant"):
        text = text[len("assistant"):].lstrip("\n: ").lstrip()
    return text.strip()

@app.post("/api/chat")
def chat(payload: dict = Body(...)):
    history = payload.get("messages", [])
    engine = payload.get("engine") or "local"
    model = payload.get("model") or (BRIEF_MODEL if engine == "local" else "default")
    if not history:
        return JSONResponse({"error": "no messages"}, status_code=400)
    convo = "\n\n".join(f"{'You' if m['role']=='user' else 'Assistant'}: {m['content']}" for m in history[:-1])
    prompt = CHAT_SYSTEM + (f"\n\nConversation so far:\n{convo}" if convo else "") + \
        f"\n\nYou: {history[-1]['content']}\nAssistant:"
    env = os.environ.copy()
    env["PATH"] = f"{Path.home()}/.npm-global/bin:{Path.home()}/.local/bin:/opt/homebrew/bin:" + env.get("PATH", "")
    cmd = _flow_cmd(engine, model, prompt, env)
    CHAT_CWD.mkdir(exist_ok=True)
    try:
        r = subprocess.run(cmd, cwd=CHAT_CWD, capture_output=True, text=True, timeout=180,
                           env=env, stdin=subprocess.DEVNULL)
        out = _clean_cli_output(r.stdout or "") or _clean_cli_output(r.stderr or "")
        return {"message": out or "(no response)"}
    except subprocess.TimeoutExpired:
        return JSONResponse({"message": f"{engine} timed out after 180s"}, status_code=504)
    except Exception as e:
        return JSONResponse({"message": f"error running {engine}: {e}"}, status_code=503)

# ---------- reel vault ----------
@app.get("/api/reels")
def reels():
    c = db(); rows = [dict(r) for r in c.execute("SELECT * FROM reels ORDER BY added DESC, id")]; c.close()
    return rows

@app.post("/api/reels/add")
def reels_add(payload: dict = Body(...)):
    urls = payload.get("urls", [])
    def run():
        subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/add_reels.py"), *urls])
    threading.Thread(target=run, daemon=True).start()
    log_activity("reel", f"queued {len(urls)} reel(s) for ingest")
    return {"queued": len(urls)}

@app.post("/api/reels/update")
def reels_update(payload: dict = Body(...)):
    reel_id = payload.get("id")
    if not reel_id:
        return {"ok": False, "error": "missing id"}
    c = db()
    c.execute("UPDATE reels SET topic=?, verdict=?, notes=? WHERE id=?",
              (payload.get("topic"), payload.get("verdict"), payload.get("notes"), reel_id))
    c.commit(); c.close()
    log_activity("reel", f"tagged reel {reel_id} → {payload.get('topic')}/{payload.get('verdict')}")
    return {"ok": True}

# ---------- life hq ----------
@app.get("/api/lifehq")
def lifehq():
    c = db()
    out = {
      "goals": [dict(r) for r in c.execute("SELECT * FROM goals WHERE done=0 ORDER BY urgent DESC, id")],
      "done_today": [dict(r) for r in c.execute("SELECT * FROM goals WHERE done=1 AND completed=?",
                     (str(datetime.date.today()),))],
      "subscriptions": [dict(r) for r in c.execute("SELECT * FROM subscriptions ORDER BY monthly DESC")],
      "networth": [dict(r) for r in c.execute("SELECT * FROM networth ORDER BY date")],
      "checkin": next((dict(r) for r in c.execute("SELECT * FROM checkins WHERE date=?",
                     (str(datetime.date.today()),))), None),
    }
    c.close(); return out

@app.post("/api/lifehq/{table}")
def lifehq_add(table: str, payload: dict = Body(...)):
    c = db(); today = str(datetime.date.today())
    if table == "goal":
        c.execute("INSERT INTO goals(text,urgent,created) VALUES(?,?,?)",
                  (payload["text"], int(payload.get("urgent", 0)), today))
        log_activity("goal", f"added goal: {payload['text']}", conn=c)
    elif table == "goal_done":
        c.execute("UPDATE goals SET done=1, completed=? WHERE id=?", (today, payload["id"]))
        done = c.execute("SELECT text FROM goals WHERE id=?", (payload["id"],)).fetchone()
        log_activity("goal", f"completed goal: {done['text'] if done else payload['id']}", conn=c)
    elif table == "goal_delete":
        c.execute("DELETE FROM goals WHERE id=?", (payload["id"],))
    elif table == "subscription":
        c.execute("INSERT INTO subscriptions(name,monthly,note) VALUES(?,?,?)",
                  (payload["name"], float(payload["monthly"]), payload.get("note", "")))
    elif table == "subscription_delete":
        c.execute("DELETE FROM subscriptions WHERE id=?", (payload["id"],))
    elif table == "networth":
        c.execute("INSERT INTO networth(date,assets,liabilities,note) VALUES(?,?,?,?)",
                  (today, float(payload["assets"]), float(payload["liabilities"]), payload.get("note", "")))
    elif table == "checkin":
        score = round((int(payload["energy"]) + int(payload["focus"]) + int(payload["mood"])) / 3 * 10)
        c.execute("INSERT OR REPLACE INTO checkins(date,energy,focus,mood,note,score) VALUES(?,?,?,?,?,?)",
                  (today, payload["energy"], payload["focus"], payload["mood"], payload.get("note", ""), score))
        log_activity("checkin", f"daily check-in logged — score {score}", conn=c)
    c.commit(); c.close()
    if table == "networth":  # amounts stay out of the feed on purpose
        log_activity("networth", "net worth snapshot recorded")
    return {"ok": True}

@app.post("/api/overseer")
def overseer():
    c = db()
    goals = [dict(r) for r in c.execute("SELECT text,urgent,created FROM goals WHERE done=0")]
    done = [dict(r) for r in c.execute("SELECT text FROM goals WHERE done=1 ORDER BY id DESC LIMIT 10")]
    checkin = next((dict(r) for r in c.execute("SELECT * FROM checkins ORDER BY date DESC LIMIT 1")), {})
    c.close()
    prompt = f"""You are The Overseer — Nate's blunt but supportive accountability AI. Today is {datetime.date.today()}.
Open goals (with created dates): {json.dumps(goals)}
Recently completed: {json.dumps(done)}
Latest check-in (energy/focus/mood 1-10): {json.dumps(checkin)}
In under 120 words: call out anything slipping (old goals, low scores), acknowledge real wins, and name the ONE thing to do next. Direct, human, no fluff, no markdown headers."""
    try:
        return {"message": ollama_gen(prompt).strip()}
    except Exception as e:
        return JSONResponse({"message": f"Overseer offline (is ollama running?): {e}"}, status_code=503)

# ---------- briefs ----------
@app.get("/api/briefs")
def briefs():
    files = sorted((ROOT / "data" / "briefs").glob("*.md"), reverse=True)[:14]
    return [{"name": f.stem, "content": f.read_text()} for f in files]

@app.post("/api/briefs/generate")
def brief_now():
    r = subprocess.run([str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/morning_brief.py")],
                       capture_output=True, text=True, timeout=600)
    log_activity("brief", "morning brief generated" if r.returncode == 0 else "brief generation failed")
    return {"ok": r.returncode == 0, "log": (r.stdout + r.stderr)[-500:]}

# ---------- terminal: background agent runs (claude / codex / local) ----------
TERM_DIR = ROOT / "data" / "term"
TERM_DIR.mkdir(exist_ok=True)
GUI_SNAPSHOT = TERM_DIR / "gui_snapshot.json"
JOBS = {}  # id -> {proc, meta}
MAX_FINISHED_JOBS = 200  # cap so a long-running server doesn't accumulate finished jobs forever

def _prune_jobs():
    finished = [jid for jid, j in JOBS.items() if j["meta"]["status"] != "running"]
    if len(finished) <= MAX_FINISHED_JOBS:
        return
    finished.sort(key=lambda jid: JOBS[jid]["meta"].get("started", ""))
    for jid in finished[:len(finished) - MAX_FINISHED_JOBS]:
        del JOBS[jid]

CLAUDE_MODELS = ["default", "opus", "sonnet", "haiku"]

def _watch(jid):
    j = JOBS[jid]
    j["proc"].wait()
    j["meta"]["status"] = "done" if j["proc"].returncode == 0 else f"exit {j['proc'].returncode}"
    j["meta"]["ended"] = datetime.datetime.now().strftime("%H:%M:%S")
    _prune_jobs()

# ---------- reel-derived tools dashboard ----------
TOOLS_DIR = ROOT / "reels-build"
TOOLS_MANIFEST_FILE = TOOLS_DIR / "tools_manifest.json"

def _load_tools_manifest():
    try:
        return json.loads(TOOLS_MANIFEST_FILE.read_text())
    except Exception:
        return []

@app.get("/api/tools")
def tools_list():
    return _load_tools_manifest()

COMPARE_FILE = ROOT / "data" / "compare.json"

@app.get("/api/compare")
def compare_list():
    try:
        return json.loads(COMPARE_FILE.read_text())
    except Exception:
        return []

@app.post("/api/tools/{tool_id}/run")
def tools_run(tool_id: str, payload: dict = Body(...)):
    tool = next((t for t in _load_tools_manifest() if t["id"] == tool_id), None)
    if not tool:
        return JSONResponse({"error": "unknown tool"}, status_code=404)
    tool_dir = TOOLS_DIR / tool_id
    script = tool_dir / tool["script"]
    if not script.exists():
        return JSONResponse({"error": "script missing"}, status_code=404)
    args = (payload.get("args") or "").strip()
    cmd = ["python3", tool["script"]] + (args.split() if args else [])
    jid = datetime.datetime.now().strftime("%H%M%S") + "tl"
    log = open(TERM_DIR / f"{jid}.log", "w")
    env = os.environ.copy()
    env["PATH"] = f"{Path.home()}/.npm-global/bin:{Path.home()}/.local/bin:/opt/homebrew/bin:" + env.get("PATH", "")
    proc = subprocess.Popen(cmd, cwd=tool_dir, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=env)
    JOBS[jid] = {"proc": proc, "meta": {"id": jid, "engine": "tool", "model": tool["name"],
        "prompt": f"{tool['name']}: {args[:100]}", "cwd": str(tool_dir), "status": "running",
        "started": datetime.datetime.now().strftime("%H:%M:%S")}}
    threading.Thread(target=_watch, args=(jid,), daemon=True).start()
    log_activity("tool", f"ran tool {tool['name']} ({tool_id}) args={args[:120]}")
    return {"id": jid}

# ---------- learning mode ----------
LEARN_RESOURCES_FILE = TOOLS_DIR / "Daa8fy8PKC1" / "resources.json"
LEARN_CACHE_DIR = ROOT / "data" / "learn"
LEARN_CACHE_DIR.mkdir(exist_ok=True)

def _curated_resources_for(subject):
    try:
        items = json.loads(LEARN_RESOURCES_FILE.read_text())
    except Exception:
        items = []
    words = [w.lower() for w in subject.split() if len(w) > 2]
    matches = []
    for r in items:
        hay = f"{r['name']} {r['note']} {r['category']}".lower()
        if any(w in hay for w in words):
            matches.append(r)
    return matches[:6]

@app.post("/api/learn/plan")
def learn_plan(payload: dict = Body(...)):
    subject = (payload.get("subject") or "").strip()
    if not subject:
        return JSONResponse({"error": "need a subject"}, status_code=400)

    cache_key = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:60]
    cache_file = LEARN_CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists() and not payload.get("regenerate"):
        cached = json.loads(cache_file.read_text())
        cached["from_cache"] = True
        return cached

    prompt = f"""You are building a short local study plan for the subject: "{subject}".
Reply with ONLY valid JSON, no markdown fences, matching this exact shape:
{{
  "overview": "2-3 sentence plain-language overview of the subject",
  "topics": [{{"title": "...", "why": "one sentence on why this matters, in order from foundational to advanced"}}],
  "quiz": [{{"question": "...", "options": ["...","...","...","..."], "answer_index": 0, "explanation": "one sentence"}}]
}}
Give 4-6 topics and exactly 5 quiz questions, multiple choice with 4 options each, answer_index is 0-based.
Keep everything factually accurate and concise. No preamble, no markdown, JSON only."""

    try:
        raw = ollama_gen(prompt, model=BRIEF_MODEL, timeout=180)
        start, end = raw.find("{"), raw.rfind("}")
        plan = json.loads(raw[start:end + 1])
    except Exception as e:
        return JSONResponse({"error": f"local model generation failed: {e}"}, status_code=502)

    plan["subject"] = subject
    plan["curated_resources"] = _curated_resources_for(subject)
    plan["search_links"] = {
        "YouTube": f"https://www.youtube.com/results?search_query={urllib.parse.quote(subject + ' course')}",
        "freeCodeCamp": f"https://www.freecodecamp.org/news/search/?query={urllib.parse.quote(subject)}",
    }
    plan["generated"] = datetime.datetime.now().isoformat(timespec="seconds")
    plan["from_cache"] = False
    cache_file.write_text(json.dumps(plan, indent=2))
    log_activity("learn", f"generated study plan for '{subject}'")
    return plan

@app.get("/api/learn/history")
def learn_history():
    out = []
    for f in sorted(LEARN_CACHE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(f.read_text())
            out.append({"subject": d.get("subject"), "generated": d.get("generated"), "key": f.stem})
        except Exception:
            continue
    return out[:20]

@app.get("/api/term/options")
def term_options():
    local = []
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=3) as r:
            local = [m["name"] for m in json.loads(r.read()).get("models", [])]
    except Exception:
        pass
    return {"claude": CLAUDE_MODELS, "codex": ["default"], "local": local}

def _run_text(cmd, timeout=6, input_text=None):
    try:
        return subprocess.run(cmd, input=input_text, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()
    except Exception:
        return ""

def _osascript(script, timeout=8):
    return _run_text(["osascript", "-"], timeout=timeout, input_text=script)

def _domain(url):
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""

def _tab_category(title, url):
    text = f"{title} {url}".lower()
    if any(x in text for x in ("claude.ai", "chatgpt", "gemini.google", "aistudio.google",
                               "perplexity", "plaud", "nuwa", "xnote",
                               "flowtica", "rokid", "halliday", "brilliant.xyz",
                               "bee.computer", "notis.io", "meta.com/ai-glasses")):
        return "AI/tools"
    if any(x in text for x in ("github.com", "docs.google", "atlassian.net", "mail.google",
                               "calendar.google", "linkedin.com")):
        return "work/admin"
    if any(x in text for x in ("bmw", "e46", "m3", "ecs tuning", "ecstuning",
                               "fcpeuro", "garagistic", "racegerman", "turnermotorsport",
                               "ebay.com", "speedzone")):
        return "cars/parts"
    if any(x in text for x in ("zillow", "instagram", "facebook", "spotify")):
        return "personal"
    return "other"

def _browser_tabs_for(app_name):
    script = f'''
set output to ""
set sep to ASCII character 9
try
  tell application "{app_name}"
    repeat with w in windows
      repeat with t in tabs of w
        set output to output & "{app_name}" & sep & title of t & sep & URL of t & linefeed
      end repeat
    end repeat
  end tell
end try
return output
'''
    rows = []
    for line in _osascript(script, timeout=10).splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        browser, title, url = parts
        rows.append({"browser": browser, "title": title, "url": url,
                     "domain": _domain(url), "category": _tab_category(title, url)})
    return rows

def _browser_tabs():
    tabs = []
    for app_name in ("Arc", "Google Chrome"):
        tabs.extend(_browser_tabs_for(app_name))
    return tabs

def _task_from_terminal_title(title, processes):
    parts = re.split(r"\s+—\s+", title)
    task = ""
    for p in parts:
        p = p.strip()
        if p.startswith("✳"):
            task = p.lstrip("✳").strip()
            break
    if not task and "codex" in processes.lower():
        task = "Codex session"
    if not task and "claude" in processes.lower():
        task = "Claude Code session"
    if not task:
        task = "Shell"
    return task

def _terminal_tabs():
    script = '''
set output to ""
set sep to ASCII character 9
try
  tell application "Terminal"
    set oldDelims to AppleScript's text item delimiters
    set AppleScript's text item delimiters to ", "
    repeat with w in windows
      set windowName to name of w
      repeat with t in tabs of w
        try
          set ttyName to tty of t
        on error
          set ttyName to ""
        end try
        try
          set procList to processes of t as text
        on error
          set procList to ""
        end try
        try
          set busyText to busy of t as text
        on error
          set busyText to "false"
        end try
        set output to output & windowName & sep & ttyName & sep & busyText & sep & procList & linefeed
      end repeat
    end repeat
    set AppleScript's text item delimiters to oldDelims
  end tell
end try
return output
'''
    rows = []
    for line in _osascript(script).splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        title, tty, busy, processes = parts
        pl = processes.lower()
        engine = "Codex" if "codex" in pl else "Claude" if "claude" in pl else "Shell"
        status = "busy" if busy.lower() == "true" else "idle"
        task = _task_from_terminal_title(title, processes)
        rows.append({"title": title, "tty": tty, "status": status, "engine": engine,
                     "task": task, "processes": processes})
    return rows

def _cli_processes():
    out = _run_text(["ps", "-axo", "pid,ppid,tty,stat,etime,pcpu,pmem,args"], timeout=6)
    keep = re.compile(r"(claude(\.exe)?|codex|desktop-commander|filegraph|markitdown-mcp|"
                      r"uvicorn|node server\.js|ollama serve)", re.I)
    rows = []
    for line in out.splitlines()[1:]:
        if not keep.search(line):
            continue
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        pid, ppid, tty, stat, etime, cpu, mem, args = parts
        rows.append({"pid": pid, "ppid": ppid, "tty": tty, "stat": stat,
                     "etime": etime, "cpu": cpu, "mem": mem, "args": args[:260]})
    return rows[:80]

def _local_services():
    out = sh("lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null")
    services = []
    port_names = {"8437": "FileGraph", "8444": "Agent Deck", "8450": "Mission Control",
                  "11434": "Ollama API", "52509": "Ollama app", "42050": "OneDrive",
                  "5000": "Control Center", "7000": "Control Center", "65014": "rapportd"}
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        name, pid, user = parts[0], parts[1], parts[2]
        target = parts[-2] if parts[-1] == "(LISTEN)" else parts[-1]
        m = re.search(r":(\d+)$", target)
        port = m.group(1) if m else ""
        services.append({"name": port_names.get(port, name), "command": name, "pid": pid,
                         "user": user, "target": target, "port": port,
                         "url": f"http://127.0.0.1:{port}" if port else ""})
    return services

def _load_gui_snapshot():
    if not GUI_SNAPSHOT.exists():
        return {}
    try:
        return json.loads(GUI_SNAPSHOT.read_text())
    except Exception:
        return {}

@app.get("/api/term/snapshot")
def term_snapshot():
    services = _local_services()
    ports = {s["port"] for s in services}
    tracked = [{"name": "Mission Control", "port": "8450", "status": "online" if "8450" in ports else "offline"},
               {"name": "Agent Deck", "port": "8444", "status": "online" if "8444" in ports else "offline"},
               {"name": "FileGraph", "port": "8437", "status": "online" if "8437" in ports else "offline"},
               {"name": "Ollama", "port": "11434", "status": "online" if "11434" in ports else "offline"}]
    gui = _load_gui_snapshot()
    terminal_tabs = _terminal_tabs() or gui.get("terminal_tabs", [])
    browser_tabs = _browser_tabs() or gui.get("browser_tabs", [])
    snapshot = {"generated": datetime.datetime.now().isoformat(timespec="seconds"),
                "gui_generated": gui.get("generated"), "terminal_tabs": terminal_tabs,
                "cli_processes": _cli_processes(),
                "services": services, "tracked_apps": tracked,
                "browser_tabs": browser_tabs}
    try:
        (TERM_DIR / "session_snapshot.json").write_text(json.dumps(snapshot, indent=2))
    except Exception:
        pass
    return snapshot

@app.post("/api/term/run")
def term_run(payload: dict = Body(...)):
    engine = payload.get("engine", "claude")
    model = payload.get("model", "default")
    prompt = payload.get("prompt", "").strip()
    cwd = os.path.expanduser(payload.get("cwd") or "~/Projects")
    if not prompt or not os.path.isdir(cwd):
        return JSONResponse({"error": "need a prompt and a valid folder"}, status_code=400)
    env = os.environ.copy()
    if engine == "claude":
        cmd = ["claude", "-p", prompt, "--permission-mode", "acceptEdits", "--verbose"]
        if model != "default":
            cmd += ["--model", model]
    elif engine == "local":
        env.update({"ANTHROPIC_BASE_URL": OLLAMA, "ANTHROPIC_AUTH_TOKEN": "ollama"})
        cmd = ["claude", "-p", prompt, "--permission-mode", "acceptEdits", "--model", model]
    elif engine == "codex":
        cmd = ["codex", "exec", "--sandbox", "workspace-write"]
        if model != "default":
            cmd += ["-m", model]
        cmd += [prompt]
    elif engine == "shell":
        # Not general-purpose exec: the Workflows test panel is the only caller,
        # and it only ever sends one of these four fixed commands. Anyone who can
        # reach this endpoint (e.g. a malicious page in a browser tab, since this
        # server has no auth) would otherwise get unauthenticated arbitrary shell
        # execution as this user.
        allowed_shell_prompts = {
            "python3 ~/scripts/repomap.py ~/Projects/mission-control",
            "python3 ~/scripts/web-search.py 'Agentic AI'",
            "python3 ~/scripts/web-scrape.py https://example.com",
            "tail -n 20 ~/scripts/clap_detector.out",
        }
        if prompt not in allowed_shell_prompts:
            return JSONResponse({"error": "shell engine only allows the fixed Workflows test commands"}, status_code=403)
        cmd = ["bash", "-c", prompt]
    else:
        return JSONResponse({"error": "unknown engine"}, status_code=400)
    jid = datetime.datetime.now().strftime("%H%M%S") + engine[:2]
    log = open(TERM_DIR / f"{jid}.log", "w")
    env["PATH"] = f"{Path.home()}/.npm-global/bin:{Path.home()}/.local/bin:/opt/homebrew/bin:" + env.get("PATH", "")
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=env)
    JOBS[jid] = {"proc": proc, "meta": {"id": jid, "engine": engine, "model": model,
        "prompt": prompt[:160], "cwd": cwd, "status": "running",
        "started": datetime.datetime.now().strftime("%H:%M:%S")}}
    threading.Thread(target=_watch, args=(jid,), daemon=True).start()
    log_activity("term", f"launched {engine} job {jid}: {prompt[:120]}")
    return {"id": jid}

@app.get("/api/term/jobs")
def term_jobs():
    return [j["meta"] for j in list(JOBS.values())][::-1]

@app.get("/api/term/out/{jid}")
def term_out(jid: str, off: int = 0):
    f = TERM_DIR / f"{jid}.log"
    if not f.exists():
        return {"text": "", "off": 0, "status": "unknown"}
    data = f.read_bytes()
    meta = JOBS.get(jid, {}).get("meta", {"status": "done"})
    return {"text": data[off:].decode(errors="replace"), "off": len(data),
            "status": meta["status"]}

@app.post("/api/term/stop")
def term_stop(payload: dict = Body(...)):
    j = JOBS.get(payload.get("id"))
    if j and j["proc"].poll() is None:
        j["proc"].terminate()
        j["meta"]["status"] = "stopped"
    return {"ok": True}

# ---------- swarm: plan → route → parallel workers → shared memory → synthesis ----------
SWARM_DIR = ROOT / "data" / "swarm"
SWARM_DIR.mkdir(exist_ok=True)
SWARMS = {}  # rid -> {goal, cwd, plan, jobs: [jid], status}

def _load_swarms_from_disk():
    for d in sorted(SWARM_DIR.iterdir()):
        mf = d / "meta.json"
        if not d.is_dir() or not mf.exists() or d.name in SWARMS:
            continue
        try:
            m = json.loads(mf.read_text())
        except Exception:
            continue
        m["jobs"] = []
        m["status"] = "done" if (d / "result.md").exists() else "interrupted"
        SWARMS[m["id"]] = m

ROUTE = {"simple":  ("claude", "haiku"),
         "medium":  ("claude", "haiku"),
         "complex": ("claude", "default")}

def _swarm_plan(goal):
    prompt = (f'Decompose this goal into 2-4 independent subtasks for parallel AI workers. '
              f'Each subtask: short title, a self-contained prompt for the worker, and complexity '
              f'(simple=mechanical, medium=standard coding/writing, complex=needs deep reasoning).\n'
              f'GOAL: {goal}\nReply JSON: {{"subtasks":[{{"title":"...","prompt":"...","complexity":"simple|medium|complex"}}]}}')
    try:
        req = urllib.request.Request(f"{OLLAMA}/api/generate", method="POST",
            data=json.dumps({"model": "llama3.2", "prompt": prompt, "stream": False,
                             "format": "json"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            subs = json.loads(json.loads(r.read())["response"]).get("subtasks", [])
            subs = [s for s in subs if s.get("prompt")][:4]
            if subs:
                return subs
    except Exception:
        pass
    return [{"title": "Task", "prompt": goal, "complexity": "medium"}]

def _spawn_worker(rid, idx, sub, cwd, mem_path):
    engine, model = ROUTE.get(sub.get("complexity", "medium"), ROUTE["medium"])
    wprompt = (f"You are worker {idx+1} in a swarm working toward: {SWARMS[rid]['goal']}\n"
               f"YOUR SUBTASK: {sub['prompt']}\n"
               f"Shared memory file: {mem_path} — read it first for context from other workers; "
               f"when finished, APPEND a section '## Worker {idx+1}: {sub['title']}' summarizing "
               f"what you did and key findings. Keep it under 200 words.")
    env = os.environ.copy()
    env["PATH"] = f"{Path.home()}/.npm-global/bin:{Path.home()}/.local/bin:/opt/homebrew/bin:" + env.get("PATH", "")
    if engine == "local":
        env.update({"ANTHROPIC_BASE_URL": OLLAMA, "ANTHROPIC_AUTH_TOKEN": "ollama"})
        cmd = ["claude", "-p", wprompt, "--permission-mode", "acceptEdits", "--model", model]
    else:
        cmd = ["claude", "-p", wprompt, "--permission-mode", "acceptEdits"]
        if model != "default":
            cmd += ["--model", model]
    jid = f"{rid}w{idx+1}"
    log = open(TERM_DIR / f"{jid}.log", "w")
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, env=env)
    JOBS[jid] = {"proc": proc, "meta": {"id": jid, "engine": engine, "model": model,
        "prompt": sub["title"], "cwd": cwd, "status": "running",
        "started": datetime.datetime.now().strftime("%H:%M:%S")}}
    threading.Thread(target=_watch, args=(jid,), daemon=True).start()
    return jid

def _swarm_finish(rid):
    s = SWARMS[rid]
    for jid in s["jobs"]:
        JOBS[jid]["proc"].wait()
        JOBS[jid]["meta"].setdefault("ended", datetime.datetime.now().strftime("%H:%M:%S"))
    mem = (SWARM_DIR / rid / "memory.md").read_text()
    try:
        summary = ollama_gen(f"Synthesize this swarm run into a short result report (what was accomplished, "
                             f"key findings, anything unresolved). Under 200 words, markdown.\n\n{mem[:6000]}",
                             model="qwen2.5-coder:32b")
    except Exception as e:
        summary = f"(synthesis unavailable: {e})"
    (SWARM_DIR / rid / "result.md").write_text(summary)
    s["status"] = "done"
    mf = SWARM_DIR / rid / "meta.json"
    if mf.exists():
        m = json.loads(mf.read_text()); m["status"] = "done"
        mf.write_text(json.dumps(m))

@app.post("/api/swarm/run")
def swarm_run(payload: dict = Body(...)):
    goal = payload.get("goal", "").strip()
    cwd = os.path.expanduser(payload.get("cwd") or "~/Projects/mission-control/sandbox")
    if not goal or not os.path.isdir(cwd):
        return JSONResponse({"error": "need a goal and valid folder"}, status_code=400)
    rid = "s" + datetime.datetime.now().strftime("%H%M%S")
    (SWARM_DIR / rid).mkdir(exist_ok=True)
    plan = _swarm_plan(goal)
    mem_path = SWARM_DIR / rid / "memory.md"
    mem_path.write_text(f"# Swarm Memory — {rid}\nGOAL: {goal}\n\nPLAN:\n" +
        "\n".join(f"- [{s['complexity']}] {s['title']}" for s in plan) + "\n\n---\n")
    SWARMS[rid] = {"id": rid, "goal": goal, "cwd": cwd, "plan": plan, "jobs": [],
                   "status": "running", "started": datetime.datetime.now().strftime("%H:%M:%S")}
    SWARMS[rid]["jobs"] = [_spawn_worker(rid, i, s, cwd, mem_path) for i, s in enumerate(plan)]
    (SWARM_DIR / rid / "meta.json").write_text(json.dumps(
        {k: SWARMS[rid][k] for k in ("id", "goal", "cwd", "plan", "started")}))
    threading.Thread(target=_swarm_finish, args=(rid,), daemon=True).start()
    log_activity("swarm", f"swarm {rid} launched ({len(plan)} workers): {goal[:120]}")
    return {"id": rid, "plan": plan}

@app.get("/api/swarm/runs")
def swarm_runs():
    _load_swarms_from_disk()
    return [{"id": s["id"], "goal": s["goal"][:120], "status": s["status"],
             "started": s["started"], "workers": len(s["jobs"])} for s in list(SWARMS.values())][::-1]

@app.get("/api/swarm/{rid}")
def swarm_detail(rid: str):
    _load_swarms_from_disk()
    s = SWARMS.get(rid)
    if not s:
        return JSONResponse({"error": "unknown run"}, status_code=404)
    mem = (SWARM_DIR / rid / "memory.md")
    res = (SWARM_DIR / rid / "result.md")
    return {"id": rid, "goal": s["goal"], "status": s["status"], "plan": s["plan"],
            "workers": [JOBS[j]["meta"] for j in s["jobs"] if j in JOBS],
            "memory": mem.read_text() if mem.exists() else "",
            "result": res.read_text() if res.exists() else ""}

# ---------- flows: saved agent chains — each step's output feeds the next ----------
FLOW_DIR = ROOT / "data" / "flows"
FLOW_DIR.mkdir(exist_ok=True)
FLOW_RUNS = {}  # rid -> {id, flow_id, flow_name, input, cwd, steps:[{name,status,output}], status, current_step, started, result}

def _plan_flow_steps(goal):
    prompt = ('Design a sequential pipeline of 2-4 agent steps to accomplish this goal. Each step builds on '
              'the previous step\'s output. For each step give: a short name, an engine — "claude" (capable '
              'general reasoning), "local" (free/fast, good for simple mechanical work), or "codex" (code-focused) '
              '— and a prompt. Step 1\'s prompt must reference {goal}; every later step\'s prompt must reference '
              '{input} (the previous step\'s output).\n'
              f'GOAL: {goal}\n'
              'Reply JSON: {"steps":[{"name":"...","engine":"claude|local|codex","prompt":"..."}]}')
    try:
        req = urllib.request.Request(f"{OLLAMA}/api/generate", method="POST",
            data=json.dumps({"model": "llama3.2", "prompt": prompt, "stream": False, "format": "json"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            steps = json.loads(json.loads(r.read())["response"]).get("steps", [])
            steps = [s for s in steps if s.get("prompt")][:5]
            for s in steps:
                s["engine"] = s.get("engine") if s.get("engine") in ("claude", "local", "codex") else "claude"
                s["model"] = BRIEF_MODEL if s["engine"] == "local" else "default"
                s.setdefault("name", "Step")
            if steps:
                return steps
    except Exception:
        pass
    return [{"name": "Step 1", "engine": "claude", "model": "default", "prompt": "{goal}"}]

@app.post("/api/flows/plan")
def flows_plan(payload: dict = Body(...)):
    goal = payload.get("goal", "").strip()
    if not goal:
        return JSONResponse({"error": "need a goal"}, status_code=400)
    return {"name": goal[:60], "steps": _plan_flow_steps(goal)}

def _load_flow_runs_from_disk():
    for d in sorted(FLOW_DIR.iterdir()):
        mf = d / "meta.json"
        if not d.is_dir() or not mf.exists() or d.name in FLOW_RUNS:
            continue
        try:
            FLOW_RUNS[d.name] = json.loads(mf.read_text())
        except Exception:
            continue

@app.get("/api/filegraph/relations")
def get_filegraph_relations():
    db_path = Path.home() / ".filegraph" / "filegraph.db"
    if not db_path.exists():
        return {"nodes": [], "links": []}
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    nodes = {}
    links = []
    # Fetch relations
    for r in c.execute("SELECT source_id, target_id, kind FROM relations LIMIT 1000"):
        links.append({"source": str(r["source_id"]), "target": str(r["target_id"]), "type": r["kind"]})
        nodes[r["source_id"]] = True
        nodes[r["target_id"]] = True
    
    node_list = []
    if nodes:
        ids = list(nodes.keys())
        placeholders = ",".join("?" for _ in ids)
        for r in c.execute(f"SELECT id, path, name, kind FROM files WHERE id IN ({placeholders})", ids):
            node_list.append({"id": str(r["id"]), "name": r["name"], "path": r["path"], "group": r["kind"]})
    c.close()
    return {"nodes": node_list, "links": links}

def _save_flow_run(rid):
    d = FLOW_DIR / rid
    d.mkdir(exist_ok=True)
    (d / "meta.json").write_text(json.dumps(FLOW_RUNS[rid]))

def _flow_cmd(engine, model, prompt, env):
    if engine == "local":
        env.update({"ANTHROPIC_BASE_URL": OLLAMA, "ANTHROPIC_AUTH_TOKEN": "ollama"})
        return ["claude", "-p", prompt, "--permission-mode", "acceptEdits", "--model", model]
    if engine == "codex":
        cmd = ["codex", "exec", "--sandbox", "workspace-write"]
        if model != "default":
            cmd += ["-m", model]
        return cmd + [prompt]
    cmd = ["claude", "-p", prompt, "--permission-mode", "acceptEdits"]
    if model != "default":
        cmd += ["--model", model]
    return cmd

def _run_flow(rid, flow, input_text, cwd):
    r = FLOW_RUNS[rid]
    current = input_text
    env_base = os.environ.copy()
    env_base["PATH"] = f"{Path.home()}/.npm-global/bin:{Path.home()}/.local/bin:/opt/homebrew/bin:" + env_base.get("PATH", "")
    for i, step in enumerate(flow["steps"]):
        jid = f"{rid}f{i+1}"
        prompt = step["prompt"].replace("{input}", current).replace("{goal}", input_text)
        env = env_base.copy()
        cmd = _flow_cmd(step.get("engine", "claude"), step.get("model", "default"), prompt, env)
        log = open(TERM_DIR / f"{jid}.log", "w")
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env)
        JOBS[jid] = {"proc": proc, "meta": {"id": jid, "engine": step.get("engine", "claude"),
            "model": step.get("model", "default"), "prompt": step["name"], "cwd": cwd, "status": "running",
            "started": datetime.datetime.now().strftime("%H:%M:%S")}}
        r["steps"][i]["jid"] = jid; r["steps"][i]["status"] = "running"; r["current_step"] = i
        _save_flow_run(rid)
        proc.wait()
        rc = proc.returncode
        JOBS[jid]["meta"]["status"] = "done" if rc == 0 else f"exit {rc}"
        JOBS[jid]["meta"]["ended"] = datetime.datetime.now().strftime("%H:%M:%S")
        output = (TERM_DIR / f"{jid}.log").read_text(errors="replace").strip()
        r["steps"][i]["status"] = JOBS[jid]["meta"]["status"]
        r["steps"][i]["output"] = output[-4000:]
        current = output or current
        _save_flow_run(rid)
    r["status"] = "done"; r["result"] = current; r["current_step"] = len(flow["steps"])
    _save_flow_run(rid)

@app.get("/api/flows")
def flows_list():
    c = db(); rows = [dict(r) for r in c.execute("SELECT * FROM flows ORDER BY created DESC")]; c.close()
    for row in rows:
        try:
            row["steps"] = json.loads(row["steps"] or "[]")
        except:
            row["steps"] = []
    return rows

@app.post("/api/flows")
def flows_save(payload: dict = Body(...)):
    fid = payload.get("id") or ("flow" + datetime.datetime.now().strftime("%y%m%d%H%M%S"))
    c = db()
    c.execute("""INSERT OR REPLACE INTO flows(id,name,steps,created)
      VALUES(?,?,?,COALESCE((SELECT created FROM flows WHERE id=?),?))""",
      (fid, payload["name"], json.dumps(payload["steps"]), fid, str(datetime.date.today())))
    c.commit(); c.close()
    log_activity("flow", f"saved flow '{payload['name']}' ({len(payload['steps'])} steps)")
    return {"id": fid}

@app.post("/api/flows/{fid}/delete")
def flows_delete(fid: str):
    c = db(); c.execute("DELETE FROM flows WHERE id=?", (fid,)); c.commit(); c.close()
    return {"ok": True}

@app.post("/api/flows/{fid}/run")
def flows_run(fid: str, payload: dict = Body(...)):
    c = db(); row = c.execute("SELECT * FROM flows WHERE id=?", (fid,)).fetchone(); c.close()
    if not row:
        return JSONResponse({"error": "unknown flow"}, status_code=404)
    flow = {"id": fid, "name": row["name"], "steps": json.loads(row["steps"])}
    input_text = payload.get("input", "").strip()
    cwd = os.path.expanduser(payload.get("cwd") or "~/Projects/mission-control/sandbox")
    if not input_text or not os.path.isdir(cwd):
        return JSONResponse({"error": "need input and a valid folder"}, status_code=400)
    rid = "r" + datetime.datetime.now().strftime("%H%M%S")
    FLOW_RUNS[rid] = {"id": rid, "flow_id": fid, "flow_name": flow["name"], "input": input_text, "cwd": cwd,
        "steps": [{"name": s["name"], "status": "pending", "output": ""} for s in flow["steps"]],
        "status": "running", "current_step": 0, "started": datetime.datetime.now().strftime("%H:%M:%S"), "result": ""}
    _save_flow_run(rid)
    threading.Thread(target=_run_flow, args=(rid, flow, input_text, cwd), daemon=True).start()
    log_activity("flow", f"flow '{flow['name']}' run {rid}: {input_text[:120]}")
    return {"id": rid}

@app.get("/api/flows/runs")
def flows_runs():
    _load_flow_runs_from_disk()
    return sorted(FLOW_RUNS.values(), key=lambda r: r["started"], reverse=True)[:30]

@app.get("/api/flows/run/{rid}")
def flows_run_detail(rid: str):
    _load_flow_runs_from_disk()
    r = FLOW_RUNS.get(rid)
    if not r:
        return JSONResponse({"error": "unknown run"}, status_code=404)
    return r


# ---------- hardware / software control ----------
@app.post("/api/hardware/control")
def hardware_control(payload: dict = Body(...)):
    action = payload.get("action")
    if action == "sleep":
        sh("pmset sleepnow")
    elif action == "volume_up":
        _osascript("set volume output volume (output volume of (get volume settings) + 10)")
    elif action == "volume_down":
        _osascript("set volume output volume (output volume of (get volume settings) - 10)")
    elif action == "mute":
        _osascript("set volume with output muted")
    elif action == "unmute":
        _osascript("set volume without output muted")
    else:
        return JSONResponse({"error": "unknown action"}, status_code=400)
    log_activity("hardware", f"hardware action: {action}")
    return {"ok": True, "action": action}

@app.post("/api/software/control")
def software_control(payload: dict = Body(...)):
    action = payload.get("action")
    app_name = payload.get("app")
    if not app_name:
        return JSONResponse({"error": "missing app name"}, status_code=400)
        
    if action == "open":
        # list-arg subprocess (no shell=True) so app_name can't break out into
        # arbitrary shell commands regardless of what characters it contains
        subprocess.run(["open", "-a", app_name], capture_output=True, timeout=15)
    elif action == "quit":
        # escape embedded quotes so app_name can't break out of the AppleScript
        # string literal and inject arbitrary AppleScript
        safe_name = app_name.replace('\\', '\\\\').replace('"', '\\"')
        _osascript(f'tell application "{safe_name}" to quit')
    else:
        return JSONResponse({"error": "unknown action"}, status_code=400)
    log_activity("software", f"software action: {action} {app_name}")
    return {"ok": True, "action": action, "app": app_name}

app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
