"""
Multi-agent orchestration engine.

Responsibilities:
  - Route incoming Slack messages to the right agent(s)
  - Decompose complex tasks and delegate subtasks
  - Manage task lifecycle (pending → in_progress → waiting → done)
  - Handle inter-agent delegation
  - Enforce autonomy levels before any reply is posted
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Optional

from agents.models import Agent, Task, TaskPriority, TaskStatus, Delegation
from agents.registry import registry
from agents.roles.prompts import build_system_prompt
from memory.manager import MemoryManager
from providers import get_provider, Message
from safety.guard import SafetyGuard
from tools.dispatcher import ToolDispatcher

log = logging.getLogger(__name__)


class Orchestrator:
    """
    Central brain that processes every Slack event, routes it, calls the
    right agent, enforces safety, and returns a reply (or queues for review).
    """

    def __init__(self):
        self.memory = MemoryManager()
        self.safety = SafetyGuard()
        self.tools = ToolDispatcher()

    # ─────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ─────────────────────────────────────────────────────────────────────────

    async def handle_message(
        self,
        text: str,
        channel: str,
        user: str,
        ts: str,
        thread_ts: Optional[str] = None,
        files: Optional[list] = None,
    ) -> list[dict]:
        """
        Process an incoming Slack message.
        Returns a list of reply dicts: [{agent, channel, text, thread_ts, needs_review}]
        """
        # 1. Find agents listening on this channel
        agents = registry.agents_for_channel(channel)
        if not agents:
            log.debug("No agents on channel %s", channel)
            return []

        # 2. Check if message is a direct delegation (@agent-name …)
        targeted = self._extract_targeted_agents(text, agents)
        if targeted:
            responding_agents = targeted
        else:
            # Route to orchestrator first; fall back to all channel agents
            orch = registry.get_orchestrator()
            responding_agents = [orch] if orch else agents[:1]

        replies = []
        for agent in responding_agents:
            reply = await self._process_for_agent(
                agent=agent,
                text=text,
                channel=channel,
                user=user,
                ts=ts,
                thread_ts=thread_ts or ts,
            )
            if reply:
                replies.append(reply)

        return replies

    # ─────────────────────────────────────────────────────────────────────────
    # Core per-agent processing
    # ─────────────────────────────────────────────────────────────────────────

    async def _process_for_agent(
        self,
        agent: Agent,
        text: str,
        channel: str,
        user: str,
        ts: str,
        thread_ts: str,
    ) -> Optional[dict]:
        # Safety pre-check on incoming text
        if not await self.safety.check_input(text, agent):
            log.warning("Safety guard blocked input for agent %s", agent.name)
            return None

        # Build conversation history from memory
        history = await self.memory.get_context(agent.name, channel, thread_ts)

        # Build messages
        system_prompt = build_system_prompt(
            role=agent.role,
            display_name=agent.display_name,
            team_name=registry._team_name,
            autonomy=agent.safety.autonomy,
            description=agent.description,
            custom_prompt=agent.system_prompt,
        )
        messages = [Message(role="system", content=system_prompt)]
        messages.extend(history)
        messages.append(Message(role="user", content=f"<@{user}>: {text}"))

        # Collect enabled tools for this agent
        tool_schemas = self.tools.get_schemas_for_agent(agent)

        # Call LLM (with tool loop)
        provider = get_provider(agent.provider)
        response_text, tool_results = await self._llm_tool_loop(
            provider=provider,
            agent=agent,
            messages=messages,
            tools=tool_schemas,
        )

        if not response_text:
            return None

        # Safety post-check on output
        safe, filtered_text = await self.safety.check_output(response_text, agent)
        if not safe:
            filtered_text = "⚠️ My response was flagged by the safety filter. Please rephrase your request or contact a human."

        # Update memory
        await self.memory.add_message(agent.name, channel, thread_ts, "user", f"<@{user}>: {text}")
        await self.memory.add_message(agent.name, channel, thread_ts, "assistant", filtered_text)

        # Update agent stats
        registry.update_agent(agent.name, message_count=agent.message_count + 1)

        needs_review = agent.safety.autonomy == "review"

        return {
            "agent": agent.name,
            "channel": channel,
            "text": filtered_text,
            "thread_ts": thread_ts,
            "needs_review": needs_review,
            "tool_results": tool_results,
            "ts": ts,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # LLM + Tool loop (ReAct style)
    # ─────────────────────────────────────────────────────────────────────────

    async def _llm_tool_loop(
        self, provider, agent: Agent, messages: list[Message], tools: list[dict]
    ) -> tuple[str, list]:
        MAX_ITERATIONS = 8
        tool_results_log = []

        for _ in range(MAX_ITERATIONS):
            resp = await provider.chat(
                messages=messages,
                model=agent.model,
                temperature=agent.temperature,
                max_tokens=agent.max_tokens,
                tools=tools or None,
            )

            if not resp.tool_calls:
                return resp.content, tool_results_log

            # Execute tool calls
            messages.append(Message(role="assistant", content=resp.content or "", tool_calls=resp.tool_calls))

            for tc in resp.tool_calls:
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"]["arguments"])

                log.info("Agent %s calling tool %s(%s)", agent.name, fn_name, fn_args)

                try:
                    result = await self.tools.execute(fn_name, fn_args, agent)
                    tool_results_log.append({"tool": fn_name, "args": fn_args, "result": result})
                    result_content = json.dumps(result) if isinstance(result, dict) else str(result)
                except Exception as exc:
                    result_content = f"Tool error: {exc}"
                    tool_results_log.append({"tool": fn_name, "args": fn_args, "error": str(exc)})

                messages.append(Message(
                    role="tool",
                    content=result_content,
                    name=fn_name,
                ))

        log.warning("Max tool iterations reached for agent %s", agent.name)
        return "I've reached my processing limit. Please try a more specific request.", tool_results_log

    # ─────────────────────────────────────────────────────────────────────────
    # Task management
    # ─────────────────────────────────────────────────────────────────────────

    async def create_task(
        self,
        title: str,
        description: str,
        assigned_to: str,
        created_by: str,
        channel: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        thread_ts: Optional[str] = None,
    ) -> Task:
        task = Task(
            title=title,
            description=description,
            assigned_to=assigned_to,
            created_by=created_by,
            channel=channel,
            priority=priority,
            thread_ts=thread_ts,
        )
        registry.add_task(task)
        log.info("Task created: %s → %s", task.id, assigned_to)
        return task

    async def delegate_task(
        self,
        task_id: str,
        from_agent: str,
        to_agent: str,
        reason: str = "",
    ) -> Delegation:
        task = registry.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        delegation = Delegation(
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=reason,
        )
        registry.update_task(task_id, assigned_to=to_agent, status=TaskStatus.DELEGATED)
        log.info("Task %s delegated: %s → %s (%s)", task_id, from_agent, to_agent, reason)
        return delegation

    async def decompose_task(
        self,
        parent_task: Task,
        orchestrator_agent: Agent,
    ) -> list[Task]:
        """Ask the orchestrator LLM to decompose a complex task into subtasks."""
        provider = get_provider(orchestrator_agent.provider)
        prompt = f"""Decompose the following task into 2-5 concrete subtasks that can be assigned to specialist agents.
