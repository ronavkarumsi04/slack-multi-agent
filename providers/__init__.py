"""
Provider registry — auto-detects which providers are available
based on environment variables.
"""
from __future__ import annotations

from typing import Optional

from .base import BaseProvider, Message, ProviderResponse
from .nim_provider import NIMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .groq_provider import GroqProvider

_PROVIDER_MAP = {
    "nim": NIMProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "groq": GroqProvider,
}

_instances: dict[str, BaseProvider] = {}


def get_provider(name: str) -> BaseProvider:
    """Return a (cached) provider instance by name."""
    if name not in _instances:
        cls = _PROVIDER_MAP.get(name)
        if cls is None:
            raise ValueError(f"Unknown provider: {name}. Available: {list(_PROVIDER_MAP)}")
        _instances[name] = cls()
    return _instances[name]


def available_providers() -> list[str]:
    """Return names of providers whose API keys are configured."""
    return [name for name, cls in _PROVIDER_MAP.items() if cls().is_available()]


def default_provider() -> BaseProvider:
    """Return NIM if available, else first available provider."""
    for name in ["nim", "openai", "anthropic", "groq"]:
        p = get_provider(name)
        if p.is_available():
            return p
    raise RuntimeError("No LLM provider configured. Set at least one API key in .env")


__all__ = [
    "BaseProvider", "Message", "ProviderResponse",
    "NIMProvider", "OpenAIProvider", "AnthropicProvider", "GroqProvider",
    "get_provider", "available_providers", "default_provider",
]
