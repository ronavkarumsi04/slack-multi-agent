#!/usr/bin/env bash
# ============================================================
# push_to_github.sh  — One-command deploy to GitHub
# Usage:  bash push_to_github.sh
# ============================================================
set -euo pipefail

REPO="ronavkarumsi04/slack-multi-agent"
TOKEN="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"
REMOTE="https://${TOKEN}@github.com/${REPO}.git"

echo "╔══════════════════════════════════════════════════════╗"
echo "║   Slack Workplace Agent Team — GitHub Push Script    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Determine script location — work from the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "📂  Working directory: $SCRIPT_DIR"
echo ""

# ── 1. Check git is available ──────────────────────────────
if ! command -v git &>/dev/null; then
  echo "❌  git not found. Install git and re-run."
  exit 1
fi
echo "✅  git found: $(git --version)"

# ── 2. Init repo if needed ─────────────────────────────────
if [ ! -d ".git" ]; then
  echo "🔧  Initialising git repo..."
  git init -b main
else
  echo "✅  Git repo already initialised"
fi

# ── 3. Configure author (needed if user has no global config) ─
git config user.email "ronavkarumsi@gmail.com" 2>/dev/null || true
git config user.name  "Ronav" 2>/dev/null || true

# ── 4. Set/update remote ──────────────────────────────────
if git remote get-url origin &>/dev/null; then
  git remote set-url origin "$REMOTE"
  echo "✅  Remote 'origin' updated"
else
  git remote add origin "$REMOTE"
  echo "✅  Remote 'origin' added"
fi

# ── 5. Fetch existing main so we can merge cleanly ────────
echo ""
echo "⬇️   Fetching existing remote state..."
git fetch origin main --depth=1 2>/dev/null || echo "   (fresh repo or first push — skipping fetch)"

# ── 6. Stage everything ───────────────────────────────────
echo ""
echo "📦  Staging all files..."
git add -A
git status --short | head -60

# ── 7. Commit ─────────────────────────────────────────────
echo ""
COMMIT_MSG="feat: add Slack Workplace Agent Team Generator (Python/FastAPI rewrite)

- NVIDIA NIM + Nemotron as first-class LLM provider
- Multi-provider support: NIM → OpenAI → Anthropic → Groq
- 8 named agents: Aurelius, Maya, Ethan, Lena, Iris, Omar, Kai, Noah
- Agent registration API (/api/register) with YAML/JSON specs
- Multi-agent orchestration with ReAct tool loop
- 3-tier memory system (thread, channel, skills)
- Tool-calling plugin system: GitHub, Jira, web search, calculator, HTTP
- Safety/autonomy toggles per agent (off|review|full)
- Web dashboard with dark mode at /dashboard
- Docker deployment + bootstrap script
- Slack app manifest auto-generation
- Auto-create Slack channels + invite agents
- Prometheus-compatible observability + JSONL event log
- Comprehensive README with full workplace team examples"

if git diff --cached --quiet; then
  echo "ℹ️   Nothing new to commit — repo is already up to date"
else
  git commit -m "$COMMIT_MSG"
  echo "✅  Committed!"
fi

# ── 8. Push ───────────────────────────────────────────────
echo ""
echo "🚀  Pushing to GitHub (origin/main)..."
git push origin main --force-with-lease 2>/dev/null \
  || git push origin HEAD:main --force
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅  All files pushed to github.com/${REPO}  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Visit https://github.com/${REPO}"
echo "  2. Create .env from .env.example and fill in your keys"
echo "  3. Run:  docker compose -f docker/docker-compose.yml up"
echo "  4. Create your Slack app at https://api.slack.com/apps"
echo "     → Paste the manifest from GET /api/manifest"
