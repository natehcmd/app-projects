"""
Hands AI Ollama Provider
Talks to a local Ollama instance via HTTP.
"""

import json
import logging
from typing import AsyncIterator

import httpx

from .base import BaseProvider
from config import config

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    PROVIDER_NAME = "ollama"

    def _host(self) -> str:
        return config.get("ollama_host", "http://localhost:11434")

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self._host()}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._host()}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = data.get("models", [])
                return [
                    {
                        "id": m["name"],
                        "name": m["name"],
                        "provider": self.PROVIDER_NAME,
                        "size": m.get("size"),
                        "modified_at": m.get("modified_at"),
                    }
                    for m in models
                ]
        except Exception as e:
            logger.warning(f"Ollama list_models failed: {e}")
            return []

    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        model = config.get("active_model", "llama3.2")
        if model == "auto":
            models = await self.list_models()
            model = models[0]["id"] if models else "llama3.2"
        # Strip provider prefix if present (e.g. "ollama/llama3.2" → "llama3.2")
        if "/" in model and model.startswith("ollama/"):
            model = model.split("/", 1)[1]

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self._host()}/api/chat",
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield token
                            if chunk.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
        except httpx.ConnectError:
            yield "[Hands AI] Ollama is not running. Start it with `ollama serve` or switch providers."
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            yield f"[Hands AI] Ollama error: {e}"
