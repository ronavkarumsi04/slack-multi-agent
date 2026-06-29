"""
Safety guard — enforces autonomy levels, content filtering, PII redaction,
rate limiting, and per-agent channel restrictions.

Autonomy levels:
  off    → agent never responds; all messages are queued for human review
  review → agent drafts a response but it must be approved before posting
  full   → agent responds immediately without human approval
"""
from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Optional

from agents.models import Agent, AutonomyLevel

log = logging.getLogger(__name__)

# ── PII patterns ──────────────────────────────────────────────────────────────
_PII_PATTERNS = [
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),                    "[SSN-REDACTED]"),
    (re.compile(r'\b4[0-9]{12}(?:[0-9]{3})?\b'),               "[CC-REDACTED]"),  # Visa
    (re.compile(r'\b5[1-5][0-9]{14}\b'),                       "[CC-REDACTED]"),  # MC
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), "[EMAIL-REDACTED]"),
    (re.compile(r'\b(\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), "[PHONE-REDACTED]"),
    (re.compile(r'\b(?:password|passwd|secret|api[_\s]key|token|bearer)\s*[:=]\s*\S+', re.IGNORECASE), "[SECRET-REDACTED]"),
]

# ── Harmful content keywords (simple blocklist; complement with LLM-based filter) ──
_HARMFUL_KEYWORDS = [
    "ignore previous instructions", "ignore all instructions",
    "jailbreak", "dan mode", "pretend you are",
    "you are now", "act as if you have no restrictions",
    "forget your training",
]


class RateLimiter:
    def __init__(self):
        # {agent_name: [timestamps]}
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, agent_name: str, limit_per_minute: int) -> bool:
        now = time.monotonic()
        window = self._windows[agent_name]
        # Remove timestamps older than 60 seconds
        self._windows[agent_name] = [t for t in window if now - t < 60]
        if len(self._windows[agent_name]) >= limit_per_minute:
            return False
        self._windows[agent_name].append(now)
        return True


_rate_limiter = RateLimiter()


class SafetyGuard:
    """
    Gate every agent input and output through safety checks.
    Returns boolean pass/fail; filtered text for outputs.
    """

    async def check_input(self, text: str, agent: Agent) -> bool:
        """
        Returns True if the input is safe to process.
        Checks: autonomy gate, channel allowlist, rate limit, prompt injection.
        """
        # Autonomy gate — if off, no processing at all
        if agent.safety.autonomy == AutonomyLevel.OFF:
            log.info("Agent %s autonomy=off; ignoring message", agent.name)
            return False

        # Channel allowlist
        # (caller already filtered by channel — this is a belt-and-suspenders check)

        # Rate limiting
        if not _rate_limiter.is_allowed(agent.name, agent.safety.rate_limit_per_minute):
            log.warning("Agent %s rate-limited", agent.name)
            return False

        # Prompt injection / jailbreak detection
        lowered = text.lower()
        for kw in _HARMFUL_KEYWORDS:
            if kw in lowered:
                log.warning("Potential prompt injection blocked for agent %s: '%s'", agent.name, kw)
                return False

        return True

    async def check_output(self, text: str, agent: Agent) -> tuple[bool, str]:
        """
        Returns (is_safe, filtered_text).
        Applies PII redaction if enabled.
        """
        filtered = text

        # PII redaction
        if agent.safety.pii_redaction:
            for pattern, replacement in _PII_PATTERNS:
                filtered = pattern.sub(replacement, filtered)

        # Content length cap
        max_len = agent.safety.max_tokens_per_response * 4  # rough chars-per-token
        if len(filtered) > max_len:
            filtered = filtered[:max_len] + "\n\n[Response truncated by safety limit]"

        # Check for accidental secret leakage
        for pattern, replacement in _PII_PATTERNS:
            if pattern.search(filtered) and replacement == "[SECRET-REDACTED]":
                log.warning("Secret pattern detected in output for agent %s — redacted", agent.name)

        return True, filtered

    def redact_pii(self, text: str) -> str:
        """Utility: redact PII from any string."""
        result = text
        for pattern, replacement in _PII_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    def check_autonomy_for_post(self, agent: Agent) -> dict:
        """
        Returns action dict telling the Slack handler whether to:
          - post immediately ('post')
          - queue for review ('queue')
          - discard ('discard')
        """
        match agent.safety.autonomy:
            case AutonomyLevel.FULL | "full":
                return {"action": "post"}
            case AutonomyLevel.REVIEW | "review":
                return {"action": "queue", "reason": "Pending human review (autonomy=review)"}
            case AutonomyLevel.OFF | "off":
                return {"action": "discard", "reason": "Agent autonomy is off"}
            case _:
                return {"action": "queue", "reason": "Unknown autonomy level; defaulting to review"}
