"""
Hands AI OpenAI / Codex Provider
Uses the official openai SDK with streaming support.
"""

import logging
from typing import AsyncIterator

from .base import BaseProvider
from config import config

logger = logging.getLogger(__name__)

OPENAI_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
    {"id": "o3", "name": "o3", "provider": "openai"},
    {"id": "o4-mini", "name": "o4-mini", "provider": "openai"},
]


class OpenAIProvider(BaseProvider):
    PROVIDER_NAME = "openai"

    def _get_client(self):
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai package not installed")
        api_key = config.get("openai_api_key", "")
        if not api_key:
            raise RuntimeError("OpenAI API key not set. Run: hands config set openai-key <key>")
        return openai.AsyncOpenAI(api_key=api_key)

    async def is_available(self) -> bool:
        return bool(config.get("openai_api_key", ""))

    async def list_models(self) -> list[dict]:
        return OPENAI_MODELS

    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        try:
            client = self._get_client()
        except RuntimeError as e:
            yield f"[Hands AI] {e}"
            return

        model = config.get("active_model", "gpt-4o")
        if model == "auto":
            model = "gpt-4o"
        # Strip provider prefix if present
        if "/" in model and model.startswith("openai/"):
            model = model.split("/", 1)[1]

        try:
            stream_response = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
            )
            async for chunk in stream_response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            yield f"[Hands AI] OpenAI error: {e}"
