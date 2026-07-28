"""Local agent with tools: web search, page reading, file-graph search, and
media understanding (transcribe audio, watch video frames).

Reasoning runs on local ollama. Only web_search/fetch_page touch the internet.
File and media access is filtered through the user's AI access rules — the
agent sees exactly what any other AI is allowed to see.
"""
import base64
import io
import json
import re
import time
from html.parser import HTMLParser

import httpx

from . import config, db, access
from . import search as searchmod

AGENT_MODEL = "qwen3.6:35b-a3b"
VISION_MODEL = "qwen2.5vl:7b"
WHISPER_SIZE = "base"

_whisper = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    return _whisper


# ---------------------------------------------------------------- web tools

class _TextExtract(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "header", "footer", "nav"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def web_search(query: str) -> str:
    """DuckDuckGo HTML results — no API key, no tracking cookies sent."""
    try:
        r = httpx.get("https://html.duckduckgo.com/html/",
                      params={"q": query},
                      headers={"User-Agent": "Mozilla/5.0 (Macintosh) FileGraph/1.0"},
                      timeout=15, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:
        return f"search failed: {e}"
    results = []
    for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)>',
            r.text, re.S):
        url, title, snippet = m.groups()
        if (dm := re.search(r"uddg=([^&]+)", url)):
            from urllib.parse import unquote
            url = unquote(dm.group(1))
        strip = lambda s: re.sub(r"<[^>]+>", "", s).strip()
        results.append(f"- {strip(title)}\n  {url}\n  {strip(snippet)}")
        if len(results) >= 6:
            break
    return "\n".join(results) or "no results"


