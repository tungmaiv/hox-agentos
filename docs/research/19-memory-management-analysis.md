# Memory Management: Comparative Analysis & Improvement Roadmap

> **For Claude:** This is a research analysis document, not a code implementation plan.
> Use it as the basis for any subsequent implementation planning sessions.

**Goal:** Compare memory management approaches across OpenClaw, memU, and Supermemory against the existing Blitz AgentOS system; identify high-value improvements by weighing benefit vs implementation complexity.

**Architecture:** Blitz AgentOS uses a 3-tier memory system (short/medium/long-term) backed by PostgreSQL + pgvector, with async Celery embedding workers and HNSW cosine similarity search. All memory is per-user isolated via JWT-sourced `user_id`.

**Tech Stack:** Python, FastAPI, LangGraph, PostgreSQL 16 + pgvector, BAAI/bge-m3 (1024-dim), Celery, Redis.

---

## 1. System Under Review: Blitz AgentOS Memory

### Architecture

Three tiers, all stored in PostgreSQL with pgvector:

| Tier | Table | Purpose | Load | Write |
|------|-------|---------|------|-------|
| Short-term | `memory_conversations` | Verbatim last 20 turns | Sync (<50ms) | Sync, append-only |
| Medium-term | `memory_episodes` | LLM-generated summaries (last 3) | Sync (<10ms) | Async Celery |
| Long-term | `memory_facts` | Semantic facts (top 5 cosine hits) | Sync (10-50ms HNSW) | Async Celery |

### Load flow (every conversation turn)

```
_load_memory_node
  1. last 20 conversation turns  → prepend to messages
  2. last 3 episode summaries    → prepend as SystemMessage
  3. top-5 cosine-similar facts  → prepend as SystemMessage
        (query = embedding of last HumanMessage via SidecarEmbeddingProvider)
```

### Write flow (after every agent response)

```
_save_memory_node
  1. deduplication guard: only save messages[existing_count:]
  2. save_turn() for each new message (sync, atomic commit)
  3. embed_and_store.delay() for each AIMessage → Celery (fire-and-forget)
  4. summarize_episode.delay() every N turns (configurable, default 10)
```

### Embedding pipeline

- **FastAPI path**: `SidecarEmbeddingProvider` → HTTP POST to `embedding-sidecar:7997` (non-blocking, 30s timeout, fallback to in-process)
- **Celery path**: `BGE_M3Provider` → in-process FlagModel (FP16, lazy-loaded, thread executor)
- **Model**: BAAI/bge-m3, dim=1024 (LOCKED — full reindex required to change)
- **Index**: HNSW partial index (`WHERE embedding IS NOT NULL`) with cosine ops

### Security invariants

- `user_id` flows exclusively from JWT → contextvar → all SQL queries
- Every query: `WHERE user_id = $1` (enforced at DB level, not application level)
- No FK to users table (Keycloak manages identity)
- Soft-delete only (`superseded_at`) — no hard deletes

### Known limitations

1. **No deduplication of facts** — duplicate/contradictory facts accumulate; only manual `mark_fact_superseded()` prevents stale retrieval
2. **Embedding lag** — facts invisible to semantic search until Celery worker processes them (up to ~1 min under load)
3. **No temporal decay** — all facts equally weighted regardless of age
4. **Fixed retrieval** — always k=5 facts, n=3 episodes, n=20 turns; no dynamic adjustment
5. **No diversity ranking** — cosine similarity alone; redundant near-duplicate facts can fill all 5 slots
6. **Single retrieval mode** — pure semantic similarity; no BM25/keyword fallback for exact matches
7. **No memory type classification** — all long-term facts treated identically; no distinction between preferences, events, skills, decisions
8. **No automatic fact invalidation** — outdated facts stay active until a developer/agent explicitly supersedes them
9. **No user profile synthesis** — no pre-built profile summary; facts retrieved on-demand per query
10. **Celery dependency for embedding** — if workers down, new facts are permanently invisible until re-indexed

---

## 2. OpenClaw Memory System

**Repository**: `openclaw/openclaw` | **Language**: TypeScript | **Scale**: Single-user (local-first)

### Architecture

Markdown files as source of truth, with a layered search index on top:

```
~/.openclaw/workspace/
  memory/
    YYYY-MM-DD.md          # Daily logs (append-only)
  MEMORY.md                # Curated long-term facts (loaded in private sessions)
  [topic-folders]/         # Structured knowledge (evergreen, no decay)
```

