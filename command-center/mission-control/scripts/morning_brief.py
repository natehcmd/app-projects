"""CEO morning brief — reads Life HQ, job tracker, memory index, and yesterday's brief;
generates today's priorities via local ollama. Runs from cron at 8am or on demand."""
import json, sys, sqlite3, datetime, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
HOME = Path.home()
MODEL = "llama3.1:8b"  # small local model: a short bullet brief doesn't need the 30B

def read(p, limit=3000):
    try:
        return Path(p).read_text()[:limit]
    except Exception:
        return "(unavailable)"

def main():
    today = datetime.date.today()
    c = sqlite3.connect(ROOT / "data" / "mission.db"); c.row_factory = sqlite3.Row
    goals = [dict(r) for r in c.execute("SELECT text,urgent,created FROM goals WHERE done=0")]
    done_recent = [dict(r) for r in c.execute(
        "SELECT text,completed FROM goals WHERE done=1 ORDER BY id DESC LIMIT 10")]
    checkin = next((dict(r) for r in c.execute("SELECT * FROM checkins ORDER BY date DESC LIMIT 1")), None)
    c.close()
    briefs = sorted((ROOT / "data" / "briefs").glob("*.md"), reverse=True)
    yesterday = briefs[0].read_text()[:1500] if briefs else "(first brief)"
    memory = read(HOME / ".claude/projects/-Users-natehoward/memory/MEMORY.md", 2500)
    tracker = read(HOME / "job-search-2026/tracker.md", 2500)

    prompt = f"""You are the CEO agent of Nate's personal operating system. Date: {today} ({today.strftime('%A')}).
Write his morning brief in markdown, as short bullet points in simple, plain English
(like texting a friend — short words, no jargon, no buzzwords, no hype). Sections:
## Yesterday  (1-3 bullets: what actually moved, from recent completions + prior brief)
## Today's Top 3  (3 numbered bullets, ranked, each ending with the first thing to do)
## Watch  (0-3 bullets: deadlines/risks — check the job tracker for dates near {today}; flag anything within 14 days)
## One Question  (one short question to focus the day)
Every line is a bullet under 20 words. Be specific and honest; if there is nothing, say "nothing". Under 150 words.

DATA
Open goals: {json.dumps(goals)}
Recently completed: {json.dumps(done_recent)}
Latest check-in: {json.dumps(checkin)}
Yesterday's brief: {yesterday}
Memory index: {memory}
Job tracker: {tracker}"""

    req = urllib.request.Request("http://localhost:11434/api/generate", method="POST",
        data=json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        brief = json.loads(r.read())["response"].strip()
    brief, note = pipeline_check(brief, prompt)
    out = ROOT / "data" / "briefs" / f"{today}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"# CEO Brief — {today}\n\n{brief}\n\n_{note}_\n")
    print(f"wrote {out}")

def pipeline_check(brief, prompt):
    """Nate: every model call goes through the pipeline. Gemini Flash checks the
    8B's brief against the data it was given (a made-up deadline is worse than
    no brief); Gemini Pro rewrites it with the reason if rejected."""
    try:
        sys.path.insert(0, str(Path.home() / ".local/share/review-pipeline/code-review-pipeline/scripts"))
        from claude_director import Dispatcher, TokenLedger
        check = ("You are checking a morning brief before the user reads it. Reject it if it states "
                 "any date, deadline, task or fact that is NOT in the DATA, or misreads it. Don't reject "
                 "for style. Do NOT use tools. Reply with ONLY: {\"ok\": true|false, \"issue\": \"...\"}"
                 "\n\nDATA AND INSTRUCTIONS:\n" + prompt[:9000] + "\n\nBRIEF:\n" + brief[:4000])
        raw = Dispatcher(TokenLedger(), failover=False).call("agy_flash", "verify", check, timeout=90)
        import re as _re
        m = _re.search(r"\{[^{}]*\"ok\"[^{}]*\}", raw or "", _re.S)
        v = json.loads(m.group(0)) if m else {}
    except Exception as e:
        return brief, f"not checked ({str(e)[:80]})"
    if v.get("ok") is True:
        return brief, "checked by Gemini ✓"
    if v.get("ok") is False:
        try:
            redo = Dispatcher(TokenLedger(), failover=False).call(
                "agy_pro", "rewrite", prompt + "\n\nA reviewer rejected an earlier draft because: "
                + str(v.get("issue", "")) + "\nFix that. Same format.", timeout=120).strip()
            if redo:
                return redo, "corrected by Gemini — the first draft had: " + str(v.get("issue", ""))[:120]
        except Exception as e:
            return brief, "⚠️ Gemini flagged: " + str(v.get("issue", ""))[:120] + f" (rewrite failed: {str(e)[:60]})"
    return brief, "not checked (no verdict)"


if __name__ == "__main__":
    main()