Available agents: {[a.name + '(' + a.role + ')' for a in registry.active_agents()]}

Task: {parent_task.title}
Description: {parent_task.description}

Respond with a JSON array: [{{"title": "...", "agent": "...", "description": "..."}}]"""

        resp = await provider.chat(
            messages=[Message(role="user", content=prompt)],
            model=orchestrator_agent.model,
            temperature=0.3,
        )

        try:
            raw = re.search(r'\[.*\]', resp.content, re.DOTALL)
            subtasks_data = json.loads(raw.group()) if raw else []
        except (json.JSONDecodeError, AttributeError):
            log.warning("Could not parse subtask decomposition: %s", resp.content)
            return []

        subtasks = []
        for d in subtasks_data:
            subtask = await self.create_task(
                title=d.get("title", "Subtask"),
                description=d.get("description", ""),
                assigned_to=d.get("agent", orchestrator_agent.name),
                created_by=orchestrator_agent.name,
                channel=parent_task.channel,
                thread_ts=parent_task.thread_ts,
            )
            subtasks.append(subtask)
            registry.update_task(parent_task.id, subtasks=parent_task.subtasks + [subtask.id])

        return subtasks

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _extract_targeted_agents(self, text: str, agents: list[Agent]) -> list[Agent]:
        """Find @agent-name mentions in message text."""
        targeted = []
        for agent in agents:
            if f"@{agent.name}" in text.lower() or f"@{agent.display_name.lower().replace(' ', '-')}" in text.lower():
                targeted.append(agent)
        return targeted


orchestrator = Orchestrator()
