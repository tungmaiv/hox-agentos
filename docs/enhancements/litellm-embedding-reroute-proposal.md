# Enhancement Proposal: Reroute blitz/embedder via LiteLLM → Ollama GPU

**Status:** Proposed
**Date:** 2026-03-16
**Author:** Architecture Team
**Priority:** High — Image size bloat (12.7GB backend image)

---

## Problem Statement

The backend Docker image is **12.7GB**, primarily caused by two sources:

| Source | Size |
|--------|------|
| `torch` + `transformers` + `flagembedding` deps (in-process BGE-M3) | ~2GB |
| `/root/.cache/uv` left behind after `uv sync` in Dockerfile | ~7.5GB |
| **Total bloat** | **~9.5GB** |

### Root Cause

The current embedding design runs BGE-M3 **in-process** inside the backend container via `FlagEmbedding`:

```
Backend container → FlagModel("BAAI/bge-m3") loaded at startup
                  → CPU-bound inference in Celery workers
```

This violates the project's own invariant:

> **"All LLM calls via LiteLLM Proxy"** — `core/config.py`, CLAUDE.md §2

A second provider (`SidecarEmbeddingProvider`) calls an `infinity-emb` Docker sidecar on port 7997, adding infrastructure complexity without solving the core issue.

---

## Proposed Solution

Replace both `BGE_M3Provider` and `SidecarEmbeddingProvider` with a single `LiteLLMEmbeddingProvider` that:

1. Calls `http://litellm:4000/v1/embeddings` (existing LiteLLM proxy)
2. LiteLLM routes to `ollama/bge-m3` on the host GPU (`http://host.docker.internal:11434`)
3. Returns the same 1024-dim vectors — **no DB reindex needed**

```
Before:
  Backend container  →  FlagModel (in-process, CPU, 2GB deps)
  Backend container  →  infinity-emb sidecar (port 7997)

After:
  Backend container  →  LiteLLM proxy (:4000)  →  Ollama bge-m3 (host GPU)
```

---

## Technical Design

### New Provider: `LiteLLMEmbeddingProvider`

```python
class LiteLLMEmbeddingProvider:
    dimension: int = 1024

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.litellm_url}/v1/embeddings",
                json={"input": texts, "model": settings.embedding_model_name},
                headers={"Authorization": f"Bearer {settings.litellm_master_key}"},
                timeout=60.0,  # GPU model load on first call ~15s
            )
            resp.raise_for_status()
            data = resp.json()
            return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
```

### LiteLLM Config Addition (`infra/litellm/config.yaml`)

```yaml
- model_name: blitz-embedder
  litellm_params:
    model: ollama/bge-m3
    api_base: http://host.docker.internal:11434
```

### Settings Change (`backend/core/config.py`)

```python
# Remove:
embedding_model_path: str = "BAAI/bge-m3"
embedding_sidecar_url: str = "http://embedding-sidecar:7997"

# Add:
embedding_model_name: str = "blitz-embedder"
```

---

## Impact Analysis

### Files Modified

| File | Change Type | Scope |
|------|-------------|-------|
| `infra/litellm/config.yaml` | Add model entry | 5 lines |
| `backend/memory/embeddings.py` | Full rewrite (shorter) | ~80 lines → ~50 lines |
| `backend/core/config.py` | Replace 2 settings with 1 | 2 lines |
| `backend/agents/master_agent.py` | Import + instantiation | 4 lines |
| `backend/scheduler/tasks/embedding.py` | Import + instantiation | 4 lines |
| `backend/skill_repos/service.py` | Import + instantiation | 2 lines |
| `backend/skill_repos/routes.py` | Import + instantiation | 2 lines |
| `backend/main.py` | Startup validation | 4 lines |
| `backend/pyproject.toml` | Remove 2 deps | 2 lines |
| `backend/Dockerfile` | Cache cleanup | 1 line |
| `docker-compose.yml` | Remove sidecar service + volume | ~15 lines |

