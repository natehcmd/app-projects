"""End-to-end smoke test for Command Center — stdlib only, never touches real data.

    .venv/bin/python tests/smoke_api.py

Copies the app + data into a temp dir, starts it on a spare port, then:
  * every GET endpoint returns 200 JSON with a session (the way the page calls it)
  * sensitive endpoints refuse a request with no session/token
  * a DNS-rebinding request (foreign Host header) gets no token and no cookie
  * /api/projects stays under a latency budget
Exit code 1 on any failure.
"""
import http.cookiejar
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENSITIVE = ["/api/team", "/api/team/runs", "/api/filegraph/file", "/api/compare/models", "/api/reels/board", "/api/briefs/short", "/api/learn/card", "/api/activity", "/api/briefs", "/api/lifehq", "/api/plaid/accounts",
             "/api/roadmap", "/api/search", "/api/swarm/runs", "/api/term/jobs",
             "/api/artifacts", "/api/flows/runs"]
SLOW_BUDGET_S = {"/api/projects": 4.0, "/api/term/snapshot": 4.0}
fails = []


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


def main():
    tmp = tempfile.mkdtemp(prefix="cc-smoke-")
    for name in os.listdir(HERE):
        if name in (".venv", "__pycache__", "sandbox", "models"):
            continue
        src, dst = os.path.join(HERE, name), os.path.join(tmp, name)
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
    port = free_port()
    uvicorn = os.path.join(HERE, ".venv", "bin", "uvicorn")
    proc = subprocess.Popen([uvicorn, "server:app", "--host", "127.0.0.1", "--port", str(port)],
                            cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = "http://127.0.0.1:%d" % port
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/vitals", timeout=1); break
            except Exception:
                time.sleep(0.5)
        else:
            check(False, "server did not start: " + proc.stderr.read(2000).decode(errors="replace"))
            return

        jar = http.cookiejar.CookieJar()
        sess = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        sess.open(base + "/", timeout=10).read()
        src = open(os.path.join(tmp, "server.py")).read()
        gets = sorted(set(re.findall(r'@app\.get\("(/api/[^"{]+)"\)', src)) - {"/api/artifacts/content", "/api/apps/icon", "/api/reels/thumb", "/api/reels/video",
                                                                                 "/api/briefs/short", "/api/learn/card",
                                                                                 "/api/compare/duel", "/api/filegraph/file", "/api/team/run"})

        print("GET endpoints with a session:")
        for path in gets:
            t = time.time()
            try:
                r = sess.open(base + path, timeout=30)
                body, code = r.read(), r.status
            except urllib.error.HTTPError as e:
                body, code = e.read(), e.code
            dt = time.time() - t
            try:
                json.loads(body)
                is_json = True
            except ValueError:
                is_json = False
            check(code == 200 and is_json, "%s -> %s%s (%.2fs)" % (path, code, "" if is_json else " non-JSON", dt))
            if path in SLOW_BUDGET_S:
                check(dt < SLOW_BUDGET_S[path], "%s under %.0fs budget (%.2fs)" % (path, SLOW_BUDGET_S[path], dt))

        print("App icons:")
        apps = json.loads(sess.open(base + "/api/apps", timeout=30).read())
        with_bundle = [a for a in apps if a.get("appBundle")]
        if with_bundle:
            r = sess.open(base + "/api/apps/icon?id=" + urllib.parse.quote(with_bundle[0]["id"]), timeout=30)
            png = r.read()
            check(r.status == 200 and png[:8] == b"\x89PNG\r\n\x1a\n", "real icon PNG for %s (%d bytes)" % (with_bundle[0]["name"], len(png)))
        tools = [a for a in apps if a.get("area") == "Reel Apps"]
        check(len(tools) > 0 and all(a["kind"] == "Tool (command line)" for a in tools if not a.get("appBundle")),
              "reel builds without an app bundle are labelled command-line tools (%d)" % len(tools))

        print("Reels board:")
        board = json.loads(sess.open(base + "/api/reels/board", timeout=30).read())
        vids = [r for r in board if r["has_video"]]
        check(len(vids) > 0, "reels with a local video (%d of %d)" % (len(vids), len(board)))
        check(not any(r["build"].get("state") == "done" for r in board), "no build ever reads as done")
        if vids:
            r = sess.open(base + "/api/reels/thumb?id=" + urllib.parse.quote(vids[0]["id"]), timeout=40)
            check(r.status == 200 and r.read()[:2] == b"\xff\xd8", "thumbnail JPEG for %s" % vids[0]["id"])
            req = urllib.request.Request(base + "/api/reels/video?id=" + urllib.parse.quote(vids[0]["id"]),
                                         headers={"Range": "bytes=0-99"})
            r = sess.open(req, timeout=30)
            check(r.status in (200, 206) and r.headers.get("Content-Type") == "video/mp4", "video streams (%s)" % r.status)
        for bad in ("../../etc/passwd", "a/b", "x" * 80):
            try:
                code = sess.open(base + "/api/reels/video?id=" + urllib.parse.quote(bad), timeout=10).status
            except urllib.error.HTTPError as e:
                code = e.code
            check(code == 404, "video refuses id %r (%s)" % (bad[:20], code))
        try:
            code = urllib.request.urlopen(urllib.request.Request(base + "/api/reels/build", data=b'{"id":"abcdef"}',
                headers={"Content-Type": "application/json", "Sec-Fetch-Site": "cross-site"}), timeout=10).status
        except urllib.error.HTTPError as e:
            code = e.code
        check(code in (401, 403), "build refuses anonymous cross-site (%s)" % code)

        print("Briefs / Learn inputs:")
        for path, want in (("/api/briefs/short?name=../../server", 404), ("/api/briefs/short?name=", 404),
                           ("/api/learn/card?kind=__proto__", 400)):
            try:
                code = sess.open(base + path, timeout=15).status
            except urllib.error.HTTPError as e:
                code = e.code
            check(code == want, "%s -> %s (want %s)" % (path, code, want))

        print("Compare head-to-head guards:")
        def post(path, body):
            req = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            try:
                return sess.open(req, timeout=15).status
            except urllib.error.HTTPError as e:
                return e.code
        check(post("/api/compare/duel", {"prompt": "hi", "models": ["claude_adjudicator", "local_small"]}) == 400,
              "Claude refused without allow_metered")
        check(post("/api/compare/duel", {"prompt": "hi", "models": ["local_small"]}) == 400, "one model refused")
        check(post("/api/compare/duel", {"prompt": "hi", "models": ["rm -rf", "x"]}) == 400, "unknown models refused")
        try:
            code = sess.open(base + "/api/compare/duel?id=../../mission", timeout=10).status
        except urllib.error.HTTPError as e:
            code = e.code
        check(code == 400, "duel id path refused (%s)" % code)
        try:
            code = sess.open(base + "/api/team/run?id=../../team", timeout=10).status
        except urllib.error.HTTPError as e:
            code = e.code
        check(code == 400, "team run id path refused (%s)" % code)
        check(post("/api/team/ask", {"idea": ""}) == 400, "empty idea refused")

        print("Sensitive endpoints without a session:")
        for path in [p for p in SENSITIVE if p in gets]:   # only those this build has
            try:
                code = urllib.request.urlopen(urllib.request.Request(
                    base + path, headers={"Sec-Fetch-Site": "cross-site"}), timeout=10).status
            except urllib.error.HTTPError as e:
                code = e.code
            check(code in (401, 403), "%s refuses anonymous cross-site (%s)" % (path, code))

        print("Hub: only Nate moves cards to Done:")
        hub = json.load(open(os.path.join(tmp, "static", "hub.json")))
        card = hub["projects"][0]["name"]
        tok = json.loads(sess.open(base + "/api/hands/token", timeout=10).read()).get("token", "")
        def move(opener, lane, headers):
            req = urllib.request.Request(base + "/api/hub/move", method="POST",
                                         data=json.dumps({"name": card, "lane": lane, "token": tok}).encode(),
                                         headers={"Content-Type": "application/json", **headers})
            try:
                return opener.open(req, timeout=10).status
            except urllib.error.HTTPError as e:
                return e.code
        agent = urllib.request.build_opener()          # no cookie: token only, like Hammond/agents
        check(move(agent, "done", {"Authorization": "Bearer " + tok}) == 403, "agent with token cannot move a card to Done")
        check(move(sess, "done", {}) == 200, "Nate's browser session can move a card to Done")
        moved = [p for p in json.load(open(os.path.join(tmp, "static", "hub.json")))["projects"] if p["name"] == card][0]
        check(moved.get("moved_by") == "nate", "move records who made it (%s)" % moved.get("moved_by"))

        print("DNS rebinding:")
        req = urllib.request.Request(base + "/api/hands/token",
                                     headers={"Host": "evil.example:%d" % port, "Sec-Fetch-Site": "same-origin"})
        try:
            r = urllib.request.urlopen(req, timeout=10)
            code, body, cookie = r.status, r.read().decode(), r.headers.get("Set-Cookie")
        except urllib.error.HTTPError as e:
            code, body, cookie = e.code, e.read().decode(), e.headers.get("Set-Cookie")
        check('"token"' not in body, "foreign Host gets no Hands token (%s)" % code)
        check(not cookie, "foreign Host gets no session cookie")
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%s" % ("ALL PASSED" if not fails else "%d FAILED" % len(fails)))


if __name__ == "__main__":
    main()
    sys.exit(1 if fails else 0)
