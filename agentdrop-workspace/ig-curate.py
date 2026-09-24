#!/usr/bin/env python3
"""Curation pipeline for the AgentDrop Library.

The curation inbox is **tech.review.nate** — that's the account `ig-login.py`
must log into (.ig-session.json). Two ways a reel gets in:
  1. Nate SAVES it on tech.review.nate → mirrored from the saved collection.
  2. He DMs it to tech.review.nate from natep.howard (his main account) →
     pulled from DMs. Reels DM'd by anyone else are skipped, with the reason
     recorded in the ledger.

Both land as best-quality mp4 + caption sidecar in ~/AgentDrop-Workspace/reels/,
which is the only folder the AgentDrop Library reads.

Login: the CLI session saved by ig-login.py (.ig-session.json) — run that
script once, logged into tech.review.nate, no browser needed. If no CLI
session exists, falls back to reading the Arc browser's Instagram login.
Idempotent: a reel already in reels/ is skipped; each DM message is processed
once via the .dm-seen.json watermark.
"""
import glob
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

WORKSPACE = os.path.expanduser("~/AgentDrop-Workspace")
REELS_DIR = os.path.join(WORKSPACE, "reels")
SEEN_PATH = os.path.join(WORKSPACE, ".dm-seen.json")
SKIPS_PATH = os.path.join(WORKSPACE, ".curate-skips.json")
SESSION_PATH = os.path.join(WORKSPACE, ".ig-session.json")
COOKIES = os.path.join(WORKSPACE, ".ig-cookies.txt")
# DM senders whose shared reels get curated: natep.howard (Nate's main
# account, sending to tech.review.nate) plus the logged-in curation account
# itself (added at runtime, for self-shares within tech.review.nate) — reels
# DM'd by anyone else are skipped with a reason in the ledger.
ALLOWED_SENDERS = {"natep.howard"}

os.makedirs(REELS_DIR, exist_ok=True)

# Skip ledger: everything that looked like library material but didn't land in
# reels/, with the reason why. The AgentDrop Library shows this next to the
# grid. Keyed by reel code / message id so repeat runs update instead of spam.
try:
    SKIPS = json.load(open(SKIPS_PATH))
except Exception:
    SKIPS = {}


