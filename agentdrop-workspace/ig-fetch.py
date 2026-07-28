#!/usr/bin/env python3
"""Fetch one Instagram reel/post video into the Library via instagrapi.

Fallback for when yt-dlp's Instagram extractor is broken (chronic). Logs in
with the CLI session from ig-login.py (.ig-session.json), resolves the media,
and downloads its direct CDN video URL.

Usage: .venv/bin/python ig-fetch.py <instagram-url>
Prints the destination path on success.
"""
import os
import re
import subprocess
import sys

WORKSPACE = os.path.expanduser("~/AgentDrop-Workspace")
REELS_DIR = os.path.join(WORKSPACE, "reels")
SESSION_PATH = os.path.join(WORKSPACE, ".ig-session.json")
COOKIES = os.path.join(WORKSPACE, ".ig-cookies.txt")

from instagrapi import Client


def get_sessionid():
    """CLI session from ig-login.py first; then the curator's cookie file."""
    if os.path.exists(SESSION_PATH):
        import json
        sid = (json.load(open(SESSION_PATH)).get("authorization_data") or {}).get("sessionid")
        if sid:
            return sid
    if os.path.exists(COOKIES):
        with open(COOKIES) as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 7 and parts[5] == "sessionid":
                    return parts[6]
    sys.exit("no Instagram session — run ig-login.py once to sign in")


def main():
    url = sys.argv[1]
    os.makedirs(REELS_DIR, exist_ok=True)

    # Shortcode straight from the URL — no API call needed to detect an
    # already-downloaded reel.
    match = re.search(r"instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", url)
    if match:
        code = match.group(1)
        dest = os.path.join(REELS_DIR, f"{code}.mp4")
        if os.path.exists(dest):
            print(dest)
            return

    cl = Client()
    cl.delay_range = [1, 3]
    cl.login_by_sessionid(get_sessionid())

    pk = cl.media_pk_from_url(url)
    # media_info_v1 = private API; the public GraphQL path instagrapi tries
    # first in media_info() currently gets HTML back from Instagram.
    try:
        m = cl.media_info_v1(pk)
    except Exception as e:
        if "feedback_required" in str(e):
            sys.exit("Instagram is rate-limiting this account right now — try again "
                     "in a while. If the reel is saved/DM'd on the curation account, "
                     "the 10-minute curator will pick it up automatically.")
        raise
    if not getattr(m, "video_url", None):
        sys.exit(f"{m.code} has no video (media_type={m.media_type}) — only reels/videos supported")

    dest = os.path.join(REELS_DIR, f"{m.code}.mp4")
    if not os.path.exists(dest):
        r = subprocess.run(["curl", "-sL", "--fail", "-o", dest, str(m.video_url)],
                           timeout=300)
        if r.returncode != 0 or not os.path.exists(dest) or os.path.getsize(dest) == 0:
            if os.path.exists(dest):
                os.remove(dest)
            sys.exit("download failed")

    sidecar = os.path.join(REELS_DIR, f"{m.code}.txt")
    if not os.path.exists(sidecar):
        uploader = m.user.username if getattr(m, "user", None) else ""
        with open(sidecar, "w") as f:
            f.write((f"@{uploader}: " if uploader else "") + (m.caption_text or "").strip())

    print(dest)


if __name__ == "__main__":
    main()
