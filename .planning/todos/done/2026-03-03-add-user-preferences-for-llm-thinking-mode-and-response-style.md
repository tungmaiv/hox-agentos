---
created: 2026-03-03T10:34:04.786Z
title: Add user preferences for LLM thinking mode and response style
area: ui
files:
  - backend/api/routes/user_instructions.py
  - backend/agents/master_agent.py
  - backend/prompts/master_agent.md
  - infra/litellm/config.yaml
  - frontend/src/components/chat/chat-panel.tsx
---

## Problem

Currently, LLM behavior (thinking mode, response verbosity) is controlled only at the infrastructure level (LiteLLM config.yaml). Users cannot customize their experience:

1. **Thinking mode**: qwen3.5:cloud has thinking mode ON by default, generating 300-500 hidden reasoning tokens per message (6x slower). Some users may want detailed reasoning, others want fast responses. There's no per-user toggle.

2. **Response style**: The master agent prompt hardcodes "Be concise" (rule #6). Users asking for detailed explanations get truncated responses compared to direct model access. No way to switch between concise/detailed/auto per session.

3. **Session parameters**: The chat UI has no controls for adjusting model behavior mid-conversation. Users must ask an admin to change config files.

## Solution

### Backend
- Extend user settings/preferences API (or create new endpoint) to support per-user LLM config:
  - `thinking_mode`: boolean (default: false for speed)
  - `response_style`: enum (concise | detailed | auto) — default: auto
- Store in `user_instructions` or new `user_preferences` table
- Pass preferences through to LiteLLM calls via `extra_body` params in `get_llm()` or at the agent node level
- Adjust system prompt dynamically based on `response_style` preference

### Frontend Chat UI
- Add session parameter controls accessible from chat panel (gear icon or settings dropdown):
  - Thinking mode toggle (on/off)
  - Response length selector (concise / detailed / auto)
- Persist per-session (React state) with optional save-to-backend for cross-session persistence
- Show indicator when thinking mode is active (slower but more thorough)

### Integration
- `_master_node` in `master_agent.py` reads user preferences and:
  - Passes `think: true/false` via LLM call params
  - Adjusts system prompt tone/length instructions based on response_style
