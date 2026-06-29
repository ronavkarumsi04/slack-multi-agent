"""Web search plugin — searches the web using DuckDuckGo (no API key needed)."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from tools.dispatcher import BasePlugin
from agents.models import Agent

log = logging.getLogger(__name__)


class Plugin(BasePlugin):
    name = "web_search"

    def get_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for up-to-date information.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query":       {"type": "string", "description": "Search query"},
                            "max_results": {"type": "integer", "default": 5},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "description": "Fetch the text content of a web page URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string"},
                        },
                        "required": ["url"],
                    },
                },
            },
        ]

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        if function_name == "web_search":
            query = arguments["query"]
            max_r = arguments.get("max_results", 5)
            # DuckDuckGo instant-answers API (no key needed)
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_redirect": "1"},
                )
                data = resp.json()
            results = []
            # Abstract
            if data.get("Abstract"):
                results.append({"title": data.get("Heading", query), "snippet": data["Abstract"], "url": data.get("AbstractURL", "")})
            # Related topics
            for topic in data.get("RelatedTopics", [])[:max_r]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({"title": topic.get("Text", "")[:80], "snippet": topic.get("Text", ""), "url": topic.get("FirstURL", "")})
            return results[:max_r] or [{"title": "No results", "snippet": f"No instant results for: {query}"}]

        elif function_name == "fetch_url":
            url = arguments["url"]
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
            # Strip HTML tags naively
            import re
            text = re.sub(r'<[^>]+>', ' ', resp.text)
            text = re.sub(r'\s+', ' ', text).strip()
            return {"url": url, "content": text[:3000]}

        return {"error": f"Unknown function {function_name}"}
