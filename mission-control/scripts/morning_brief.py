"""CEO morning brief — reads Life HQ, job tracker, memory index, and yesterday's brief;
generates today's priorities via local ollama. Runs from cron at 8am or on demand."""
import json, sqlite3, datetime, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
HOME = Path.home()
MODEL = "llama3.2"

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
Write his morning brief in markdown. Sections:
## Yesterday  (what actually moved, from recent completions + prior brief)
## Today's Top 3  (ranked, each with a concrete first action)
## Watch  (deadlines/risks — check the job tracker for dates near {today}; flag anything within 14 days)
## One Question  (a single sharp question to focus the day)
Be specific and honest, no filler. Under 300 words.

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
    out = ROOT / "data" / "briefs" / f"{today}.md"
    out.write_text(f"# CEO Brief — {today}\n\n{brief}\n")
    print(f"wrote {out}")

if __name__ == "__main__":
    main()
