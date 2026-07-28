"""
Hands AI Base Provider
Abstract base class all providers must implement.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseProvider(ABC):
    """Abstract base for all AI providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        stream: bool = False,
    ) -> AsyncIterator[str]:
        """
        Send a chat request and yield response tokens.
        messages: list of {"role": "user"/"assistant"/"system", "content": "..."}
        stream: if True, yield tokens as they arrive; if False, yield single full response
        """
        ...

    @abstractmethod
    async def list_models(self) -> list[dict]:
        """
        Return list of available models.
        Each dict: {"id": str, "name": str, "provider": str}
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this provider is currently usable."""
        ...
