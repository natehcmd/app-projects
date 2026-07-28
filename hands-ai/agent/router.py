"""
Hands AI Provider Router
Selects the right provider, handles auto-selection and routing.
"""

import logging
from typing import AsyncIterator

from config import config
from providers import OllamaProvider, ClaudeProvider, OpenAIProvider, BaseProvider

logger = logging.getLogger(__name__)


class ProviderRouter:
    def __init__(self):
        self.ollama = OllamaProvider()
        self.claude = ClaudeProvider()
        self.openai = OpenAIProvider()

        self._providers = {
            "ollama": self.ollama,
            "claude": self.claude,
            "openai": self.openai,
        }

    def get_provider(self, name: str) -> BaseProvider | None:
        return self._providers.get(name)

    async def get_active_provider(self) -> tuple[str, BaseProvider]:
        """Return (provider_name, provider_instance) for the currently configured provider."""
        active = config.get("active_provider", "auto")
        if active == "auto":
            return await self.auto_select()

        provider = self._providers.get(active)
        if provider and await provider.is_available():
            return active, provider

        # Configured provider not available — fall back
        logger.warning(f"Configured provider '{active}' not available, falling back to auto-select")
        return await self.auto_select()

    async def auto_select(self) -> tuple[str, BaseProvider]:
        """Pick the best available provider: Ollama > Claude > OpenAI."""
        if await self.ollama.is_available():
            return "ollama", self.ollama
        if await self.claude.is_available():
            return "claude", self.claude
        if await self.openai.is_available():
            return "openai", self.openai
        # Return Claude as default even if no key — error message will be informative
        return "claude", self.claude

    async def route_chat(
        self,
        messages: list[dict],
        stream: bool = True,
    ) -> AsyncIterator[str]:
        """Route a chat request to the active provider."""
        provider_name, provider = await self.get_active_provider()
        logger.info(f"Routing to provider: {provider_name}")
        async for token in provider.chat(messages, stream=stream):
            yield token

    async def list_all_models(self) -> list[dict]:
        """Gather models from all providers, marking availability."""
        results = []
        for name, provider in self._providers.items():
            available = await provider.is_available()
            models = await provider.list_models()
            for m in models:
                results.append({**m, "available": available})
        return results

    async def get_status(self) -> dict:
        """Return current status including active provider/model."""
        provider_name, _ = await self.get_active_provider()
        return {
            "active_provider": provider_name,
            "active_model": config.get("active_model", "auto"),
            "providers": {
                name: await provider.is_available()
                for name, provider in self._providers.items()
            },
        }


# Singleton
router = ProviderRouter()
