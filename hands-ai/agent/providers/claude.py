"""
Hands AI Claude / Anthropic Provider
Uses the official anthropic SDK with streaming support.
"""

import logging
from typing import AsyncIterator

from .base import BaseProvider
from config import config

logger = logging.getLogger(__name__)

CLAUDE_MODELS = [
    {"id": "claude-opus-4-7", "name": "Claude Opus 4.7", "provider": "claude"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "claude"},
    {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "provider": "claude"},
]


class ClaudeProvider(BaseProvider):
    PROVIDER_NAME = "claude"

    def _get_client(self):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError("anthropic package not installed")
        api_key = config.get("anthropic_api_key", "")
        if not api_key:
            raise RuntimeError("Anthropic API key not set. Run: hands config set anthropic-key <key>")
        return anthropic.AsyncAnthropic(api_key=api_key)

    async def is_available(self) -> bool:
        return bool(config.get("anthropic_api_key", ""))

    async def list_models(self) -> list[dict]:
        return CLAUDE_MODELS

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

        model = config.get("active_model", "claude-sonnet-4-6")
        if model == "auto":
            model = "claude-sonnet-4-6"
        # Strip provider prefix if present
        if "/" in model and model.startswith("claude/"):
            model = model.split("/", 1)[1]

        # Separate system messages from conversation
        system_content = None
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs = {
            "model": model,
            "max_tokens": 8096,
            "messages": chat_messages,
        }
        if system_content:
            kwargs["system"] = system_content

        try:
            async with client.messages.stream(**kwargs) as stream_ctx:
                async for text in stream_ctx.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Claude chat error: {e}")
            yield f"[Hands AI] Claude error: {e}"
