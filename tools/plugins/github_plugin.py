"""GitHub plugin — search repos, create issues, list PRs, post comments."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from config.settings import settings
from tools.dispatcher import BasePlugin
from agents.models import Agent

log = logging.getLogger(__name__)


class Plugin(BasePlugin):
    name = "github"

    def get_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "github_create_issue",
                    "description": "Create a GitHub issue in a repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string", "description": "Repository owner (user or org)"},
                            "repo":  {"type": "string", "description": "Repository name"},
                            "title": {"type": "string", "description": "Issue title"},
                            "body":  {"type": "string", "description": "Issue body (markdown)"},
                            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to apply"},
                        },
                        "required": ["owner", "repo", "title", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_list_prs",
                    "description": "List open pull requests in a GitHub repository.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner": {"type": "string"},
                            "repo":  {"type": "string"},
                            "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                        },
                        "required": ["owner", "repo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_get_issue",
                    "description": "Get details of a specific GitHub issue.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "owner":        {"type": "string"},
                            "repo":         {"type": "string"},
                            "issue_number": {"type": "integer"},
                        },
                        "required": ["owner", "repo", "issue_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "github_search_code",
                    "description": "Search GitHub code across repositories.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "GitHub code search query"},
                        },
                        "required": ["query"],
                    },
                },
            },
        ]

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        token = settings.github_token
        if not token:
            return {"error": "GitHub token not configured (GITHUB_TOKEN)"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient(headers=headers, timeout=30) as client:
            if function_name == "github_create_issue":
                owner, repo = arguments["owner"], arguments["repo"]
                payload = {"title": arguments["title"], "body": arguments["body"]}
                if "labels" in arguments:
                    payload["labels"] = arguments["labels"]
                resp = await client.post(f"https://api.github.com/repos/{owner}/{repo}/issues", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return {"number": data["number"], "url": data["html_url"], "status": "created"}

            elif function_name == "github_list_prs":
                owner, repo = arguments["owner"], arguments["repo"]
                state = arguments.get("state", "open")
                resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}/pulls", params={"state": state})
                resp.raise_for_status()
                prs = resp.json()
                return [{"number": p["number"], "title": p["title"], "url": p["html_url"], "author": p["user"]["login"]} for p in prs[:20]]

            elif function_name == "github_get_issue":
                owner, repo, num = arguments["owner"], arguments["repo"], arguments["issue_number"]
                resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}/issues/{num}")
                resp.raise_for_status()
                d = resp.json()
                return {"number": d["number"], "title": d["title"], "body": d["body"], "state": d["state"], "url": d["html_url"]}

            elif function_name == "github_search_code":
                resp = await client.get("https://api.github.com/search/code", params={"q": arguments["query"]})
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return [{"path": i["path"], "repo": i["repository"]["full_name"], "url": i["html_url"]} for i in items[:10]]

        return {"error": f"Unknown function {function_name}"}
