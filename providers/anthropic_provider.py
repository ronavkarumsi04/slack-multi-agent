"""Anthropic provider (Claude 3.5 Sonnet, Haiku, Opus)."""
from __future__ import annotations

import logging
from typing import AsyncIterator, Optional

import anthropic
from anthropic import AsyncAnthropic

from .base import BaseProvider, Message, ProviderResponse
from config.settings import settings

log = logging.getLogger(__name__)


class AnthropicProvider(BaseProvider):
    provider_name = "anthropic"

    def __init__(self):
        self._client: Optional[AsyncAnthropic] = None

    @property
    def client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _split_system(self, messages: list[Message]):
        """Anthropic requires system message separate from conversation."""
        system = ""
        conv = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                conv.append({"role": m.role, "content": m.content})
        return system, conv

    async def chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
        stream: bool = False,
    ) -> ProviderResponse:
        resolved = model or settings.anthropic_default_model
        system, conv = self._split_system(messages)
        t0 = self._timer_ms()

        kwargs = dict(model=resolved, max_tokens=max_tokens, messages=conv, temperature=temperature)
        if system:
            kwargs["system"] = system
        if tools:
            # Convert OpenAI-style tool defs to Anthropic format
            kwargs["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in tools
            ]

        resp = await self.client.messages.create(**kwargs)
        content = ""
        tool_calls_raw = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls_raw.append({"id": block.id, "type": "function", "function": {"name": block.name, "arguments": str(block.input)}})

        return ProviderResponse(
            content=content,
            model=resolved,
            provider=self.provider_name,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            latency_ms=self._timer_ms() - t0,
            tool_calls=tool_calls_raw,
            raw=resp,
        )

    async def stream_chat(self, messages, model=None, temperature=0.7, max_tokens=2048) -> AsyncIterator[str]:
        resolved = model or settings.anthropic_default_model
        system, conv = self._split_system(messages)
        kwargs = dict(model=resolved, max_tokens=max_tokens, messages=conv, temperature=temperature)
        if system:
            kwargs["system"] = system
        async with self.client.messages.stream(**kwargs) as s:
            async for text in s.text_stream:
                yield text