Index backed by one of: SQLite + sqlite-vec, LanceDB, or QMD (local sidecar).

### Memory types

| Type | Description | Decay |
|------|-------------|-------|
| Session | Per-conversation turn history | Pruned at context limit |
| Daily logs | Timestamped daily notes | Exponential decay (30-day half-life) |
| Long-term | Curated `MEMORY.md` facts | No decay (evergreen) |
| Topic folders | Structured knowledge domains | No decay (evergreen) |

### Retrieval strategy

**Hybrid search** combining two signals, weighted sum:
- **BM25 (full-text)**: Exact keyword matching, fast
- **Vector similarity**: Semantic embedding search

Re-ranked with two optional post-processors:
- **Temporal decay**: `score * exp(-lambda * age_days)` (default λ = ln(2)/30)
- **MMR (Maximal Marginal Relevance)**: `λ * relevance - (1-λ) * max_similarity_to_selected` — penalizes redundant results to increase diversity

### Key innovations

1. **Agentic memory persistence**: Before context compaction, a silent agent turn explicitly asks the model to write durable facts to `MEMORY.md` — model-driven memory curation
2. **Temporal decay + evergreen separation**: Decaying memories vs. permanent knowledge handled by file location, not metadata
3. **Hybrid BM25 + vector**: Catches exact matches (person names, project names) that pure vector search misses
4. **MMR diversity re-ranking**: Prevents 5 near-identical facts from filling the context window
5. **Multi-backend pluggability**: Same interface over SQLite, LanceDB, or QMD

### Advantages

- Zero-dependency for basic operation (plain Markdown files)
- Human-readable memory (can edit `MEMORY.md` directly)
- Hybrid search dramatically better than pure vector for keyword-heavy queries
- MMR diversity removes redundancy from retrieved context
- Temporal decay naturally down-weights stale information
- Agent-driven curation means model decides what's worth keeping

### Disadvantages

- **Single-user only** — no multi-tenant isolation architecture
- File system as DB — concurrent writes require file locking; sync issues on mobile
- No automatic fact deduplication at write time
- No contradiction detection — model must notice conflicts
- TypeScript only — no Python library to adopt directly
- No structured memory types — all facts in flat Markdown

### Complexity to implement equivalent in AgentOS

| Feature | Effort | Notes |
|---------|--------|-------|
| Hybrid BM25 + vector search | Medium | PostgreSQL has `pg_trgm` for trigram FTS; combine with existing HNSW |
| Temporal decay scoring | Low | Add `created_at` weighting in `search_facts()` SQL or post-filter |
| MMR diversity re-ranking | Low | Pure Python post-processing on top-K results |
| Agentic memory curation | Medium | Add memory-write tool; agent calls it during summarization |

---

## 3. memU (NevaMind-AI)

**Repository**: `NevaMind-AI/memU` | **Language**: Python 3.9+ | **Scale**: Multi-user, enterprise-ready

### Architecture

Three-layer hierarchical memory model:

```
Resource Layer   ← original conversations, documents, images, videos
     ↓ extraction
Item Layer       ← typed facts with embeddings (6 types)
     ↓ organization
Category Layer   ← auto-grouped topics with cross-references (like a filesystem)
```

### Memory types (6 distinct categories)

| Type | Description | Metadata |
|------|-------------|---------|
| **Profile** | Demographics, stable preferences | `updated_at`, frequency tracking |
| **Event** | Temporal occurrences | `happened_at`, duration |
| **Knowledge** | Facts, learned concepts | Source, confidence |
| **Behavior** | Recurring patterns, habits | Frequency counter, last_seen |
| **Skill** | Capabilities, tools, techniques | Proficiency level |
| **Tool** | Tool/API call histories | Call count, last parameters |

Each type has **specialized LLM extraction prompts** tuned for its semantics.

### Retrieval strategy (dual-mode)

**Mode 1 — RAG (fast, ~200ms)**:
- Embedding → cosine similarity → top-K items
- Hierarchical: search Categories → Items → Resources
- Early termination when sufficient results found

**Mode 2 — LLM (accurate, ~500-1000ms)**:
- Query rewriting across stages
- LLM ranks and reasons about candidate memories
- Handles complex multi-constraint queries better than vector similarity

User (or agent) selects mode per query.

