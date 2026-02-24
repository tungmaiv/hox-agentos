

## 1. Design goals (vs. OpenClaw)

What we reuse from OpenClaw:[^3][^2][^1]

- Memory as **RAG, not raw prompt dump**: store history and notes in a database, then retrieve a few relevant chunks via embeddings.
- **Chunking + embeddings**: index text into fixed‑size chunks (~300–500 tokens) and run vector search.
- **Hybrid retrieval**: combine vector search with keyword/metadata filters where useful.

Enterprise‑specific enhancements:

- Multi‑tenant, **per‑user and per‑workspace isolation** (no shared `MEMORY.md` flat files).
- **PostgreSQL + pgvector** (or similar) instead of local SQLite for multi‑user scale.[^4][^2]
- Strong RBAC/ACL integration: memory access is always filtered by roles and scopes.
- Optional encryption at rest (column or tablespace) and redaction of sensitive fields.
- Rich schema: distinguish conversational transcripts, episodic notes, and long‑term facts.

***

## 2. Memory layers and schema

Blitz will still use a **three‑tier hierarchy**, but backed by relational tables instead of Markdown files.[^5][^1]

### 2.1 Conceptual layers

- **Short‑term (verbatim)**
    - Raw recent conversation turns per user \& channel.
    - Used to maintain continuity within a session.
- **Medium‑term (summaries / episodic)**
    - Summaries of past interactions, tasks, and workflows.
    - Used to compress old conversations and jobs into small “episodes”.
- **Long‑term (factual / profile)**
    - Stable facts about user, teams, projects, and domain knowledge.
    - Backed by embeddings for semantic recall (like OpenClaw’s memory_search).[^6][^3]


### 2.2 PostgreSQL schema (simplified)

#### `memory_conversations` (short‑term)

```sql
CREATE TABLE memory_conversations (
  id               UUID PRIMARY KEY,
  user_id          UUID NOT NULL,
  conversation_id  UUID NOT NULL,
  role             TEXT NOT NULL,      -- "user" | "assistant" | "system"
  channel          TEXT NOT NULL,      -- "web", "telegram", "slack", etc.
  content          TEXT NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mem_conv_user_conv_time
  ON memory_conversations (user_id, conversation_id, created_at);
```


#### `memory_episodes` (medium‑term)

```sql
CREATE TABLE memory_episodes (
  id               UUID PRIMARY KEY,
  user_id          UUID NOT NULL,
  workspace_id     UUID,
  conversation_id  UUID,
  title            TEXT,
  summary          TEXT NOT NULL,
  tags             TEXT[],
  started_at       TIMESTAMPTZ,
  ended_at         TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mem_episodes_user_time
  ON memory_episodes (user_id, started_at DESC);
```


#### `memory_facts` + `pgvector` (long‑term)

