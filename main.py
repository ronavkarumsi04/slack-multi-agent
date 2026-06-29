"""
Main FastAPI application entry point.
Mounts:
  /api          → REST API (agent registration, tasks, stats)
  /dashboard    → Web UI
  /health       → Health check

Starts Slack Bolt in background (Socket Mode or HTTP webhook).
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from config.settings import settings
from api.routes.register import router as register_router
from dashboard.app import router as dashboard_router
from observability.logger import event_logger

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger(__name__)


# ── Lifespan (startup/shutdown) ───────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("🚀 Starting %s (env=%s)", settings.app_name, settings.app_env)
    event_logger.log_registration("startup", 0)

    # Start Slack Bolt
    slack_task = None
    if settings.slack_bot_token and settings.slack_app_token:
        slack_task = asyncio.create_task(_start_slack())
    elif settings.slack_bot_token:
        log.info("Slack running in HTTP webhook mode (no SLACK_APP_TOKEN)")
    else:
        log.warning("No Slack tokens configured — Slack integration disabled")

    yield

    # Shutdown
    if slack_task:
        slack_task.cancel()
        try:
            await slack_task
        except asyncio.CancelledError:
            pass
    log.info("👋 Shutdown complete")


async def _start_slack():
    """Start Slack Bolt in Socket Mode."""
    try:
        from slack.event_handler import create_slack_app, start_socket_mode
        slack_app = create_slack_app(
            bot_token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret or "dev-secret",
        )
        log.info("⚡ Slack Socket Mode starting...")
        await start_socket_mode(slack_app, settings.slack_app_token)
    except Exception as exc:
        log.error("Slack startup failed: %s", exc)


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Production-grade multi-agent Slack workplace system powered by NVIDIA NIM. "
            "Auto-provisions Slack apps, channels, and agent teams from a single YAML spec."
        ),
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ───────────────────────────────────────────────────────────
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "development" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────────────
    app.include_router(register_router)
    if settings.dashboard_enabled:
        app.include_router(dashboard_router)

    # ── Slack webhook routes (HTTP mode) ─────────────────────────────────────
    if settings.slack_bot_token and not settings.slack_app_token:
        try:
            from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
            from slack.event_handler import create_slack_app
            slack_app = create_slack_app(settings.slack_bot_token, settings.slack_signing_secret or "")
            slack_handler = AsyncSlackRequestHandler(slack_app)

            from fastapi import Request

            @app.post("/api/slack/events")
            async def slack_events(req: Request):
                return await slack_handler.handle(req)

            @app.post("/api/slack/interactive")
            async def slack_interactive(req: Request):
                return await slack_handler.handle(req)

            @app.post("/api/slack/commands")
            async def slack_commands(req: Request):
                return await slack_handler.handle(req)

        except Exception as exc:
            log.warning("Could not mount Slack webhook routes: %s", exc)

    # ── Health & root ─────────────────────────────────────────────────────────
    @app.get("/health")
    async def health():
        from agents.registry import registry
        from providers import available_providers
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
            "agents": len(registry.active_agents()),
            "providers": available_providers(),
            "slack_connected": bool(settings.slack_bot_token),
        }

    @app.get("/")
    async def root():
        return {
            "name": settings.app_name,
            "version": "2.0.0",
            "docs": "/api/docs",
            "dashboard": "/dashboard" if settings.dashboard_enabled else None,
            "health": "/health",
        }

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )
