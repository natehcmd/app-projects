from collections import Counter, defaultdict
from pathlib import Path
import re

from filegraph import db

HOME = Path.home()
OUT = HOME / "AI_CONTEXT_MINDMAP.md"
DRIVE = str(HOME / "Library/CloudStorage/GoogleDrive-np.howard9@gmail.com/My Drive")
REELS = HOME / "AgentDrop-Workspace/reels"
SENSITIVE = ("/.ssh/", "/.mcp-auth/", "/.aws/", "/.gnupg/", "/Library/Keychains/")


def safe(path: str) -> bool:
    return not any(x in path for x in SENSITIVE)


def section(title, items):
    out = [f"## {title}", ""]
    out.extend(f"- {x}" for x in items)
    out.append("")
    return out

con = db.connect()
lines = [
    "# AI Context Mind Map",
    "",
    "> Compact navigation context for AI assistants. Use FileGraph for exact search and file context.",
    "> Generated locally; no file contents were uploaded or copied.",
    "",
    "## Root Map",
    "",
    "- Google Drive / My Drive",
    "  - Personal, Work, Media, AI, Inventory, Archives, Backups",
    "  - Indexed as cloud metadata; do not download unless explicitly requested",
    "- Local workspace",
    "  - Projects: active code and app repositories",
    "  - AgentDrop-Workspace/reels: saved short-video archive",
    "  - Documents and media: personal working files",
    "- Semantic layer",
    "  - FileGraph SQLite index: ~/.filegraph/filegraph.db",
    "  - Local embeddings: semantic search without rereading full files",
    "",
]

# Drive hierarchy and content profile.
rows = con.execute(
    "SELECT path, kind, ext, is_dir FROM files WHERE path LIKE ? AND is_dir=0",
    (DRIVE + "/%",),
).fetchall()
top = defaultdict(Counter)
for r in rows:
    p = r["path"]
    if not safe(p):
        continue
    rel = p[len(DRIVE) + 1 :]
    root = rel.split("/", 1)[0]
    top[root][r["kind"]] += 1
    top[root]["files"] += 1
drive_items = []
for root, counts in sorted(top.items(), key=lambda x: (-x[1]["files"], x[0].lower())):
    kinds = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()) if k != "files")
    drive_items.append(f"`{root}` — {counts['files']:,} files ({kinds})")
lines += section("Google Drive Map", drive_items[:120])

# Project map: compact direct-child map, with counts and detected project markers.
project_items = []
projects_root = HOME / "Projects"
for root in sorted((p for p in projects_root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
    prefix = str(root) + "/"
    count = con.execute("SELECT COUNT(*) FROM files WHERE path LIKE ?", (prefix + "%",)).fetchone()[0]
    kinds = con.execute(
        "SELECT kind, COUNT(*) c FROM files WHERE path LIKE ? AND is_dir=0 GROUP BY kind ORDER BY c DESC",
        (prefix + "%",),
    ).fetchall()
    markers = []
    for name in ("README.md", "CLAUDE.md", "package.json", "pyproject.toml", "Cargo.toml", "Package.swift"):
        if (root / name).exists():
            markers.append(name)
    kind_text = ", ".join(f"{r['kind']}={r['c']}" for r in kinds[:5])
    marker_text = "; markers: " + ", ".join(markers) if markers else ""
    project_items.append(f"`{root}` — {count:,} indexed records ({kind_text}){marker_text}")
lines += section("Project / Code Mind Map", project_items)

# Reel map: compact topic buckets from sidecar text and hashtags.
buckets = defaultdict(list)
patterns = {
    "AI / agents": r"\b(ai|agent|claude|gpt|llm|ollama|prompt|vibe cod)",
    "Software / web development": r"\b(code|coding|app|web|javascript|python|swift|api|developer|ship)",
    "Security / privacy": r"\b(security|privacy|token|password|vulnerab|rate limit|cyber)",
    "Business / money": r"\b(business|money|sales|marketing|startup|income|invest|finance)",
    "Health / lifestyle": r"\b(health|fitness|workout|food|sleep|mindset|life)",
    "Design / creativity": r"\b(design|creative|art|music|photo|video|edit)",
}
reel_count = 0
reel_video_count = len(list(REELS.glob("*.mp4")))
for p in sorted(REELS.glob("*.txt")):
    text = p.read_text(errors="ignore")[:12000]
    reel_count += 1
    tags = sorted(set(re.findall(r"#[A-Za-z0-9_]+", text)))
    matched = [name for name, pat in patterns.items() if re.search(pat, text, re.I)]
    if not matched:
        matched = ["Unclassified / review"]
    compact = " ".join(text.split())[:180]
    entry = f"`{p.stem}` — {compact}"
    for bucket in matched:
        buckets[bucket].append(entry)
reel_items = [
    f"Saved reels: {reel_video_count} videos + {reel_count} caption sidecars",
    "Each reel has a semantic embedding in FileGraph.",
]
for bucket in sorted(buckets):
    reel_items.append(f"**{bucket}** ({len(buckets[bucket])})")
    reel_items.extend(f"  - {x}" for x in buckets[bucket][:80])
lines += section("Reel Archive Mind Map", reel_items)

lines += [
    "## AI Retrieval Rules",
    "",
    "- Start with this map to choose a domain, then query FileGraph for exact files.",
    "- Prefer semantic search over opening whole folders or rereading all Reel transcripts.",
    "- Google Drive entries are metadata-first; fetch file contents only for the selected result.",
    "- Do not expose credentials, tokens, private keys, or authentication files in summaries.",
    "- For reels, use the reel ID to locate the local video, caption, transcript, and embedding.",
    "",
    "## FileGraph Access",
    "",
    "- Web UI: http://127.0.0.1:8437",
    "- Database: `~/.filegraph/filegraph.db`",
    "- Search tools: `search_files`, `get_file_context`, `list_folder`, `graph_overview`",
    "",
]
OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)
print(f"drive_files={len(rows)} reels={reel_count} projects={len(project_items)}")