Using `pgvector` (or similar) for embeddings:[^2][^4]

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memory_facts (
  id               UUID PRIMARY KEY,
  user_id          UUID NOT NULL,
  workspace_id     UUID,
  scope            TEXT NOT NULL,       -- "user_profile", "project", "org"
  subject          TEXT NOT NULL,       -- e.g. "project:CRM-1234"
  title            TEXT,
  content          TEXT NOT NULL,
  tags             TEXT[],
  embedding        vector(768),         -- dimension per embedding model
  provider         TEXT,                -- "openai", "gemini", "local"
  model            TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mem_facts_user_scope_subject
  ON memory_facts (user_id, scope, subject);

CREATE INDEX idx_mem_facts_embedding
  ON memory_facts USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```


#### `memory_files` / `memory_chunks` (optional)

If you also want OpenClaw‑style Markdown/project memory, you can mirror its SQLite layout in Postgres:[^3][^2]

```sql
CREATE TABLE memory_files (
  id           UUID PRIMARY KEY,
  user_id      UUID NOT NULL,
  workspace_id UUID,
  path         TEXT NOT NULL,      -- logical path
  size_bytes   BIGINT,
  mtime        TIMESTAMPTZ,
  hash         TEXT,               -- SHA256
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_chunks (
  id           UUID PRIMARY KEY,
  file_id      UUID NOT NULL REFERENCES memory_files(id),
  user_id      UUID NOT NULL,
  workspace_id UUID,
  start_line   INT,
  end_line     INT,
  content      TEXT NOT NULL,
  embedding    vector(768),
  provider     TEXT,
  model        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_mem_chunks_embedding
  ON memory_chunks USING ivfflat (embedding vector_cosine_ops);
```


***

## 3. Embedding pipeline \& indexer

We borrow OpenClaw’s **dirty‑bit + async indexer** model, but run it as a backend worker and support multiple providers.[^1][^2][^3]

### 3.1 Components

- `memory/indexer.py` (FastAPI/worker module)
    - Manages batches of items needing embeddings or re‑embeddings.
- `memory/embeddings.py`
    - Abstracts providers (OpenAI, Gemini, local model).
    - Caches embeddings for unchanged content (hash‑based, like OpenClaw).[^2][^1]


### 3.2 What gets embedded

- **Facts**: `memory_facts.content` (and optionally `title`).
- **Markdown chunks**: `memory_chunks.content`.
- **Episode summaries**: optional embedding for episodic search.

Each new or updated record:

1. Compute a content hash.
2. If hash unchanged, skip.
3. If changed, enqueue embedding job with `(id, table, provider, model, text)`.

Indexing jobs run in Celery workers or an async background scheduler.

### 3.3 Embedding provider strategy (enterprise)

- Primary: **local embedding service** (on‑prem GPU or CPU) for privacy.
- Secondary: remote provider (OpenAI/Gemini) as a fallback where allowed, controlled via policy flags.[^7][^8]
- Config per tenant / env:
    - `memory.embedding.provider = "local" | "openai" | "gemini"`
    - `memory.embedding.model = "all-MiniLM-L6-v2" | "text-embedding-3-small" | ...`

You can reuse OpenClaw’s idea of recording provider/model per row so you can switch models later and reindex only when necessary.[^1]

***

## 4. Retrieval algorithms

### 4.1 Short‑term

- For each LLM call, retrieve last N turns from `memory_conversations` filtered by `user_id`, `conversation_id`, and `channel`.
- Implement compaction/pruning logic similar to OpenClaw’s context compaction once token usage crosses a threshold.[^9][^3]


### 4.2 Medium‑term

- When conversation length or elapsed time passes a threshold:
    - Summarizer tool condenses last M turns into a short summary.
    - Insert summary as a new `memory_episodes` row.
    - Optionally mark those turns as “summarized” to skip in future prompts.
- At prompt assembly time:
    - Load 1–5 recent episodes based on time and tags relevant to the current workflow.


### 4.3 Long‑term / facts

**Memory search tool** (Blitz equivalent of `memory_search`):[^6][^1]

Inputs:

- `user_id`, `workspace_id`, `query`, `limit`, optional `scope`, `tags`.

Steps:

1. Compute query embedding using same provider/model as facts index.
2. Run vector search:

```sql
SELECT id, subject, title, content, scope, tags
FROM memory_facts
WHERE user_id = $1
  AND (workspace_id = $2 OR workspace_id IS NULL)
  AND (scope = ANY($3) OR $3 IS NULL)
ORDER BY embedding <-> $query_embedding
LIMIT $limit;
```

3. Optionally combine with keyword filters:
    - e.g., `tags @> ARRAY['project:CRM-1234']`.
    - Or use a simple reranking step in Python.
4. Return top‑K snippets to the agent; do not dump entire tables.

The **agent orchestration** uses this result exactly like OpenClaw: only inject relevant facts (~1–2K tokens) into the prompt instead of all memory.[^10]

***

## 5. Security and isolation

Enterprise requirements go beyond OpenClaw’s single‑user model.[^11][^2]

### 5.1 Per‑user \& per‑workspace boundaries

- All memory tables have `user_id` and `workspace_id`.
- Every memory read/write function is wrapped in a helper that always filters on these columns using the authenticated user from Keycloak.[^5][^1]


### 5.2 RBAC/ACL overlay

- Introduce **scopes** on facts and episodes:
    - `scope = "user_profile"`, only visible to the user and selected roles.
    - `scope = "team"`, visible to team members.
    - `scope = "org"`, visible to specific roles (e.g., admins, managers).
- Store allowed roles in a separate `memory_visibility` table or a `roles` array column.
- Before running vector queries, add a filter on user’s allowed scopes/roles.


### 5.3 Encryption \& compliance

- Option A: rely on full‑disk encryption and database‑level encryption (e.g., pgcrypto).
- Option B: encrypt `content` and `summary` columns per tenant with an app‑level key.
- Maintain audit logs for:
    - When memory_search is invoked.
    - Which facts/chunks were returned to which user.

***

## 6. Integration into Blitz AgentOS

### 6.1 Backend modules

In the existing `backend/` tree:[^12][^5]

```text
backend/
  memory/
    short_term.py
    medium_term.py
    long_term.py
    summarizer.py
    embeddings.py
    indexer.py
  tools/
    memory_tools.py
```

- `short_term.py` – append/read last N conversation turns.
- `medium_term.py` – create \& fetch episodes.
- `long_term.py` – create/update facts and run semantic search.
- `summarizer.py` – LLM‑based summarization for episodes.
- `embeddings.py` – provider abstraction.
- `indexer.py` – queue \& worker logic for embedding jobs.

`tools/memory_tools.py` defines LangGraph tools:

- `memory_search` – long‑term facts search.
- `memory_get_episodes` – list recent episodes.
- `memory_write_fact` – save new fact.
- `memory_summarize_conversation` – create episode summaries.


### 6.2 Agent prompt assembly

In `agents/master_agent.py`:

1. Gather short‑term context: last N turns.
2. If needed, call `memory_search` and `memory_get_episodes`.
3. Build prompt template:
    - System: instructions.
    - Memory: long‑term facts + episode summaries.
    - Conversation: recent messages.
4. Run LLM; on tool results or user feedback, optionally update memory (facts or episodes).

***

## 7. Tech stack summary for memory subsystem

- **Database**: PostgreSQL + pgvector for embeddings.[^4][^2]
- **ORM**: SQLAlchemy / SQLModel in Python.
- **Embeddings**:
    - Local: text embedding service (self‑hosted model, e.g., all‑MiniLM).
    - Cloud: OpenAI / Gemini as configurable providers (per env \& tenant).[^8][^7]
- **Backend**: FastAPI services in `backend/memory/*`.
- **Queues**: Celery or RQ with Redis for embedding/indexing jobs (can share with scheduler).
- **LLM summarization**: same main LLM or a cheaper summarization model.
- **Security**: Keycloak JWT → user context; RBAC + ACL applied on all memory queries.[^13][^5]

This design gives you OpenClaw’s strengths—local‑first RAG, semantic search, efficient context use—but with the isolation, RBAC, encryption, and observability you need for Blitz as an enterprise AgentOS.
<span style="display:none">[^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^30][^31][^32][^33][^34]</span>

<div align="center">⁂</div>

[^1]: https://docs.openclaw.ai/concepts/memory

[^2]: https://www.pingcap.com/blog/local-first-rag-using-sqlite-ai-agent-memory-openclaw/

[^3]: https://github.com/openclaw/openclaw/discussions/2984

[^4]: https://github.com/openclaw/openclaw/issues/18595/linked_closing_reference

[^5]: 04-Quan-Tri-Bo-Nho-Phan-Cap-Cho-Agent-AI-Doanh-Nghiep.md

[^6]: https://www.howtouseopenclaw.com/en/concepts/memory

[^7]: https://github.com/openclaw/openclaw/issues/11268

[^8]: https://github.com/openclaw/openclaw/issues/6668

[^9]: https://github.com/openclaw/openclaw/issues/5771

[^10]: https://www.reddit.com/r/openclaw/comments/1r5mgmu/psa_turn_on_memory_search_with_embeddings_in/

[^11]: https://www.toddpigram.com/2026/02/run-openclaw-securely-in-docker.html

[^12]: 18-Cau-Truc-He-Thong-Agentic-Enterprise-Da-Nen-Tang.md

[^13]: 08-Tich-hop-Keycloak-vao-Bao-mat-Copilot-Runtime-va-Agentic-AI.md

[^14]: https://github.com/openclaw/openclaw/blob/main/docs/index.md

[^15]: https://github.com/openclaw/openclaw/issues/24448/linked_closing_reference

[^16]: https://github.com/openclaw/openclaw/issues/10553

[^17]: https://github.com/openclaw/openclaw/pull/10765

[^18]: https://github.com/openclaw/openclaw/discussions/22044

[^19]: https://github.com/openclaw/openclaw/issues/8131

[^20]: https://github.com/openclaw/openclaw/issues/12937/linked_closing_reference

[^21]: https://github.com/openclaw/openclaw/discussions/20028

[^22]: https://github.com/openclaw/openclaw/discussions/20625

[^23]: https://github.com/openclaw/openclaw

[^24]: https://docs.openclaw.ai/cli/memory

[^25]: https://openclaw.im/docs/concepts/memory

[^26]: https://openclawlab.com/en/docs/concepts/memory/

[^27]: https://openclawcn.com/en/docs/concepts/memory/

[^28]: https://x.com/thenewstack/status/2024540490377425336

[^29]: https://viblo.asia/p/deep-dive-hybrid-memory-search-architecture-trong-openclaw-y0VGwzPEVPA

[^30]: http://clawdocs.org/architecture/memory-system/

[^31]: https://www.facebook.com/groups/cto.founder/posts/2691285967904613/

[^32]: https://github.com/VoltAgent/awesome-openclaw-skills/blob/main/README.md

[^33]: https://lumadock.com/tutorials/openclaw-memory-explained

[^34]: https://www.reddit.com/r/LocalLLaMA/comments/1puzgsx/localraggo_offline_rag_toolkit_in_go_with_clean/

