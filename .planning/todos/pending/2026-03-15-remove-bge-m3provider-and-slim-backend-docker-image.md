---
created: 2026-03-15T19:35:23.860Z
title: Remove BGE_M3Provider and slim backend Docker image
area: infrastructure
files:
  - backend/memory/embeddings.py
  - backend/pyproject.toml
  - backend/Dockerfile
  - docker-compose.yml
  - docs/enhancements/litellm-embedding-reroute-proposal.md
---

## Problem

Backend Docker image is ~12.7GB due to two causes:
1. `FlagEmbedding` + `torch` + `transformers` installed in-process (~2GB) — used by `BGE_M3Provider` which is kept as fallback
2. `uv sync` in Dockerfile leaves behind `/root/.cache/uv` (~7.5GB) that is never cleaned up

`SidecarEmbeddingProvider` (calling infinity-emb HTTP sidecar) already exists and works, but `BGE_M3Provider` remains as a fallback, keeping all heavy ML deps in the image.

## Solution

**Option C from `docs/enhancements/litellm-embedding-reroute-proposal.md`** — keep the infinity-emb sidecar, remove the in-process fallback:

1. **Fix Dockerfile cache** — add `--no-cache-dir` or multi-stage build to drop the 7.5GB `uv` cache layer
2. **Remove `BGE_M3Provider`** from `backend/memory/embeddings.py` — `SidecarEmbeddingProvider` becomes the only provider
3. **Remove deps** — drop `flagembedding`, `torch`, `transformers` from `backend/pyproject.toml` and regenerate lockfile
4. **Update all call sites** — `backend/agents/master_agent.py`, `backend/scheduler/tasks/embedding.py`, `backend/skill_repos/service.py` to use `SidecarEmbeddingProvider` only
5. **Delete tests** for removed provider, keep sidecar tests

**Do NOT** route through LiteLLM (Option A) — infinity-emb is purpose-built for embeddings, isolated from LiteLLM blast radius, and has no host Ollama dependency.

Expected result: ~9.5GB savings, backend image drops from ~12.7GB to ~3-4GB.
