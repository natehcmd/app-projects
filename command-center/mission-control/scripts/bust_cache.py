"""Stamp static/index.html asset links with a content hash (?v=…).

Run after editing any static .js/.css: browsers otherwise keep serving the
old file on a normal refresh (seen 2026-09-24 — fixes were live on disk but
invisible until a hard reload)."""
import hashlib, os, re
STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
p = os.path.join(STATIC, "index.html")
s = open(p).read()
def ver(m):
    f = os.path.join(STATIC, m.group(2))
    h = hashlib.sha1(open(f, "rb").read()).hexdigest()[:8] if os.path.exists(f) else "0"
    return '{}="{}?v={}"'.format(m.group(1), m.group(2), h)
s2 = re.sub(r'(src|href)="([\w-]+\.(?:js|css))(?:\?v=[0-9a-f]+)?"', ver, s)
open(p, "w").write(s2)
print("stamped", len(re.findall(r'\?v=[0-9a-f]+', s2)), "asset links")
