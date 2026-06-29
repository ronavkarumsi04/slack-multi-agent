"""
Structured event logger + metrics collector.
Writes JSON-formatted logs and exposes Prometheus-compatible metrics.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# ── Log file setup ─────────────────────────────────────────────────────────────
_LOG_DIR = Path("logs")
_LOG_DIR.mkdir(exist_ok=True)
_EVENT_LOG = _LOG_DIR / "events.jsonl"
_ERROR_LOG  = _LOG_DIR / "errors.jsonl"


def _write_jsonl(path: Path, record: dict):
    try:
        with path.open("a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as exc:
        log.warning("Could not write log: %s", exc)


class MetricsCollector:
    """Lightweight in-memory metrics (counters + histograms)."""

    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = {}
        self._start_time = time.time()

    def inc(self, name: str, value: int = 1, labels: dict | None = None):
        key = name if not labels else f"{name}{{{','.join(f'{k}={v}' for k,v in labels.items())}}}"
        self._counters[key] += value

    def observe(self, name: str, value: float):
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 10_000:
            self._histograms[name] = self._histograms[name][-5_000:]

    def set_gauge(self, name: str, value: float):
        self._gauges[name] = value

    def summary(self) -> dict:
        import statistics
        hist_summary = {}
        for name, values in self._histograms.items():
            if values:
                hist_summary[name] = {
                    "count": len(values),
                    "mean": round(statistics.mean(values), 2),
                    "p50": round(statistics.median(values), 2),
                    "p95": round(sorted(values)[int(len(values) * 0.95)], 2),
                    "max": round(max(values), 2),
                }
        return {
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "counters": dict(self._counters),
            "histograms": hist_summary,
            "gauges": dict(self._gauges),
        }

    def prometheus_text(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        for name, value in self._counters.items():
            safe = name.replace("{", "").replace("}", "").replace(",", "_").replace("=", "_")
            lines.append(f"# TYPE {safe} counter")
            lines.append(f"{name} {value}")
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines)


class EventLogger:
    """
    Logs all agent events in structured JSON.
    Also maintains a recent-events ring buffer for the dashboard.
    """

    def __init__(self, max_recent: int = 500):
        self.metrics = MetricsCollector()
        self._recent: deque[dict] = deque(maxlen=max_recent)

    def _emit(self, event_type: str, data: dict, level: str = "info"):
        record = {
            "ts": datetime.utcnow().isoformat(),
            "event": event_type,
            "level": level,
            **data,
        }
        _write_jsonl(_EVENT_LOG if level != "error" else _ERROR_LOG, record)
        self._recent.appendleft(record)

        std_log = log.error if level == "error" else log.info
        std_log("[%s] %s", event_type, json.dumps(data, default=str)[:200])

    # ── Agent events ─────────────────────────────────────────────────────────

    def log_agent_response(self, reply: dict):
        self._emit("agent_response", {
            "agent": reply.get("agent"),
            "channel": reply.get("channel"),
            "needs_review": reply.get("needs_review"),
            "text_len": len(reply.get("text", "")),
            "tool_calls": len(reply.get("tool_results", [])),
        })
        self.metrics.inc("agent_responses_total", labels={"agent": reply.get("agent", "unknown")})
        if reply.get("needs_review"):
            self.metrics.inc("responses_pending_review_total")

    def log_task_created(self, task_id: str, agent: str, title: str, priority: str):
        self._emit("task_created", {"task_id": task_id, "agent": agent, "title": title, "priority": priority})
        self.metrics.inc("tasks_created_total", labels={"agent": agent})

    def log_task_completed(self, task_id: str, agent: str, duration_ms: float):
        self._emit("task_completed", {"task_id": task_id, "agent": agent, "duration_ms": duration_ms})
        self.metrics.inc("tasks_completed_total", labels={"agent": agent})
        self.metrics.observe("task_duration_ms", duration_ms)

    def log_tool_call(self, agent: str, tool: str, success: bool, duration_ms: float):
        self._emit("tool_call", {"agent": agent, "tool": tool, "success": success, "duration_ms": duration_ms})
        self.metrics.inc("tool_calls_total", labels={"agent": agent, "tool": tool, "success": str(success)})
        self.metrics.observe("tool_duration_ms", duration_ms)

    def log_llm_call(self, provider: str, model: str, input_tokens: int, output_tokens: int, latency_ms: float):
        self._emit("llm_call", {
            "provider": provider, "model": model,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "latency_ms": round(latency_ms, 1),
        })
        self.metrics.inc("llm_calls_total", labels={"provider": provider})
        self.metrics.inc("tokens_in_total", value=input_tokens)
        self.metrics.inc("tokens_out_total", value=output_tokens)
        self.metrics.observe("llm_latency_ms", latency_ms)

    def log_safety_block(self, agent: str, reason: str):
        self._emit("safety_block", {"agent": agent, "reason": reason}, level="warning")
        self.metrics.inc("safety_blocks_total", labels={"agent": agent})

    def log_error(self, component: str, error: str, context: dict | None = None):
        self._emit("error", {"component": component, "error": error, **(context or {})}, level="error")
        self.metrics.inc("errors_total", labels={"component": component})

    def log_registration(self, team_name: str, agent_count: int):
        self._emit("team_registered", {"team": team_name, "agents": agent_count})
        self.metrics.inc("registrations_total")
        self.metrics.set_gauge("registered_agents", agent_count)

    # ── Recent events for dashboard ───────────────────────────────────────────

    def recent_events(self, limit: int = 100, event_type: Optional[str] = None) -> list[dict]:
        events = list(self._recent)
        if event_type:
            events = [e for e in events if e["event"] == event_type]
        return events[:limit]

    def read_log_tail(self, n: int = 200) -> list[dict]:
        """Read last N lines from the event log file."""
        records = []
        try:
            lines = _EVENT_LOG.read_text().strip().split("\n") if _EVENT_LOG.exists() else []
            for line in lines[-n:]:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
        return list(reversed(records))


# Global singleton
event_logger = EventLogger()
