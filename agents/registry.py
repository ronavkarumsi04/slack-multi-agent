"""
In-memory + persistent agent registry.
Stores all registered agents, supports CRUD, and broadcasts changes.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import Agent, AgentSpec, TeamSpec, Task, TaskStatus

log = logging.getLogger(__name__)

_PERSIST_FILE = Path("agents_state.json")


class AgentRegistry:
    """Singleton registry for all live agents and tasks."""

    def __init__(self):
        self._agents: dict[str, Agent] = {}     # name → Agent
        self._tasks: dict[str, Task] = {}       # task_id → Task
        self._team_name: str = "Agent Team"
        self._load_from_disk()

    # ── Agents ───────────────────────────────────────────────────────────────

    def register(self, spec: AgentSpec, team_name: str = "") -> Agent:
        agent = Agent(**spec.dict())
        if team_name:
            self._team_name = team_name
        self._agents[agent.name] = agent
        log.info("Registered agent: %s (%s)", agent.name, agent.role)
        self._save_to_disk()
        return agent

    def get(self, name: str) -> Optional[Agent]:
        return self._agents.get(name)

    def get_by_id(self, agent_id: str) -> Optional[Agent]:
        return next((a for a in self._agents.values() if a.id == agent_id), None)

    def all_agents(self) -> list[Agent]:
        return list(self._agents.values())

    def active_agents(self) -> list[Agent]:
        return [a for a in self._agents.values() if a.is_active]

    def agents_for_channel(self, channel_name: str) -> list[Agent]:
        return [a for a in self.active_agents() if channel_name in a.channels]

    def update_agent(self, name: str, **kwargs) -> Optional[Agent]:
        agent = self._agents.get(name)
        if not agent:
            return None
        for k, v in kwargs.items():
            if hasattr(agent, k):
                setattr(agent, k, v)
        agent.last_active = datetime.utcnow()
        self._save_to_disk()
        return agent

    def deactivate(self, name: str) -> bool:
        agent = self._agents.get(name)
        if agent:
            agent.is_active = False
            self._save_to_disk()
            return True
        return False

    def get_orchestrator(self) -> Optional[Agent]:
        for a in self.active_agents():
            if a.role == "orchestrator":
                return a
        return None

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def add_task(self, task: Task) -> Task:
        self._tasks[task.id] = task
        if task.assigned_to in self._agents:
            self._agents[task.assigned_to].task_count += 1
        self._save_to_disk()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)
        task.updated_at = datetime.utcnow()
        if kwargs.get("status") == TaskStatus.DONE:
            task.completed_at = datetime.utcnow()
        self._save_to_disk()
        return task

    def tasks_for_agent(self, agent_name: str) -> list[Task]:
        return [t for t in self._tasks.values() if t.assigned_to == agent_name]

    def all_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def pending_review_tasks(self) -> list[Task]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.WAITING]

    # ── Serialisation ─────────────────────────────────────────────────────────

    def _save_to_disk(self):
        try:
            data = {
                "team_name": self._team_name,
                "agents": {n: a.dict() for n, a in self._agents.items()},
                "tasks":  {i: t.dict() for i, t in self._tasks.items()},
            }
            _PERSIST_FILE.write_text(json.dumps(data, default=str, indent=2))
        except Exception as exc:
            log.warning("Could not persist registry: %s", exc)

    def _load_from_disk(self):
        if not _PERSIST_FILE.exists():
            return
        try:
            data = json.loads(_PERSIST_FILE.read_text())
            self._team_name = data.get("team_name", "Agent Team")
            for n, d in data.get("agents", {}).items():
                self._agents[n] = Agent(**d)
            for i, d in data.get("tasks", {}).items():
                self._tasks[i] = Task(**d)
            log.info("Loaded %d agents, %d tasks from disk", len(self._agents), len(self._tasks))
        except Exception as exc:
            log.warning("Could not load registry from disk: %s", exc)

    # ── Stats ──────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        tasks = self.all_tasks()
        return {
            "total_agents": len(self._agents),
            "active_agents": len(self.active_agents()),
            "total_tasks": len(tasks),
            "tasks_by_status": {s.value: sum(1 for t in tasks if t.status == s.value) for s in TaskStatus},
            "team_name": self._team_name,
        }


# Global singleton
registry = AgentRegistry()
