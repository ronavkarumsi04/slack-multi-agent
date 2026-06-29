"""
POST /api/register  — Register an entire agent team from a YAML or JSON spec.
GET  /api/agents    — List all registered agents.
GET  /api/agents/{name} — Get a single agent.
DELETE /api/agents/{name} — Deactivate an agent.
"""
from __future__ import annotations

import logging
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from agents.models import AgentSpec, TeamSpec, AutonomyLevel
from agents.registry import registry
from slack.provisioner import SlackProvisioner

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Agent Registration"])

provisioner = SlackProvisioner()


# ── Register a full team ─────────────────────────────────────────────────────

@router.post("/register")
async def register_team(request: Request, background_tasks: BackgroundTasks):
    """
    Accept JSON or YAML body describing an entire agent team.
    Registers agents, provisions Slack channels, and wires routing.

    Example YAML body:
      team_name: eng-team
      agents:
        - name: eng-bot
          role: engineer
          provider: nim
          channels: [engineering, incidents]
          autonomy: review
    """
    content_type = request.headers.get("content-type", "")
    body = await request.body()

    try:
        if "yaml" in content_type or "text/plain" in content_type:
            raw = yaml.safe_load(body)
        else:
            import json
            raw = json.loads(body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse body: {exc}")

    try:
        team = TeamSpec(**raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid team spec: {exc}")

    # Register each agent
    registered = []
    for spec in team.agents:
        agent = registry.register(spec, team_name=team.team_name)
        registered.append(agent.name)

    # Provision Slack (async — non-blocking)
    background_tasks.add_task(
        provisioner.provision_team,
        team=team,
        agents=registry.all_agents(),
    )

    return JSONResponse({
        "status": "ok",
        "team": team.team_name,
        "registered_agents": registered,
        "message": f"Registered {len(registered)} agents. Slack provisioning in progress.",
    })


# ── Register a single agent ──────────────────────────────────────────────────

@router.post("/agents")
async def register_agent(spec: AgentSpec, background_tasks: BackgroundTasks):
    agent = registry.register(spec)
    background_tasks.add_task(provisioner.provision_agent_channels, agent)
    return {"status": "ok", "agent": agent.dict()}


# ── List agents ───────────────────────────────────────────────────────────────

@router.get("/agents")
async def list_agents(active_only: bool = False):
    agents = registry.active_agents() if active_only else registry.all_agents()
    return {
        "agents": [
            {
                "name": a.name,
                "display_name": a.display_name,
                "role": a.role,
                "provider": a.provider,
                "model": a.model,
                "channels": a.channels,
                "autonomy": a.safety.autonomy,
                "is_active": a.is_active,
                "message_count": a.message_count,
                "task_count": a.task_count,
                "last_active": a.last_active.isoformat() if a.last_active else None,
            }
            for a in agents
        ],
        "total": len(agents),
    }


@router.get("/agents/{name}")
async def get_agent(name: str):
    agent = registry.get(name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return agent.dict()


@router.delete("/agents/{name}")
async def deactivate_agent(name: str):
    success = registry.deactivate(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    return {"status": "ok", "message": f"Agent '{name}' deactivated"}


# ── Tasks ─────────────────────────────────────────────────────────────────────

@router.get("/tasks")
async def list_tasks(agent: str | None = None, status: str | None = None):
    tasks = registry.all_tasks()
    if agent:
        tasks = [t for t in tasks if t.assigned_to == agent]
    if status:
        tasks = [t for t in tasks if t.status == status]
    return {"tasks": [t.dict() for t in tasks], "total": len(tasks)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = registry.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task.dict()


@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, updates: dict[str, Any]):
    task = registry.update_task(task_id, **updates)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {"status": "ok", "task": task.dict()}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def stats():
    return registry.stats()


# ── Manifest generation ───────────────────────────────────────────────────────

@router.get("/manifest")
async def generate_manifest(team: str | None = None):
    """Generate a Slack app manifest JSON for the current agent team."""
    agents = registry.all_agents()
    return provisioner.generate_app_manifest(agents, team or registry._team_name)


# ── Provider status ──────────────────────────────────────────────────────────

@router.get("/providers")
async def list_providers():
    from providers import available_providers, get_provider
    result = {}
    for name in ["nim", "openai", "anthropic", "groq"]:
        p = get_provider(name)
        result[name] = {"available": p.is_available()}
    return {"providers": result, "available": available_providers()}
