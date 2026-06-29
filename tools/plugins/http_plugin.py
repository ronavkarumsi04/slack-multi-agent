"""Generic HTTP plugin — lets agents call arbitrary REST APIs."""
from __future__ import annotations
import logging
from typing import Any
import httpx
from tools.dispatcher import BasePlugin
from agents.models import Agent

log = logging.getLogger(__name__)


class Plugin(BasePlugin):
    name = "http"

    def get_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "http_request",
                    "description": "Make an HTTP request to an external API endpoint.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "method":  {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
                            "url":     {"type": "string"},
                            "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                            "body":    {"type": "object", "description": "JSON body for POST/PUT/PATCH"},
                            "params":  {"type": "object", "description": "Query parameters"},
                        },
                        "required": ["url"],
                    },
                },
            },
        ]

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        if function_name == "http_request":
            # Block internal/private IPs
            url = arguments["url"]
            blocked = ["localhost", "127.", "0.0.0.0", "169.254.", "10.", "192.168.", "172.16."]
            if any(b in url for b in blocked):
                return {"error": "Requests to internal/private addresses are blocked"}

            method = arguments.get("method", "GET").upper()
            headers = arguments.get("headers", {})
            body = arguments.get("body")
            params = arguments.get("params")

            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.request(
                    method=method, url=url, headers=headers,
                    json=body if body else None,
                    params=params if params else None,
                )
            try:
                data = resp.json()
            except Exception:
                data = resp.text[:2000]

            return {"status_code": resp.status_code, "body": data}

        return {"error": f"Unknown function {function_name}"}
