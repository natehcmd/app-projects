"""Central configuration for File Graph. Everything is local — no network calls
except to the local ollama instance."""
import os
from pathlib import Path

HOME = Path.home()
APP_DIR = HOME / ".filegraph"
DB_PATH = APP_DIR / "filegraph.db"

OLLAMA_URL = os.environ.get("FILEGRAPH_OLLAMA", "http://127.0.0.1:11434")
EMBED_MODEL = os.environ.get("FILEGRAPH_EMBED_MODEL", "nomic-embed-text")

SERVER_HOST = "127.0.0.1"  # local only, never expose
SERVER_PORT = 8437

# Directory names never descended into (noise / system / huge)
EXCLUDE_DIR_NAMES = {
    "node_modules", ".git", ".svn", ".hg", "__pycache__", ".venv", "venv",
    ".cache", "Caches", ".npm", ".yarn", ".pnpm-store", ".cargo", ".rustup",
    ".gradle", ".m2", ".Trash", ".DS_Store", "DerivedData", ".docker",
    ".ollama", ".vscode-server", "site-packages", ".mypy_cache",
    ".pytest_cache", ".next", "dist", "build", ".terraform", ".filegraph",
}

# Top-level home dirs skipped entirely
EXCLUDE_TOP_LEVEL = {"Library", "Applications", "Public"}

# Bundle-ish dirs treated as a single opaque file
BUNDLE_SUFFIXES = (".app", ".photoslibrary", ".musiclibrary", ".framework",
                   ".xcodeproj", ".playground", ".bundle", ".dmg")

# Cloud-streamed locations: metadata is indexed but contents are NEVER read,
# so we never trigger a download.
CLOUD_MARKERS = ("Google Drive", "OneDrive", "Library/CloudStorage", "Dropbox")

# Extensions we consider text and will extract/embed
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml", ".html",
    ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".rb", ".rs", ".go",
    ".java", ".kt", ".swift", ".c", ".h", ".cpp", ".hpp", ".sh", ".zsh",
    ".bash", ".sql", ".env.example", ".tex", ".r", ".jl", ".lua", ".php",
    ".pl", ".scala", ".vue", ".svelte",
}

KIND_MAP = {
    "code": {".py", ".js", ".jsx", ".ts", ".tsx", ".rb", ".rs", ".go", ".java",
             ".kt", ".swift", ".c", ".h", ".cpp", ".hpp", ".sh", ".zsh",
             ".bash", ".sql", ".r", ".jl", ".lua", ".php", ".pl", ".scala",
             ".vue", ".svelte", ".css", ".html"},
    "doc": {".txt", ".md", ".markdown", ".rst", ".pdf", ".doc", ".docx",
            ".pages", ".rtf", ".tex"},
    "data": {".csv", ".tsv", ".json", ".yaml", ".yml", ".toml", ".xml",
             ".ini", ".cfg", ".conf", ".db", ".sqlite", ".parquet"},
    "image": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".svg",
              ".tiff", ".bmp", ".icns"},
    "video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "audio": {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"},
    "archive": {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".dmg"},
}

MAX_EXTRACT_BYTES = 2 * 1024 * 1024   # don't read files bigger than 2 MB
EMBED_CHARS = 6000                     # chars of content fed to the embedder
PROJECT_MARKERS = {".git", "package.json", "pyproject.toml", "Cargo.toml",
                   "go.mod", "CLAUDE.md", "Makefile", ".project"}


def kind_of(ext: str) -> str:
    ext = ext.lower()
    for kind, exts in KIND_MAP.items():
        if ext in exts:
            return kind
    return "other"


def is_cloud_path(path: str) -> bool:
    return any(m in path for m in CLOUD_MARKERS)
