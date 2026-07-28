import os
import re
import sys
from pathlib import Path

# Match common function/class definitions for code files
PATTERNS = {
    ".py": [re.compile(r"^\s*(def|class)\s+(\w+)")],
    ".js": [re.compile(r"^\s*(function|class)\s+(\w+)")],
    ".ts": [re.compile(r"^\s*(function|class|interface|type)\s+(\w+)")],
    ".swift": [re.compile(r"^\s*(func|class|struct|protocol|enum)\s+(\w+)")]
}

EXCLUDE_DIRS = {".git", "node_modules", "dist", "build", ".build", "__pycache__", ".venv"}

def generate_map(dir_path: Path, indent=""):
    for item in sorted(dir_path.iterdir()):
        if item.name in EXCLUDE_DIRS or item.name.startswith("."):
            continue
            
        if item.is_dir():
            print(f"{indent}📁 {item.name}/")
            generate_map(item, indent + "  ")
        elif item.suffix in PATTERNS:
            print(f"{indent}📄 {item.name}")
            try:
                with open(item, "r", errors="ignore") as f:
                    for line in f:
                        for pattern in PATTERNS[item.suffix]:
                            match = pattern.match(line)
                            if match:
                                print(f"{indent}  ↳ {line.strip()}")
            except Exception:
                pass

if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    generate_map(target)
