"""
Abstract base class for all LLM providers.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional


@dataclass
class Message:
    role: str                       # system | user | assistant | tool
    content: str
    name: Optional[str] = None      # tool name when role == "tool"
    tool_calls: Optional[list] = None


@dataclass
class ProviderResponse:
    content: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    tool_calls: list = field(default_factory=list)
    raw: Any = None


class BaseProvider(ABC):
    """All LLM providers implement this interface."""

    provider_name: str = "base"

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
        stream: bool = False,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the required API key / env vars are set."""
        ...

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _timer_ms() -> float:
        return time.monotonic() * 1_000

    def _messages_to_dicts(self, messages: list[Message]) -> list[dict]:
        result = []
        for m in messages:
            d: dict = {"role": m.role, "content": m.content}
            if m.name:
                d["name"] = m.name
            if m.tool_calls:
                d["tool_calls"] = m.tool_calls
            result.append(d)
        return result