def record_skip(key, reason, title="", url=""):
    SKIPS[key] = {
        "key": key,
        "reason": reason,
        "title": (title or "").strip()[:200],
        "url": url,
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print(f"  ⤫ skipped {key}: {reason}")


def clear_skip(key):
    SKIPS.pop(key, None)


def save_skips():
    # keep the 200 most recent so the ledger stays readable
    entries = sorted(SKIPS.values(), key=lambda e: e.get("when", ""), reverse=True)[:200]
    json.dump({e["key"]: e for e in entries}, open(SKIPS_PATH, "w"), indent=1)


from instagrapi import Client


def write_cookie_file(cl):
    """Write a yt-dlp-compatible Netscape cookie file from the API session."""
    import time
    expires = str(int(time.time()) + 86400 * 365)
    lines = ["# Netscape HTTP Cookie File\n"]
    for name, value in cl.private.cookies.get_dict().items():
        lines.append(f".instagram.com\tTRUE\t/\tTRUE\t{expires}\t{name}\t{value}\n")
    with open(COOKIES, "w") as f:
        f.writelines(lines)
    os.chmod(COOKIES, 0o600)


def login():
    """Prefer the CLI session from ig-login.py; fall back to Arc's login."""
    cl = Client()
    cl.delay_range = [1, 3]
    if os.path.exists(SESSION_PATH):
        data = json.load(open(SESSION_PATH))
        sid = (data.get("authorization_data") or {}).get("sessionid")
        if not sid:
            sys.exit(f"no sessionid in {SESSION_PATH} — rerun ig-login.py")
        cl.login_by_sessionid(sid)
        return cl
    import browser_cookie3
    try:
        cookies = list(browser_cookie3.arc(domain_name="instagram.com"))
    except browser_cookie3.BrowserCookieError:
        cookies = []
    sid = next((c.value for c in cookies if c.name == "sessionid"), None)
    if not sid:
        sys.exit("no CLI session — run ig-login.py (logged into tech.review.nate) first")
    cl.login_by_sessionid(sid)
    return cl


def download_reel(code, caption, uploader, video_url=None):
    """Fetch a reel best-quality via yt-dlp, falling back to the direct CDN
    URL instagrapi already gave us (yt-dlp's Instagram extractor breaks
    whenever Instagram changes their API — the CDN URL keeps working).
    Returns 'exists' | 'downloaded' | 'failed'."""
    dest = os.path.join(REELS_DIR, f"{code}.mp4")
    if os.path.exists(dest):
        return "exists"
    url = f"https://www.instagram.com/reel/{code}/"
    print(f"  ↓ {code}" + (f" (@{uploader})" if uploader else ""))
    r = subprocess.run(
        ["yt-dlp", "--quiet", "--no-warnings", "--cookies", COOKIES,
         "-f", "bv*+ba/b", "--merge-output-format", "mp4", "-o", dest, url],
        capture_output=True, text=True, timeout=300,
    )
    # A failed merge (Instagram's extractor breaking mid-stream is common)
    # leaves the separately-fetched video/audio DASH fragments behind as
    # "{code}.fdash-<id>v.mp4" / "{code}.fdash-<id>a.m4a" — real leftover
    # junk, not alternate copies. Without this they silently doubled disk
    # usage and inflated the "reels total" count every single run.
    for frag in glob.glob(os.path.join(REELS_DIR, f"{code}.fdash-*")):
        os.remove(frag)
    if r.returncode != 0 or not os.path.exists(dest):
        err = r.stderr.strip()[:160]
        if video_url:
            print("    yt-dlp failed, trying direct CDN URL…")
            r2 = subprocess.run(
                ["curl", "-sL", "--fail", "-o", dest, str(video_url)],
                capture_output=True, text=True, timeout=300,
            )
            if r2.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) == 0:
                if os.path.exists(dest):
                    os.remove(dest)
                record_skip(code, f"Download failed (yt-dlp and direct URL): {err or 'unknown error'}",
                            title=caption, url=url)
                return "failed"
        else:
            print(f"    failed: {err}", file=sys.stderr)
            record_skip(code, f"Download failed: {err or 'unknown yt-dlp error'}",
                        title=caption, url=url)
            return "failed"
    clear_skip(code)
    sidecar = os.path.join(REELS_DIR, f"{code}.txt")
    if not os.path.exists(sidecar):
        with open(sidecar, "w") as f:
            f.write((f"@{uploader}: " if uploader else "") + (caption or "").strip())
    return "downloaded"


def sync_saved(cl):
    print("Saved collection…")
    try:
        meds = cl.collection_medias("ALL_MEDIA_AUTO_COLLECTION", amount=0)
    except Exception as e:
        print(f"  couldn't read saved: {str(e)[:160]}", file=sys.stderr)
        return 0
    new = 0
    for m in meds:
        if m.media_type != 2:  # reels/videos only
            kind = {1: "a photo post", 8: "a carousel/album"}.get(m.media_type, "not a video")
            record_skip(m.code, f"Saved item is {kind} — only reels/videos are curated",
                        title=m.caption_text,
                        url=f"https://www.instagram.com/p/{m.code}/")
            continue
        uploader = m.user.username if getattr(m, "user", None) else ""
        if download_reel(m.code, m.caption_text, uploader,
                         video_url=getattr(m, "video_url", None)) == "downloaded":
            new += 1
    return new


def extract_shared(msg):
    """How to fetch a reel shared in a DM, or None if the message isn't one.

    Returns a dict: {"code", "caption", "uploader"} for a proper reel share
    (best quality via reel URL), or {"direct_url", "caption", "name"} for an
    xma-style share that only carries a direct (possibly preview) video URL.
    """
    for attr in ("clip", "media_share"):
        media = getattr(msg, attr, None)
        if media and getattr(media, "code", None):
            return {"code": media.code,
                    "caption": getattr(media, "caption_text", "") or "",
                    "uploader": media.user.username if getattr(media, "user", None) else "",
                    "video_url": getattr(media, "video_url", None)}
    xma = getattr(msg, "xma_share", None)
    if xma and getattr(xma, "video_url", None):
        return {"direct_url": xma.video_url,
                "caption": getattr(xma, "title", "") or "",
                "name": f"dm_{msg.id}"}
    return None


