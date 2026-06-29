"""
NVIDIA NIM provider — first-class integration.

Supports:
  • nvidia/llama-3.1-nemotron-70b-instruct (default)
  • nvidia/nemotron-4-340b-instruct
  • mistralai/mixtral-8x22b-instruct-v0.1  (via NIM)
  • meta/llama-3.1-405b-instruct           (via NIM)
  • nv-mistralai/mistral-nemo-12b-instruct
  • Any other model available on integrate.api.nvidia.com

NIM uses an OpenAI-compatible REST API so we reuse the openai SDK.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Optional

from openai import AsyncOpenAI, APIError

from .base import BaseProvider, Message, ProviderResponse
from config.settings import settings

log = logging.getLogger(__name__)

# All Nemotron / NIM model aliases
NIM_MODELS = {
    "nemotron-70b":   "nvidia/llama-3.1-nemotron-70b-instruct",
    "nemotron-340b":  "nvidia/nemotron-4-340b-instruct",
    "nemotron-nano":  "nvidia/llama-3.2-nemo-instruct",
    "llama3-405b":    "meta/llama-3.1-405b-instruct",
    "mixtral-8x22b":  "mistralai/mixtral-8x22b-instruct-v0.1",
    "mistral-nemo":   "nv-mistralai/mistral-nemo-12b-instruct",
    "hermes3-70b":    "nvidia/hermes-3-llama-3.1-70b",
    "hermes3-8b":     "nvidia/hermes-3-llama-3.1-8b",
}


class NIMProvider(BaseProvider):
    provider_name = "nim"

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.nim_api_key or "no-key",
                base_url=settings.nim_base_url,
                timeout=settings.nim_timeout,
            )
        return self._client

    def is_available(self) -> bool:
        return bool(settings.nim_api_key)

    def _resolve_model(self, model: Optional[str]) -> str:
        m = model or settings.nim_default_model
        return NIM_MODELS.get(m, m)

    async def chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools: Optional[list[dict]] = None,
        stream: bool = False,
    ) -> ProviderResponse:
        resolved = self._resolve_model(model)
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
            log.error("NIM API error: %s", exc)
            raise

        choice = resp.choices[0]
        content = choice.message.content or ""
        tool_calls_raw = []

        if choice.message.tool_calls:
            tool_calls_raw = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return ProviderResponse(
            content=content,
            model=resolved,
            provider=self.provider_name,
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
            latency_ms=self._timer_ms() - t0,
            tool_calls=tool_calls_raw,
            raw=resp,
        )

    async def stream_chat(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        resolved = self._resolve_model(model)
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

    # ── NIM-specific: list available models ──────────────────────────────────
    async def list_models(self) -> list[str]:
        try:
            resp = await self.client.models.list()
            return [m.id for m in resp.data]
        except Exception as exc:
            log.warning("Could not list NIM models: %s", exc)
            return list(NIM_MODELS.values())
