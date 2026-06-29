"""
Slack event handler — processes all incoming Slack events via Bolt.
Supports both Socket Mode (xapp- token) and HTTP webhook mode.
"""
from __future__ import annotations

import logging
from typing import Optional

from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from agents.orchestrator import orchestrator
from agents.registry import registry
from safety.guard import SafetyGuard
from observability.logger import event_logger

log = logging.getLogger(__name__)
safety = SafetyGuard()


def create_slack_app(bot_token: str, signing_secret: str) -> AsyncApp:
    app = AsyncApp(token=bot_token, signing_secret=signing_secret)

    # ── App mention (@agent-name message) ────────────────────────────────────
    @app.event("app_mention")
    async def handle_mention(event, say, client):
        text = event.get("text", "")
        channel = event.get("channel", "")
        user = event.get("user", "")
        ts = event.get("ts", "")
        thread_ts = event.get("thread_ts", ts)

        log.info("Mention in #%s from %s: %s", channel, user, text[:80])

        replies = await orchestrator.handle_message(
            text=text,
            channel=channel,
            user=user,
            ts=ts,
            thread_ts=thread_ts,
        )

        for reply in replies:
            await _dispatch_reply(reply, say, client)
            event_logger.log_agent_response(reply)

    # ── Regular channel message ───────────────────────────────────────────────
    @app.event("message")
    async def handle_message(event, say, client):
        # Skip bot messages and sub-types (edits, deletes, etc.)
        if event.get("bot_id") or event.get("subtype"):
            return

        text = event.get("text", "")
        channel = event.get("channel", "")
        user = event.get("user", "")
        ts = event.get("ts", "")
        thread_ts = event.get("thread_ts", ts)

        # Only respond if agents are listening on this channel
        ch_name = await _resolve_channel_name(client, channel)
        agents = registry.agents_for_channel(ch_name)
        if not agents:
            return

        replies = await orchestrator.handle_message(
            text=text,
            channel=channel,
            user=user,
            ts=ts,
            thread_ts=thread_ts,
        )

        for reply in replies:
            await _dispatch_reply(reply, say, client)
            event_logger.log_agent_response(reply)

    # ── App Home opened ───────────────────────────────────────────────────────
    @app.event("app_home_opened")
    async def handle_home(event, client):
        user_id = event["user"]
        agents = registry.active_agents()
        tasks = registry.pending_review_tasks()

        agent_blocks = []
        for a in agents[:10]:
            agent_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{a.emoji} *{a.display_name}* `{a.role}` | `{a.provider}` | autonomy: `{a.safety.autonomy}`\n"
                            f"Messages: {a.message_count} | Tasks: {a.task_count}",
                },
            })
            agent_blocks.append({"type": "divider"})

        review_text = f"*{len(tasks)} message(s) pending your review*" if tasks else "✅ No pending reviews"

        view = {
            "type": "home",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "🤖 Agent Team Dashboard"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*{registry._team_name}* — {len(agents)} active agents"}},
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": review_text}},
                {"type": "divider"},
                {"type": "header", "text": {"type": "plain_text", "text": "Active Agents"}},
                *agent_blocks,
            ],
        }
        await client.views_publish(user_id=user_id, view=view)

    # ── Slash command /agent ──────────────────────────────────────────────────
    @app.command("/agent")
    async def handle_agent_command(ack, respond, command, client):
        await ack()
        text = command.get("text", "").strip()
        channel_id = command.get("channel_id", "")

        if not text:
            agents = registry.active_agents()
            lines = [f"{a.emoji} `{a.name}` ({a.role}) | {a.provider}" for a in agents]
            await respond(text="*Registered Agents:*\n" + "\n".join(lines) or "No agents registered yet.")
            return

        # Parse: /agent [agent-name] [message]
        parts = text.split(" ", 1)
        agent_name = parts[0]
        msg = parts[1] if len(parts) > 1 else ""

        agent = registry.get(agent_name)
        if not agent:
            await respond(text=f"❌ Agent `{agent_name}` not found. Use `/agent` to list all agents.")
            return

        if not msg:
            await respond(text=f"{agent.emoji} *{agent.display_name}*\nRole: `{agent.role}` | Provider: `{agent.provider}` | Autonomy: `{agent.safety.autonomy}`")
            return

        replies = await orchestrator.handle_message(
            text=f"@{agent_name} {msg}",
            channel=channel_id,
            user=command.get("user_id", "unknown"),
            ts=str(__import__("time").time()),
        )

        for reply in replies:
            await respond(text=reply["text"])

    # ── Slash command /tasks ──────────────────────────────────────────────────
    @app.command("/tasks")
    async def handle_tasks_command(ack, respond, command):
        await ack()
        agent_filter = command.get("text", "").strip() or None
        tasks = registry.tasks_for_agent(agent_filter) if agent_filter else registry.all_tasks()

        if not tasks:
            await respond(text="No tasks found.")
            return

        lines = []
        for t in tasks[-10:]:
            emoji = {"pending": "⏳", "in_progress": "🔄", "waiting": "👁️", "done": "✅", "failed": "❌", "delegated": "↪️"}.get(t.status, "•")
            lines.append(f"{emoji} [{t.priority.upper()}] *{t.title}* → `{t.assigned_to}` ({t.status})")

        await respond(text="*Recent Tasks:*\n" + "\n".join(lines))

    return app


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _dispatch_reply(reply: dict, say, client):
    """Post a reply, respecting the autonomy setting."""
    agent = registry.get(reply["agent"])
    if not agent:
        return

    action = safety.check_autonomy_for_post(agent)

    if action["action"] == "post":
        await say(text=reply["text"], thread_ts=reply.get("thread_ts"))

    elif action["action"] == "queue":
        # Post a "pending review" placeholder in the thread
        await say(
            text=f"_{agent.emoji} {agent.display_name} drafted a response — pending review by a team member._",
            thread_ts=reply.get("thread_ts"),
        )
        # In a full implementation, store the draft and post a review button block
        log.info("Queued reply from %s for human review", reply["agent"])

    else:
        log.info("Reply from %s discarded (autonomy=off)", reply["agent"])


_channel_name_cache: dict[str, str] = {}


async def _resolve_channel_name(client, channel_id: str) -> str:
    if channel_id in _channel_name_cache:
        return _channel_name_cache[channel_id]
    try:
        resp = await client.conversations_info(channel=channel_id)
        name = resp["channel"]["name"]
        _channel_name_cache[channel_id] = name
        return name
    except Exception:
        return channel_id


async def start_socket_mode(app: AsyncApp, app_token: str):
    handler = AsyncSocketModeHandler(app, app_token)
    await handler.start_async()
