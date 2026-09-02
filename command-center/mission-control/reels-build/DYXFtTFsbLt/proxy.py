#!/usr/bin/env python3
"""
claude-code-ollama-proxy
========================

A tiny local HTTP proxy that translates the Anthropic "Messages API"
(what the Claude Code CLI speaks) into Ollama's local chat API, so you
can point Claude Code at a locally-running open-source model (e.g.
Qwen2.5-Coder) instead of Anthropic's cloud.

No external dependencies -- Python standard library only.

Run:
    python3 proxy.py

Then in another terminal:
    export ANTHROPIC_BASE_URL=http://localhost:8787
    export ANTHROPIC_API_KEY=local-not-checked   # any non-empty string
    claude

See README.md for full setup instructions.
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Config (override via environment variables)
# ---------------------------------------------------------------------------

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
# The local model to actually use, regardless of what "model" the caller
# (Claude Code) asked for -- Claude Code will ask for e.g. "claude-3-5-sonnet",
# which obviously doesn't exist locally, so we always redirect to this.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4-mini")
LISTEN_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("PROXY_PORT", "8787"))


def log(*args):
    print(f"[proxy] {' '.join(str(a) for a in args)}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Format translation helpers
# ---------------------------------------------------------------------------

def extract_text(content):
    """Anthropic message 'content' can be a plain string or a list of
    content blocks ({"type": "text", "text": "..."}), possibly mixed with
    tool_use/tool_result blocks. We flatten to plain text for Ollama."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                parts.append(block.get("text", ""))
            elif btype == "tool_result":
                inner = block.get("content", "")
                parts.append(extract_text(inner) if not isinstance(inner, str) else inner)
            elif btype == "tool_use":
                parts.append(f"[tool call: {block.get('name')}({json.dumps(block.get('input', {}))})]")
        return "\n".join(p for p in parts if p)
    return ""


def anthropic_to_ollama(body):
    """Build an Ollama /api/chat request from an Anthropic Messages request."""
    messages = []
    system = body.get("system")
    if system:
        sys_text = extract_text(system) if not isinstance(system, str) else system
        if sys_text:
            messages.append({"role": "system", "content": sys_text})

    for m in body.get("messages", []):
        role = m.get("role", "user")
        if role not in ("user", "assistant", "system"):
            role = "user"
        messages.append({"role": role, "content": extract_text(m.get("content", ""))})

    return {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": bool(body.get("stream", False)),
        "options": {
            "temperature": body.get("temperature", 0.7),
        },
    }


def ollama_chat(payload, stream):
    """POST to Ollama's /api/chat endpoint. Returns either a parsed dict
    (non-streaming) or a generator of parsed line dicts (streaming)."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=600)

    if not stream:
        return json.loads(resp.read().decode("utf-8"))

    def gen():
        for raw_line in resp:
            line = raw_line.decode("utf-8").strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

    return gen()


def build_anthropic_response(model_name, ollama_result):
    """Wrap an Ollama chat completion in an Anthropic-shaped response."""
    text = ollama_result.get("message", {}).get("content", "")
    prompt_tokens = ollama_result.get("prompt_eval_count", 0)
    completion_tokens = ollama_result.get("eval_count", 0)
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model_name,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": prompt_tokens,
            "output_tokens": completion_tokens,
        },
    }


def sse_event(event_type, data):
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        log(fmt % args)

    def _send_json(self, status, obj):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send_json(200, {"ok": True, "ollama_url": OLLAMA_URL, "model": OLLAMA_MODEL})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/v1/messages"):
            self._send_json(404, {"error": "unsupported endpoint", "path": self.path})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        wants_stream = bool(body.get("stream", False))
        ollama_payload = anthropic_to_ollama(body)
        model_name = body.get("model", OLLAMA_MODEL)

        try:
            if wants_stream:
                self._handle_stream(ollama_payload, model_name)
            else:
                result = ollama_chat(ollama_payload, stream=False)
                self._send_json(200, build_anthropic_response(model_name, result))
        except urllib.error.URLError as e:
            log("Could not reach Ollama:", e)
            self._send_json(502, {
                "error": {
                    "type": "api_error",
                    "message": f"Could not reach Ollama at {OLLAMA_URL} ({e}). "
                               f"Is `ollama serve` running and is the model pulled?",
                }
            })

    def _handle_stream(self, ollama_payload, model_name):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
        self.wfile.write(sse_event("message_start", {
            "type": "message_start",
            "message": {
                "id": msg_id, "type": "message", "role": "assistant",
                "model": model_name, "content": [],
                "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        }))
        self.wfile.write(sse_event("content_block_start", {
            "type": "content_block_start", "index": 0,
            "content_block": {"type": "text", "text": ""},
        }))

        completion_tokens = 0
        for chunk in ollama_chat(ollama_payload, stream=True):
            piece = chunk.get("message", {}).get("content", "")
            if piece:
                self.wfile.write(sse_event("content_block_delta", {
                    "type": "content_block_delta", "index": 0,
                    "delta": {"type": "text_delta", "text": piece},
                }))
                self.wfile.flush()
            if chunk.get("done"):
                completion_tokens = chunk.get("eval_count", completion_tokens)

        self.wfile.write(sse_event("content_block_stop", {"type": "content_block_stop", "index": 0}))
        self.wfile.write(sse_event("message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn", "stop_sequence": None},
            "usage": {"output_tokens": completion_tokens},
        }))
        self.wfile.write(sse_event("message_stop", {"type": "message_stop"}))


def main():
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(__doc__)
        print("Config is via environment variables (OLLAMA_URL, OLLAMA_MODEL, "
              "PROXY_HOST, PROXY_PORT) — this script takes no CLI flags.")
        return
    if len(sys.argv) > 1:
        log(f"Unrecognized argument(s): {' '.join(sys.argv[1:])}. This script takes no "
            "CLI flags — configure via environment variables instead. Run with --help.")
        sys.exit(2)

    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler)
    log(f"Listening on http://{LISTEN_HOST}:{LISTEN_PORT}")
    log(f"Forwarding to Ollama at {OLLAMA_URL}, using model '{OLLAMA_MODEL}'")
    log("Set ANTHROPIC_BASE_URL to this address before running `claude`.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
