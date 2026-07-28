"""Read a short text preview from files that look like text. Never touches
cloud-streamed files (the scanner guards that) and never reads big files."""
import os
import re
from . import config


def extract_preview(path: str, ext: str, size: int) -> str:
    if size == 0 or size > config.MAX_EXTRACT_BYTES:
        return ""
    if ext not in config.TEXT_EXTS:
        return ""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read(config.EMBED_CHARS)
    except OSError:
        return ""
    # binary sniff: too many replacement/control chars means not really text
    if text.count("\x00") > 0:
        return ""
    return text.strip()


def embedding_text(row) -> str:
    """The text actually fed to the embedding model for a file row."""
    parts = [f"File: {row['name']}", f"Path: {row['path']}", f"Type: {row['kind']}"]
    if row["preview"]:
        parts.append(row["preview"])
    return "\n".join(parts)[: config.EMBED_CHARS]


def extract_relations(text: str, ext: str) -> list[str]:
    """Extract string references (imports, links) that might be file relations."""
    rels = []
    if ext == ".py":
        for m in re.finditer(r'^\s*(?:from\s+([.\w]+)\s+import|import\s+([.\w]+))', text, re.M):
            mod = m.group(1) or m.group(2)
            if mod:
                rels.append(mod.split('.')[0])
    elif ext in (".js", ".ts", ".jsx", ".tsx"):
        for m in re.finditer(r'(?:import.*from|require\()\s*[\'"]([^\'"]+)[\'"]', text):
            rels.append(m.group(1))
    elif ext == ".md":
        for m in re.finditer(r'\[.*?\]\(([^)]+)\)', text):
            tgt = m.group(1)
            if not tgt.startswith("http"):
                rels.append(tgt)
    return list(set(rels))
