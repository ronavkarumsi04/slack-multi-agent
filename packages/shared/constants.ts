export const AGENTS = {
  AURELIUS: 'Aurelius',
  MAYA: 'Maya',
  ETHAN: 'Ethan',
  LENA: 'Lena',
  IRIS: 'Iris',
  OMAR: 'Omar',
  KAI: 'Kai',
  NOAH: 'Noah'
} as const;

export const AGENT_ROLES = {
  [AGENTS.AURELIUS]: 'Orchestrator & Decision Maker',
  [AGENTS.MAYA]: 'Engineering Specialist',
  [AGENTS.ETHAN]: 'Research Specialist',
  [AGENTS.LENA]: 'Operations & Planning',
  [AGENTS.IRIS]: 'Communications & Writing',
  [AGENTS.OMAR]: 'Customer & Partner Experience',
  [AGENTS.KAI]: 'Automation & Scripts (Task Automator)',
  [AGENTS.NOAH]: 'Personal Assistant'
} as const;

export const CHANNELS = {
  ORCHESTRATOR: 'aurelius-orchestrator',
  ENGINEERING: 'maya-engineering',
  RESEARCH: 'ethan-research',
  OPERATIONS: 'lena-operations',
  COMMS: 'iris-communications',
  CUSTOMER: 'omar-customer',
  AUTOMATION: 'kai-automation',
  PERSONAL: 'noah-personal',
  GENERAL: 'agent-discussion',
  APPROVALS: 'agent-approvals',
  LOGS: 'agent-logs'
} as const;

export const COMMANDS = {
  MODEL: '/model',
  KB: '/kb',
  AGENT: '/agent',
  TASK: '/task',
  HELP: '/help'
} as const;

export const NIM_MODELS = [
  'meta/llama-3.1-70b-instruct',
  'meta/llama-3.1-8b-instruct',
  'mistralai/mixtral-8x7b-instruct-v0.1',
  'nvidia/nemotron-3-ultra',
  'google/gemma-2-27b-it'
] as const;

export const FALLBACK_MODELS = [
  'llama-3.1-70b-versatile',      // Groq
  'mixtral-8x7b-32768',           // Groq
  'gemma2-9b-it'                  // Groq
] as const;
