"""Bridge Instagram Saved media already synced by ~/AgentDrop-Workspace/sync-instagram-saved.sh
(gallery-dl reading cookies from an already-logged-in Arc session — no password involved anywhere
in this pipeline) into Mission Control's reel vault: convert each file's numeric media id to its
Instagram shortcode, skip anything already known, transcribe locally via whisper, classify via
ollama, and insert into mission.db.

Usage: sync_agentdrop_reels.py [--limit N]
"""
import json, sqlite3, subprocess, sys, datetime, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "data" / "mission.db"
MODEL = ROOT / "models" / "ggml-base.en.bin"
SRC_DIR = Path.home() / "AgentDrop-Workspace" / "instagram-saved"
TOPICS = ("claude-setup skills multi-agent local-models design security career jarvis "
          "memory-graph leadgen learning ads content-bait uncategorized")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

def pk_to_shortcode(pk):
    n, s = int(pk), ""
    while n:
        s = ALPHABET[n % 64] + s
        n //= 64
    return s

def sh(args, timeout=300):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

def classify(caption, transcript):
    prompt = (f"Classify this Instagram reel into ONE topic from: {TOPICS}. "
              f"Also write a one-sentence note on whether it names a real installable tool or is a comment-bait funnel.\n"
              f"CAPTION: {caption[:500]}\nTRANSCRIPT: {transcript[:1000]}\n"
              f'Reply as JSON: {{"topic": "...", "note": "..."}}')
    try:
        req = urllib.request.Request("http://localhost:11434/api/generate", method="POST",
            data=json.dumps({"model": "llama3.2", "prompt": prompt, "stream": False,
                             "format": "json"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            out = json.loads(json.loads(r.read())["response"])
            return out.get("topic", "uncategorized"), out.get("note", "")
    except Exception:
        return "uncategorized", ""

def known_ids():
    c = sqlite3.connect(DB)
    ids = {row[0] for row in c.execute("SELECT id FROM reels")}
    c.close()
    return ids

def ingest_local(mp4, rid):
    wav = mp4.with_suffix(".sync.wav")
    clean = f"https://www.instagram.com/reel/{rid}/"
    caption, uploader = "", "?"
    r = sh(["yt-dlp", "-q", "--no-warnings", "-J", clean])
    if r.returncode == 0 and r.stdout.strip():
        try:
            d = json.loads(r.stdout)
            caption = (d.get("description") or "")[:2000]
            uploader = d.get("uploader") or d.get("channel") or "?"
        except Exception:
            pass
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-ar", "16000", "-ac", "1", str(wav)])
    tx = ""
    if wav.exists():
        w = sh(["whisper-cli", "-m", str(MODEL), "-f", str(wav), "-np", "-nt"])
        tx = w.stdout.strip()
        wav.unlink(missing_ok=True)
    topic, note = classify(caption, tx)
    c = sqlite3.connect(DB)
    c.execute("""INSERT OR IGNORE INTO reels(id,uploader,caption,transcript,url,added,topic,verdict,notes)
      VALUES(?,?,?,?,?,?,?,?,?)""",
      (rid, uploader, caption, tx[:6000], clean, str(datetime.date.today()), topic, "review", note))
    c.commit(); c.close()
    print(f"OK {rid} [{topic}] {note[:80]}")

def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    if not SRC_DIR.exists():
        print("no synced folder yet — run sync-instagram-saved.sh first"); return
    known = known_ids()
    new = 0
    for mp4 in sorted(SRC_DIR.glob("*.mp4")):
        pk = mp4.stem.split("_")[0]
        if not pk.isdigit():
            continue
        rid = pk_to_shortcode(pk)
        if rid in known:
            continue
        ingest_local(mp4, rid)
        new += 1
        if limit and new >= limit:
            break
    print(f"done — {new} new reels added to vault")

if __name__ == "__main__":
    main()
