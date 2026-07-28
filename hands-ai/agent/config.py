"""
Hands AI Config Manager
Handles reading/writing ~/.hands/config.json
"""

import json
import os
from pathlib import Path
from typing import Any


HANDS_DIR = Path.home() / ".hands"
CONFIG_PATH = HANDS_DIR / "config.json"

DEFAULTS = {
    "active_provider": "ollama",
    "active_model": "phi4-mini:latest",
    "anthropic_api_key": "",
    "openai_api_key": "",
    "ollama_host": "http://localhost:11434",
}


class ConfigManager:
    def __init__(self):
        self._data: dict[str, Any] = {}
        self._ensure_dir()
        self.load()

    def _ensure_dir(self):
        HANDS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            HANDS_DIR.chmod(0o700)
        except OSError:
            pass

    def load(self) -> dict[str, Any]:
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r") as f:
                    stored = json.load(f)
                self._data = {**DEFAULTS, **stored}
            except (json.JSONDecodeError, OSError):
                self._data = dict(DEFAULTS)
        else:
            self._data = dict(DEFAULTS)
            self.save()
        return self._data

    def save(self):
        fd = os.open(CONFIG_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(self._data, f, indent=2)
        try:
            CONFIG_PATH.chmod(0o600)
        except OSError:
            pass

    def update(self, partial: dict[str, Any]):
        self._data.update(partial)
        self.save()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def get_public(self) -> dict[str, Any]:
        """Return config without exposing secrets — masks API keys."""
        result = {}
        for k, v in self._data.items():
            if "api_key" in k:
                if v:
                    result[k] = "****" + str(v)[-4:] if len(str(v)) > 4 else "****"
                else:
                    result[k] = ""
            else:
                result[k] = v
        return result

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any):
        self._data[key] = value
        self.save()


# Singleton
config = ConfigManager()