### Multi-user isolation

- **Scope-based**: `scope_fields` parameter ties each repository to a user namespace
- `build_scoped_models()` creates per-user model variants at runtime
- Database-level filtering on `scope_fields` values
- PostgreSQL row-level security ready (not enforced in core, delegated to DB config)

### Key innovations

1. **6-type memory taxonomy**: Enables type-specific extraction prompts → much higher extraction quality vs. generic "extract facts"
2. **Dual-mode retrieval**: Switch between speed (RAG) and accuracy (LLM reasoning) per query
3. **Deduplication via content hash**: `compute_content_hash()` on whitespace-normalized content prevents duplicate facts at write time
4. **Pipeline abstraction**: Workflow steps with dependency validation — extensible without touching core
5. **LLM client interception**: Before/after/error hooks for observability and behavior modification
6. **Category hierarchy**: Auto-organized topic folders enable browsable memory structure
7. **Behavior + Skill tracking**: Captures user capability graph, not just facts

### Advantages

- Multi-user natively; scope isolation well-designed
- Type-specific extraction significantly improves fact quality
- Content hash deduplication prevents fact accumulation
- Dual retrieval mode (speed vs. accuracy) covers different latency requirements
- Pipeline abstraction makes it extensible cleanly
- Python — directly adoptable into AgentOS
- Supports same PostgreSQL + pgvector backend as AgentOS

### Disadvantages

- High complexity: 6 types × specialized prompts × dual retrieval modes × pipeline abstraction = large implementation surface
- Scope isolation delegated to DB config — not as airtight as AgentOS's contextvar + SQL-level enforcement
- LLM mode is expensive (multiple LLM calls per retrieval)
- No temporal decay — event-based categorization handles recency, but no automatic down-weighting
- Pipeline state validation at runtime (not compile-time) — errors surface late
- Category layer adds overhead for small memory sets (< 1,000 facts)

### Complexity to implement equivalent in AgentOS

| Feature | Effort | Notes |
|---------|--------|-------|
| 6-type taxonomy | High | New extraction prompts, schema changes, new Celery tasks |
| Content hash dedup | Low | Add hash column to `memory_facts`; check before insert |
| Dual retrieval mode | Medium | New `search_facts_llm()` function, agent-selectable |
| Pipeline abstraction | High | Major refactor of `_load_memory_node` / `_save_memory_node` |
| Behavior/Skill tracking | High | New tables, new extraction logic, new query paths |

---

## 4. Supermemory (openclaw-supermemory + supermemory.ai)

**Repository**: `supermemoryai/openclaw-supermemory` | **Language**: TypeScript (plugin) + proprietary backend | **Scale**: SaaS + enterprise self-hosted (Cloudflare Workers)

### Architecture

Vector-graph hybrid with automatic profiling, temporal tracking, and multi-modal ingestion:

```
Conversation Turn
  ↓ Auto-Capture Hook (async, after AI turn)
    → supermemory.addMemory(text, metadata, sessionId, containerTag, entityContext)
  ↓ Auto-Recall Hook (sync, before AI response)
    → getProfile(query) → static facts + dynamic facts
    → search(query, limit, container) → semantic results with relevance%
    → formatContext() → <supermemory-context>...</supermemory-context>
```

### Memory types (5 categories, auto-detected)

| Type | Detection | Example |
|------|-----------|---------|
| **preference** | prefer, like, love, hate, want | "User prefers TypeScript" |
| **fact** | is, are, has, have | "User is a distributed systems specialist" |
| **decision** | decided, will use, going with | "Going with microservices for payment service" |
| **entity** | phone/email patterns, "is called" | Contact info, organization names |
| **other** | fallback | Miscellaneous context |

Plus automatic profile synthesis:
- **Static Profile**: Stable facts (expertise, preferences)
- **Dynamic Profile**: Temporary states (current projects, recent activity)

### Retrieval strategy (vector-graph hybrid)

**Layer 1 — Vector search**: Embedding cosine similarity → top-K candidates

**Layer 2 — Graph relationships**:
- **Updates**: New fact supersedes old one → marks old with `isLatest=false`
- **Extends**: New detail enriches existing fact → linked relationship
- **Derives**: Inferred insights from pattern recognition

**Temporal features**:
- Auto-expiry for temporary facts (meetings, exams)
- Contradiction resolution via update graph edges
- Time-stamped recall context: `[72%] [3d ago] User prefers async communication`

