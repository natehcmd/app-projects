#!/usr/bin/env python3
"""Push newly-synced reels into the "agent drop and ig reels" Gemini Notebook.

Runs after ig-curate.py in the same launchd cycle. Idempotent — tracks what's
already been pushed so re-runs only push genuinely new reels. Uses
notebooklm-py (installed in .nblm-venv, a separate Python 3.12 venv — the
main .venv's Python 3.14 can't build the cookie-extraction dependency)
authenticated via Chrome cookie extraction (see README.md in this folder for
how to re-auth if the session expires).

Three source types per reel, tracked SEPARATELY (.nblm-pushed-{link,text,
video}.json), not as one combined per-code flag. A combined flag means a
partial failure (e.g. caption succeeds, video times out) re-pushes the
already-succeeded half on retry, creating a duplicate source in the notebook
— confirmed as a real risk, not hypothetical (found and cleaned up ~20 stray
duplicate/error sources from exactly this on 2026-09-02). "link" only applies
to real reel-code items (public instagram.com/reel/<code>/ URL) — dm_-prefixed
DM shares have no public URL, so they only ever get caption + video.

Video processing verification: `source add --type file` returning exit 0
only means the UPLOAD succeeded — NotebookLM then processes the file
server-side, asynchronously, and can fail that step while the CLI call
already reported success. Marking a video "pushed" on add's exit code alone
was a real bug (confirmed 2026-09-02: 8 videos silently sat in the notebook
as permanent "error" status sources, invisible to this script, for over a
day). Fixed by calling `source wait` after every video add and only counting
it pushed once processing genuinely completes; a wait failure deletes the
resulting error source (so it doesn't sit there as cruft) and is tracked in
the permafail file below instead of being retried forever.

Known permanent failures: 8 reels whose video consistently fails NotebookLM's
server-side processing regardless of encoding — confirmed via two separate
manual re-encode attempts (default H.264 High profile, then a conservative
Baseline profile/no-B-frames re-encode) that both hit the identical
Google-side error. Not a file-corruption, codec, container, or duration issue
(verified: the shortest successfully-processed video in the corpus, 7.75s, is
shorter than several of these 8). Root cause is server-side and outside what
re-encoding can fix. Pre-seeded into .nblm-video-permafail.json so the
automated pipeline doesn't keep re-attempting (and re-erroring) them forever;
these reels still get a caption + link source, so their content isn't lost.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

# notebooklm-py talks to NotebookLM's internal RPC API, not a public rate-safe
# endpoint. Pushing 100+ sources back-to-back with no pacing triggers
# server-side throttling that gets worse over the run (confirmed 2026-09-01:
# a batch with no delay went from ~all-success in the first third to
# "RPC GET_NOTEBOOK failed after 30.007s: server-error retries exhausted" for
# most of the rest). Pacing alone wasn't a full fix — retrying transient
# failures with backoff (added 2026-09-02) is the other half: a single
# server-error no longer permanently drops that push for the run.
PACING_SECONDS = 5
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 15
VIDEO_WAIT_TIMEOUT = 150  # source wait's own internal poll timeout is ~120s
# After this many independently-confirmed processing failures (not upload
# failures — genuine "uploaded fine, then errored in processing" outcomes),
# stop retrying automatically and require manual clearing of the permafail
# entry. Sub-1 would never retry a possibly-transient one; keeping it low
# still bounds the wasted-cruft risk since each attempt creates then deletes
# one error source.
PERMFAIL_THRESHOLD = 2

WORKSPACE = Path.home() / "AgentDrop-Workspace"
REELS_DIR = WORKSPACE / "reels"
LINK_PUSHED_PATH = WORKSPACE / ".nblm-pushed-link.json"
TEXT_PUSHED_PATH = WORKSPACE / ".nblm-pushed-text.json"
VIDEO_PUSHED_PATH = WORKSPACE / ".nblm-pushed-video.json"
VIDEO_PERMAFAIL_PATH = WORKSPACE / ".nblm-video-permafail.json"
NBLM = WORKSPACE / ".nblm-venv" / "bin" / "notebooklm"
# Recreated 2026-09-01 under the personal account (np.howard9@gmail.com) —
# the old jov.ai-owned notebook (6a75f403-b35e-4793-9175-257136c71316)
# vanished and auth for that profile had expired anyway.
NOTEBOOK_ID = "19a6c976-94be-4f87-bf5e-49156cd40d96"  # "agent drop and ig reels"


def load_set(path: Path) -> set:
    try:
        return set(json.loads(path.read_text()))
    except Exception:
        return set()


def save_set(path: Path, s: set) -> None:
    path.write_text(json.dumps(sorted(s), indent=1))


def load_permafail() -> dict:
    try:
        return json.loads(VIDEO_PERMAFAIL_PATH.read_text())
    except Exception:
        return {}


def save_permafail(d: dict) -> None:
    VIDEO_PERMAFAIL_PATH.write_text(json.dumps(d, indent=1, sort_keys=True))


def title_for(code: str) -> str:
    if code.startswith("dm_"):
        return f"AgentDrop DM Share {code}"
    return f"Instagram Reel {code}"


def _nblm(args: list, timeout: int):
    return subprocess.run([str(NBLM), *args, "-n", NOTEBOOK_ID, "--json"],
                          capture_output=True, text=True, timeout=timeout)


def _run_with_retry(args: list, timeout: int, label: str) -> bool:
    for attempt in range(1, MAX_RETRIES + 1):
        result = _nblm(args, timeout)
        if result.returncode == 0:
            return True
        err = (result.stderr.strip() or result.stdout.strip())[:200]
        if attempt < MAX_RETRIES:
            wait = RETRY_BACKOFF_SECONDS * attempt
            print(f"  {label} attempt {attempt}/{MAX_RETRIES} failed: {err} — retrying in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)
        else:
            print(f"  FAILED {label} after {MAX_RETRIES} attempts: {err}", file=sys.stderr)
    return False


def push_link(code: str) -> bool:
    url = f"https://www.instagram.com/reel/{code}/"
    return _run_with_retry(
        ["source", "add", url, "--type", "text", "--title", title_for(code) + " (link)"],
        60, f"{code} (link)")


def push_text(code: str, text: str) -> bool:
    return _run_with_retry(
        ["source", "add", text, "--type", "text", "--title", title_for(code) + " (caption)"],
        60, f"{code} (caption)")


def push_video(code: str, video_path: Path, permafail: dict) -> bool:
    """Upload, then verify actual server-side processing via `source wait` —
    not just the upload's exit code (see module docstring). On a genuine
    processing failure, deletes the resulting error source and records it in
    `permafail`; after PERMFAIL_THRESHOLD such failures, future runs skip
    this code automatically instead of re-erroring it every cycle."""
    for attempt in range(1, MAX_RETRIES + 1):
        add = _nblm(["source", "add", str(video_path), "--type", "file",
                     "--title", title_for(code) + " (video)", "--mime-type", "video/mp4"],
                    180)
        if add.returncode != 0:
            err = (add.stderr.strip() or add.stdout.strip())[:200]
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_SECONDS * attempt
                print(f"  {code} (video) upload attempt {attempt}/{MAX_RETRIES} failed: {err} — retrying in {wait}s",
                      file=sys.stderr)
                time.sleep(wait)
                continue
            print(f"  FAILED {code} (video) upload after {MAX_RETRIES} attempts: {err}", file=sys.stderr)
            return False

        try:
            source_id = json.loads(add.stdout)["source"]["id"]
        except Exception:
            print(f"  {code} (video): upload succeeded but couldn't parse source id — treating as failed", file=sys.stderr)
            return False

        wait = _nblm(["source", "wait", source_id], VIDEO_WAIT_TIMEOUT)
        if wait.returncode == 0:
            return True

        # Processing genuinely failed — clean up the error source rather
        # than leaving it as cruft, and record the failure.
        _nblm(["source", "delete", source_id, "-y"], 30)
        entry = permafail.get(code, {"failures": 0, "last_error": ""})
        entry["failures"] += 1
        entry["last_error"] = (wait.stderr.strip() or wait.stdout.strip())[:300]
        permafail[code] = entry
        save_permafail(permafail)
        print(f"  {code} (video): processing failed ({entry['failures']} total) — {entry['last_error'][:150]}",
              file=sys.stderr)
        return False

    return False


def main():
    if not NBLM.exists():
        print(f"notebooklm CLI not found at {NBLM} — run setup first.", file=sys.stderr)
        sys.exit(1)
    pushed_link = load_set(LINK_PUSHED_PATH)
    pushed_text = load_set(TEXT_PUSHED_PATH)
    pushed_video = load_set(VIDEO_PUSHED_PATH)
    permafail = load_permafail()
    new_link = new_text = new_video = fail_link = fail_text = fail_video = 0
    skipped_permafail = 0

    codes = sorted({f.stem for f in REELS_DIR.glob("*.txt")} | {f.stem for f in REELS_DIR.glob("*.mp4")})
    for code in codes:
        txt_path = REELS_DIR / f"{code}.txt"
        vid_path = REELS_DIR / f"{code}.mp4"
        text = txt_path.read_text(errors="replace").strip() if txt_path.exists() else ""
        has_video = vid_path.exists()
        is_dm = code.startswith("dm_")

        is_permafailed = permafail.get(code, {}).get("failures", 0) >= PERMFAIL_THRESHOLD
        need_link = (not is_dm) and code not in pushed_link
        need_text = bool(text) and code not in pushed_text
        need_video = has_video and code not in pushed_video and not is_permafailed
        if is_permafailed and has_video and code not in pushed_video:
            skipped_permafail += 1
        if not need_link and not need_text and not need_video:
            continue

        did_anything = False
        if need_link:
            print(f"  pushing {code} (link)…")
            if push_link(code):
                pushed_link.add(code)
                new_link += 1
            else:
                fail_link += 1
            save_set(LINK_PUSHED_PATH, pushed_link)
            did_anything = True
            time.sleep(PACING_SECONDS)

        if need_text:
            print(f"  pushing {code} (caption)…")
            if push_text(code, text):
                pushed_text.add(code)
                new_text += 1
            else:
                fail_text += 1
            save_set(TEXT_PUSHED_PATH, pushed_text)
            did_anything = True

        if need_video:
            print(f"  pushing {code} (video)…")
            if push_video(code, vid_path, permafail):
                pushed_video.add(code)
                new_video += 1
            else:
                fail_video += 1
            save_set(VIDEO_PUSHED_PATH, pushed_video)
            did_anything = True

        if did_anything:
            time.sleep(PACING_SECONDS)

    print(f"nblm_sync: link {new_link} pushed / {fail_link} failed ({len(pushed_link)} total); "
          f"text {new_text} pushed / {fail_text} failed ({len(pushed_text)} total); "
          f"video {new_video} pushed / {fail_video} failed ({len(pushed_video)} total, "
          f"{skipped_permafail} skipped as known-permanent-failures).")


if __name__ == "__main__":
    main()
