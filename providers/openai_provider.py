"""OpenAI provider (GPT-4o, GPT-4-turbo, o1, etc.)"""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI, APIError

from .base import BaseProvider, Message, ProviderResponse
from config.settings import settings

log = logging.getLogger(__name__)


class OpenAIProvider(BaseProvider):
    provider_name = "openai"

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    def is_available(self) -> bool:
        return bool(settings.openai_api_key)

    async def chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
        stream: bool = False,
    ) -> ProviderResponse:
        resolved = model or settings.openai_default_model
        t0 = self._timer_ms()
        kwargs: dict[str, Any] = dict(
            model=resolved,
            messages=self._messages_to_dicts(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            resp = await self.client.chat.completions.create(**kwargs)
        except APIError as exc:
            log.error("OpenAI error: %s", exc)
            raise

        choice = resp.choices[0]
        tool_calls_raw = []
        if choice.message.tool_calls:
            tool_calls_raw = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in choice.message.tool_calls
            ]
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
        resolved = model or settings.openai_default_model
        stream = await self.client.chat.completions.create(
            model=resolved,
            messages=self._messages_to_dicts(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