### Multi-user isolation

- **Container tags**: `openclaw_<hostname>` default namespace per user
- **Custom containers**: `work`, `personal`, `project_X` — per-context namespacing
- **Session binding**: `customId = session_<session_key>` for session-scoped memories
- **Cloud**: Single API key per user/org; enforced at service layer

### Key innovations

1. **Vector + graph hybrid**: Update/extend/derive relationships solve RAG's staleness problem
2. **Auto-profiling**: Static + dynamic user profile pre-built (~50ms lookup) vs. per-query RAG (~300ms)
3. **Contradiction resolution**: Graph edges mark superseded facts → old info never resurfaces
4. **Multi-modal**: PDFs (text), images (OCR), videos (transcription), code (AST-aware)
5. **Connectors**: Real-time sync from Google Drive, Gmail, Notion, OneDrive, GitHub
6. **Benchmark-validated**: #1 on LongMemEval, LoCoMo, ConvoMem benchmarks
7. **Noise filtering**: Excludes casual/ephemeral content at extraction time

### Advantages

- Strongest retrieval quality of all systems reviewed (benchmark-validated)
- Auto-profiling eliminates per-query profile construction overhead
- Graph-based update tracking solves the contradiction/staleness problem elegantly
- Temporal recall context (`[72%] [3d ago]`) gives LLM explicit recency signals
- Auto-capture is completely passive — no agent code changes required

### Disadvantages

- **SaaS dependency**: Self-hosting is enterprise-only (Cloudflare Workers, requires vendor partnership) — conflicts with AgentOS on-premise requirement
- **Cloudflare lock-in**: Backend runs on Cloudflare Durable Objects — not portable to Docker Compose
- **Proprietary backend**: Graph engine implementation is closed-source
- **TypeScript plugin only**: Python SDK exists but graph features may be limited
- **Eventual consistency**: Auto-capture is async; facts not immediately searchable
- **Cost**: Cloud API is metered; enterprise self-hosting requires dedicated infrastructure

### Complexity to implement equivalent in AgentOS

| Feature | Effort | Notes |
|---------|--------|-------|
| Static user profile synthesis | Medium | Add `memory_profile` table; rebuild on new facts |
| Graph update tracking (supersedes) | Medium | Add `supersedes_fact_id FK` column to `memory_facts` |
| Temporal recall context (`[X%] [Nd ago]`) | Low | Format query results with similarity% + age in SystemMessage |
| Graph extends/derives relationships | Very High | Requires LLM-driven relationship extraction at write time |
| Contradiction detection | High | LLM compares new fact against existing similar facts; expensive |
| Multi-modal ingestion | Very High | Out of scope for MVP |
| Noise filtering at extraction | Low-Medium | Add filtering step in `summarize_episode` Celery task |

---

## 5. Comparative Analysis Matrix

### Feature Comparison

| Feature | AgentOS (current) | OpenClaw | memU | Supermemory |
|---------|-------------------|----------|------|-------------|
| **Memory tiers** | 3 (short/medium/long) | 3 (session/daily/LT) | 4 (resource/item/category + profile) | 2 (profile + memory) |
| **Memory types** | None (all "facts") | None (all "notes") | 6 typed categories | 5 typed categories |
| **Retrieval** | Pure cosine similarity | BM25 + vector + MMR | Dual: RAG or LLM | Vector + graph |
| **Temporal decay** | None | Exponential (30-day HL) | None (type-based) | Auto-expiry for ephemeral |
| **Diversity ranking** | None | MMR | None | None |
| **Deduplication** | None | Partial (file-based) | Content hash | Graph update edges |
| **Contradiction handling** | Manual `superseded_at` | None | None | Graph update edges |
| **User profile** | None | None (MEMORY.md manual) | Category summaries | Static + dynamic auto-built |
| **Multi-user** | Yes (JWT + SQL) | No | Yes (scope-based) | Yes (container tags) |
| **Security isolation** | Airtight (DB-level) | N/A | Delegated to DB | Service-level |
| **Self-hosted** | Yes (Docker Compose) | Yes (local) | Yes (PostgreSQL) | Enterprise-only |
| **Embedding model** | BAAI/bge-m3 fixed | Pluggable | Pluggable | Pluggable |
| **Backend** | PostgreSQL + pgvector | SQLite/LanceDB/QMD | PostgreSQL + pgvector | Cloudflare + PostgreSQL |
| **Language** | Python | TypeScript | Python | TypeScript (plugin) |
| **Benchmark validated** | No | No | 92.09% LoCoMo | #1 on 3 benchmarks |