### Test Changes

| File | Action |
|------|--------|
| `tests/memory/test_embeddings.py` | **Delete** — tests removed provider |
| `tests/memory/test_sidecar_embedding.py` | **Delete** — tests removed provider |
| `tests/memory/test_litellm_embedding.py` | **Create** — mock httpx, 6 test cases |
| `tests/agents/test_master_agent_memory.py` | **Update** — 5 patch string replacements |

---

## Benefits

| Benefit | Detail |
|---------|--------|
| **Image size** | ~12.7GB → ~3–4GB (saves ~9.5GB) |
| **Build time** | Faster — no 2GB ML dep download |
| **Architecture consistency** | Follows "all LLM calls via LiteLLM" invariant |
| **GPU acceleration** | Ollama uses host GPU; current code uses CPU |
| **Reduced complexity** | Remove infinity-emb sidecar + volume; single embedding path |
| **Maintainability** | One provider class instead of two |

---

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| `ollama pull bge-m3` not run on host | Medium | Add to `docs/dev-context.md` as prerequisite; startup validation logs clear error |
| First embedding call slow (~15s GPU load) | Low | `timeout=60.0` in provider; subsequent calls fast |
| Vector dimension mismatch (not 1024) | Very Low | `validate_dimension()` at startup; bge-m3 via Ollama = same model |
| LiteLLM proxy down at startup | Low | Existing infra already requires LiteLLM healthy before backend starts |
| Ollama bge-m3 embedding format differs from FlagEmbedding | Very Low | Both use standard cosine-normalized 1024-dim vectors; no DB reindex needed |

---

## Pre-Requisites

Before deploying this change:

```bash
# On the host machine (not in Docker):
ollama pull bge-m3

# Verify:
curl http://localhost:11434/api/embed -d '{"model": "bge-m3", "input": ["test"]}'
```

---

## Deployment Steps

1. Merge code changes
2. Run `uv lock` to regenerate lockfile with deps removed
3. `just rebuild backend` — image now ~3–4GB
4. `just up litellm` — LiteLLM picks up new `blitz-embedder` route
5. Verify: `just logs backend | grep litellm_embedding_validated`
6. Smoke test: POST to `http://localhost:4000/v1/embeddings` with `model: blitz-embedder`

---

## Verification Checklist

```bash
# 1. Heavy deps removed from lockfile
grep -E "flagembedding|transformers|torch" backend/uv.lock | head
# → empty

# 2. No legacy provider references remain
grep -rn "BGE_M3Provider\|SidecarEmbeddingProvider\|FlagEmbedding\|FlagModel" \
  backend/ --include="*.py" | grep -v ".venv"
# → empty

# 3. Full test suite passes (946 baseline; ~9 deleted, ~6 new)
cd backend && PYTHONPATH=. .venv/bin/pytest tests/ -q

# 4. Embedding smoke test
curl -s -X POST http://localhost:4000/v1/embeddings \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -d '{"input": ["test"], "model": "blitz-embedder"}' | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d['data'][0]['embedding']))"
# → 1024

# 5. Image size
docker images hox-agentos-backend --format "{{.Size}}"
# → < 5GB
```

---

## Decision

| Option | Pros | Cons |
|--------|------|------|
| **A: Implement this proposal** (recommended) | Fixes image bloat, GPU acceleration, architectural consistency | Requires `ollama pull bge-m3` on host |
| B: Keep BGE_M3Provider + fix Dockerfile cache | Fixes cache bloat (~7.5GB) | Retains 2GB ML deps in image, CPU-only |
| C: Keep SidecarEmbeddingProvider only | Simpler than B | Retains infinity-emb sidecar, no GPU, still has in-process fallback code |

**Recommendation: Option A.** The change is low-risk (same model, same vectors, no reindex), removes significant complexity, and enforces the LiteLLM invariant already in CLAUDE.md.