def fetch_page(url: str) -> str:
    try:
        r = httpx.get(url, timeout=20, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (Macintosh) FileGraph/1.0"})
        r.raise_for_status()
    except Exception as e:
        return f"fetch failed: {e}"
    p = _TextExtract()
    try:
        p.feed(r.text)
    except Exception:
        return r.text[:4000]
    return "\n".join(p.parts)[:5000]


# --------------------------------------------------------------- file tools

def _allowed(path: str) -> bool:
    con = db.connect()
    ok = access.is_allowed(access.list_rules(con), path)
    con.close()
    return ok


def search_files(query: str, mode: str = "semantic") -> str:
    con = db.connect()
    rows = (searchmod.semantic_search(con, query, 10) if mode == "semantic"
            else searchmod.keyword_search(con, query, 10))
    rules = access.list_rules(con)
    con.close()
    lines = [f"- {r['path']} ({r['kind']})" for r in rows
             if access.is_allowed(rules, r["path"])][:10]
    return "\n".join(lines) or "no matching files"


def get_file_context(path: str) -> str:
    if not _allowed(path):
        return "blocked by the user's privacy rules"
    con = db.connect()
    rel = searchmod.related(con, path)
    con.close()
    if "error" in rel:
        return rel["error"]
    
    parts = [f"File: {path}"]
    if rel.get("linked"):
        parts.append("Linked Files: " + ", ".join(r["path"] for r in rel["linked"]))
    if rel.get("siblings"):
        parts.append("Same Folder: " + ", ".join(r["path"] for r in rel["siblings"]))
    if rel.get("semantic"):
        parts.append("Similar Content: " + ", ".join(r["path"] for r in rel["semantic"]))
    return "\n".join(parts)


def read_file(path: str) -> str:
    if not _allowed(path):
        return "blocked by the user's privacy rules"
    con = db.connect()
    row = con.execute("SELECT preview FROM files WHERE path=?", (path,)).fetchone()
    con.close()
    if row and row["preview"]:
        return row["preview"][:4000]
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read(4000) or "(empty file)"
    except OSError as e:
        return f"cannot read: {e}"


# -------------------------------------------------------------- media tools

def transcribe_media(path: str) -> str:
    """Listen: transcribe the audio track of any audio/video file."""
    if not _allowed(path):
        return "blocked by the user's privacy rules"
    try:
        model = _get_whisper()
        segments, info = model.transcribe(path, vad_filter=True)
        out = []
        for seg in segments:
            out.append(f"[{int(seg.start)//60}:{int(seg.start)%60:02d}] {seg.text.strip()}")
            if sum(len(s) for s in out) > 6000:
                out.append("… (truncated)")
                break
        head = f"(language: {info.language}, duration: {int(info.duration)}s)\n"
        return head + ("\n".join(out) or "(no speech detected)")
    except Exception as e:
        return f"transcription failed: {e}"


def _sample_frames(path: str, count: int = 4) -> list[bytes]:
    import av
    from PIL import Image
    frames = []
    with av.open(path) as container:
        stream = container.streams.video[0]
        duration = float(stream.duration * stream.time_base) if stream.duration else 60
        for i in range(count):
            ts = duration * (i + 0.5) / count
            container.seek(int(ts / stream.time_base), stream=stream)
            for frame in container.decode(stream):
                img = frame.to_image()
                img.thumbnail((768, 768), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, "JPEG", quality=80)
                frames.append(buf.getvalue())
                break
    return frames


def watch_video(path: str) -> str:
    """Watch: describe sampled frames with a local vision model, plus the
    audio transcript."""
    if not _allowed(path):
        return "blocked by the user's privacy rules"
    parts = []
    try:
        frames = _sample_frames(path)
        for i, jpeg in enumerate(frames):
            r = httpx.post(f"{config.OLLAMA_URL}/api/chat", json={
                "model": VISION_MODEL,
                "stream": False,
                "messages": [{
                    "role": "user",
                    "content": "Describe this video frame in 1-2 sentences.",
                    "images": [base64.b64encode(jpeg).decode()],
                }],
            }, timeout=180)
            r.raise_for_status()
            desc = r.json()["message"]["content"].strip()
            parts.append(f"Frame {i + 1}/{len(frames)}: {desc}")
    except Exception as e:
        parts.append(f"(frame analysis failed: {e})")
    parts.append("\nAudio transcript:\n" + transcribe_media(path))
    return "\n".join(parts)


# --------------------------------------------------------------- agent loop

TOOLS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Search the web. Returns titles, URLs and snippets.",
        "parameters": {"type": "object", "required": ["query"],
                       "properties": {"query": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "fetch_page",
        "description": "Fetch a web page and return its readable text.",
        "parameters": {"type": "object", "required": ["url"],
                       "properties": {"url": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "search_files",
        "description": "Search the user's local file knowledge graph. "
                       "mode='semantic' (by meaning) or 'keyword' (by name).",
        "parameters": {"type": "object", "required": ["query"],
                       "properties": {"query": {"type": "string"},
                                      "mode": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "get_file_context",
        "description": "Get file relations, siblings, and semantically similar files.",
        "parameters": {"type": "object", "required": ["path"],
                       "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read the text content of a local file by absolute path.",
        "parameters": {"type": "object", "required": ["path"],
                       "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "transcribe_media",
        "description": "Listen to a local audio or video file: transcribe its "
                       "speech with timestamps.",
        "parameters": {"type": "object", "required": ["path"],
                       "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "watch_video",
        "description": "Watch a local video file: describe sampled frames "
                       "visually AND transcribe the audio.",
        "parameters": {"type": "object", "required": ["path"],
                       "properties": {"path": {"type": "string"}}}}},
]

TOOL_FNS = {
    "web_search": lambda a: web_search(a.get("query", "")),
    "fetch_page": lambda a: fetch_page(a.get("url", "")),
    "search_files": lambda a: search_files(a.get("query", ""), a.get("mode", "semantic")),
    "get_file_context": lambda a: get_file_context(a.get("path", "")),
    "read_file": lambda a: read_file(a.get("path", "")),
    "transcribe_media": lambda a: transcribe_media(a.get("path", "")),
    "watch_video": lambda a: watch_video(a.get("path", "")),
}

SYSTEM = """You are the File Graph agent, running fully locally on the user's \
Mac. You can search the web, read pages, search the user's indexed files, read \
files, transcribe audio, and watch videos (frames + transcript). Use tools \
whenever they would help; chain them as needed. Cite file paths and URLs you \
used. Be concise and friendly. Today's date: {date}."""


def run_agent(user_message: str, history: list[dict]):
    """Generator yielding SSE-ready event dicts."""
    messages = ([{"role": "system",
                  "content": SYSTEM.format(date=time.strftime("%B %d, %Y"))}]
                + history + [{"role": "user", "content": user_message}])
    for _ in range(8):
        try:
            r = httpx.post(f"{config.OLLAMA_URL}/api/chat", json={
                "model": AGENT_MODEL, "messages": messages,
                "tools": TOOLS, "stream": False,
            }, timeout=300)
            r.raise_for_status()
            msg = r.json()["message"]
        except Exception as e:
            yield {"type": "error", "text": f"agent model error: {e}"}
            return
        calls = msg.get("tool_calls") or []
        if not calls:
            yield {"type": "final", "text": msg.get("content", "").strip()}
            return
        messages.append(msg)
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            yield {"type": "tool", "name": name,
                   "detail": json.dumps(args)[:200]}
            result = (TOOL_FNS[name](args) if name in TOOL_FNS
                      else f"unknown tool {name}")
            messages.append({"role": "tool", "content": str(result)[:8000]})
    yield {"type": "final", "text": "I hit my step limit — try a narrower question."}