### Strengths & Weaknesses Summary

| System | Biggest Strength | Biggest Weakness |
|--------|-----------------|-----------------|
| **AgentOS** | Security isolation (airtight), self-hosted, production-ready | No dedup, no decay, no diversity, pure cosine only |
| **OpenClaw** | Hybrid search + MMR diversity, temporal decay, human-readable | Single-user, file-based (no multi-tenant) |
| **memU** | 6-type taxonomy, content hash dedup, dual retrieval mode | High complexity, LLM retrieval is expensive |
| **Supermemory** | Vector-graph, auto-profiling, contradiction resolution, benchmarks | SaaS/Cloudflare dependency, closed-source graph, enterprise self-host only |

---

## 6. What AgentOS Can Learn — Benefit vs. Complexity Assessment

Ranked by **net value** (benefit × confidence ÷ implementation cost):

### Tier 1: High Benefit, Low Complexity — Implement Now

**1.1 Temporal recall context in SystemMessage injection**
- **From**: Supermemory
- **What**: Prefix each retrieved fact with its age and similarity: `[87%] [2d ago] User prefers Vietnamese for documents`
- **Benefit**: LLM can self-calibrate trust in older facts; improves accuracy of time-sensitive decisions
- **Effort**: 1–2 hours (format change in `_load_memory_node`)
- **Files**: `backend/agents/master_agent.py`, `backend/memory/long_term.py`

**1.2 Temporal decay scoring in `search_facts()`**
- **From**: OpenClaw
- **What**: Weight cosine similarity by age: `score * exp(-lambda * age_days)`. Configurable λ and half-life per user.
- **Benefit**: Recent interactions outweigh old ones naturally; no manual superseding needed for time-sensitive facts
- **Effort**: 2–4 hours (SQL query update + config field)
- **Files**: `backend/memory/long_term.py`, `backend/core/config.py`
- **Schema change**: None (use existing `created_at`)

**1.3 MMR diversity re-ranking**
- **From**: OpenClaw
- **What**: After cosine search returns k=10 candidates, apply MMR to select top 5 with diversity: `λ * relevance - (1-λ) * max_similarity_to_selected`
- **Benefit**: Prevents 5 near-duplicate facts from filling context; retrieves broader context coverage
- **Effort**: 2–3 hours (pure Python post-processing, no schema change)
- **Files**: `backend/memory/long_term.py` (new `mmr_rerank()` helper)

**1.4 Content hash deduplication at write time**
- **From**: memU
- **What**: Before inserting a new `memory_facts` row, compute SHA-256 hash of normalized content; skip insert if hash exists for same user
- **Benefit**: Eliminates duplicate fact accumulation without LLM comparison; cheap O(1) check
- **Effort**: 3–4 hours (add `content_hash` column, check before insert in Celery task)
- **Files**: `backend/memory/long_term.py`, migration `022_add_fact_content_hash.py`
- **Schema change**: `ALTER TABLE memory_facts ADD COLUMN content_hash TEXT; CREATE UNIQUE INDEX ON memory_facts (user_id, content_hash) WHERE superseded_at IS NULL`

### Tier 2: High Benefit, Medium Complexity — Plan for Next Phase

**2.1 Hybrid BM25 + vector search**
- **From**: OpenClaw
- **What**: Combine pgvector HNSW cosine search with PostgreSQL `pg_trgm` trigram similarity or `tsvector` full-text search; weighted sum of both scores
- **Benefit**: Catches exact keyword matches (names, project codes, acronyms) that pure vector search misses; dramatically improves recall for precise queries
- **Effort**: 1–2 days
- **Files**: `backend/memory/long_term.py`, migration to add `tsvector` column + GIN index
- **Schema change**: `ALTER TABLE memory_facts ADD COLUMN content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED; CREATE INDEX ON memory_facts USING gin(content_tsv)`

