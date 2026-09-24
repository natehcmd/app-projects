"""Keep the Reels tab in step with the Instagram library ig-curate maintains.

    sync_library.py            # add new library reels, backfill empty transcripts
    sync_library.py --limit 5  # at most 5 reels this run (transcription is ~10s each)

ig-curate.py drops reels into ~/AgentDrop-Workspace/reels/<code>.mp4 (+ .txt
caption) every 10 minutes, but the Reels tab reads the `reels` table, which
only add_reels.py filled — from URLs, by hand. On 2026-09-24 the tab showed
104 reels while 112 were on disk, and every transcript was empty. This uses
the video already on disk (DM shares have no URL to re-download), local
whisper for the transcript and local qwen for the topic — nothing metered.
"""
import datetime
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from add_reels import DB, MODEL, classify, sh  # noqa: E402

LIB = Path.home() / "AgentDrop-Workspace" / "reels"


def transcribe(mp4: Path) -> str:
    wav = Path("/tmp") / (mp4.stem + ".wav")
    sh(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-ar", "16000", "-ac", "1", str(wav)])
    if not wav.exists():
        return ""
    w = sh(["whisper-cli", "-m", str(MODEL), "-f", str(wav), "-np", "-nt"])
    wav.unlink(missing_ok=True)
    return w.stdout.strip()


def caption_and_uploader(code: str):
    txt = LIB / f"{code}.txt"
    cap = txt.read_text(errors="replace").strip() if txt.exists() else ""
    m = re.match(r"@([\w.]+):\s*", cap)
    return (cap[m.end():] if m else cap), (m.group(1) if m else "?")


def main(limit: int) -> None:
    c = sqlite3.connect(DB)
    have = {r[0]: r[1] for r in c.execute("SELECT id, COALESCE(transcript,'') FROM reels")}
    todo = [p for p in sorted(LIB.glob("*.mp4"), key=lambda p: -p.stat().st_mtime)
            if p.stem not in have or not have[p.stem].strip()]
    done = 0
    for mp4 in todo[:limit]:
        code = mp4.stem
        caption, uploader = caption_and_uploader(code)
        tx = transcribe(mp4)
        topic, note = classify(caption, tx)
        url = "" if code.startswith("dm_") else f"https://www.instagram.com/reel/{code}/"
        added = datetime.date.fromtimestamp(mp4.stat().st_mtime).isoformat()
        if code in have:   # backfill: keep the user's verdict/notes, fill transcript/topic
            c.execute("UPDATE reels SET transcript=?, topic=COALESCE(NULLIF(topic,''),?) WHERE id=?",
                      (tx[:6000], topic, code))
        else:
            c.execute("""INSERT INTO reels(id,uploader,caption,transcript,url,added,topic,verdict,notes)
                         VALUES(?,?,?,?,?,?,?,'review',?)""",
                      (code, uploader, caption[:2000], tx[:6000], url, added, topic, note))
        c.commit()
        done += 1
        print(f"{'backfill' if code in have else 'added'} {code} [{topic}] {len(tx)} chars")
    c.close()
    print(f"sync: {done} processed, {max(0, len(todo) - done)} remaining")


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9
    main(lim)
