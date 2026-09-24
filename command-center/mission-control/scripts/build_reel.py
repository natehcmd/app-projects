"""Build a small tool from one saved reel, down the model hierarchy.

    .venv/bin/python scripts/build_reel.py <reel_id>

Seeds reels-build/<id>/ (REEL.md with the caption + transcript, a stub tool
and a test), then runs the review pipeline's agent_loop.py on it: an
unmetered worker writes the change, the supervisor scores it, the test must
pass, and Claude is asked at most once per outer round. Progress goes to
data/builds/<id>.json, which the Reels tab polls.

The best a build can end on is "ready for Nate" — never done. Nate marks it.
"""
import datetime
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILDS = ROOT / "data" / "builds"
PIPELINE = Path.home() / ".local/share/review-pipeline/code-review-pipeline/scripts"
REEL_ID = re.compile(r"^[A-Za-z0-9_-]{5,64}$")

STUB_TOOL = '''"""{title}"""
import argparse


def main(argv=None):
    ap = argparse.ArgumentParser(description="See REEL.md for what this should do.")
    ap.parse_args(argv)
    raise SystemExit("not built yet")


if __name__ == "__main__":
    main()
'''

STUB_TEST = '''import subprocess
import sys
import unittest


class ToolRuns(unittest.TestCase):
    def test_help(self):
        r = subprocess.run([sys.executable, "tool.py", "--help"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_default_run(self):
        # The built tool must do something useful with no arguments (a demo run).
        r = subprocess.run([sys.executable, "tool.py"], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.strip(), "tool printed nothing")


if __name__ == "__main__":
    unittest.main()
'''


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def status(reel_id, **kw):
    BUILDS.mkdir(parents=True, exist_ok=True)
    f = BUILDS / f"{reel_id}.json"
    cur = json.loads(f.read_text()) if f.exists() else {}
    cur.update(kw, updated=now())
    f.write_text(json.dumps(cur, indent=1))
    return cur


def main(reel_id):
    if not REEL_ID.match(reel_id):
        raise SystemExit("bad reel id")
    c = sqlite3.connect(ROOT / "data" / "mission.db")
    c.row_factory = sqlite3.Row
    row = c.execute("SELECT * FROM reels WHERE id=?", (reel_id,)).fetchone()
    c.close()
    if not row:
        raise SystemExit("unknown reel")
    out = ROOT / "reels-build" / reel_id
    if out.exists() and any(p.name not in {".git"} for p in out.iterdir()):
        status(reel_id, state="failed", step="already has a build — not overwriting", ended=now())
        raise SystemExit("already built")

    status(reel_id, state="running", step="setting up the folder", started=now(), ended=None, log=[])
    out.mkdir(parents=True, exist_ok=True)
    caption = (row["caption"] or "").strip()
    (out / "REEL.md").write_text(
        f"# Reel {reel_id}\n\nLink: {row['url'] or ''}\n\n## Caption\n\n{caption}\n\n"
        f"## Transcript\n\n{(row['transcript'] or '(no transcript)').strip()}\n")
    (out / "tool.py").write_text(STUB_TOOL.format(title=(caption.splitlines() or ['Reel tool'])[0][:80].replace('"', "'")))
    (out / "test_tool.py").write_text(STUB_TEST)
    git = ["git", "-C", str(out)]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["add", "-A"], check=True)
    subprocess.run(git + ["-c", "user.name=reel-builder", "-c", "user.email=reel-builder@localhost",
                          "commit", "-qm", "seed from reel"], check=True)

    goal = ("Read REEL.md. Turn tool.py into a small, genuinely useful Python 3 command-line tool "
            "(standard library only) that does what the reel describes. If the reel only teases "
            "something without naming it, build the most reasonable honest version of the topic and "
            "say so in the tool's --help. Running `python3 tool.py` with no arguments must print a short "
            "demo. Keep test_tool.py passing; do not weaken it.")
    status(reel_id, step="AI is writing the tool (Gemini writes, tests check, Claude signs off)")
    env = dict(os.environ, PATH="/opt/homebrew/bin:" + os.environ.get("PATH", ""))
    proc = subprocess.Popen(
        [sys.executable, "-u", str(PIPELINE / "agent_loop.py"), str(out), goal,
         "--focus", "tool.py", "--worker-model", "agy_deep", "--max-inner", "4", "--max-outer", "2",
         "--ceiling", "8000", "--test-command", f"{sys.executable} -m unittest -q test_tool"],
        cwd=str(PIPELINE), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log = (log + [line[:200]])[-40:]
            status(reel_id, log=log)
    rc = proc.wait()
    if rc == 0:
        status(reel_id, state="ready_for_nate", step="built and tests pass — waiting for Nate to check", ended=now())
    else:
        why = next((l for l in reversed(log) if any(k in l for k in
                    ("iteration_cap", "no_improvement", "budget_exhausted", "error", "Error"))), "see log")
        status(reel_id, state="failed", step=f"stopped: {why[:140]}", ended=now())
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) if len(sys.argv) == 2 else "usage: build_reel.py <reel_id>")
