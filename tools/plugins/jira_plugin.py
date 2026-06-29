"""Jira plugin — create issues, search, update status, add comments."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from config.settings import settings
from tools.dispatcher import BasePlugin
from agents.models import Agent

log = logging.getLogger(__name__)


class Plugin(BasePlugin):
    name = "jira"

    def _base(self) -> str:
        return settings.jira_url.rstrip("/") if settings.jira_url else ""

    def _auth(self):
        return (settings.jira_email, settings.jira_api_token)

    def get_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "jira_create_issue",
                    "description": "Create a Jira issue/ticket.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_key": {"type": "string"},
                            "summary":     {"type": "string"},
                            "description": {"type": "string"},
                            "issue_type":  {"type": "string", "enum": ["Bug", "Story", "Task", "Epic"], "default": "Task"},
                            "priority":    {"type": "string", "enum": ["Highest","High","Medium","Low","Lowest"], "default": "Medium"},
                            "labels":      {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["project_key", "summary"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_search_issues",
                    "description": "Search Jira using JQL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "jql":        {"type": "string", "description": "Jira Query Language string"},
                            "max_results":{"type": "integer", "default": 10},
                        },
                        "required": ["jql"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "jira_update_issue",
                    "description": "Update a Jira issue's status or fields.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_key":   {"type": "string"},
                            "transition":  {"type": "string", "description": "Target status (e.g. 'In Progress', 'Done')"},
                            "comment":     {"type": "string"},
                        },
                        "required": ["issue_key"],
                    },
                },
            },
        ]

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        if not all([settings.jira_url, settings.jira_email, settings.jira_api_token]):
            return {"error": "Jira credentials not configured (JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN)"}

        base = self._base()
        auth = self._auth()
        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        async with httpx.AsyncClient(auth=auth, headers=headers, timeout=30) as client:
            if function_name == "jira_create_issue":
                payload = {
                    "fields": {
                        "project": {"key": arguments["project_key"]},
                        "summary": arguments["summary"],
                        "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": arguments.get("description", "")}]}]},
                        "issuetype": {"name": arguments.get("issue_type", "Task")},
                        "priority": {"name": arguments.get("priority", "Medium")},
                    }
                }
                if "labels" in arguments:
                    payload["fields"]["labels"] = arguments["labels"]
                resp = await client.post(f"{base}/rest/api/3/issue", json=payload)
                resp.raise_for_status()
                d = resp.json()
                return {"key": d["key"], "url": f"{base}/browse/{d['key']}", "status": "created"}

            elif function_name == "jira_search_issues":
                resp = await client.get(f"{base}/rest/api/3/search", params={"jql": arguments["jql"], "maxResults": arguments.get("max_results", 10)})
                resp.raise_for_status()
                issues = resp.json().get("issues", [])
                return [{"key": i["key"], "summary": i["fields"]["summary"], "status": i["fields"]["status"]["name"]} for i in issues]

            elif function_name == "jira_update_issue":
                key = arguments["issue_key"]
                if "transition" in arguments:
                    trans_resp = await client.get(f"{base}/rest/api/3/issue/{key}/transitions")
                    trans_resp.raise_for_status()
                    transitions = trans_resp.json().get("transitions", [])
                    match = next((t for t in transitions if arguments["transition"].lower() in t["name"].lower()), None)
                    if match:
                        await client.post(f"{base}/rest/api/3/issue/{key}/transitions", json={"transition": {"id": match["id"]}})
                if "comment" in arguments:
                    await client.post(f"{base}/rest/api/3/issue/{key}/comment", json={"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": arguments["comment"]}]}]}})
                return {"status": "updated", "key": key}

        return {"error": f"Unknown function {function_name}"}