**2.2 Simplified memory type taxonomy (3 types, not 6)**
- **From**: memU, Supermemory
- **What**: Classify facts into 3 types at extraction time: `preference`, `event`, `knowledge`. Use type-specific extraction prompts. Store `memory_type` column.
- **Benefit**: Higher extraction quality per type; enables type-filtered retrieval; behavioral analytics become possible
- **Effort**: 1–2 days (new extraction prompts in `summarize_episode`, schema change, query updates)
- **Schema change**: `ALTER TABLE memory_facts ADD COLUMN memory_type TEXT CHECK (memory_type IN ('preference', 'event', 'knowledge'))`
- **Note**: Start with 3 types (not memU's 6) to keep complexity manageable

**2.3 Static user profile synthesis**
- **From**: Supermemory
- **What**: Maintain a `memory_profile` table with synthesized profile facts (top stable preferences, expertise, communication style). Rebuild asynchronously when new facts are added. Inject at top of context as lightweight always-on context (~200 tokens).
- **Benefit**: Profile facts always available without per-query search; dramatically reduces cold-start problem for new conversations; ~50ms vs 50ms HNSW search
- **Effort**: 2–3 days (new table, Celery profile-rebuild task, `_load_memory_node` update)
- **Schema change**: New `memory_profile` table (`user_id, key, value, confidence, updated_at`)

**2.4 `supersedes_fact_id` graph edge for contradiction tracking**
- **From**: Supermemory
- **What**: When `mark_fact_superseded()` is called, also record which new fact supersedes the old one via FK. Enables lineage tracking and future graph traversal.
- **Benefit**: Low overhead; enables audit trail of how user's knowledge evolved; foundation for future graph retrieval
- **Effort**: 4–8 hours (schema change + update `mark_fact_superseded()`)
- **Schema change**: `ALTER TABLE memory_facts ADD COLUMN superseded_by UUID REFERENCES memory_facts(id)`

### Tier 3: Medium Benefit, High Complexity — Evaluate Post-MVP

**3.1 LLM-based retrieval mode (dual-mode, à la memU)**
- **From**: memU
- **What**: Alternative retrieval path that uses LLM reasoning over candidate facts rather than cosine similarity alone; selectable per query
- **Benefit**: Better for complex multi-constraint queries ("what did I prefer last time I worked on a Python project with tight deadlines?")
- **Effort**: 3–5 days + significant LLM token cost
- **Recommendation**: Only implement if users report complex query failures with vector search

**3.2 Behavior and Skill tracking (à la memU)**
- **From**: memU
- **What**: Separate `memory_skills` and `memory_behaviors` tables; track capability graph and recurring patterns with frequency counters
- **Benefit**: Enables proactive suggestions ("you usually prefer dark mode, shall I set it up?")
- **Effort**: 5–7 days (new tables, extraction logic, retrieval integration)
- **Recommendation**: Valuable for v2.x but out of scope for current 100-user MVP

**3.3 Category hierarchy (à la memU)**
- **From**: memU
- **What**: Auto-organize facts into topic categories (like folder hierarchy); enables browsable memory structure
- **Benefit**: Enables richer retrieval (fetch all facts about "Python projects"); user-facing memory browser
- **Effort**: 5–10 days (new `memory_categories` table, LLM categorization step, traversal queries)
- **Recommendation**: Deferred until memory browser UI is prioritized

**3.4 Graph update edges for contradiction detection (à la Supermemory)**
- **From**: Supermemory
- **What**: At write time, compare new fact against top-5 similar existing facts via LLM; detect contradictions; auto-supersede stale facts
- **Benefit**: Fully automated fact lifecycle; solves the staleness problem completely
- **Effort**: 7–14 days (LLM comparison at write, graph edges, careful dedup logic)
- **Recommendation**: High value but expensive; implement content hash dedup (1.4) first as 80% solution

### Tier 4: Low Benefit or Incompatible — Do Not Implement

| Feature | Reason to Skip |
|---------|---------------|
| Supermemory cloud API integration | SaaS dependency violates on-premise requirement; enterprise self-host requires Cloudflare Workers — incompatible with Docker Compose |
| OpenClaw Markdown file storage | AgentOS is multi-user; per-user Markdown files don't scale and lose SQL isolation guarantees |
| memU pipeline abstraction | Major refactor with minimal user-visible benefit at 100-user scale; YAGNI |
| Multi-modal ingestion (images, video, PDF) | Out of scope for MVP chat/workflow system |
| External connectors (Gmail, Drive, etc.) | Planned as tools, not memory sources; separate concern |
| Temporal decay for episodes (medium-term) | Episodes are summaries; decay makes less sense than for raw facts |

---

## 7. Recommended Implementation Sequence

### Sprint 1 (2–3 days): Quick wins — no schema changes
1. Add temporal recall context to SystemMessage format (`[87%] [2d ago]`)
2. Add MMR diversity re-ranking to `search_facts()` result post-processing
3. Add temporal decay score weighting in `search_facts()` SQL
4. Unit tests for all three

### Sprint 2 (3–5 days): Schema additions — low risk
1. Add `content_hash` column to `memory_facts` + unique index + dedup check in Celery task
2. Add `superseded_by` FK column to `memory_facts` + update `mark_fact_superseded()`
3. Migration `022_memory_improvements.py` for both schema changes
4. Tests for dedup + supersedes lineage

### Sprint 3 (1 week): Hybrid search + type taxonomy
1. Add `content_tsv` generated column + GIN index to `memory_facts`
2. Update `search_facts()` to combine HNSW cosine + tsvector ranking
3. Add `memory_type` column with 3-type taxonomy
4. Update `summarize_episode` Celery task to use type-specific extraction prompts
5. Migration `023_hybrid_search_and_types.py`
6. Tests for hybrid search and type extraction

### Sprint 4 (1 week): User profile synthesis
1. New `memory_profile` table
2. `rebuild_profile_task` Celery task (triggered after N new facts)
3. `_load_memory_node` injects profile as always-on SystemMessage prefix
4. Migration `024_user_profile.py`
5. Tests for profile rebuild + injection

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Temporal decay lambda miscalibrated | Medium | Medium | Make λ configurable via `system_config`; default to 30-day half-life |
| MMR increases latency | Low | Low | Pure Python post-processing on k=10 results; <5ms |
| Content hash collisions on semantically different facts | Low | Medium | Hash full normalized content; collisions are false dedup of identical text — acceptable |
| Hybrid search breaks existing tests | Medium | Low | Keep pure vector as fallback; feature flag in config |
| Profile rebuild creates thundering herd | Medium | Medium | Debounce: only rebuild if >N new facts since last rebuild; use Celery beat not eager |
| `superseded_by` introduces circular FK | Low | High | Enforce at application layer: never set `superseded_by` to self or to a fact already superseded |
| Vector dimension lock (1024) | N/A | High | Do not change embedding model; all improvements work within existing 1024-dim space |

---

## 9. Critical Files for Implementation

| File | Change |
|------|--------|
| `backend/memory/long_term.py` | Add temporal decay, MMR rerank, BM25 hybrid, content hash check |
| `backend/memory/medium_term.py` | Minor: episode retrieval unchanged |
| `backend/memory/short_term.py` | Unchanged |
| `backend/memory/embeddings.py` | Unchanged |
| `backend/agents/master_agent.py` | Update `_load_memory_node` for temporal context format + profile injection |
| `backend/core/models/memory_long_term.py` | Add `content_hash`, `superseded_by`, `memory_type` columns |
| `backend/core/config.py` | Add `memory_decay_halflife_days`, `memory_mmr_lambda`, `memory_hybrid_bm25_weight` settings |
| `backend/scheduler/tasks/embedding.py` | Add dedup check; type-specific extraction prompts |
| `backend/alembic/versions/022_*.py` | Migration: content_hash, superseded_by |
| `backend/alembic/versions/023_*.py` | Migration: tsvector, memory_type |
| `backend/alembic/versions/024_*.py` | Migration: memory_profile table |
| `tests/memory/test_long_term.py` | Tests for all new features |

---

## 10. Verification Criteria

For each sprint, verify by:

1. **Sprint 1**: `PYTHONPATH=. .venv/bin/pytest tests/memory/ -v` passes; manually confirm SystemMessage format includes `[XX%] [Nd ago]` in agent responses
2. **Sprint 2**: Insert duplicate fact → second insert skipped (check row count); call `mark_fact_superseded()` → `superseded_by` FK populated
3. **Sprint 3**: Query with exact keyword match → `search_facts()` returns correct fact even when vector similarity is low; new facts saved with `memory_type` populated
4. **Sprint 4**: New conversation → profile SystemMessage injected before facts/episodes; Celery `rebuild_profile_task` fires after N new facts
5. **All sprints**: `PYTHONPATH=. .venv/bin/pytest tests/ -q` reports ≥ 258 tests passing (no regressions)