def download_direct(url, name, caption):
    """Fetch an xma direct video URL (no reel code). 'exists'|'downloaded'|'failed'."""
    dest = os.path.join(REELS_DIR, f"{name}.mp4")
    if os.path.exists(dest):
        return "exists"
    print(f"  ↓ {name} (direct)")
    r = subprocess.run(
        ["yt-dlp", "--quiet", "--no-warnings", "-o", dest, url],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0 or not os.path.exists(dest):
        err = r.stderr.strip()[:160]
        print(f"    failed: {err}", file=sys.stderr)
        record_skip(name, f"Download failed: {err or 'unknown yt-dlp error'}", title=caption)
        return "failed"
    clear_skip(name)
    sidecar = os.path.join(REELS_DIR, f"{name}.txt")
    if not os.path.exists(sidecar):
        with open(sidecar, "w") as f:
            f.write((caption or "").strip())
    return "downloaded"


def sync_dms(cl):
    print("DM inbox…")
    seen = set(json.load(open(SEEN_PATH))) if os.path.exists(SEEN_PATH) else set()
    own_pk = str(cl.user_id)
    threads = list(cl.direct_threads(amount=20)) + list(cl.direct_pending_inbox(20))
    new = 0
    for t in threads:
        users_by_pk = {str(u.pk): u for u in t.users}
        for msg in t.messages:
            if msg.id in seen:
                continue
            sender = (cl.username if str(msg.user_id) == own_pk
                      else (users_by_pk.get(str(msg.user_id)).username
                            if users_by_pk.get(str(msg.user_id)) else None))
            shared = extract_shared(msg)
            if not shared:
                seen.add(msg.id)  # ordinary text/like — not library material
                continue
            if sender not in ALLOWED_SENDERS:
                key = shared.get("code") or shared.get("name") or msg.id
                record_skip(key,
                            f"Shared by @{sender or 'unknown'} — not one of your allowed senders",
                            title=shared.get("caption", ""),
                            url=f"https://www.instagram.com/reel/{shared['code']}/" if shared.get("code") else "")
                seen.add(msg.id)
                continue
            if "code" in shared:
                status = download_reel(shared["code"], shared["caption"], shared["uploader"],
                                       video_url=shared.get("video_url"))
            else:
                status = download_direct(shared["direct_url"], shared["name"], shared["caption"])
            if status in ("downloaded", "exists"):
                seen.add(msg.id)
                if status == "downloaded":
                    new += 1
            # on failure: leave unseen so next run retries
    json.dump(sorted(seen), open(SEEN_PATH, "w"))
    return new


def main():
    cl = login()
    write_cookie_file(cl)
    print(f"Curating as @{cl.username}")
    ALLOWED_SENDERS.add(cl.username)

    saved_new = sync_saved(cl)
    dm_new = sync_dms(cl)
    save_skips()

    # ".fdash-" fragments are cleaned up in download_reel() as they're
    # created, but excluding them here too means a stray one from an old
    # run (or a future code path) can't quietly inflate this count.
    total = len([f for f in os.listdir(REELS_DIR) if f.endswith(".mp4") and ".fdash-" not in f])
    print(f"✅ curated — {saved_new} new from saved, {dm_new} new from DMs · "
          f"{total} reels total in library · {len(SKIPS)} in the skip ledger")

    # Push any newly-curated reels into the "agent drop and ig reels" Gemini
    # Notebook — separate Python 3.12 venv (notebooklm-py's cookie-extraction
    # dependency can't build under this project's main 3.14 venv). Best-effort:
    # a failure here (e.g. expired Chrome cookie session) shouldn't fail the
    # whole curation run — the reel is already safely in reels/ either way,
    # nblm_sync.py will just pick it up again next run.
    nblm_sync = os.path.join(WORKSPACE, "nblm_sync.py")
    nblm_python = os.path.join(WORKSPACE, ".nblm-venv", "bin", "python3")
    if os.path.exists(nblm_sync) and os.path.exists(nblm_python):
        try:
            subprocess.run([nblm_python, nblm_sync], timeout=300)
        except Exception as e:
            print(f"  (nblm_sync failed, will retry next run: {e})", file=sys.stderr)


if __name__ == "__main__":
    main()
