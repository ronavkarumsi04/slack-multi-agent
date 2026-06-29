#!/usr/bin/env bash
# ============================================================
#  Slack Workplace Agent Team Generator — One-Command Bootstrap
#  Usage: bash scripts/bootstrap.sh
# ============================================================
set -euo pipefail
IFS=$'\n\t'

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Slack Workplace Agent Team Generator — Bootstrap       ║${NC}"
echo -e "${CYAN}║   Powered by NVIDIA NIM + Nemotron                       ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
info "Checking prerequisites..."

command -v python3 >/dev/null 2>&1 || error "Python 3.11+ is required"
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
info "Python $PY_VER detected"

command -v docker >/dev/null 2>&1 || warn "Docker not found — skipping Docker setup"
DOCKER_AVAILABLE=$(command -v docker >/dev/null 2>&1 && echo "yes" || echo "no")

# ── 2. Virtual environment ────────────────────────────────────────────────────
info "Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  ok "Created .venv"
else
  info ".venv already exists — skipping"
fi

source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
ok "Dependencies installed"

# ── 3. Environment file ───────────────────────────────────────────────────────
info "Checking .env file..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  warn ".env created from .env.example — please edit it with your API keys!"
  echo ""
  echo -e "  ${YELLOW}Required keys:${NC}"
  echo "    NIM_API_KEY            → https://build.nvidia.com/nim/apis (free tier available)"
  echo "    SLACK_BOT_TOKEN        → https://api.slack.com/apps → OAuth & Permissions"
  echo "    SLACK_APP_TOKEN        → https://api.slack.com/apps → Basic Information → App-Level Tokens"
  echo "    SLACK_SIGNING_SECRET   → https://api.slack.com/apps → Basic Information"
  echo ""
else
  ok ".env already exists"
fi

# ── 4. Create required directories ───────────────────────────────────────────
info "Creating runtime directories..."
mkdir -p logs data dashboard/templates
ok "Directories ready"

# ── 5. Docker startup (optional) ─────────────────────────────────────────────
if [ "$DOCKER_AVAILABLE" = "yes" ]; then
  info "Starting Docker services (Redis + Postgres)..."
  cd docker
  docker compose up -d redis postgres 2>/dev/null || warn "Docker compose failed — using in-process storage"
  cd ..
  ok "Docker services started"
fi

# ── 6. Register the example workplace team ────────────────────────────────────
REGISTER_EXAMPLE=${REGISTER_EXAMPLE:-"no"}
if [ "$REGISTER_EXAMPLE" = "yes" ]; then
  info "Registering example workplace team..."
  # Start app in background temporarily
  python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
  APP_PID=$!
  sleep 4

  curl -s -X POST http://localhost:8000/api/register \
    -H "Content-Type: application/yaml" \
    --data-binary @examples/full-workplace-team.yaml | python3 -m json.tool

  kill $APP_PID 2>/dev/null || true
  ok "Example team registered"
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Bootstrap complete! Next steps:                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  1. Edit .env with your API keys"
echo "  2. Start the app:              python main.py"
echo "     OR with Docker:             cd docker && docker compose up"
echo "  3. Open the dashboard:         http://localhost:8000/dashboard"
echo "  4. View API docs:              http://localhost:8000/api/docs"
echo "  5. Register your team:         POST http://localhost:8000/api/register"
echo "     with examples/full-workplace-team.yaml as the body"
echo ""
echo -e "  ${CYAN}Generate a Slack App Manifest:${NC}  GET http://localhost:8000/api/manifest"
echo -e "  ${CYAN}Paste it at:${NC} https://api.slack.com/apps → Create App → From manifest"
echo ""
