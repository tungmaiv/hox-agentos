---
created: 2026-03-08T03:56:00.563Z
title: LLM model and provider configurable in admin console
area: ui
files:
  - infra/litellm/config.yaml
  - backend/core/config.py
---

## Problem

LLM model aliases (blitz/master, blitz/fast, blitz/coder, blitz/summarizer) are hardcoded in `infra/litellm/config.yaml`. Changing providers or models requires:
1. Manually editing the YAML file
2. Force-recreating the LiteLLM container (`docker compose up -d --force-recreate litellm`)
3. No visibility into which models are active from the UI

This became a real pain point when the weekly Ollama cloud quota was hit — switching to local qwen2.5 models required file edits and container restarts.

## Solution

Add an LLM Configuration section to the Admin Console (e.g., `/admin/config` or new `/admin/llm` tab) that allows:

- View currently active model for each alias (blitz/master, blitz/fast, blitz/coder, blitz/summarizer)
- Select provider: Ollama (local), OpenRouter, Anthropic, OpenAI, Z.ai, custom
- Select model per alias from a dropdown (populated by querying the provider's available models)
- Set API keys per provider (stored encrypted in DB, same pattern as credential storage)
- Test connection button — sends a test prompt and shows latency + response
- Apply changes hot-reloads LiteLLM config without container restart (LiteLLM supports `/reload` endpoint)

LiteLLM exposes `POST /config/update` and supports hot config reload — no container restart needed.
Fallback chain should also be configurable (e.g., "if master fails, try openrouter/free").
