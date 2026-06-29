"""
Tool dispatcher — central registry for all agent tools.
Manages plugin loading, schema generation, and execution.
"""
from __future__ import annotations

import importlib
import logging
from typing import Any, Optional

from agents.models import Agent

log = logging.getLogger(__name__)

# Map tool name → plugin module path
PLUGIN_REGISTRY: dict[str, str] = {
    "github":       "tools.plugins.github_plugin",
    "jira":         "tools.plugins.jira_plugin",
    "google_drive": "tools.plugins.gdrive_plugin",
    "web_search":   "tools.plugins.web_search_plugin",
    "code_runner":  "tools.plugins.code_runner_plugin",
    "slack":        "tools.plugins.slack_plugin",
    "calculator":   "tools.plugins.calculator_plugin",
    "http":         "tools.plugins.http_plugin",
}


class BasePlugin:
    """Every plugin must inherit from this and implement get_schemas() + execute()."""
    name: str = "base"

    def get_schemas(self) -> list[dict]:
        """Return OpenAI-style function schemas for this plugin's tools."""
        return []

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        raise NotImplementedError


class ToolDispatcher:
    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}
        self._load_all_plugins()

    def _load_all_plugins(self):
        for name, module_path in PLUGIN_REGISTRY.items():
            try:
                mod = importlib.import_module(module_path)
                plugin_cls = getattr(mod, "Plugin")
                self._plugins[name] = plugin_cls()
                log.debug("Loaded plugin: %s", name)
            except Exception as exc:
                log.warning("Could not load plugin '%s': %s", name, exc)

    def get_schemas_for_agent(self, agent: Agent) -> list[dict]:
        """Return combined tool schemas for all tools enabled on this agent."""
        schemas = []
        enabled_names = {t.name for t in agent.tools if t.enabled}

        for plugin_name, plugin in self._plugins.items():
            if plugin_name in enabled_names:
                schemas.extend(plugin.get_schemas())

        return schemas

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        """Route a tool call to the appropriate plugin."""
        # Find which plugin owns this function
        for plugin_name, plugin in self._plugins.items():
            for schema in plugin.get_schemas():
                if schema.get("function", {}).get("name") == function_name:
                    # Check the tool is enabled for this agent
                    enabled = {t.name for t in agent.tools if t.enabled}
                    if plugin_name not in enabled:
                        return {"error": f"Tool '{plugin_name}' is not enabled for agent '{agent.name}'"}

                    # Get per-agent tool config
                    tool_config = next(
                        (t.config for t in agent.tools if t.name == plugin_name), {}
                    )
                    return await plugin.execute(function_name, arguments, agent)

        return {"error": f"Unknown function: {function_name}"}

    def list_available_tools(self) -> dict[str, list[str]]:
        """Return {plugin_name: [function_names]} for all loaded plugins."""
        return {
            name: [s.get("function", {}).get("name", "") for s in plugin.get_schemas()]
            for name, plugin in self._plugins.items()
        }
