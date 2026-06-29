"""Groq provider (Llama 3.1 70B, Mixtral, Gemma2)."""
from __future__ import annotations

import logging
from typing import AsyncIterator, Optional

from groq import AsyncGroq

from .base import BaseProvider, Message, ProviderResponse
from config.settings import settings

log = logging.getLogger(__name__)


class GroqProvider(BaseProvider):
    provider_name = "groq"

    def __init__(self):
        self._client: Optional[AsyncGroq] = None

    @property
    def client(self) -> AsyncGroq:
        if self._client is None:
            self._client = AsyncGroq(api_key=settings.groq_api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(settings.groq_api_key)

    async def chat(self, messages, model=None, temperature=0.7, max_tokens=2048, tools=None, stream=False) -> ProviderResponse:
        resolved = model or settings.groq_default_model
        t0 = self._timer_ms()
        kwargs = dict(model=resolved, messages=self._messages_to_dicts(messages), temperature=temperature, max_tokens=max_tokens)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = await self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        tool_calls_raw = []
        if choice.message.tool_calls:
            tool_calls_raw = [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in choice.message.tool_calls]
        return ProviderResponse(
            content=choice.message.content or "",
            model=resolved,
            provider=self.provider_name,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            latency_ms=self._timer_ms() - t0,
            tool_calls=tool_calls_raw,
            raw=resp,
        )

    async def stream_chat(self, messages, model=None, temperature=0.7, max_tokens=2048) -> AsyncIterator[str]:
        resolved = model or settings.groq_default_model
        stream = await self.client.chat.completions.create(
            model=resolved, messages=self._messages_to_dicts(messages),
            temperature=temperature, max_tokens=max_tokens, stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
