"""Ingest Instagram reel URLs: fetch metadata + audio, transcribe locally, classify via ollama, store.
Usage: add_reels.py <url> [url...]"""
import json, re, sqlite3, subprocess, sys, datetime, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB = ROOT / "data" / "mission.db"
MODEL = ROOT / "models" / "ggml-base.en.bin"
TOPICS = "claude-setup skills multi-agent local-models design security career jarvis memory-graph leadgen learning ads uncategorized"

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

def ingest(url):
    m = re.search(r"instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)", url)
    if not m:
        print(f"skip (not a reel url): {url}"); return
    rid = m.group(1)
    meta_f = ROOT / "data" / "reels" / "meta" / f"{rid}.json"
    tx_f = ROOT / "data" / "reels" / "tx" / f"{rid}.txt"
    audio = ROOT / "data" / "reels" / f"{rid}.m4a"
    wav = audio.with_suffix(".wav")
    clean = f"https://www.instagram.com/reel/{rid}/"
    r = sh(["yt-dlp", "-q", "--no-warnings", "-J", clean])
    if r.returncode != 0 or not r.stdout.strip():
        print(f"FAIL meta {rid}"); return
    meta_f.write_text(r.stdout)
    d = json.loads(r.stdout)
    sh(["yt-dlp", "-q", "--no-warnings", "-f", "ba/b", "-x", "--audio-format", "m4a",
        "-o", str(audio), clean])
    tx = ""
    if audio.exists():
        sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-ar", "16000", "-ac", "1", str(wav)])
        w = sh(["whisper-cli", "-m", str(MODEL), "-f", str(wav), "-np", "-nt"])
        tx = w.stdout.strip()
        tx_f.write_text(tx)
        wav.unlink(missing_ok=True); audio.unlink(missing_ok=True)
    caption = (d.get("description") or "")[:2000]
    topic, note = classify(caption, tx)
    c = sqlite3.connect(DB)
    c.execute("""INSERT OR REPLACE INTO reels(id,uploader,caption,transcript,url,added,topic,verdict,notes)
      VALUES(?,?,?,?,?,?,?,COALESCE((SELECT verdict FROM reels WHERE id=?),'review'),?)""",
      (rid, d.get("uploader") or d.get("channel") or "?", caption, tx[:6000], clean,
       str(datetime.date.today()), topic, rid, note))
    c.commit(); c.close()
    print(f"OK {rid} [{topic}] {note[:80]}")

if __name__ == "__main__":
    for u in sys.argv[1:]:
        ingest(u)
