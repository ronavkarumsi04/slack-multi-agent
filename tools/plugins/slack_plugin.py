"""Slack plugin — lets agents read channels, search messages, post to other channels."""
from __future__ import annotations
import logging
from typing import Any
from tools.dispatcher import BasePlugin
from agents.models import Agent

log = logging.getLogger(__name__)


class Plugin(BasePlugin):
    name = "slack"

    def get_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "slack_search_messages",
                    "description": "Search Slack messages across channels.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query":       {"type": "string"},
                            "max_results": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_post_message",
                    "description": "Post a message to a Slack channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string", "description": "Channel name (without #) or ID"},
                            "text":    {"type": "string"},
                        },
                        "required": ["channel", "text"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "slack_get_channel_history",
                    "description": "Get recent messages from a Slack channel.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "limit":   {"type": "integer", "default": 10},
                        },
                        "required": ["channel"],
                    },
                },
            },
        ]

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        from config.settings import settings
        if not settings.slack_bot_token:
            return {"error": "Slack bot token not configured"}

        from slack_sdk.web.async_client import AsyncWebClient
        client = AsyncWebClient(token=settings.slack_bot_token)

        if function_name == "slack_search_messages":
            resp = await client.search_messages(query=arguments["query"], count=arguments.get("max_results", 5))
            matches = resp.get("messages", {}).get("matches", [])
            return [{"text": m.get("text", ""), "channel": m.get("channel", {}).get("name", ""), "ts": m.get("ts", "")} for m in matches]

        elif function_name == "slack_post_message":
            resp = await client.chat_postMessage(channel=arguments["channel"], text=arguments["text"])
            return {"ok": resp["ok"], "ts": resp.get("ts"), "channel": resp.get("channel")}

        elif function_name == "slack_get_channel_history":
            # Resolve channel name to ID if needed
            channel = arguments["channel"]
            if not channel.startswith("C"):
                channels = await client.conversations_list(limit=200)
                match = next((c for c in channels["channels"] if c["name"] == channel.lstrip("#")), None)
                channel = match["id"] if match else channel

            resp = await client.conversations_history(channel=channel, limit=arguments.get("limit", 10))
            msgs = resp.get("messages", [])
            return [{"text": m.get("text", ""), "user": m.get("user", ""), "ts": m.get("ts", "")} for m in msgs]

        return {"error": f"Unknown function {function_name}"}
