"""
Centralised settings loaded from environment variables / .env file.
All secrets are stored here and never hard-coded elsewhere.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── App ─────────────────────────────────────────────────────────────────
    app_name: str = "Slack Agent Team Generator"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Database / Cache ─────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "sqlite:///./agents.db"

    # ── NVIDIA NIM (first-class provider) ────────────────────────────────────
    nim_api_key: Optional[str] = None
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nim_default_model: str = "nvidia/llama-3.1-nemotron-70b-instruct"
    nim_timeout: int = 120

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = None
    openai_default_model: str = "gpt-4o"

    # ── Anthropic ────────────────────────────────────────────────────────────
    anthropic_api_key: Optional[str] = None
    anthropic_default_model: str = "claude-3-5-sonnet-20241022"

    # ── Groq ─────────────────────────────────────────────────────────────────
    groq_api_key: Optional[str] = None
    groq_default_model: str = "llama-3.1-70b-versatile"

    # ── Slack ─────────────────────────────────────────────────────────────────
    slack_bot_token: Optional[str] = None           # xoxb-…
    slack_app_token: Optional[str] = None           # xapp-…  (Socket Mode)
    slack_signing_secret: Optional[str] = None
    slack_admin_token: Optional[str] = None         # xoxp-… for admin APIs

    # ── Plugin credentials ────────────────────────────────────────────────────
    github_token: Optional[str] = None
    jira_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    google_drive_credentials_json: Optional[str] = None

    # ── Safety ────────────────────────────────────────────────────────────────
    default_autonomy: Literal["off", "review", "full"] = "review"
    safety_enabled: bool = True
    content_filter_threshold: float = 0.7

    # ── Observability ─────────────────────────────────────────────────────────
    otel_endpoint: Optional[str] = None
    metrics_enabled: bool = True
    trace_enabled: bool = True

    # ── Dashboard ─────────────────────────────────────────────────────────────
    dashboard_enabled: bool = True
    dashboard_api_key: Optional[str] = None        # simple bearer auth


settings = Settings()
