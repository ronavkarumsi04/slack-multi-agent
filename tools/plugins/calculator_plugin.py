"""Calculator/code execution plugin — safe math eval and Python snippets."""
from __future__ import annotations
import ast
import math
import logging
from typing import Any
from tools.dispatcher import BasePlugin
from agents.models import Agent

log = logging.getLogger(__name__)

# Safe builtins for expression eval
_SAFE_NAMES = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
_SAFE_NAMES.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum, "len": len, "int": int, "float": float})


class Plugin(BasePlugin):
    name = "calculator"

    def get_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "calculate",
                    "description": "Evaluate a mathematical expression safely. Supports standard math functions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string", "description": "Math expression, e.g. 'sqrt(144) + 2**10'"},
                        },
                        "required": ["expression"],
                    },
                },
            },
        ]

    async def execute(self, function_name: str, arguments: dict, agent: Agent) -> Any:
        if function_name == "calculate":
            expr = arguments["expression"]
            try:
                tree = ast.parse(expr, mode="eval")
                # Restrict to safe nodes
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id not in _SAFE_NAMES:
                            return {"error": f"Function '{node.func.id}' not allowed"}
                result = eval(compile(tree, "<string>", "eval"), {"__builtins__": {}}, _SAFE_NAMES)
                return {"expression": expr, "result": result}
            except Exception as exc:
                return {"error": f"Evaluation error: {exc}"}
        return {"error": f"Unknown function {function_name}"}
