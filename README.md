# 🤖 Slack Workplace Agent Team Generator

> **Production-grade, multi-agent Slack workplace system powered by NVIDIA NIM + Nemotron models.**
> Register an entire AI-powered team from a single YAML spec — engineering, ops, support, PM, security, and more.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![NVIDIA NIM](https://img.shields.io/badge/NVIDIA-NIM-76b900.svg)](https://build.nvidia.com/nim/apis)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![Slack Bolt](https://img.shields.io/badge/Slack-Bolt-4A154B.svg)](https://slack.dev/bolt-python)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ What's New in v2.0

| Feature | Description |
|---|---|
| **NVIDIA NIM first-class** | Nemotron-70B, Nemotron-340B, Hermes-3, and all NIM models as primary provider |
| **One-command registration** | POST a YAML/JSON spec → agents + Slack channels auto-provisioned |
| **Multi-agent orchestration** | Task routing, delegation, ReAct tool loops, subtask decomposition |
| **Memory + skills** | Per-thread, per-channel, and long-term skill memory (Hermes-style) |
| **Plugin tool system** | GitHub, Jira, Google Drive, Web Search, Calculator, HTTP, Slack — all extensible |
| **Safety toggles** | `autonomy: off|review|full` per agent + PII redaction + prompt injection guard |
| **Slack App Manifest** | Auto-generate a complete Slack manifest from your team spec |
| **Web dashboard** | Live agent grid, task board, event log, Prometheus metrics |
| **Docker stack** | One `docker compose up` for the full system with Redis + Postgres |

---

## 🏗 Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                     Slack Workspace                                 │
│  #engineering  #incidents  #product  #support  #agent-coordination │
└────────────────────┬───────────────────────────────────────────────┘
                     │ Slack Events (Socket Mode / Webhooks)
                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                FastAPI Application  (:8000)                         │
│                                                                     │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────────┐ │
│  │  /api/       │  │  /dashboard   │  │  Slack Bolt             │ │
│  │  register    │  │  (Web UI)     │  │  event_handler.py       │ │
│  │  agents      │  │               │  │                         │ │
│  │  tasks       │  └───────────────┘  └────────────┬────────────┘ │
│  │  manifest    │                                   │              │
│  └──────────────┘                                   ▼              │
│                                        ┌─────────────────────────┐ │
│                                        │  Orchestrator           │ │
│                                        │  • Route to agents      │ │
│                                        │  • Delegate tasks       │ │
│                                        │  • Decompose subtasks   │ │
│                                        └──────────┬──────────────┘ │
└─────────────────────────────────────────────────┬─┘────────────────┘
                                                   │
        ┌──────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│  Agent Layer                                                       │
│                                                                    │
│  AgentRegistry ──► [arch-bot] [eng-bot] [ops-bot] [support-bot]  │
│                    [pm-bot]   [data-bot] [sec-bot]                │
│                                                                    │
│  Each agent has:                                                   │
│    Provider (NIM/OpenAI/Anthropic/Groq)                           │
│    Memory (thread + channel + skills)                              │
│    Tools (GitHub, Jira, Web, HTTP, Slack…)                        │
│    Safety (autonomy level + PII redaction)                         │
└──────────┬──────────────────────┬───────────────────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────┐   ┌────────────────────────────────────────┐
│  LLM Providers   │   │  Tool Plugins                          │
│                  │   │                                        │
│  ★ NVIDIA NIM   │   │  github_plugin    jira_plugin          │
│    Nemotron-70B  │   │  web_search       calculator_plugin    │
│    Nemotron-340B │   │  slack_plugin     http_plugin          │
│    Hermes-3      │   │  gdrive_plugin    [custom...]          │
│  • OpenAI        │   └────────────────────────────────────────┘
│  • Anthropic     │
│  • Groq          │   ┌────────────────────────────────────────┐
└──────────────────┘   │  Memory (Redis / in-process)          │
                        │  • Thread context                     │
                        │  • Channel summaries                  │
                        │  • Learned skills                     │
                        └────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Clone and bootstrap

```bash
git clone https://github.com/YOUR_ORG/slack-multi-agent.git
cd slack-multi-agent
bash scripts/bootstrap.sh
```

The bootstrap script:
- Creates a Python virtual environment and installs dependencies
- Copies `.env.example` → `.env` (fill in your keys)
- Starts Redis + Postgres via Docker (if Docker is available)

### 2. Configure API keys

```bash
# Edit .env with your keys:
NIM_API_KEY=nvapi-...        # https://build.nvidia.com/nim/apis (free tier!)
SLACK_BOT_TOKEN=xoxb-...     # https://api.slack.com/apps
SLACK_APP_TOKEN=xapp-...     # App-Level Tokens → connections:write scope
SLACK_SIGNING_SECRET=...
```

> **NIM API key** is available for free at [build.nvidia.com/nim/apis](https://build.nvidia.com/nim/apis).

### 3. Create your Slack App

```bash
# Start the app
python main.py

# Generate a Slack App Manifest for your team
curl http://localhost:8000/api/manifest | python -m json.tool > manifest.json
```

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From a manifest**
2. Paste the contents of `manifest.json`
3. Install the app to your workspace
4. Copy the Bot Token (`xoxb-…`) and App-Level Token (`xapp-…`) into `.env`

### 4. Register your agent team

```bash
# Register the full workplace team (Eng, Ops, Support, PM, Data, Security)
curl -X POST http://localhost:8000/api/register \
     -H "Content-Type: application/yaml" \
     --data-binary @examples/full-workplace-team.yaml
```

This single command:
- Registers 7 agents with their roles, providers, and models
- Auto-creates Slack channels (`#engineering`, `#incidents`, `#product`, etc.)
- Auto-creates per-agent channels (`#agent-eng-bot`, etc.)
- Posts welcome messages in each channel
- Wires all routing so agents respond to messages in their channels

### 5. Open the dashboard

```bash
open http://localhost:8000/dashboard
```

---

## 🐳 Docker Deployment

```bash
# Full stack (app + Redis + Postgres)
cd docker
docker compose up -d

# With observability (Prometheus + Grafana)
docker compose --profile observability up -d

# View logs
docker compose logs -f app
```

The Docker stack includes:
- **App** on port `8000` with auto-restart
- **Redis** for conversation memory
- **Postgres** for task persistence
- **Prometheus** on `9090` (observability profile)
- **Grafana** on `3000` (observability profile)

---

## 📋 Agent Registration API

### Full team registration

```bash
POST /api/register
Content-Type: application/yaml   # or application/json

team_name: My Startup Team
agents:
  - name: eng-bot
    role: engineer
    provider: nim
    model: nvidia/llama-3.1-nemotron-70b-instruct
    channels: [engineering, general]
    tools:
      - name: github
        enabled: true
    safety:
      autonomy: review
```

### Single agent registration

```bash
POST /api/agents
Content-Type: application/json

{
  "name": "data-bot",
  "role": "data_analyst",
  "provider": "nim",
  "model": "nvidia/hermes-3-llama-3.1-70b",
  "channels": ["analytics"],
  "tools": [{"name": "calculator", "enabled": true}],
  "safety": {"autonomy": "full"}
}
```

### Other endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/agents` | List all agents |
| `GET` | `/api/agents/{name}` | Get a single agent |
| `DELETE` | `/api/agents/{name}` | Deactivate an agent |
| `GET` | `/api/tasks` | List tasks (filter by agent/status) |
| `PATCH` | `/api/tasks/{id}` | Update a task |
| `GET` | `/api/stats` | Team statistics |
| `GET` | `/api/manifest` | Generate Slack App Manifest |
| `GET` | `/api/providers` | Check which providers are configured |
| `GET` | `/api/docs` | Swagger UI |
| `GET` | `/dashboard` | Web dashboard |
| `GET` | `/dashboard/api/metrics` | Metrics JSON |
| `GET` | `/dashboard/api/metrics/prometheus` | Prometheus text |
| `GET` | `/health` | Health check |

---

## 🧠 NVIDIA NIM Models

NIM is the **default and first-class provider**. All models are available at `https://integrate.api.nvidia.com/v1` with your NIM API key.

| Alias | Full Model ID | Best For |
|---|---|---|
| `nemotron-70b` | `nvidia/llama-3.1-nemotron-70b-instruct` | General, orchestration, complex reasoning |
| `nemotron-340b` | `nvidia/nemotron-4-340b-instruct` | Ultra-complex tasks, highest quality |
| `hermes3-70b` | `nvidia/hermes-3-llama-3.1-70b` | Tool calling, structured output |
| `hermes3-8b` | `nvidia/hermes-3-llama-3.1-8b` | Fast tool-calling, high throughput |
| `llama3-405b` | `meta/llama-3.1-405b-instruct` | Flagship open model quality |
| `mixtral-8x22b` | `mistralai/mixtral-8x22b-instruct-v0.1` | Multi-language, code |
| `mistral-nemo` | `nv-mistralai/mistral-nemo-12b-instruct` | Fast, efficient, customer-facing |

Use short aliases directly in your YAML spec:

```yaml
model: nemotron-70b      # → resolved to full NIM model ID automatically
```

---

## 🏢 Full Workplace Team Example

The `examples/full-workplace-team.yaml` defines a complete 7-agent team:

```
Acme Engineering Team
│
├── 🧠 arch-bot       (Orchestrator) — NIM Nemotron-70B
│   └── Channels: #engineering, #incidents, #product, #agent-coordination
│
├── ⚙️ eng-bot        (Engineer)     — NIM Nemotron-70B
│   └── Channels: #engineering, #incidents
│   └── Tools: GitHub, Web Search, Calculator, HTTP
│
├── 🛠️ ops-bot        (DevOps/SRE)   — NIM Nemotron-340B
│   └── Channels: #incidents, #engineering
│   └── Tools: GitHub, Web Search, HTTP
│
├── 💬 support-bot    (Support)      — NIM Mistral-Nemo-12B
│   └── Channels: #customer-support
│   └── Tools: Jira, Web Search, Slack
│
├── 📋 pm-bot         (PM)           — OpenAI GPT-4o
│   └── Channels: #product, #engineering
│   └── Tools: Jira, GitHub, Web Search
│
├── 📊 data-bot       (Data Analyst) — NIM Hermes-3-70B
│   └── Channels: #data-insights, #product
│   └── Tools: Calculator, Web Search, HTTP
│
└── 🔒 sec-bot        (Security)     — Anthropic Claude 3.5
    └── Channels: #security-alerts, #engineering, #incidents
    └── Tools: GitHub, Web Search, HTTP
```

**How it works in Slack:**

```
You: @eng-bot Can you review the auth changes in PR #247?
eng-bot: Sure! Looking at PR #247 now...
  [calls github_list_prs tool]
  [calls github_get_issue tool]
  I've reviewed PR #247. Here are my findings:
  
  ⚠️ Security concern in auth.py line 142: ...
  ✅ Good use of parameterized queries
  📝 Suggest adding rate limiting middleware
  
  Tagging @sec-bot for the security concern.

sec-bot: Thanks for the tag! I see a potential JWT validation gap...
```

---

## 🔒 Safety & Autonomy Levels

Each agent has an independently configurable `autonomy` level:

| Level | Behavior |
|---|---|
| `off` | Agent never responds. All messages blocked. Use for paused/deactivated agents. |
| `review` | Agent drafts a response, but it's queued for human approval before posting. *(Default)* |
| `full` | Agent posts immediately without human approval. Use only for trusted, well-tested agents. |

### Additional safety features

- **Prompt injection guard** — blocks known jailbreak patterns before LLM call
- **PII redaction** — SSN, credit cards, emails, phone numbers, secrets redacted from all outputs
- **Rate limiting** — configurable per-agent messages-per-minute cap
- **Content length cap** — enforces `max_tokens_per_response` limit
- **Channel allowlist** — optionally restrict an agent to specific channels only

```yaml
safety:
  autonomy: review          # off | review | full
  content_filter: true      # LLM-based content filtering
  pii_redaction: true       # redact SSN, CC, email, phone, secrets
  rate_limit_per_minute: 30
  max_tokens_per_response: 2048
  allowed_channels:         # empty = all channels; list = restricted
    - engineering
    - incidents
```

---

## 🔧 Tool Plugins

Agents call external tools in a ReAct loop (up to 8 iterations per message).

### Built-in plugins

| Plugin | Functions | Auth |
|---|---|---|
| `github` | `github_create_issue`, `github_list_prs`, `github_get_issue`, `github_search_code` | `GITHUB_TOKEN` |
| `jira` | `jira_create_issue`, `jira_search_issues`, `jira_update_issue` | `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` |
| `web_search` | `web_search`, `fetch_url` | None (DuckDuckGo) |
| `calculator` | `calculate` | None |
| `slack` | `slack_search_messages`, `slack_post_message`, `slack_get_channel_history` | `SLACK_BOT_TOKEN` |
| `http` | `http_request` | None |

### Adding a custom plugin

```python
# tools/plugins/my_plugin.py
from tools.dispatcher import BasePlugin
from agents.models import Agent

class Plugin(BasePlugin):
    name = "my_tool"

    def get_schemas(self) -> list[dict]:
        return [{
            "type": "function",
            "function": {
                "name": "my_function",
                "description": "Does something useful",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"}
                    },
                    "required": ["input"]
                }
            }
        }]

    async def execute(self, function_name: str, arguments: dict, agent: Agent):
        if function_name == "my_function":
            return {"result": f"Processed: {arguments['input']}"}
```

Then add to `tools/dispatcher.py`:
```python
PLUGIN_REGISTRY["my_tool"] = "tools.plugins.my_plugin"
```

And enable it in your agent spec:
```yaml
tools:
  - name: my_tool
    enabled: true
    config:
      api_url: https://my-api.example.com
```

---

## 🧠 Memory & Skills

Each agent maintains three levels of memory:

### 1. Thread-level (short-term)
Full message history for the current Slack thread. Auto-summarised after `summarise_after` messages.

### 2. Channel-level (medium-term)
Compressed summaries of past conversations in each channel, injected as system context.

### 3. Skill memory (long-term)
Procedural knowledge extracted from conversations — things the agent "learned" about your codebase, preferences, and workflows. Persisted across restarts (Redis or disk).

```yaml
memory:
  enabled: true
  max_context_messages: 80    # max messages kept in active context window
  summarise_after: 30         # auto-summarise after this many messages
  persist_skills: true        # extract and store learned skills
```

**Example learned skill:**
> "When creating GitHub issues for frontend bugs, always add labels: ['bug', 'frontend'] and link to the Jira ticket in the description."

---

## 🔌 Multi-Provider Support

| Provider | Key Variable | Default Model |
|---|---|---|
| **NVIDIA NIM** ⭐ | `NIM_API_KEY` | `nvidia/llama-3.1-nemotron-70b-instruct` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` |
| Groq | `GROQ_API_KEY` | `llama-3.1-70b-versatile` |

Provider fallback order: NIM → OpenAI → Anthropic → Groq (uses first with a valid key).

Check which providers are active:
```bash
curl http://localhost:8000/api/providers
```

---

## 📊 Observability & Dashboard

### Web Dashboard (`/dashboard`)
- **Agent grid** — role, provider, autonomy level, message/task counts, active status
- **Task board** — pending, in-progress, waiting for review, done
- **Event log** — last 100 events with timestamps and agent attribution
- **Auto-refreshes** every 15 seconds

### Prometheus metrics (`/dashboard/api/metrics/prometheus`)
```
agent_responses_total{agent="eng-bot"} 42
llm_calls_total{provider="nim"} 156
tokens_in_total 284920
tokens_out_total 64830
task_duration_ms{quantile="0.95"} 3420.5
safety_blocks_total{agent="eng-bot"} 2
tool_calls_total{agent="ops-bot",tool="github"} 17
```

### Structured event log (`logs/events.jsonl`)
```json
{"ts":"2026-06-28T12:00:00","event":"agent_response","agent":"eng-bot","channel":"engineering","text_len":412,"tool_calls":2}
{"ts":"2026-06-28T12:00:01","event":"llm_call","provider":"nim","model":"nvidia/llama-3.1-nemotron-70b-instruct","input_tokens":1240,"output_tokens":387,"latency_ms":1832.4}
{"ts":"2026-06-28T12:00:01","event":"tool_call","agent":"eng-bot","tool":"github_create_issue","success":true,"duration_ms":340.1}
```

---

## 📁 Project Structure

```
slack-multi-agent/
│
├── main.py                      ← FastAPI app entry point
├── requirements.txt
├── .env.example                 ← Copy to .env and fill in keys
│
├── config/
│   └── settings.py              ← All env vars via pydantic-settings
│
├── providers/                   ← LLM provider abstraction
│   ├── base.py                  ← BaseProvider interface
│   ├── nim_provider.py          ← ★ NVIDIA NIM (first-class)
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   └── groq_provider.py
│
├── agents/                      ← Agent models and runtime
│   ├── models.py                ← Pydantic models (AgentSpec, Task, etc.)
│   ├── registry.py              ← Global agent + task store
│   ├── orchestrator.py          ← Multi-agent routing, delegation, ReAct
│   └── roles/
│       └── prompts.py           ← Role-based system prompts
│
├── api/routes/
│   └── register.py              ← REST API endpoints
│
├── slack/
│   ├── provisioner.py           ← Auto-create channels + app manifest
│   └── event_handler.py         ← Slack Bolt event handlers
│
├── memory/
│   └── manager.py               ← Thread/channel/skill memory
│
├── tools/
│   ├── dispatcher.py            ← Plugin registry + execution
│   └── plugins/
│       ├── github_plugin.py
│       ├── jira_plugin.py
│       ├── web_search_plugin.py
│       ├── calculator_plugin.py
│       ├── slack_plugin.py
│       └── http_plugin.py
│
├── safety/
│   └── guard.py                 ← Autonomy enforcement, PII, rate limiting
│
├── observability/
│   └── logger.py                ← Structured event log + Prometheus metrics
│
├── dashboard/
│   └── app.py                   ← FastAPI + Jinja2 web dashboard
│
├── examples/
│   ├── full-workplace-team.yaml ← 7-agent full workplace team
│   └── minimal-nim-team.yaml    ← 3-agent NIM-only starter
│
├── scripts/
│   └── bootstrap.sh             ← One-command setup
│
└── docker/
    ├── Dockerfile
    ├── docker-compose.yml       ← App + Redis + Postgres + Prometheus + Grafana
    └── prometheus.yml
```

---

## 🛠 Slash Commands

Once the Slack app is installed, use these slash commands:

| Command | Description |
|---|---|
| `/agent` | List all registered agents |
| `/agent eng-bot` | Show eng-bot's status and config |
| `/agent eng-bot Why is my build failing?` | Ask eng-bot directly |
| `/tasks` | Show recent tasks across all agents |
| `/tasks eng-bot` | Show tasks assigned to eng-bot |
| `/register` | (Admin) Register agents via manifest |

---

## 🔐 Security Considerations

1. **Never commit `.env`** — add it to `.gitignore` immediately
2. **Use `autonomy: review`** for all production agents until you've validated their behavior
3. **Scope Slack tokens** — the bot token only needs the scopes in the manifest
4. **Rotate NIM API keys** regularly at build.nvidia.com
5. **Dashboard auth** — set `DASHBOARD_API_KEY` in production to protect the web UI
6. **Redis TLS** — use `rediss://` URL in production with TLS-enabled Redis

---

## 🧪 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-plugin`
3. Add your plugin in `tools/plugins/my_plugin.py` (see [Custom Plugins](#adding-a-custom-plugin))
4. Add tests in `tests/`
5. Open a pull request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [NVIDIA NIM](https://build.nvidia.com/nim/apis) for Nemotron and Hermes models
- [Slack Bolt for Python](https://slack.dev/bolt-python) for the event framework
- [FastAPI](https://fastapi.tiangolo.com) for the REST API layer
- [Pydantic](https://docs.pydantic.dev) for data validation
