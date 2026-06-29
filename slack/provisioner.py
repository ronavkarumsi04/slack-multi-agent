"""
Slack Provisioner — auto-creates channels, invites bots, and generates manifests.

Requires a Slack bot token with these scopes:
  channels:manage  groups:write  chat:write  users:read  team:read

For workspace-level provisioning (creating apps programmatically), the
Slack API does not expose a public endpoint — instead we generate a full
App Manifest JSON that the user can paste into api.slack.com/apps.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from agents.models import Agent, TeamSpec

log = logging.getLogger(__name__)


class SlackProvisioner:

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client:
            return self._client
        try:
            from config.settings import settings
            if not settings.slack_bot_token:
                return None
            from slack_sdk.web.async_client import AsyncWebClient
            self._client = AsyncWebClient(token=settings.slack_bot_token)
        except Exception as exc:
            log.warning("Could not create Slack client: %s", exc)
        return self._client

    # ─────────────────────────────────────────────────────────────────────────
    # Channel management
    # ─────────────────────────────────────────────────────────────────────────

    async def create_channel(self, name: str, is_private: bool = False, topic: str = "") -> Optional[str]:
        """Create a Slack channel. Returns channel ID or None on failure."""
        client = self._get_client()
        if not client:
            log.warning("Slack client unavailable — skipping channel creation for #%s", name)
            return None

        clean_name = name.lower().replace(" ", "-").replace("#", "")
        try:
            resp = await client.conversations_create(name=clean_name, is_private=is_private)
            channel_id = resp["channel"]["id"]
            log.info("Created Slack channel #%s (%s)", clean_name, channel_id)

            if topic:
                await client.conversations_setTopic(channel=channel_id, topic=topic)

            return channel_id
        except Exception as exc:
            # Channel may already exist
            if "name_taken" in str(exc):
                log.info("Channel #%s already exists — looking up ID", clean_name)
                return await self._find_channel_id(clean_name)
            log.warning("Could not create channel #%s: %s", clean_name, exc)
            return None

    async def _find_channel_id(self, name: str) -> Optional[str]:
        client = self._get_client()
        if not client:
            return None
        try:
            resp = await client.conversations_list(limit=999, exclude_archived=True)
            for ch in resp.get("channels", []):
                if ch["name"] == name:
                    return ch["id"]
        except Exception as exc:
            log.warning("Could not list channels: %s", exc)
        return None

    async def invite_bot_to_channel(self, channel_id: str, bot_user_id: str):
        client = self._get_client()
        if not client:
            return
        try:
            await client.conversations_invite(channel=channel_id, users=bot_user_id)
            log.info("Invited bot %s to channel %s", bot_user_id, channel_id)
        except Exception as exc:
            if "already_in_channel" not in str(exc):
                log.warning("Could not invite %s to %s: %s", bot_user_id, channel_id, exc)

    async def set_channel_description(self, channel_id: str, description: str):
        client = self._get_client()
        if not client:
            return
        try:
            await client.conversations_setPurpose(channel=channel_id, purpose=description)
        except Exception as exc:
            log.debug("Could not set channel purpose: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────
    # Full team provisioning
    # ─────────────────────────────────────────────────────────────────────────

    async def provision_team(self, team: TeamSpec, agents: list[Agent]):
        """Create all channels for the team and invite relevant agents."""
        log.info("Provisioning Slack team: %s", team.team_name)

        # 1. Create shared channels
        shared_channel_ids: dict[str, str] = {}
        for ch_spec in team.shared_channels:
            ch_id = await self.create_channel(
                name=ch_spec.name,
                is_private=ch_spec.is_private,
                topic=ch_spec.topic,
            )
            if ch_id:
                shared_channel_ids[ch_spec.name] = ch_id
                if ch_spec.description:
                    await self.set_channel_description(ch_id, ch_spec.description)

        # 2. Create coordination channel
        coord_id = await self.create_channel(
            name=team.coordination_channel,
            topic=f"🤖 Agent coordination hub for {team.team_name}",
        )

        # 3. Provision each agent's channels
        for agent in agents:
            # Create agent-specific channel
            agent_channel = f"agent-{agent.name}"
            agent_ch_id = await self.create_channel(
                name=agent_channel,
                topic=f"{agent.emoji} {agent.display_name} — {agent.description or agent.role}",
            )

            all_channel_ids = {}
            if agent_ch_id:
                all_channel_ids[agent_channel] = agent_ch_id

            # Create/join channels listed in spec
            for ch_name in agent.channels:
                ch_id = shared_channel_ids.get(ch_name) or await self.create_channel(name=ch_name)
                if ch_id:
                    all_channel_ids[ch_name] = ch_id

            # Join coordination channel
            if coord_id:
                all_channel_ids[team.coordination_channel] = coord_id

            # Update agent record with resolved channel IDs
            from agents.registry import registry
            registry.update_agent(agent.name, channel_ids=all_channel_ids)

            # Post welcome message in agent channel
            if agent_ch_id:
                await self._post_agent_welcome(agent_ch_id, agent, team.team_name)

        log.info("Team provisioning complete for %s", team.team_name)

    async def provision_agent_channels(self, agent: Agent):
        """Provision channels for a single newly registered agent."""
        from agents.models import TeamSpec, ChannelSpec
        dummy_team = TeamSpec(
            team_name="Agent Team",
            agents=[agent],
            shared_channels=[ChannelSpec(name=ch) for ch in agent.channels],
        )
        await self.provision_team(dummy_team, [agent])

    async def _post_agent_welcome(self, channel_id: str, agent: Agent, team_name: str):
        client = self._get_client()
        if not client:
            return
        try:
            msg = (
                f"{agent.emoji} *{agent.display_name}* is online!\n"
                f">Role: `{agent.role}` | Provider: `{agent.provider}` | Model: `{agent.model or 'default'}`\n"
                f">Autonomy: `{agent.safety.autonomy}` | Team: *{team_name}*\n"
                f">{agent.description or 'Ready to assist.'}\n\n"
                f"_Mention me with `@{agent.name}` to interact._"
            )
            await client.chat_postMessage(channel=channel_id, text=msg)
        except Exception as exc:
            log.debug("Welcome message failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────
    # App Manifest generator
    # ─────────────────────────────────────────────────────────────────────────

    def generate_app_manifest(self, agents: list[Agent], team_name: str) -> dict:
        """
        Generate a Slack App Manifest (JSON) that can be pasted into
        https://api.slack.com/apps → Create New App → From a manifest.

        This grants all scopes needed by the agent team.
        """
        # Collect all slash commands from agents
        slash_commands = [
            {
                "command": "/agent",
                "url": "https://YOUR_HOST/api/slack/commands",
                "description": "Interact with the agent team",
                "usage_hint": "[agent-name] [message]",
                "should_escape": False,
            },
            {
                "command": "/register",
                "url": "https://YOUR_HOST/api/register",
                "description": "Register a new agent team from YAML/JSON",
                "usage_hint": "",
                "should_escape": False,
            },
            {
                "command": "/tasks",
                "url": "https://YOUR_HOST/api/slack/commands",
                "description": "View pending tasks and agent activity",
                "usage_hint": "[agent-name]",
                "should_escape": False,
            },
        ]

        manifest = {
            "display_information": {
                "name": f"{team_name} Agent Hub",
                "description": f"AI agent team powered by NVIDIA NIM | {len(agents)} agents",
                "background_color": "#1a1a2e",
                "long_description": (
                    f"Automatically provisioned Slack workspace for the {team_name} agent team. "
                    f"Agents: {', '.join(a.display_name for a in agents)}. "
                    "Powered by NVIDIA NIM Nemotron models and the Slack Workplace Agent Team Generator."
                ),
            },
            "features": {
                "app_home": {
                    "home_tab_enabled": True,
                    "messages_tab_enabled": True,
                    "messages_tab_read_only_enabled": False,
                },
                "bot_user": {
                    "display_name": f"{team_name} Bot",
                    "always_online": True,
                },
                "slash_commands": slash_commands,
            },
            "oauth_config": {
                "redirect_urls": ["https://YOUR_HOST/api/slack/oauth"],
                "scopes": {
                    "bot": [
                        "app_mentions:read",
                        "channels:history",
                        "channels:join",
                        "channels:manage",
                        "channels:read",
                        "chat:write",
                        "chat:write.customize",
                        "commands",
                        "files:read",
                        "groups:history",
                        "groups:read",
                        "groups:write",
                        "im:history",
                        "im:read",
                        "im:write",
                        "mpim:history",
                        "mpim:read",
                        "mpim:write",
                        "reactions:read",
                        "reactions:write",
                        "search:read",
                        "team:read",
                        "users:read",
                        "users:read.email",
                        "usergroups:read",
                        "usergroups:write",
                        "workflow.steps:execute",
                    ]
                },
            },
            "settings": {
                "event_subscriptions": {
                    "request_url": "https://YOUR_HOST/api/slack/events",
                    "bot_events": [
                        "app_home_opened",
                        "app_mention",
                        "file_shared",
                        "message.channels",
                        "message.groups",
                        "message.im",
                        "message.mpim",
                        "reaction_added",
                    ],
                },
                "interactivity": {
                    "is_enabled": True,
                    "request_url": "https://YOUR_HOST/api/slack/interactive",
                },
                "org_deploy_enabled": False,
                "socket_mode_enabled": True,
                "token_rotation_enabled": False,
            },
            "_metadata": {
                "team_name": team_name,
                "agent_count": len(agents),
                "agents": [
                    {
                        "name": a.name,
                        "role": a.role,
                        "provider": a.provider,
                        "channels": a.channels,
                    }
                    for a in agents
                ],
                "generated_by": "Slack Workplace Agent Team Generator",
            },
        }

        return manifest
