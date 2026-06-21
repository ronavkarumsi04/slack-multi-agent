# Slack Multi-Agent System — Aurelius & Team

A fully free, cloud-hosted multi-agent Slack system with 8 specialized AI agents, shared knowledge base, sandboxed browser automation, GitHub integration, and runtime model switching via NVIDIA NIM.

## 🎯 Overview

| Agent | Role | Specialty |
|-------|------|-----------|
| **Aurelius** | Orchestrator | Coordinates team, summarizes discussions, requests confirmations |
| **Maya** | Engineering | Code, architecture, debugging, technical decisions |
| **Ethan** | Research | Web research, synthesis, citations, feasibility |
| **Lena** | Operations | Planning, task breakdown, timelines, blockers |
| **Iris** | Communications | Writing, announcements, docs, tone adaptation |
| **Omar** | Customer Experience | Feedback, onboarding, support, advocacy |
| **Kai** | Automation | Sandbox browser tasks, scraping, testing, scripts |
| **Noah** | Personal Assistant | Calendar, reminders, notes, private tasks |

## 🚀 Quick Start (5 Minutes)

### Prerequisites
- GitHub account
- Slack workspace (admin access)
- Vercel account (free)
- Supabase account (free)
- Upstash Redis account (free)
- NVIDIA NIM API key (free tier) — [Get one here](https://build.nvidia.com/)
- Groq API key (free fallback) — [Get one here](https://console.groq.com/)

### 1. Clone & Install
```bash
git clone <your-repo-url>
cd slack-multi-agent
npm install
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with all your keys
```

### 3. Set Up Infrastructure
```bash
# Create Supabase tables
npm run setup:supabase

# Create Redis indexes
npm run setup:redis

# Generate Slack app manifest
npm run setup:slack
```

### 4. Deploy to Vercel
```bash
vercel --prod
# Add all env vars in Vercel dashboard
```

### 5. Install Slack App
- Use the generated manifest URL or manual setup (see Slack App Checklist below)
- Subscribe to events, add slash commands, install to workspace

### 6. Create Channels
Create these channels in Slack and invite the bot:
```
#aurelius-orchestrator
#maya-engineering
#ethan-research
#lena-operations
#iris-communications
#omar-customer
#kai-automation
#noah-personal
#agent-discussion
#agent-approvals
#agent-logs
```

### 7. Test It
In Slack:
```
/model status
/kb add "Test" "This is a test entry" #test
/kb search "test"
/task run "Visit example.com and get title" --domains example.com
@Aurelius Hello team, let's plan a new feature
```

## 📁 Project Structure

```
slack-multi-agent/
├── apps/
│   ├── slack-bot/          # Main Bolt app (Vercel serverless)
│   └── dashboard/          # Next.js admin dashboard
├── packages/
│   ├── shared/             # Types, constants, prompts
│   └── config/             # Validation schemas
├── scripts/                # Setup scripts
├── supabase/               # Database migrations
├── docker/                 # Sandbox Docker image
└── vercel.json             # Vercel deployment config
```

## 🤖 Slack Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/model status` | Show current model | `/model status` |
| `/model set nim:<model>` | Set NIM model | `/model set nim:meta/llama-3.1-70b-instruct` |
| `/model set fallback:<model>` | Set fallback model | `/model set fallback:llama-3.1-70b-versatile` |
| `/model list` | List available models | `/model list` |
| `/kb add "title" "content" #tags` | Add knowledge entry | `/kb add "API Spec" "REST API v2..." #api #v2` |
| `/kb search "query" [#tag]` | Search knowledge | `/kb search "authentication" #api` |
| `/kb list [#tag]` | List recent entries | `/kb list #api` |
| `/kb delete <id>` | Delete entry | `/kb delete kb_12345` |
| `/task run "desc" --domains d1,d2 --timeout 60` | Request automation | `/task run "Scrape pricing" --domains pricing.com --timeout 30` |
| `/task approve <id>` | Approve task | `/task approve task_abc123` |
| `/task reject <id> "reason"` | Reject task | `/task reject task_abc123 "Not needed"` |
| `/task list` | List pending tasks | `/task list` |
| `/task logs <id>` | View task logs | `/task logs task_abc123` |
| `/task allowlist add|remove <domain>` | Manage domains | `/task allowlist add api.github.com` |
| `/agent prompt <agent> "new prompt"` | Update agent prompt | `/agent prompt Maya "You are a senior engineer..."` |
| `/agent status` | Show all agent status | `/agent status` |
| `/help` | Show all commands | `/help` |

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Slack     │────▶│  Vercel      │────▶│  NVIDIA NIM │
│   Events    │     │  (Bolt App)  │     │  (Primary)  │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌─────────┐ ┌──────────┐ ┌──────────┐
         │Supabase │ │ Upstash  │ │  GitHub  │
         │(KB/DB)  │ │ Redis    │ │  (Sync)  │
         └─────────┘ └──────────┘ └──────────┘
              │
              ▼
         ┌──────────┐
         │ Sandbox  │
         │(Playwright)│
         └──────────┘
```

## 🔧 Configuration

### Agent Prompts
Edit `packages/shared/prompts.ts` or use `/agent prompt <agent> "new prompt"` in Slack.

### Model Switching
```bash
# In Slack
/model set nim:meta/llama-3.1-8b-instruct    # Faster, smaller
/model set nim:nvidia/nemotron-3-ultra       # Best reasoning
/model set fallback:llama-3.1-70b-versatile  # Free fallback
```

### Knowledge Base
- Stored in Supabase (PostgreSQL + pgvector)
- Full-text search enabled
- Tags for categorization
- Agents can read/write via tools

### Sandbox (Kai)
- Playwright in Docker container
- Domain allowlist enforced
- Approval required before execution
- Logs stored in Redis (7-day retention)
- Max 60s per task (configurable)

## 📊 Monitoring

### Vercel Dashboard
- Function logs: `vercel logs`
- Metrics: Function duration, errors, invocations

### Slack Channels
- `#agent-logs` — All agent activity
- `#agent-approvals` — Kai task approvals
- `#agent-discussion` — Inter-agent conversations

### Health Checks
```bash
# Check deployment
curl https://your-app.vercel.app/api/health

# Check Redis
redis-cli -u $UPSTASH_REDIS_REST_URL ping

# Check Supabase
curl -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" $SUPABASE_URL/rest/v1/
```

## 🐛 Troubleshooting

| Problem | Solution |
|---------|----------|
| "NIM_API_KEY not set" | Add to Vercel env vars, redeploy |
| Slack commands not working | Verify signing secret, check Vercel function logs |
| Agents not responding | Check NIM API quota, try `/model set fallback:...` |
| Kai tasks failing | Check allowlist, verify domain accessibility |
| Knowledge base empty | Run `npm run setup:supabase`, check RLS policies |
| Session lost | Redis TTL expired (30 days), just continue |

## 💰 Free Tier Limits

| Service | Free Limit | Our Usage |
|---------|------------|-----------|
| Vercel | 100GB-hours/mo | ~10GB-hours |
| Supabase | 500MB DB, 1GB bandwidth | ~50MB |
| Upstash Redis | 10K requests/day | ~2K/day |
| NVIDIA NIM | 1M tokens/mo | ~200K/mo |
| Groq | 14K requests/day | Fallback only |
| GitHub Actions | 2K minutes/mo | ~200/min |
| Playwright (local) | Unlimited | Local only |

## 🔐 Security

- All secrets in Vercel environment variables (never in code)
- Slack request verification on every request
- Rate limiting per user (10 req/min)
- Kai sandbox: no network by default, allowlist only
- Supabase RLS policies (team isolation)
- No persistent browser state between tasks

## 📝 License

MIT — Use freely for any purpose.

---

## 2. STEP-BY-STEP IMPLEMENTATION PLAN

### Phase 1: Foundation & Infrastructure

**Step 1 — Create GitHub Repository**
- **What to do:** Create a new private GitHub repository named `slack-multi-agent` and clone it locally
- **Where to put it:** GitHub.com → New Repository → Private → Initialize with README
- **What should happen next:** You have a remote repo ready for code
- **How to verify:** `git remote -v` shows your repo URL
- **Common problems and solutions:** If "repository name already exists," add a suffix like `-team`

**Step 2 — Initialize Project Structure**
- **What to do:** Create all folders and files from the repo skeleton above using your file explorer or terminal
- **Where to put it:** Root of cloned repository
- **What should happen next:** All directories exist, ready for code
- **How to verify:** `find . -type f -name "*.ts" -o -name "*.json" | head -20` shows files
- **Common problems and solutions:** Missing `turbo.json` — copy from skeleton; permission errors — run `chmod -R 755 .`

**Step 3 — Install Dependencies**
- **What to do:** Run `npm install` at root to install all workspace dependencies
- **Where to put it:** Terminal at repository root
- **What should happen next:** `node_modules` created, all packages linked
- **How to verify:** `npm list --workspaces` shows all packages without errors
- **Common problems and solutions:** Peer dependency warnings are normal; if `turbo` not found, run `npm install -g turbo`

**Step 4 — Create Vercel Project**
- **What to do:** Go to Vercel dashboard → Add New Project → Import your GitHub repo → Framework: Other → Build Command: `npm run build` → Output Directory: (leave blank)
- **Where to put it:** Vercel.com dashboard
- **What should happen next:** Project created, ready for environment variables
- **How to verify:** Vercel shows project with "Ready to deploy" status
- **Common problems and solutions:** If "No framework detected," create `vercel.json` first (see skeleton)

**Step 5 — Create Supabase Project**
- **What to do:** Go to Supabase.com → New Project → Choose free tier → Name: `slack-multi-agent` → Save credentials
- **Where to put it:** Supabase.com dashboard
- **What should happen next:** Project provisioned (2-3 minutes), you get URL and keys
- **How to verify:** Project status shows "Active," API settings show URL and anon/service keys
- **Common problems and solutions:** If "project name taken," add random suffix; save keys immediately — service role key shown once

**Step 6 — Create Upstash Redis Database**
- **What to do:** Go to Upstash.com → Create Database → Type: Redis → Region: closest to you → Free tier
- **Where to put it:** Upstash.com dashboard
- **What should happen next:** Database created, you get REST URL and token
- **How to verify:** Dashboard shows "Connected" and REST endpoint
- **Common problems and solutions:** If region unavailable, pick next closest; copy both URL and token

**Step 7 — Get NVIDIA NIM API Key**
- **What to do:** Go to build.nvidia.com → Sign in → Get API Key → Create new key → Name: `slack-multi-agent` → Copy key
- **Where to put it:** NVIDIA Build dashboard
- **What should happen next:** You have a `NIM_API_KEY` starting with `nvapi-`
- **How to verify:** Key works in curl test (see Step 15)
- **Common problems and solutions:** If no credits, check NVIDIA free tier eligibility; key must be kept secret

**Step 8 — Get Groq API Key (Fallback)**
- **What to do:** Go to console.groq.com → API Keys → Create Key → Name: `slack-fallback` → Copy
- **Where to put it:** Groq console
- **What should happen next:** You have a `GROQ_API_KEY` starting with `gsk_`
- **How to verify:** Key works in test request
- **Common problems and solutions:** Free tier has rate limits; that's fine for fallback

---

### Phase 2: Slack App Creation

**Step 9 — Create Slack App from Manifest**
- **What to do:** Run `npm run setup:slack` to generate manifest, then go to api.slack.com/apps → Create New App → From Manifest → Paste JSON → Select workspace
- **Where to put it:** Terminal (run script) → Slack API dashboard
- **What should happen next:** App created with all scopes, events, commands pre-configured
- **How to verify:** App shows "Installed" in your workspace, OAuth tokens generated
- **Common problems and solutions:** If manifest invalid, check JSON syntax; if workspace not listed, you need admin rights

**Step 10 — Configure Slack App Settings Manually (If Not Using Manifest)**
- **What to do:** In Slack App config: OAuth & Permissions → Add scopes (see checklist below) → Event Subscriptions → Enable → Request URL: `https://your-vercel-app.vercel.app/slack/events` → Subscribe to events → Slash Commands → Add all 5 commands → Interactivity → Enable → Request URL same as events
- **Where to put it:** api.slack.com/apps → Your App
- **What should happen next:** All URLs verified, green checkmarks
- **How to verify:** Each section shows "Saved" with green check
- **Common problems and solutions:** Vercel URL not ready yet — deploy first (Step 18), then update URLs; "URL verification failed" — check Vercel logs for 404

**Step 11 — Install App to Workspace**
- **What to do:** OAuth & Permissions → Install to Workspace → Allow
- **Where to put it:** Slack App config
- **What should happen next:** Bot User OAuth Token (`xoxb-...`) and Signing Secret generated
- **How to verify:** Tokens appear, "Installed" badge shows
- **Common problems and solutions:** If "app not approved," ask workspace admin to approve

**Step 12 — Generate App-Level Token**
- **What to do:** Basic Information → App-Level Tokens → Generate Token → Name: `socket-mode` → Scopes: `connections:write`, `authorizations:read` → Copy token (`xapp-...`)
- **Where to put it:** Slack App config → Basic Information
- **What should happen next:** Token generated for Socket Mode (optional but recommended)
- **How to verify:** Token starts with `xapp-`
- **Common problems and solutions:** If using HTTP mode (Vercel), you don't strictly need this but it enables real-time features

---

### Phase 3: Database & Storage Setup

**Step 13 — Run Supabase Migrations**
- **What to do:** In Supabase SQL Editor → New Query → Paste contents of `supabase/migrations/001_init_schema.sql` → Run → Repeat for 002 and 003
- **Where to put it:** Supabase Dashboard → SQL Editor
- **What should happen next:** Tables created: `knowledge_base`, `task_approvals`, `agent_configs`, `allowlist_domains`
- **How to verify:** Table Editor shows 4 tables with correct columns
- **Common problems and solutions:** If "pgvector not available," skip vector column or enable extension; RLS policies in 003 may need adjustment for service role

**Step 14 — Initialize Redis Indexes**
- **What to do:** Run `npm run setup:redis` — creates Redis keys for config, sessions, allowlist
- **Where to put it:** Terminal at repo root
- **What should happen next:** Redis has initial keys: `config:<team>`, `allowlist:<team>`
- **How to verify:** Upstash dashboard shows keys; `redis-cli` can query them
- **Common problems and solutions:** If connection fails, check UPSTASH_REDIS_REST_URL and TOKEN in .env

---

### Phase 4: Code Implementation

**Step 15 — Add All Source Code**
- **What to do:** Copy all code files from Section 1 into their exact locations in the repo
- **Where to put it:** Exact paths from repo skeleton
- **What should happen next:** TypeScript compiles without errors
- **How to verify:** `npm run build` succeeds
- **Common problems and solutions:** Missing imports — check `packages/shared` exports; path aliases — ensure `tsconfig.json` has correct `baseUrl` and `paths`

**Step 16 — Configure Environment Variables in Vercel**
- **What to do:** Vercel Dashboard → Project → Settings → Environment Variables → Add all from `.env.example` (10 variables) → Apply to Production, Preview, Development
- **Where to put it:** Vercel project settings
- **What should happen next:** All vars show in dashboard with correct environments
- **How to verify:** `vercel env ls` shows all 10 variables
- **Common problems and solutions:** "Secret not found" — create Vercel secrets first: `vercel secret add nim-api-key "your-key"` then reference `@nim-api-key`

**Step 17 — Deploy to Vercel**
- **What to do:** `vercel --prod` from terminal OR push to main branch (auto-deploy)
- **Where to put it:** Terminal or GitHub push
- **What should happen next:** Deployment succeeds, you get a `https://slack-multi-agent.vercel.app` URL
- **How to verify:** Visit URL → shows "OK" or health endpoint responds
- **Common problems and solutions:** Build fails — check Vercel build logs; function timeout — increase `maxDuration` in vercel.json

**Step 18 — Update Slack App URLs**
- **What to do:** Slack App → Event Subscriptions → Request URL: `https://your-app.vercel.app/slack/events` → Save → Interactivity → Request URL: same → Save
- **Where to put it:** Slack App config
- **What should happen next:** Both URLs verify with green checkmarks
- **How to verify:** Slack shows "Verified" with timestamp
- **Common problems and solutions:** 404 — check vercel.json routes; 500 — check Vercel function logs for missing env vars

---

### Phase 5: Slack Workspace Setup

**Step 19 — Create Required Channels**
- **What to do:** In Slack, create 11 channels (public or private) from the CHANNELS list, invite the bot user (`@Aurelius`) to each
- **Where to put it:** Slack workspace
- **What should happen next:** Bot is member of all channels
- **How to verify:** `/invite @Aurelius` in each channel works; bot appears in member list
- **Common problems and solutions:** If bot not found, reinstall app; if private channels, use `/invite @Aurelius` from a member

**Step 20 — Set Channel IDs in Environment (Optional)**
- **What to do:** Get each channel ID (Right-click → Copy Link → extract ID) → Add to Vercel env vars: `SLACK_ORCHESTRATOR_CHANNEL`, `SLACK_ENGINEERING_CHANNEL`, etc.
- **Where to put it:** Vercel environment variables
- **What should happen next:** App can post to specific channels by ID
- **How to verify:** `/agent status` shows channel connections
- **Common problems and solutions:** Channel IDs start with `C` (public) or `G` (private); don't confuse with names

---

### Phase 6: Testing & Verification

**Step 21 — Test Model Switching**
- **What to do:** In Slack: `/model status` → `/model list` → `/model set nim:meta/llama-3.1-8b-instruct` → `/model status`
- **Where to put it:** Any Slack channel with bot
- **What should happen next:** Model changes confirmed, status shows new model
- **How to verify:** Response shows updated provider and model
- **Common problems and solutions:** "Unknown model" — check spelling against NIM_MODELS list; fallback works if NIM fails

**Step 22 — Test Knowledge Base**
- **What to do:** `/kb add "Test Entry" "This is test content" #test #demo` → `/kb search "test"` → `/kb list #test` → `/kb delete <id>`
- **Where to put it:** Slack
- **What should happen next:** Entries added, searched, listed, deleted successfully
- **How to verify:** Search returns the entry; delete removes it
- **Common problems and solutions:** "Supabase not configured" — check SUPABASE_URL and SERVICE_ROLE_KEY; RLS blocking — ensure service role bypasses RLS

**Step 23 — Test Kai Sandbox Automation**
- **What to do:** `/task allowlist add example.com` → `/task run "Get page title" --domains example.com --timeout 30` → `/task approve <id>` → `/task logs <id>`
- **Where to put it:** Slack
- **What should happen next:** Task approved, Kai executes, logs show page title
- **How to verify:** Logs show navigation, title extraction, success
- **Common problems and solutions:** "Domain not allowed" — run allowlist add first; timeout — increase `--timeout`; Playwright not installed — deploy includes it via Docker

**Step 24 — Test Agent Conversations**
- **What to do:** In `#agent-discussion`: `@Aurelius Let's plan a blog post about our launch` → Watch agents respond in their channels → Aurelius posts summary in `#agent-approvals` → Click "Approve"
- **Where to put it:** Slack channels
- **What should happen next:** Agents discuss, Aurelius summarizes, approval requested, execution on confirm
- **How to verify:** Messages appear in specialist channels; summary in approvals; buttons work
- **Common problems and solutions:** Agents silent — check bot is in channels; mentions not working — verify `app_mentions:read` scope

**Step 25 — Test Agent Prompt Updates**
- **What to do:** `/agent prompt Maya "You are a senior TypeScript engineer who loves testing"` → `@Maya write a test for user auth`
- **Where to put it:** Slack
- **What should happen next:** Maya's behavior changes immediately
- **How to verify:** Response reflects new persona
- **Common problems and solutions:** Prompt not saved — check Supabase `agent_configs` table; old prompt cached — restart session

---

### Phase 7: Dashboard & Polish

**Step 26 — Deploy Dashboard (Optional but Recommended)**
- **What to do:** `cd apps/dashboard && vercel --prod` → Set same env vars → Access dashboard URL
- **Where to put it:** Vercel (separate project or same)
- **What should happen next:** Dashboard shows agent status, KB browser, task monitor
- **How to verify:** Pages load, data matches Slack
- **Common problems and solutions:** CORS errors — add dashboard domain to Supabase/Redis allowed origins

**Step 27 — Set Up GitHub Sync (Optional)**
- **What to do:** GitHub → Settings → Developer Settings → Personal Access Token → Repo scope → Add to Vercel env → Enable webhook in repo → Settings → Webhooks → Payload URL: `https://your-app.vercel.app/api/github/webhook`
- **Where to put it:** GitHub repo settings
- **What should happen next:** Agent configs sync to repo on change
- **How to verify:** Push to repo triggers sync; `/agent status` shows git hash
- **Common problems and solutions:** Webhook fails — check GITHUB_WEBHOOK_SECRET matches; 404 — verify API route exists

---

## 3. SLACK UI SPECIFICATION

### Home Tab (Per User)
**What the user sees:** When clicking the app in Slack sidebar, a personalized dashboard with:
- **Header:** "Welcome back, [Name] — Aurelius & Team at your service"
- **Section 1:** Current model badge (e.g., "🤖 Model: NIM llama-3.1-70b")
- **Section 2:** Quick actions — buttons for "New Task (Kai)", "Search Knowledge", "Agent Status"
- **Section 3:** Recent activity — last 5 KB entries, last 3 tasks, last 2 agent discussions
- **Section 4:** Agent cards — 8 cards showing each agent's status (idle/working), last action, one-click "Talk to [Agent]"

### Modal: Model Selector (`/model set`)
**Trigger:** User types `/model set` without args or clicks "Change Model" in Home tab
**Contents:**
- Title: "Select AI Model"
- Radio buttons: NIM Models (5 options) | Fallback Models (3 options)
- Current selection pre-checked
- "Save" button → calls `/model set` internally
- Example text: "Choose which brain powers the team. NIM models are higher quality; fallback is free and fast."

### Modal: Knowledge Base Entry (`/kb add`)
**Trigger:** `/kb add` without args or "Add Entry" button
**Contents:**
- Title: "Add to Knowledge Base"
- Text input: "Title" (required, max 100 chars)
- Textarea: "Content" (required, max 5000 chars)
- Multi-select: "Tags" (suggestions from existing tags + free input)
- "Save" button
- Example text: "Store decisions, specs, research, or anything the team should remember."

### Modal: Task Approval (Kai)
**Trigger:** Kai posts in `#agent-approvals` for approval
**Contents:**
- Title: "🤖 Automation Task Awaiting Approval"
- Fields: Task ID, Requested by, Description, Domains, Timeout
- Warning: "Kai will control a browser. Only approve if you trust the domains."
- Buttons: "✅ Approve" (primary) | "❌ Reject" (danger) | "🔄 Modify"
- Example text: "Kai wants to visit pricing.example.com to extract current prices. This takes ~15 seconds."

### Modal: Agent Prompt Editor (`/agent prompt`)
**Trigger:** `/agent prompt <agent>` without new prompt
**Contents:**
- Title: "Edit System Prompt: [Agent Name]"
- Textarea: Current prompt (pre-filled, 2000 char max)
- Hint: "Changes take effect immediately. Be specific about role, tone, and constraints."
- "Save" button
- Example text: "Maya's current prompt: 'You are Maya, an engineering specialist...'"

### Block Kit: Agent Discussion Summary (Aurelius)
**Posted in:** `#agent-approvals` after discussion
**Contents:**
- Header: "📋 Discussion Summary — [Topic]"
- Context: "Channel: #maya-engineering | 12 messages | 3 agents"
- Section: Bullet summary (3-5 points)
- Divider
- Actions: "✅ Approve & Execute" | "❌ Reject" | "🔄 Request Changes"
- Example text: "• Maya: Proposed React + Vercel architecture\n• Ethan: Confirmed feasibility, cited Next.js docs\n• Lena: Estimated 3 days, identified auth as blocker\n• Decision needed: Proceed with auth research first?"

---

## 4. SLACK APP CREATION CHECKLIST

### Required OAuth Scopes (Bot Token)
```
app_mentions:read
channels:history
channels:read
chat:write
commands
groups:history
groups:read
im:history
im:read
im:write
mpim:history
mpim:read
reactions:read
reactions:write
users:read
users:read.email
```

### Required Event Subscriptions
```
app_mention
message.channels
message.groups
message.im
reaction_added
```

### Slash Commands (All point to `https://your-app.vercel.app/slack/events`)
| Command | Description | Usage Hint |
|---------|-------------|------------|
| `/model` | Switch/view LLM model | `status`, `set nim:...`, `list` |
| `/kb` | Knowledge base CRUD | `add`, `search`, `list`, `delete` |
| `/task` | Kai sandbox automation | `run`, `approve`, `reject`, `logs`, `allowlist` |
| `/agent` | Agent management | `prompt`, `status`, `enable`, `disable` |
| `/help` | Show all commands | (no args) |

### Interactivity & Shortcuts
- **Interactivity:** ON → Request URL: `https://your-app.vercel.app/slack/events`
- **Shortcuts:** None required (all via commands/mentions)

### App Manifest (Generated by `npm run setup:slack`)
```json
# Slack App Manifest (YAML) - run script to generate
```

---

## 5. HOSTING & DEPLOYMENT CHECKLIST

### Vercel (Primary Host)
- [ ] Project created and linked to GitHub repo
- [ ] Framework: Other (custom build)
- [ ] Build Command: `npm run build`
- [ ] Install Command: `npm install`
- [ ] Node.js Version: 20.x
- [ ] Function Max Duration: 60s (in vercel.json)
- [ ] Regions: iad1 (US East) or closest

### Environment Variables (Exact Names)
| Variable | Required | Source |
|----------|----------|--------|
| `SLACK_SIGNING_SECRET` | Yes | Slack App → Basic Information |
| `SLACK_BOT_TOKEN` | Yes | Slack App → OAuth & Permissions |
| `SLACK_APP_TOKEN` | Optional | Slack App → Basic Information → App-Level Tokens |
| `NIM_API_KEY` | Yes | build.nvidia.com |
| `GROQ_API_KEY` | Yes (fallback) | console.groq.com |
| `SUPABASE_URL` | Yes | Supabase → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase → Settings → API (service_role) |
| `UPSTASH_REDIS_REST_URL` | Yes | Upstash → Database → Details |
| `UPSTASH_REDIS_REST_TOKEN` | Yes | Upstash → Database → Details |
| `GITHUB_TOKEN` | Optional | GitHub → Settings → Developer Settings → PAT |
| `GITHUB_WEBHOOK_SECRET` | Optional | Generate random string |

### Deployment Steps
1. Push to main branch → Auto-deploy
2. Or `vercel --prod` from CLI
3. Verify deployment: `https://your-app.vercel.app/api/health` returns `{"status":"ok"}`
4. Update Slack Event/Interactivity URLs to production URL
5. Test `/model status` in Slack

---

## 6. LLM SELECTION GUIDANCE

### Primary: NVIDIA NIM
- **Where to get key:** https://build.nvidia.com/ → Sign in → API Keys
- **Free tier:** 1M tokens/month (as of 2024)
- **Models available:** Llama 3.1 70B/8B, Mixtral 8x7B, Nemotron 3 Ultra, Gemma 2 27B
- **Env var:** `NIM_API_KEY` (format: `nvapi-...`)
- **Switch command:** `/model set nim:meta/llama-3.1-70b-instruct`

### Fallback: Groq (Free)
- **Where to get key:** https://console.groq.com/ → API Keys
- **Free tier:** 14,400 requests/day, 30K tokens/min
- **Models:** Llama 3.1 70B Versatile, Mixtral 8x7B, Gemma 2 9B
- **Env var:** `GROQ_API_KEY` (format: `gsk_...`)
- **Switch command:** `/model set fallback:llama-3.1-70b-versatile`

### Model Switching in Slack
```
/model status                    # Shows current model + provider
/model list                      # Lists all available models
/model set nim:meta/llama-3.1-8b-instruct    # Fast, small NIM model
/model set nim:nvidia/nemotron-3-ultra       # Best reasoning (NIM)
/model set fallback:llama-3.1-70b-versatile  # Free Groq fallback
```

### System Prompt Style (Non-Technical Example)
> "You are Maya, a senior software engineer. You write clean TypeScript, prefer functional patterns, and always add tests. You explain tradeoffs simply. When unsure, you ask clarifying questions. You document decisions in the knowledge base using `/kb add`. You collaborate with Ethan on research and Lena on timelines."

---

## 7. PERSISTENCE & STATE

### Supabase (PostgreSQL) — What Goes Where

| Table | Purpose | Key Columns | Access Pattern |
|-------|---------|-------------|----------------|
| `knowledge_base` | Shared team memory | `id`, `team_id`, `title`, `content`, `tags`, `embedding` | Agents read/write via `/kb` commands; vector search for relevance |
| `task_approvals` | Kai's sandbox requests | `id`, `team_id`, `status`, `domains`, `description` | Kai writes pending; humans approve/reject via buttons/commands |
| `agent_configs` | Runtime agent prompts | `team_id`, `agent_name`, `system_prompt`, `enabled` | `/agent prompt` updates; agents read on startup |
| `allowlist_domains` | Kai's network permissions | `team_id`, `domain`, `added_by` | `/task allowlist` manages; executor checks before navigation |

### Upstash Redis — What Goes Where

| Key Pattern | Purpose | TTL | Example |
|-------------|---------|-----|---------|
| `config:{teamId}` | Runtime config (current model) | None | `{currentModel: "nim:meta/llama-3.1-70b-instruct"}` |
| `session:{teamId}:{channelId}` | Conversation history | 30 days | `{messages: [...], createdAt: ...}` |
| `task:logs:{teamId}:{taskId}` | Kai execution logs | 7 days | `["[timestamp] Navigating...", "[timestamp] Title: ..."]` |
| `allowlist:{teamId}` | Cached domain allowlist | 1 hour | `["example.com", "api.github.com"]` |

### Verification Steps
1. **Supabase:** Table Editor → `knowledge_base` → Insert row manually → `/kb list` shows it
2. **Redis:** Upstash Console → Data Browser → Keys visible after first command
3. **Config:** `/model status` shows value from Redis
4. **Sessions:** Mention Aurelius twice → second response references first

---

## 8. TESTING & VERIFICATION PLAN

### Manual Slack Tests

| Test | Steps | Expected Result |
|------|-------|-----------------|
| **T1: Bot Responds** | `@Aurelius hello` | Aurelius replies in thread |
| **T2: Model Switch** | `/model set nim:meta/llama-3.1-8b-instruct` → `/model status` | Status shows new model |
| **T3: Fallback Works** | `/model set fallback:llama-3.1-70b-versatile` → `@Aurelius test` | Response from Groq (faster) |
| **T4: KB Add/Search** | `/kb add "Test" "Content" #tag` → `/kb search "test"` | Entry found, formatted nicely |
| **T5: KB Tags** | `/kb list #tag` | Only tagged entries shown |
| **T6: Kai Allowlist** | `/task allowlist add example.com` → `/task run "Get title" --domains example.com` | Task created, pending approval |
| **T7: Kai Approval** | In `#agent-approvals` click "Approve" → `/task logs <id>` | Logs show browser navigation, title extracted |
| **T8: Agent Delegation** | `@Aurelius Maya, write a hello world function` | Message appears in `#maya-engineering`, Maya responds |
| **T9: Discussion Summary** | Agents discuss in channel → wait for Aurelius summary in `#agent-approvals` | Summary posted with 3 buttons |
| **T10: Approval Flow** | Click "Approve" on summary → Aurelius confirms execution | "Proceeding with approved plan" |
| **T11: Prompt Update** | `/agent prompt Noah "You speak like a pirate"` → `@Noah hello` | Noah responds in pirate speak |
| **T12: Rate Limit** | Send 15 rapid commands | Responses slow down, "Too many requests" after limit |

### Automated Checks (CI)
- `npm run build` — TypeScript compiles
- `npm run test` — Unit tests pass
- `npm run lint` — No ESLint errors

---

## 9. MONITORING & TROUBLESHOOTING

### Common Problems & Fixes

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| "Slack request verification failed" | Wrong `SLACK_SIGNING_SECRET` | Copy exactly from Slack App → Basic Information |
| "NIM_API_KEY not set" | Missing in Vercel env | Add to Vercel → Settings → Environment Variables → Redeploy |
| "Function timeout" | Task > 60s | Increase `maxDuration` in vercel.json or reduce task timeout |
| "Domain not allowed" | Kai allowlist missing domain | `/task allowlist add <domain>` |
| "Supabase connection failed" | Wrong URL/key or RLS | Use service_role key; check RLS policies allow service role |
| "Redis connection failed" | Wrong Upstash credentials | Copy REST URL and TOKEN exactly (no extra spaces) |
| "Agents not in channels" | Bot not invited | `/invite @Aurelius` in each channel |
| "Commands not recognized" | Slash commands not registered | Check Slack App → Slash Commands → all 5 present |
| "Model switch not working" | Redis not saving | Check Upstash dashboard for `config:{teamId}` key |
| "Dashboard shows no data" | CORS or wrong env | Add dashboard URL to Supabase/Redis allowed origins |

### Monitoring Setup
- **Vercel:** Functions → Logs → Filter by "error"
- **Slack:** `#agent-logs` channel for all agent activity
- **Supabase:** Dashboard → Logs → Database errors
- **Upstash:** Dashboard → Metrics → Request count, latency

---

## 10. EIGHT AGENT SYSTEM PROMPTS

*All prompts are in `packages/shared/prompts.ts` and editable via `/agent prompt <agent> "new prompt"`*

1. **Aurelius (Orchestrator):** You are Aurelius, the orchestrator of a multi-agent team. Your job is to coordinate Maya (engineering), Ethan (research), Lena (operations), Iris (communications), Omar (customer experience), Kai (automation), and Noah (personal assistant). You read and write to a shared knowledge base. When agents discuss in channels, you summarize their debates, identify consensus or conflicts, and present clear options to the human for confirmation before any major action (publishing, deploying, sending external communications, spending budget). You speak concisely, use bullet points, and always ask "Shall I proceed?" before executing irreversible steps.

2. **Maya (Engineering):** You are Maya, an engineering specialist. You write clean, maintainable code, review system architecture, debug issues, and suggest technical improvements. You collaborate with Ethan on feasibility, Lena on timelines, and Kai on automation scripts. You prefer TypeScript, React, and serverless architectures. You document decisions in the knowledge base.

3. **Ethan (Research):** You are Ethan, a research specialist. You gather information from the web, papers, documentation, and the knowledge base. You synthesize findings into concise briefings with citations. You flag uncertainties and suggest experiments. You work with Maya on technical feasibility and Iris on how to communicate findings.

4. **Lena (Operations):** You are Lena, an operations and planning specialist. You break goals into tasks, estimate effort, track progress, identify blockers, and manage timelines. You create project plans, update status, and coordinate handoffs between agents. You keep the knowledge base current with project state.

5. **Iris (Communications):** You are Iris, a communications and writing specialist. You draft announcements, blog posts, documentation, emails, and Slack messages. You adapt tone for audience (technical, executive, customer). You collaborate with Omar on customer-facing content and Ethan on research-backed claims. You maintain a style guide in the knowledge base.

6. **Omar (Customer Experience):** You are Omar, a customer and partner experience specialist. You analyze feedback, draft responses, design onboarding flows, and advocate for user needs. You work with Iris on messaging, Lena on support processes, and Maya on feature requests. You track sentiment and escalation paths in the knowledge base.

7. **Kai (Automation):** You are Kai, the automation and task specialist. You run sandboxed browser tasks (Playwright) to scrape, test, fill forms, generate screenshots, and automate repetitive workflows. You ONLY act on approved tasks. You request approval in #agent-approvals with: what you'll do, which domains you'll visit, what data you'll extract, and estimated runtime. You log every action. You never access unapproved domains or execute unapproved code.

8. **Noah (Personal Assistant):** You are Noah, a personal assistant. You manage the human's calendar, reminders, notes, preferences, and routine tasks. You draft personal messages, summarize long threads, prepare meeting briefs, and handle private to-dos. You respect privacy — nothing leaves the sandbox without explicit permission. You sync with the knowledge base for context but keep personal data separate.

---

## 11. ACCEPTANCE CRITERIA (Done Checklist)

- [ ] GitHub repo created with all code pushed
- [ ] Vercel deployment successful (green build)
- [ ] Slack app installed and verified (green URL checks)
- [ ] All 11 channels created, bot invited
- [ ] Supabase tables created (4 tables visible)
- [ ] Upstash Redis connected (keys visible)
- [ ] `/model status` shows NIM model
- [ ] `/model set nim:...` changes model successfully
- [ ] `/model set fallback:...` switches to Groq
- [ ] `/kb add` + `/kb search` + `/kb list` + `/kb delete` all work
- [ ] `/task allowlist add example.com` works
- [ ] `/task run` creates approval request in `#agent-approvals`
- [ ] Clicking "Approve" executes Kai task, logs appear in `/task logs`
- [ ] `@Aurelius` mention triggers response in thread
- [ ] Aurelius delegates to specialists (messages appear in their channels)
- [ ] Agent discussion triggers Aurelius summary in `#agent-approvals`
- [ ] Approval buttons on summary work (Approve/Reject/Revise)
- [ ] `/agent prompt <agent> "..."` updates behavior immediately
- [ ] Dashboard (if deployed) shows agent status, KB, tasks
- [ ] All env vars set in Vercel (10 required + optional)
- [ ] README.md complete with all commands documented

---

## 12. ONE-PAGE QUICK CHECKLIST (Printable)

```
☐ 1. Create GitHub repo: slack-multi-agent
☐ 2. Clone locally, create folder structure
☐ 3. npm install (root)
☐ 4. Create Vercel project → link repo
☐ 5. Create Supabase project → save URL + keys
☐ 6. Create Upstash Redis → save URL + token
☐ 7. Get NIM_API_KEY from build.nvidia.com
☐ 8. Get GROQ_API_KEY from console.groq.com
☐ 9. Run: npm run setup:slack → create Slack app from manifest
☐ 10. Add all 10 env vars to Vercel (use secrets)
☐ 11. Run: npm run setup:supabase (3 migrations)
☐ 12. Run: npm run setup:redis
☐ 13. Copy all source code to exact paths
☐ 14. npm run build → verify no errors
☐ 15. vercel --prod → get production URL
☐ 16. Update Slack Event/Interactivity URLs to production URL
☐ 17. Install Slack app to workspace
☐ 18. Generate xapp token (optional)
☐ 19. Create 11 Slack channels, invite @Aurelius
☐ 20. Test: /model status → /model list → /model set nim:...
☐ 21. Test: /kb add → /kb search → /kb list → /kb delete
☐ 22. Test: /task allowlist add example.com → /task run → approve → logs
☐ 23. Test: @Aurelius mention → delegation → summary → approval
☐ 24. Test: /agent prompt Maya "..." → @Maya test
☐ 25. (Optional) Deploy dashboard → verify data sync
☐ 26. (Optional) Set up GitHub webhook sync
☐ 27. Celebrate! 🎉 Your agent team is live.
```
