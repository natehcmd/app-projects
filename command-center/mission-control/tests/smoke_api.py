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
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENSITIVE = ["/api/activity", "/api/briefs", "/api/lifehq", "/api/plaid/accounts",
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
        if name in (".venv", "reels-build", "__pycache__", "sandbox", "models"):
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
        gets = sorted(set(re.findall(r'@app\.get\("(/api/[^"{]+)"\)', src)) - {"/api/artifacts/content"})

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

        print("Sensitive endpoints without a session:")
        for path in [p for p in SENSITIVE if p in gets]:   # only those this build has
            try:
                code = urllib.request.urlopen(urllib.request.Request(
                    base + path, headers={"Sec-Fetch-Site": "cross-site"}), timeout=10).status
            except urllib.error.HTTPError as e:
                code = e.code
            check(code in (401, 403), "%s refuses anonymous cross-site (%s)" % (path, code))

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
