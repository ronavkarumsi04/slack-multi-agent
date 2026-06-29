"""
Web dashboard — FastAPI + Jinja2 UI for inspecting agents, tasks, and logs.
Mounted at /dashboard by the main app.

Features:
  • Agent status grid (role, provider, autonomy, message/task counts)
  • Live task board (pending / in-progress / done)
  • Event log tail (last 200 events, auto-refreshes every 10s)
  • Metrics summary card
  • One-click agent deactivation
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from agents.registry import registry
from observability.logger import event_logger

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Serve templates from the static folder (embedded as strings below)
_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_DIR.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

# ── Inline template (avoids extra file dependency) ────────────────────────────
_INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ team_name }} — Agent Dashboard</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0d1117; color: #e6edf3; min-height: 100vh; }
    .header { background: #161b22; border-bottom: 1px solid #30363d;
              padding: 16px 32px; display: flex; align-items: center; gap: 12px; }
    .header h1 { font-size: 1.4rem; font-weight: 600; }
    .badge { background: #1f6feb; color: #fff; border-radius: 20px;
             padding: 2px 10px; font-size: 0.75rem; font-weight: 600; }
    .nim-badge { background: #76b900; }
    .container { max-width: 1400px; margin: 0 auto; padding: 24px 32px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
    .card h2 { font-size: 1rem; font-weight: 600; margin-bottom: 12px; color: #58a6ff; }
    .agent-card { border-left: 3px solid #58a6ff; }
    .agent-card.nim { border-left-color: #76b900; }
    .agent-name { font-size: 1rem; font-weight: 700; }
    .agent-meta { font-size: 0.78rem; color: #8b949e; margin-top: 4px; }
    .tag { display: inline-block; background: #21262d; border: 1px solid #30363d;
           border-radius: 4px; padding: 1px 6px; font-size: 0.72rem; margin: 2px 1px; }
    .tag.review { border-color: #d29922; color: #d29922; }
    .tag.full { border-color: #3fb950; color: #3fb950; }
    .tag.off  { border-color: #f85149; color: #f85149; }
    .stats-row { display: flex; gap: 16px; margin-top: 10px; }
    .stat { text-align: center; }
    .stat .num { font-size: 1.4rem; font-weight: 700; color: #58a6ff; }
    .stat .lbl { font-size: 0.72rem; color: #8b949e; }
    .task-row { padding: 8px 0; border-bottom: 1px solid #21262d; font-size: 0.85rem; }
    .task-row:last-child { border-bottom: none; }
    .task-status { display: inline-block; width: 80px; font-size: 0.72rem;
                   padding: 1px 6px; border-radius: 4px; text-align: center; }
    .status-pending     { background: #21262d; color: #8b949e; }
    .status-in_progress { background: #1f3d6e; color: #58a6ff; }
    .status-waiting     { background: #3d2b00; color: #d29922; }
    .status-done        { background: #0d2818; color: #3fb950; }
    .status-failed      { background: #3d0d0a; color: #f85149; }
    .log-entry { font-size: 0.75rem; font-family: monospace; padding: 3px 0;
                 border-bottom: 1px solid #161b22; color: #8b949e; }
    .log-entry .ts  { color: #484f58; }
    .log-entry .evt { color: #58a6ff; font-weight: 600; }
    .log-entry.error .evt { color: #f85149; }
    .section-title { font-size: 1.1rem; font-weight: 600; margin: 24px 0 12px; color: #e6edf3; }
    .refresh-note { font-size: 0.75rem; color: #484f58; float: right; }
    .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
    .metric-box { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
                  padding: 12px; text-align: center; }
    .metric-box .val { font-size: 1.6rem; font-weight: 700; color: #58a6ff; }
    .metric-box .key { font-size: 0.72rem; color: #8b949e; margin-top: 4px; }
  </style>
  <script>
    // Auto-refresh every 15 seconds
    setTimeout(() => location.reload(), 15000);
  </script>
</head>
<body>
  <div class="header">
    <span style="font-size:1.6rem">🤖</span>
    <h1>{{ team_name }}</h1>
    <span class="badge">{{ agent_count }} agents</span>
    {% if nim_available %}<span class="badge nim-badge">NVIDIA NIM</span>{% endif %}
    <span class="refresh-note">Auto-refreshes every 15s</span>
  </div>

  <div class="container">

    <!-- Metrics Row -->
    <p class="section-title">📊 Overview</p>
    <div class="metrics-grid">
      <div class="metric-box"><div class="val">{{ stats.total_agents }}</div><div class="key">Total Agents</div></div>
      <div class="metric-box"><div class="val">{{ stats.active_agents }}</div><div class="key">Active</div></div>
      <div class="metric-box"><div class="val">{{ stats.total_tasks }}</div><div class="key">Total Tasks</div></div>
      <div class="metric-box"><div class="val">{{ stats.tasks_by_status.get('waiting', 0) }}</div><div class="key">Pending Review</div></div>
    </div>

    <!-- Agents -->
    <p class="section-title">🤖 Agents</p>
    <div class="grid">
      {% for a in agents %}
      <div class="card agent-card {% if a.provider == 'nim' %}nim{% endif %}">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <div class="agent-name">{{ a.emoji }} {{ a.display_name }}</div>
            <div class="agent-meta">{{ a.role }} · {{ a.provider }}{% if a.model %} · {{ a.model[:30] }}{% endif %}</div>
          </div>
          <span class="tag {{ a.safety.autonomy }}">{{ a.safety.autonomy }}</span>
        </div>
        {% if a.channels %}
        <div style="margin-top:8px;">
          {% for ch in a.channels[:5] %}<span class="tag">#{{ ch }}</span>{% endfor %}
        </div>
        {% endif %}
        {% if a.tools %}
        <div style="margin-top:4px;">
          {% for t in a.tools if t.enabled %}<span class="tag">🔧 {{ t.name }}</span>{% endfor %}
        </div>
        {% endif %}
        <div class="stats-row">
          <div class="stat"><div class="num">{{ a.message_count }}</div><div class="lbl">Messages</div></div>
          <div class="stat"><div class="num">{{ a.task_count }}</div><div class="lbl">Tasks</div></div>
          <div class="stat"><div class="num">{{ '✅' if a.is_active else '⏸️' }}</div><div class="lbl">Status</div></div>
        </div>
      </div>
      {% else %}
      <div class="card"><p style="color:#8b949e">No agents registered. POST to /api/register to add agents.</p></div>
      {% endfor %}
    </div>

    <!-- Tasks -->
    <p class="section-title">📋 Recent Tasks ({{ total_tasks }})</p>
    <div class="card">
      {% for t in tasks %}
      <div class="task-row">
        <span class="task-status status-{{ t.status }}">{{ t.status }}</span>
        <strong>{{ t.title[:60] }}</strong>
        <span style="color:#8b949e; font-size:0.78rem"> → {{ t.assigned_to }} · {{ t.priority }}</span>
      </div>
      {% else %}
      <p style="color:#8b949e; font-size:0.85rem">No tasks yet.</p>
      {% endfor %}
    </div>

    <!-- Event Log -->
    <p class="section-title">📜 Event Log (last 100)</p>
    <div class="card">
      {% for e in events %}
      <div class="log-entry {% if e.level == 'error' %}error{% endif %}">
        <span class="ts">{{ e.ts[:19] }}</span>
        <span class="evt"> {{ e.event }}</span>
        {% if e.agent %} · {{ e.agent }}{% endif %}
        {% if e.channel %} · #{{ e.channel }}{% endif %}
        {% if e.error %} · {{ e.error[:80] }}{% endif %}
      </div>
      {% else %}
      <p style="color:#8b949e; font-size:0.85rem">No events yet.</p>
      {% endfor %}
    </div>

  </div>
</body>
</html>
"""

# Write template to disk
(_TEMPLATE_DIR / "index.html").write_text(_INDEX_HTML)


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    from providers import available_providers
    agents = registry.all_agents()
    tasks = registry.all_tasks()
    events = event_logger.recent_events(limit=100)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "team_name": registry._team_name,
        "agent_count": len([a for a in agents if a.is_active]),
        "nim_available": "nim" in available_providers(),
        "stats": registry.stats(),
        "agents": agents,
        "tasks": sorted(tasks, key=lambda t: t.updated_at, reverse=True)[:20],
        "total_tasks": len(tasks),
        "events": events,
    })


@router.get("/api/metrics")
async def metrics():
    return JSONResponse(event_logger.metrics.summary())


@router.get("/api/metrics/prometheus", response_class=HTMLResponse)
async def prometheus_metrics():
    return HTMLResponse(
        content=event_logger.metrics.prometheus_text(),
        media_type="text/plain",
    )


@router.get("/api/events")
async def api_events(limit: int = 100, event_type: str | None = None):
    return {"events": event_logger.recent_events(limit=limit, event_type=event_type)}


@router.get("/api/log")
async def api_log(n: int = 100):
    return {"entries": event_logger.read_log_tail(n)}
