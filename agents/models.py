"""
Pydantic models for Agent specs, Tasks, and Registration payloads.
These are the canonical data types used throughout the system.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, validator


# ── Enums ────────────────────────────────────────────────────────────────────

class AutonomyLevel(str, Enum):
    OFF    = "off"      # never auto-respond; human approval required for every message
    REVIEW = "review"   # agent drafts a reply, human approves before sending
    FULL   = "full"     # agent acts autonomously

class AgentRole(str, Enum):
    ENGINEER        = "engineer"
    OPS             = "ops"
    SUPPORT         = "support"
    PM              = "pm"
    RESEARCHER      = "researcher"
    DATA_ANALYST    = "data_analyst"
    SECURITY        = "security"
    ORCHESTRATOR    = "orchestrator"
    CUSTOM          = "custom"

class TaskStatus(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    WAITING     = "waiting"      # waiting for human review
    DONE        = "done"
    FAILED      = "failed"
    DELEGATED   = "delegated"

class TaskPriority(str, Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    URGENT = "urgent"


# ── Agent Spec (input to /api/register) ──────────────────────────────────────

class ToolConfig(BaseModel):
    name: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)

class MemoryConfig(BaseModel):
    enabled: bool = True
    max_context_messages: int = 50
    summarise_after: int = 20           # summarise when history > N messages
    persist_skills: bool = True

class SafetyConfig(BaseModel):
    autonomy: AutonomyLevel = AutonomyLevel.REVIEW
    content_filter: bool = True
    pii_redaction: bool = True
    max_tokens_per_response: int = 2048
    rate_limit_per_minute: int = 30
    allowed_channels: list[str] = Field(default_factory=list)  # empty = all

class ChannelSpec(BaseModel):
    name: str                           # without the # prefix
    description: str = ""
    is_private: bool = False
    topic: str = ""

class AgentSpec(BaseModel):
    """
    Full specification for a single agent — sent in the registration payload.

    Example YAML (converted to this model):
      name: eng-bot
      display_name: "Engineering Bot"
      role: engineer
      provider: nim
      model: nemotron-70b
      channels:
        - engineering
        - incidents
      tools:
        - name: github
          enabled: true
      autonomy: review
    """
    name: str = Field(..., pattern=r"^[a-z0-9\-]+$")
    display_name: str = ""
    role: AgentRole = AgentRole.CUSTOM
    description: str = ""
    system_prompt: Optional[str] = None     # overrides role default if provided
    provider: str = "nim"
    model: Optional[str] = None
    channels: list[str] = Field(default_factory=list)
    tools: list[ToolConfig] = Field(default_factory=list)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    safety: SafetyConfig = Field(default_factory=SafetyConfig)
    skills: list[str] = Field(default_factory=list)   # named skill bundles
    tags: dict[str, str] = Field(default_factory=dict)
    temperature: float = 0.7
    max_tokens: int = 2048
    emoji: str = "🤖"

    @validator("display_name", always=True, pre=True)
    def _default_display(cls, v, values):
        return v or values.get("name", "agent").replace("-", " ").title()


class TeamSpec(BaseModel):
    """Top-level registration payload — describes an entire agent team."""
    team_name: str
    team_description: str = ""
    agents: list[AgentSpec]
    shared_channels: list[ChannelSpec] = Field(default_factory=list)
    coordination_channel: str = "agent-coordination"


# ── Runtime models ─────────────────────────────────────────────────────────

class Agent(AgentSpec):
    """Live agent with runtime state."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    slack_user_id: Optional[str] = None
    slack_bot_id: Optional[str] = None
    channel_ids: dict[str, str] = Field(default_factory=dict)  # name → slack_id
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: Optional[datetime] = None
    message_count: int = 0
    task_count: int = 0
    is_active: bool = True

    class Config:
        use_enum_values = True


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    assigned_to: str               # agent name
    created_by: str                # agent name or "human"
    channel: str
    thread_ts: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    parent_task_id: Optional[str] = None
    subtasks: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class Delegation(BaseModel):
    """Record of one agent delegating to another."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    from_agent: str
    to_agent: str
    reason: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
