-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Knowledge base table
CREATE TABLE knowledge_base (
  id TEXT PRIMARY KEY,
  team_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT[] DEFAULT '{}',
  embedding VECTOR(1536), -- For pgvector when enabled
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_kb_team_id ON knowledge_base(team_id);
CREATE INDEX idx_kb_user_id ON knowledge_base(user_id);
CREATE INDEX idx_kb_tags ON knowledge_base USING GIN(tags);
CREATE INDEX idx_kb_created_at ON knowledge_base(created_at DESC);

-- Full text search
CREATE INDEX idx_kb_fts ON knowledge_base USING GIN(
  to_tsvector('english', title || ' ' || content)
);

-- Task approvals table
CREATE TABLE task_approvals (
  id TEXT PRIMARY KEY,
  team_id TEXT NOT NULL,
  requested_by TEXT NOT NULL,
  description TEXT NOT NULL,
  domains TEXT[] NOT NULL,
  timeout_seconds INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected, running, completed, failed
  approved_by TEXT,
  rejected_by TEXT,
  rejection_reason TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_task_team_id ON task_approvals(team_id);
CREATE INDEX idx_task_status ON task_approvals(status);

-- Agent configurations
CREATE TABLE agent_configs (
  id TEXT PRIMARY KEY,
  team_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  enabled BOOLEAN DEFAULT TRUE,
  model_override TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(team_id, agent_name)
);

CREATE INDEX idx_agent_team_id ON agent_configs(team_id);

-- Allowlist domains
CREATE TABLE allowlist_domains (
  id BIGSERIAL PRIMARY KEY,
  team_id TEXT NOT NULL,
  domain TEXT NOT NULL,
  added_by TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(team_id, domain)
);

CREATE INDEX idx_allowlist_team_id ON allowlist_domains(team_id);
