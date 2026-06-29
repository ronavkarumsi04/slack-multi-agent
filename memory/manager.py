"""
Memory manager — stores per-agent conversation history and learned skills.

Backends:
  • In-process dict (default, fast, ephemeral)
  • Redis (recommended for production, set REDIS_URL)

Features:
  • Per-channel, per-thread context windows
  • Automatic summarisation when history exceeds threshold
  • Skill extraction and persistence (Hermes/NemoClaw-style)
  • Channel-wide "ambient" memory for shared context
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from providers.base import Message

log = logging.getLogger(__name__)


class MemoryManager:
    """
    Manages multi-level memory for all agents:
      1. Thread-level (short-term) — full message history per thread
      2. Channel-level (medium-term) — summarised context per channel
      3. Agent-level (long-term) — learned skills and preferences
    """

    def __init__(self):
        # {agent_name: {channel: {thread_ts: [Message, ...]}}}
        self._threads: dict[str, dict[str, dict[str, list[dict]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        # {agent_name: {channel: "summary text"}}
        self._channel_summaries: dict[str, dict[str, str]] = defaultdict(dict)
        # {agent_name: [skill_text, ...]}
        self._skills: dict[str, list[str]] = defaultdict(list)

        self._redis = None
        self._try_connect_redis()

    def _try_connect_redis(self):
        try:
            from config.settings import settings
            if settings.redis_url and settings.redis_url != "redis://localhost:6379/0":
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
                log.info("Memory: connected to Redis at %s", settings.redis_url)
        except Exception as exc:
            log.info("Memory: using in-process store (%s)", exc)

    # ─────────────────────────────────────────────────────────────────────────
    # Thread-level memory
    # ─────────────────────────────────────────────────────────────────────────

    async def add_message(
        self,
        agent: str,
        channel: str,
        thread_ts: str,
        role: str,
        content: str,
    ):
        msg = {"role": role, "content": content, "ts": datetime.utcnow().isoformat()}

        if self._redis:
            key = f"mem:{agent}:{channel}:{thread_ts}"
            await self._redis.rpush(key, json.dumps(msg))
            await self._redis.expire(key, 86_400 * 7)   # 7-day TTL
        else:
            self._threads[agent][channel][thread_ts].append(msg)

        # Check if summarisation is needed
        await self._maybe_summarise(agent, channel, thread_ts)

    async def get_context(
        self,
        agent: str,
        channel: str,
        thread_ts: str,
        max_messages: int = 50,
    ) -> list[Message]:
        """Return conversation history as provider Message objects."""
        if self._redis:
            key = f"mem:{agent}:{channel}:{thread_ts}"
            raw = await self._redis.lrange(key, -max_messages, -1)
            msgs = [json.loads(r) for r in raw]
        else:
            thread = self._threads[agent][channel][thread_ts]
            msgs = thread[-max_messages:]

        context: list[Message] = []

        # Inject channel summary if available (oldest context first)
        summary = self._channel_summaries.get(agent, {}).get(channel)
        if summary:
            context.append(Message(role="system", content=f"[Channel context summary]\n{summary}"))

        # Inject skills
        skills = self._skills.get(agent, [])
        if skills:
            context.append(Message(role="system", content="[Learned skills]\n" + "\n".join(f"• {s}" for s in skills[-10:])))

        for m in msgs:
            context.append(Message(role=m["role"], content=m["content"]))

        return context

    # ─────────────────────────────────────────────────────────────────────────
    # Automatic summarisation
    # ─────────────────────────────────────────────────────────────────────────

    async def _maybe_summarise(self, agent: str, channel: str, thread_ts: str):
        from agents.registry import registry
        agent_obj = registry.get(agent)
        if not agent_obj:
            return

        threshold = agent_obj.memory.summarise_after
        if not agent_obj.memory.enabled:
            return

        if self._redis:
            key = f"mem:{agent}:{channel}:{thread_ts}"
            length = await self._redis.llen(key)
        else:
            length = len(self._threads[agent][channel][thread_ts])

        if length >= threshold:
            await self._summarise_thread(agent, channel, thread_ts, agent_obj)

    async def _summarise_thread(self, agent: str, channel: str, thread_ts: str, agent_obj):
        """Summarise old messages and store as channel context."""
        try:
            from providers import get_provider
            provider = get_provider(agent_obj.provider)

            if self._redis:
                key = f"mem:{agent}:{channel}:{thread_ts}"
                raw = await self._redis.lrange(key, 0, -1)
                msgs = [json.loads(r) for r in raw]
            else:
                msgs = self._threads[agent][channel][thread_ts]

            conversation = "\n".join(f"{m['role']}: {m['content']}" for m in msgs)
            prompt = f"Summarise the following conversation into 3-5 key points and any decisions made:\n\n{conversation}"

            resp = await provider.chat(
                messages=[Message(role="user", content=prompt)],
                model=agent_obj.model,
                temperature=0.3,
                max_tokens=512,
            )

            self._channel_summaries[agent][channel] = resp.content

            # Keep only last N messages in thread
            keep = agent_obj.memory.summarise_after // 2
            if self._redis:
                # Trim Redis list
                await self._redis.ltrim(key, -keep, -1)
            else:
                self._threads[agent][channel][thread_ts] = msgs[-keep:]

            log.info("Summarised memory for agent=%s channel=%s", agent, channel)

            # Extract skills from summary
            if agent_obj.memory.persist_skills:
                await self._extract_skills(agent, resp.content, provider, agent_obj)

        except Exception as exc:
            log.warning("Memory summarisation failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────
    # Skill extraction (Hermes-style)
    # ─────────────────────────────────────────────────────────────────────────

    async def _extract_skills(self, agent: str, summary: str, provider, agent_obj):
        """Extract reusable procedural knowledge from a conversation summary."""
        try:
            prompt = f"""From the following conversation summary, extract any reusable procedures, 
preferences, or domain knowledge as concise bullet points. Only extract clear, factual patterns.

Summary: {summary}

Respond with a JSON array of strings, or [] if nothing to extract."""

            resp = await provider.chat(
                messages=[Message(role="user", content=prompt)],
                model=agent_obj.model,
                temperature=0.1,
                max_tokens=256,
            )

            import re
            raw = re.search(r'\[.*\]', resp.content, re.DOTALL)
            if raw:
                skills = json.loads(raw.group())
                self._skills[agent].extend(skills)
                log.info("Extracted %d skills for agent=%s", len(skills), agent)
        except Exception as exc:
            log.debug("Skill extraction failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────
    # Direct skill management
    # ─────────────────────────────────────────────────────────────────────────

    def add_skill(self, agent: str, skill: str):
        self._skills[agent].append(skill)
        log.info("Skill added for agent=%s: %s", agent, skill[:80])

    def get_skills(self, agent: str) -> list[str]:
        return list(self._skills.get(agent, []))

    def clear_skills(self, agent: str):
        self._skills[agent] = []

    def clear_context(self, agent: str, channel: str, thread_ts: str):
        if agent in self._threads and channel in self._threads[agent]:
            self._threads[agent][channel].pop(thread_ts, None)

    def get_stats(self) -> dict:
        return {
            "agents_with_memory": len(self._threads),
            "total_channel_summaries": sum(len(v) for v in self._channel_summaries.values()),
            "total_skills": sum(len(v) for v in self._skills.values()),
            "backend": "redis" if self._redis else "in-process",
        }
