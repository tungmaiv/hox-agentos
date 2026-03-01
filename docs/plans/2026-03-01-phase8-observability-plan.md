# Phase 8: Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add full-stack observability — Grafana dashboards, Loki log aggregation, LiteLLM cost tracking, and Telegram alerts — as five Docker Compose services with zero manual setup required after `just up`.

**Architecture:** Prometheus scrapes cAdvisor (container resources), LiteLLM `/metrics`, and FastAPI `/metrics`. Grafana Alloy reads Docker container stdout/stderr via the Docker socket and ships to Loki. Grafana uses both as data sources, with four pre-provisioned dashboards and two alert rules firing to Telegram.

**Tech Stack:** Prometheus v3, Grafana 11, Loki 3, Grafana Alloy 1, cAdvisor, `prometheus-fastapi-instrumentator`, `prometheus-client`

---

## Context for Implementer

- Working dir: `/home/tungmv/Projects/hox-agentos`
- Python backend: `backend/` — use `PYTHONPATH=. .venv/bin/pytest tests/ -q` (never `uv run pytest`)
- Current test baseline: **292 tests passing** — do not drop below this
- Docker Compose project name: `hox-agentos` (derived from directory name)
- All services on `blitz-net` Docker network
- Logs go to **container stdout** (structlog writes to sys.stdout in `core/logging.py`) — NOT to files
- The `./logs:/app/logs` volume exists but is empty; Alloy reads Docker stdout instead
- Grafana port **3001** is pre-assigned in CLAUDE.md

---

## Plan 08-01: Infrastructure Stack

### Task 1: Add `.env` variables for Grafana

**Files:**
- Modify: `.env` (add two new lines)
- Modify: `.dev-secrets.example` (document the new vars)

**Step 1: Add to `.env`**

Append these two lines:
```
GRAFANA_ADMIN_PASSWORD=blitz_grafana_admin
GRAFANA_ALERT_CHAT_ID=<your-telegram-chat-id-for-alerts>
```

**Step 2: Document in `.dev-secrets.example`**

Read the file first (`Read .dev-secrets.example`), then append:
```
# Grafana
GRAFANA_ADMIN_PASSWORD=blitz_grafana_admin   # Grafana admin UI password
GRAFANA_ALERT_CHAT_ID=                       # Telegram chat ID for Grafana service-down alerts
```

**Step 3: Commit**
```bash
git add .dev-secrets.example
git commit -m "chore(08-01): add Grafana env vars to dev-secrets example"
```
(Do NOT commit `.env` — it is gitignored.)

---

### Task 2: Create Prometheus config

**Files:**
- Create: `infra/prometheus/prometheus.yml`

**Step 1: Create the file**

```yaml
# infra/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "cadvisor"
    static_configs:
      - targets: ["cadvisor:8080"]

  - job_name: "litellm"
    static_configs:
      - targets: ["litellm:4000"]
    metrics_path: /metrics

  - job_name: "backend"
    static_configs:
      - targets: ["backend:8000"]
    metrics_path: /metrics
```

**Step 2: Commit**
```bash
git add infra/prometheus/prometheus.yml
git commit -m "chore(08-01): add Prometheus scrape config"
```

---

### Task 3: Create Loki config

**Files:**
- Create: `infra/loki/loki-config.yml`

**Step 1: Create the file**

```yaml
# infra/loki/loki-config.yml
# Single-process Loki for local dev — filesystem storage, no auth
auth_enabled: false

server:
  http_listen_port: 3100
  log_level: warn

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2020-10-24
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

analytics:
  reporting_enabled: false
```

**Step 2: Commit**
```bash
git add infra/loki/loki-config.yml
git commit -m "chore(08-01): add Loki filesystem config"
```

---

### Task 4: Create Grafana Alloy config (Docker log scraping)

**Files:**
- Create: `infra/alloy/config.alloy`

**Background:** Structlog writes JSON to container stdout (not files). Alloy reads Docker container logs via the Docker socket.

**Step 1: Create the file**

```alloy
// infra/alloy/config.alloy
// Discover all containers from the hox-agentos compose project
discovery.docker "local_containers" {
  host = "unix:///var/run/docker.sock"
}

// Keep only hox-agentos project containers, add service label
discovery.relabel "blitz_containers" {
  targets = discovery.docker.local_containers.targets

  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_project"]
    regex         = "hox-agentos"
    action        = "keep"
  }

  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/(.*)"
    target_label  = "container"
  }

  rule {
    source_labels = ["__meta_docker_container_label_com_docker_compose_service"]
    target_label  = "service"
  }
}

// Read container stdout/stderr and ship to Loki
loki.source.docker "blitz_logs" {
  host       = "unix:///var/run/docker.sock"
  targets    = discovery.relabel.blitz_containers.output
  forward_to = [loki.write.loki_server.receiver]
  labels     = { job = "blitz-agentos" }
}

loki.write "loki_server" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
```

**Step 2: Commit**
```bash
git add infra/alloy/config.alloy
git commit -m "chore(08-01): add Alloy config for Docker log shipping to Loki"
```

---

### Task 5: Create Grafana provisioning skeleton

**Files:**
- Create: `infra/grafana/provisioning/datasources/datasources.yml`
- Create: `infra/grafana/provisioning/dashboards/dashboards.yml`

**Step 1: Create datasources config**

```yaml
# infra/grafana/provisioning/datasources/datasources.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    uid: blitz-prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    uid: blitz-loki
    access: proxy
    url: http://loki:3100
    editable: false
```

**Step 2: Create dashboard provider config**

```yaml
# infra/grafana/provisioning/dashboards/dashboards.yml
apiVersion: 1

providers:
  - name: blitz-dashboards
    orgId: 1
    folder: __Blitz
    folderUid: blitz-folder
    type: file
    disableDeletion: true
    updateIntervalSeconds: 30
    options:
      path: /etc/grafana/dashboards
```

**Step 3: Create empty dashboards directory placeholder**
```bash
mkdir -p infra/grafana/dashboards
touch infra/grafana/dashboards/.gitkeep
```

**Step 4: Create alerting directory (filled in Plan 08-05)**
```bash
mkdir -p infra/grafana/provisioning/alerting
```

**Step 5: Commit**
```bash
git add infra/grafana/
git commit -m "chore(08-01): add Grafana provisioning skeleton (datasources + dashboard provider)"
```

---

### Task 6: Add 5 new services to docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Read the current `docker-compose.yml`** (use Read tool — file is 212 lines)

**Step 2: Add the 5 services before the `volumes:` section**

Add this block immediately before the `volumes:` line:

```yaml
  # ── Observability stack ───────────────────────────────────────────────────

  prometheus:
    image: prom/prometheus:v3.2.1
    volumes:
      - ./infra/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"
      - "--storage.tsdb.retention.time=15d"
      - "--web.enable-lifecycle"
    restart: unless-stopped
    networks:
      - blitz-net

  grafana:
    image: grafana/grafana:11.4.0
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_ANALYTICS_REPORTING_ENABLED: "false"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./infra/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./infra/grafana/dashboards:/etc/grafana/dashboards:ro
    depends_on:
      - prometheus
      - loki
    restart: unless-stopped
    networks:
      - blitz-net

  loki:
    image: grafana/loki:3.3.2
    volumes:
      - ./infra/loki/loki-config.yml:/etc/loki/local-config.yaml:ro
      - loki_data:/loki
    command: -config.file=/etc/loki/local-config.yaml
    restart: unless-stopped
    networks:
      - blitz-net

  alloy:
    image: grafana/alloy:v1.6.1
    volumes:
      - ./infra/alloy/config.alloy:/etc/alloy/config.alloy:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    command:
      - run
      - /etc/alloy/config.alloy
    depends_on:
      - loki
    restart: unless-stopped
    networks:
      - blitz-net

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.49.1
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    devices:
      - /dev/kmsg
    restart: unless-stopped
    networks:
      - blitz-net
```

**Step 3: Update the `volumes:` section**

The current `volumes:` section only has `postgres_data:`. Add the three new volumes:

```yaml
volumes:
  postgres_data:
  prometheus_data:
  grafana_data:
  loki_data:
```

**Step 4: Verify docker-compose is valid**
```bash
cd /home/tungmv/Projects/hox-agentos
docker compose config --quiet
```
Expected: exits 0 (no output). If there are YAML errors, fix indentation.

**Step 5: Commit**
```bash
git add docker-compose.yml
git commit -m "feat(08-01): add Prometheus, Grafana, Loki, Alloy, cAdvisor to Docker Compose"
```

---

### Task 7: Smoke-test the observability stack

**Step 1: Start the observability services**
```bash
cd /home/tungmv/Projects/hox-agentos
docker compose up -d prometheus loki grafana alloy cadvisor
```

**Step 2: Wait ~15 seconds for services to initialize, then verify**
```bash
curl -s http://localhost:9090/-/healthy   # Prometheus
curl -s http://localhost:3100/ready       # Loki
curl -s http://localhost:3001/api/health  # Grafana
```
Expected: All return `{"status":"ok"}` or `200 OK`.

**Step 3: Check Prometheus targets**
```bash
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep '"health"'
```
Expected: `"health": "unknown"` for backend/litellm (not yet running) is OK. cAdvisor should be `"health": "up"`.

**Step 4: Stop services (backend not running yet, full stack test comes after all plans)**
```bash
docker compose stop prometheus loki grafana alloy cadvisor
```

---

## Plan 08-02: LiteLLM + FastAPI Metrics

### Task 8: Enable Prometheus metrics in LiteLLM

**Files:**
- Modify: `infra/litellm/config.yaml`

**Step 1: Read `infra/litellm/config.yaml`** (already read — 50 lines)

**Step 2: Add `prometheus_metrics: true` to `litellm_settings`**

Modify the `litellm_settings` block from:
```yaml
litellm_settings:
  drop_params: true
```
to:
```yaml
litellm_settings:
  drop_params: true
  prometheus_metrics: true
```

**Step 3: Verify config is valid YAML**
```bash
python3 -c "import yaml; yaml.safe_load(open('infra/litellm/config.yaml'))" && echo "OK"
```
Expected: `OK`

**Step 4: Commit**
```bash
git add infra/litellm/config.yaml
git commit -m "feat(08-02): enable Prometheus metrics in LiteLLM config"
```

---

### Task 9: Write failing test for `/metrics` endpoint

**Files:**
- Modify: `backend/tests/test_health.py`

**Step 1: Add test at the bottom of `backend/tests/test_health.py`**

```python
def test_metrics_endpoint_returns_200() -> None:
    """Prometheus /metrics endpoint must be accessible without auth."""
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_endpoint_content_type() -> None:
    """Prometheus /metrics must return text/plain content type."""
    response = client.get("/metrics")
    assert "text/plain" in response.headers["content-type"]


def test_metrics_endpoint_contains_python_info() -> None:
    """Prometheus /metrics must contain default python_info metric."""
    response = client.get("/metrics")
    assert "python_info" in response.text
```

**Step 2: Run tests to verify they fail**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_health.py::test_metrics_endpoint_returns_200 -v
```
Expected: **FAIL** with `404 Not Found` (endpoint doesn't exist yet)

---

### Task 10: Add `prometheus-fastapi-instrumentator` to backend

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/main.py`

**Step 1: Add the dependency**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
uv add prometheus-fastapi-instrumentator
```
Expected: uv resolves and adds to `pyproject.toml`

**Step 2: Add instrumentator to `main.py`**

In `main.py`, add the import at the top (after existing imports):
```python
from prometheus_fastapi_instrumentator import Instrumentator
```

In `create_app()`, add these two lines **after** the `app = FastAPI(...)` block (before `app.add_middleware`):
```python
    # Expose /metrics endpoint for Prometheus scraping (no auth — internal network only)
    Instrumentator().instrument(app).expose(app)
```

The exact edit: after the `lifespan=lifespan,` line (line ~104), before `app.add_middleware(`:
```python
    app = FastAPI(
        title="Blitz AgentOS",
        version="1.0.0",
        description="Enterprise AI Assistant Platform",
        lifespan=lifespan,
    )

    # Expose /metrics endpoint for Prometheus scraping (no auth — internal network only)
    Instrumentator().instrument(app).expose(app)

    app.add_middleware(
```

**Step 3: Run the failing tests — they should now pass**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_health.py -v
```
Expected: **All 6 tests PASS** (3 existing + 3 new metrics tests)

**Step 4: Run full test suite — baseline must stay at 292**
```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: **292+ tests pass, 0 failures**

**Step 5: Commit**
```bash
git add backend/pyproject.toml backend/uv.lock backend/main.py backend/tests/test_health.py
git commit -m "feat(08-02): expose /metrics endpoint via prometheus-fastapi-instrumentator"
```

---

## Plan 08-03: Custom Agent Metrics

### Task 11: Write failing tests for `core/metrics.py`

**Files:**
- Create: `backend/tests/test_metrics.py`

**Step 1: Create the test file**

```python
# backend/tests/test_metrics.py
"""
Unit tests for core/metrics.py — verifies all custom Prometheus metrics
are defined, have correct label names, and can be incremented/observed.
"""
import pytest


def test_tool_calls_total_exists() -> None:
    """TOOL_CALLS_TOTAL counter must exist with correct labels."""
    from core.metrics import TOOL_CALLS_TOTAL

    # Labels: tool, success
    counter = TOOL_CALLS_TOTAL.labels(tool="email.fetch", success="true")
    before = counter._value.get()
    counter.inc()
    assert counter._value.get() == before + 1.0


def test_tool_duration_seconds_exists() -> None:
    """TOOL_DURATION_SECONDS histogram must accept observations."""
    from core.metrics import TOOL_DURATION_SECONDS

    histogram = TOOL_DURATION_SECONDS.labels(tool="email.fetch")
    histogram.observe(0.123)
    # No assertion needed — observe() raises if label mismatch


def test_memory_ops_total_exists() -> None:
    """MEMORY_OPS_TOTAL counter must exist with operation label."""
    from core.metrics import MEMORY_OPS_TOTAL

    for op in ("save_fact", "search_facts", "save_turn", "load_turns"):
        counter = MEMORY_OPS_TOTAL.labels(operation=op)
        before = counter._value.get()
        counter.inc()
        assert counter._value.get() == before + 1.0


def test_memory_duration_seconds_exists() -> None:
    """MEMORY_DURATION_SECONDS histogram must accept observations."""
    from core.metrics import MEMORY_DURATION_SECONDS

    histogram = MEMORY_DURATION_SECONDS.labels(operation="search_facts")
    histogram.observe(0.042)


def test_no_user_id_label_in_metrics() -> None:
    """
    Metrics must NOT have user_id label — high cardinality would OOM Prometheus.
    Verify by checking that only expected low-cardinality labels are present.
    """
    from core.metrics import TOOL_CALLS_TOTAL, MEMORY_OPS_TOTAL

    tool_labels = TOOL_CALLS_TOTAL._labelnames
    assert "user_id" not in tool_labels
    assert set(tool_labels) == {"tool", "success"}

    mem_labels = MEMORY_OPS_TOTAL._labelnames
    assert "user_id" not in mem_labels
    assert set(mem_labels) == {"operation"}
```

**Step 2: Run tests to verify they fail**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_metrics.py -v
```
Expected: **FAIL** with `ModuleNotFoundError: No module named 'core.metrics'`

---

### Task 12: Create `core/metrics.py`

**Files:**
- Create: `backend/core/metrics.py`

**Step 1: Create the file**

```python
# backend/core/metrics.py
"""
Prometheus metrics registry for Blitz AgentOS.

All custom metrics are defined here at module level and imported where needed.
Import this module once at startup — prometheus_client registers metrics globally.

LABEL CARDINALITY RULE:
  Labels must be LOW-cardinality only (tool name, model alias, operation type).
  NEVER use user_id, conversation_id, or any unbounded identifier as a label.
  High-cardinality labels will cause Prometheus to OOM at scale.

LLM call metrics are NOT defined here — LiteLLM exposes its own /metrics
endpoint (enabled via prometheus_metrics: true in litellm/config.yaml) with
per-model latency, token counts, and spend. Use those in the LiteLLM Costs
Grafana dashboard instead of duplicating them here.
"""
from prometheus_client import Counter, Histogram

# ── Tool call metrics ─────────────────────────────────────────────────────────

TOOL_CALLS_TOTAL = Counter(
    "blitz_tool_calls_total",
    "Total tool invocations dispatched through the tools API",
    ["tool", "success"],
)

TOOL_DURATION_SECONDS = Histogram(
    "blitz_tool_duration_seconds",
    "Tool execution duration in seconds",
    ["tool"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# ── Memory operation metrics ──────────────────────────────────────────────────

MEMORY_OPS_TOTAL = Counter(
    "blitz_memory_ops_total",
    "Total memory operations (save_fact, search_facts, save_turn, load_turns)",
    ["operation"],
)

MEMORY_DURATION_SECONDS = Histogram(
    "blitz_memory_duration_seconds",
    "Memory operation duration in seconds",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)
```

**Step 2: Run the metrics tests — they should now pass**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/test_metrics.py -v
```
Expected: **5 tests PASS**

**Step 3: Commit**
```bash
git add backend/core/metrics.py backend/tests/test_metrics.py
git commit -m "feat(08-03): add Prometheus metrics registry (tool calls + memory ops)"
```

---

### Task 13: Write failing tests for memory instrumentation

**Files:**
- Create: `backend/tests/memory/test_memory_metrics.py`

**Step 1: Create the test file**

```python
# backend/tests/memory/test_memory_metrics.py
"""
Tests that memory operations increment Prometheus metrics.
Uses the same async test patterns as existing memory tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.mark.asyncio
async def test_save_fact_increments_counter() -> None:
    """save_fact() must increment MEMORY_OPS_TOTAL with operation=save_fact."""
    from core.metrics import MEMORY_OPS_TOTAL

    before = MEMORY_OPS_TOTAL.labels(operation="save_fact")._value.get()

    # Mock the DB session — we only care about the metric, not the DB call
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    from memory.long_term import save_fact

    await save_fact(mock_session, user_id=uuid4(), content="test fact")

    after = MEMORY_OPS_TOTAL.labels(operation="save_fact")._value.get()
    assert after == before + 1.0


@pytest.mark.asyncio
async def test_search_facts_increments_counter() -> None:
    """search_facts() must increment MEMORY_OPS_TOTAL with operation=search_facts."""
    from core.metrics import MEMORY_OPS_TOTAL

    before = MEMORY_OPS_TOTAL.labels(operation="search_facts")._value.get()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    from memory.long_term import search_facts

    await search_facts(
        mock_session,
        user_id=uuid4(),
        query_embedding=[0.0] * 1024,
    )

    after = MEMORY_OPS_TOTAL.labels(operation="search_facts")._value.get()
    assert after == before + 1.0


@pytest.mark.asyncio
async def test_save_turn_increments_counter() -> None:
    """save_turn() must increment MEMORY_OPS_TOTAL with operation=save_turn."""
    from core.metrics import MEMORY_OPS_TOTAL

    before = MEMORY_OPS_TOTAL.labels(operation="save_turn")._value.get()

    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    from memory.short_term import save_turn

    await save_turn(
        mock_session,
        user_id=uuid4(),
        conversation_id=uuid4(),
        role="user",
        content="hello",
    )

    after = MEMORY_OPS_TOTAL.labels(operation="save_turn")._value.get()
    assert after == before + 1.0
```

**Step 2: Run tests to verify they fail**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/memory/test_memory_metrics.py -v
```
Expected: **FAIL** — tests run but counters don't increment (instrumentation not added yet)

---

### Task 14: Instrument `memory/long_term.py`

**Files:**
- Modify: `backend/memory/long_term.py`

**Step 1: Read `backend/memory/long_term.py`** (already read — 93 lines)

**Step 2: Add imports at the top of the file (after existing imports)**

After `import structlog`, add:
```python
import time

from core.metrics import MEMORY_DURATION_SECONDS, MEMORY_OPS_TOTAL
```

**Step 3: Instrument `save_fact()`**

Wrap the body of `save_fact()`. Replace the current body:
```python
    fact = MemoryFact(user_id=user_id, content=content, source=source)
    session.add(fact)
    logger.debug("fact_saved", user_id=str(user_id), source=source)
    return fact
```
with:
```python
    _t = time.monotonic()
    fact = MemoryFact(user_id=user_id, content=content, source=source)
    session.add(fact)
    MEMORY_OPS_TOTAL.labels(operation="save_fact").inc()
    MEMORY_DURATION_SECONDS.labels(operation="save_fact").observe(time.monotonic() - _t)
    logger.debug("fact_saved", user_id=str(user_id), source=source)
    return fact
```

**Step 4: Instrument `search_facts()`**

Wrap the body of `search_facts()`. Replace the current body:
```python
    result = await session.execute(
        select(MemoryFact)
        .where(...)
        .order_by(...)
        .limit(k)
    )
    facts = list(result.scalars().all())
    logger.debug("facts_searched", user_id=str(user_id), returned=len(facts))
    return facts
```
with:
```python
    _t = time.monotonic()
    result = await session.execute(
        select(MemoryFact)
        .where(
            MemoryFact.user_id == user_id,
            MemoryFact.embedding.is_not(None),
            MemoryFact.superseded_at.is_(None),
        )
        .order_by(MemoryFact.embedding.cosine_distance(query_embedding))
        .limit(k)
    )
    facts = list(result.scalars().all())
    MEMORY_OPS_TOTAL.labels(operation="search_facts").inc()
    MEMORY_DURATION_SECONDS.labels(operation="search_facts").observe(time.monotonic() - _t)
    logger.debug("facts_searched", user_id=str(user_id), returned=len(facts))
    return facts
```

**Step 5: Run the memory metrics tests**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/memory/test_memory_metrics.py::test_save_fact_increments_counter tests/memory/test_memory_metrics.py::test_search_facts_increments_counter -v
```
Expected: **2 tests PASS**

---

### Task 15: Instrument `memory/short_term.py`

**Files:**
- Modify: `backend/memory/short_term.py`

**Step 1: Read `backend/memory/short_term.py`** (already partially read — read the full file)

**Step 2: Add imports after existing imports**

After `import structlog`, add:
```python
import time

from core.metrics import MEMORY_DURATION_SECONDS, MEMORY_OPS_TOTAL
```

**Step 3: Instrument `save_turn()`**

Read the full `save_turn()` function body (it's after line 60). Then wrap it:

```python
async def save_turn(
    session: AsyncSession,
    *,
    user_id: UUID,
    conversation_id: UUID,
    role: str,
    content: str,
) -> ConversationTurn:
    """...(keep existing docstring)..."""
    _t = time.monotonic()
    turn = ConversationTurn(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    session.add(turn)
    MEMORY_OPS_TOTAL.labels(operation="save_turn").inc()
    MEMORY_DURATION_SECONDS.labels(operation="save_turn").observe(time.monotonic() - _t)
    logger.debug("turn_saved", user_id=str(user_id), role=role)
    return turn
```

**Step 4: Run all memory metrics tests**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/memory/test_memory_metrics.py -v
```
Expected: **3 tests PASS**

**Step 5: Run full test suite**
```bash
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: **295+ tests pass, 0 failures**

**Step 6: Commit**
```bash
git add backend/memory/long_term.py backend/memory/short_term.py \
        backend/tests/memory/test_memory_metrics.py
git commit -m "feat(08-03): instrument memory operations with Prometheus metrics"
```

---

### Task 16: Instrument `api/routes/tools.py` for tool call metrics

**Files:**
- Modify: `backend/api/routes/tools.py`

**Step 1: Read `backend/api/routes/tools.py`** (already read — 77 lines)

**Step 2: Add import after existing imports**

After `import structlog`, add:
```python
import time

from core.metrics import TOOL_CALLS_TOTAL, TOOL_DURATION_SECONDS
```

**Step 3: Instrument `call_tool()`**

Replace the body of `call_tool()` (after the `tool_def is None` check) with a timed version:

```python
    logger.info(
        "tool_call_request",
        tool=body.tool,
        user_id=str(user["user_id"]),
    )

    _t = time.monotonic()
    success = "false"
    try:
        # Route to appropriate executor
        if tool_def.get("mcp_server"):
            result = await call_mcp_tool(body.tool, body.params, user, session)
            success = "true" if result.get("success", True) else "false"
            return ToolCallResponse(
                result=result.get("result"),
                success=result.get("success", True),
                error=result.get("error"),
            )
        else:
            raise HTTPException(
                status_code=501,
                detail="Backend tool direct execution not yet implemented",
            )
    except HTTPException:
        raise
    except Exception:
        success = "false"
        raise
    finally:
        TOOL_CALLS_TOTAL.labels(tool=body.tool, success=success).inc()
        TOOL_DURATION_SECONDS.labels(tool=body.tool).observe(time.monotonic() - _t)
```

**Step 4: Run full test suite**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: **295+ tests pass, 0 failures**

**Step 5: Commit**
```bash
git add backend/api/routes/tools.py
git commit -m "feat(08-03): instrument tool API calls with Prometheus metrics"
```

---

## Plan 08-04: Grafana Dashboards

### Task 17: Service Health dashboard

**Files:**
- Create: `infra/grafana/dashboards/service-health.json`

**Step 1: Create the dashboard JSON**

```json
{
  "title": "Service Health",
  "uid": "blitz-service-health",
  "schemaVersion": 38,
  "version": 1,
  "refresh": "30s",
  "time": { "from": "now-1h", "to": "now" },
  "panels": [
    {
      "id": 1,
      "title": "Prometheus Scrape Status",
      "type": "stat",
      "gridPos": { "h": 3, "w": 24, "x": 0, "y": 0 },
      "options": {
        "reduceOptions": { "calcs": ["lastNotNull"] },
        "orientation": "auto",
        "colorMode": "background",
        "graphMode": "none",
        "textMode": "value_and_name"
      },
      "fieldConfig": {
        "defaults": {
          "mappings": [
            { "type": "value", "options": { "1": { "text": "UP", "color": "green" } } },
            { "type": "value", "options": { "0": { "text": "DOWN", "color": "red" } } }
          ],
          "thresholds": { "mode": "absolute", "steps": [{ "value": 0, "color": "red" }, { "value": 1, "color": "green" }] }
        }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "up",
          "legendFormat": "{{job}}"
        }
      ]
    },
    {
      "id": 2,
      "title": "Container CPU Usage %",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 3 },
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "custom": { "lineWidth": 2 }
        }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "rate(container_cpu_usage_seconds_total{image!=\"\", name!=\"\"}[5m]) * 100",
          "legendFormat": "{{name}}"
        }
      ]
    },
    {
      "id": 3,
      "title": "Container Memory Usage (MB)",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 3 },
      "fieldConfig": {
        "defaults": {
          "unit": "decmbytes",
          "custom": { "lineWidth": 2 }
        }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "container_memory_usage_bytes{image!=\"\", name!=\"\"} / 1024 / 1024",
          "legendFormat": "{{name}}"
        }
      ]
    },
    {
      "id": 4,
      "title": "Container Restarts",
      "type": "stat",
      "gridPos": { "h": 4, "w": 24, "x": 0, "y": 11 },
      "options": {
        "reduceOptions": { "calcs": ["lastNotNull"] },
        "colorMode": "background",
        "textMode": "value_and_name"
      },
      "fieldConfig": {
        "defaults": {
          "thresholds": { "mode": "absolute", "steps": [{ "value": 0, "color": "green" }, { "value": 1, "color": "yellow" }, { "value": 3, "color": "red" }] },
          "mappings": []
        }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "container_last_seen{image!=\"\", name!=\"\"} * 0 + on(name) group_left() changes(container_start_time_seconds{image!=\"\", name!=\"\"}[24h])",
          "legendFormat": "{{name}}"
        }
      ]
    }
  ]
}
```

**Step 2: Commit**
```bash
git add infra/grafana/dashboards/service-health.json
git commit -m "feat(08-04): add Service Health Grafana dashboard"
```

---

### Task 18: API Health dashboard

**Files:**
- Create: `infra/grafana/dashboards/api-health.json`

**Step 1: Create the dashboard JSON**

```json
{
  "title": "API Health",
  "uid": "blitz-api-health",
  "schemaVersion": 38,
  "version": 1,
  "refresh": "30s",
  "time": { "from": "now-1h", "to": "now" },
  "panels": [
    {
      "id": 1,
      "title": "Request Rate (req/s)",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "fieldConfig": {
        "defaults": { "unit": "reqps", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum by (handler) (rate(http_requests_total[5m]))",
          "legendFormat": "{{handler}}"
        }
      ]
    },
    {
      "id": 2,
      "title": "Request Latency (p50 / p95 / p99)",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "fieldConfig": {
        "defaults": { "unit": "s", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "histogram_quantile(0.50, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))",
          "legendFormat": "p50"
        },
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))",
          "legendFormat": "p95"
        },
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "histogram_quantile(0.99, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))",
          "legendFormat": "p99"
        }
      ]
    },
    {
      "id": 3,
      "title": "5xx Error Rate %",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "custom": { "lineWidth": 2 },
          "thresholds": { "mode": "absolute", "steps": [{ "value": 0, "color": "green" }, { "value": 1, "color": "yellow" }, { "value": 5, "color": "red" }] }
        }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "100 * sum(rate(http_requests_total{status_code=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))",
          "legendFormat": "5xx %"
        }
      ]
    },
    {
      "id": 4,
      "title": "Top Endpoints by Request Count",
      "type": "table",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
      "options": { "sortBy": [{ "desc": true, "displayName": "Value" }] },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "topk(10, sum by (handler, method) (increase(http_requests_total[1h])))",
          "legendFormat": "{{method}} {{handler}}",
          "instant": true
        }
      ]
    }
  ]
}
```

**Step 2: Commit**
```bash
git add infra/grafana/dashboards/api-health.json
git commit -m "feat(08-04): add API Health Grafana dashboard"
```

---

### Task 19: Agent Activity dashboard

**Files:**
- Create: `infra/grafana/dashboards/agent-activity.json`

**Step 1: Create the dashboard JSON**

```json
{
  "title": "Agent Activity",
  "uid": "blitz-agent-activity",
  "schemaVersion": 38,
  "version": 1,
  "refresh": "30s",
  "time": { "from": "now-1h", "to": "now" },
  "panels": [
    {
      "id": 1,
      "title": "Tool Call Rate by Tool",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "fieldConfig": {
        "defaults": { "unit": "ops", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum by (tool) (rate(blitz_tool_calls_total[5m]))",
          "legendFormat": "{{tool}}"
        }
      ]
    },
    {
      "id": 2,
      "title": "Tool p95 Latency",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "fieldConfig": {
        "defaults": { "unit": "s", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "histogram_quantile(0.95, sum by (le, tool) (rate(blitz_tool_duration_seconds_bucket[5m])))",
          "legendFormat": "{{tool}} p95"
        }
      ]
    },
    {
      "id": 3,
      "title": "Memory Operation Rate",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
      "fieldConfig": {
        "defaults": { "unit": "ops", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum by (operation) (rate(blitz_memory_ops_total[5m]))",
          "legendFormat": "{{operation}}"
        }
      ]
    },
    {
      "id": 4,
      "title": "Memory p95 Latency",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
      "fieldConfig": {
        "defaults": { "unit": "s", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "histogram_quantile(0.95, sum by (le, operation) (rate(blitz_memory_duration_seconds_bucket[5m])))",
          "legendFormat": "{{operation}} p95"
        }
      ]
    },
    {
      "id": 5,
      "title": "Tool Success vs Failure",
      "type": "piechart",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 16 },
      "options": { "pieType": "donut" },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum by (success) (increase(blitz_tool_calls_total[1h]))",
          "legendFormat": "success={{success}}"
        }
      ]
    },
    {
      "id": 6,
      "title": "Logs Explorer (Agent logs)",
      "type": "logs",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 16 },
      "options": { "showTime": true, "showLabels": true, "wrapLogMessage": true },
      "targets": [
        {
          "datasource": { "uid": "blitz-loki" },
          "expr": "{job=\"blitz-agentos\", service=\"backend\"}",
          "legendFormat": ""
        }
      ]
    }
  ]
}
```

**Step 2: Commit**
```bash
git add infra/grafana/dashboards/agent-activity.json
git commit -m "feat(08-04): add Agent Activity Grafana dashboard"
```

---

### Task 20: LiteLLM Costs dashboard

**Files:**
- Create: `infra/grafana/dashboards/litellm-costs.json`

**Background:** LiteLLM with `prometheus_metrics: true` exposes these metrics at `litellm:4000/metrics`:
- `litellm_requests_metric` — request count by model, user
- `litellm_total_latency_metric` — end-to-end latency
- `litellm_llm_api_duration_seconds` — LLM API call duration
- `litellm_spend_metric` — spend in USD by model, user
- `litellm_total_tokens_metric` — token count by model

**Note:** LiteLLM metric names may vary slightly by version. After enabling `prometheus_metrics: true` and starting LiteLLM, verify exact names with:
```bash
curl -s http://localhost:4000/metrics | grep "^# TYPE litellm" | head -20
```
Update PromQL in the dashboard if metric names differ from those below.

**Step 1: Create the dashboard JSON**

```json
{
  "title": "LiteLLM Costs",
  "uid": "blitz-litellm-costs",
  "schemaVersion": 38,
  "version": 1,
  "refresh": "1m",
  "time": { "from": "now-24h", "to": "now" },
  "panels": [
    {
      "id": 1,
      "title": "Total Spend Today (USD)",
      "type": "stat",
      "gridPos": { "h": 4, "w": 6, "x": 0, "y": 0 },
      "options": {
        "reduceOptions": { "calcs": ["sum"] },
        "colorMode": "background",
        "textMode": "value"
      },
      "fieldConfig": {
        "defaults": { "unit": "currencyUSD", "decimals": 4 }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum(increase(litellm_spend_metric[24h]))",
          "legendFormat": "Today"
        }
      ]
    },
    {
      "id": 2,
      "title": "Total Requests Today",
      "type": "stat",
      "gridPos": { "h": 4, "w": 6, "x": 6, "y": 0 },
      "options": {
        "reduceOptions": { "calcs": ["sum"] }
      },
      "fieldConfig": {
        "defaults": { "unit": "short" }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum(increase(litellm_requests_metric[24h]))",
          "legendFormat": "Requests"
        }
      ]
    },
    {
      "id": 3,
      "title": "Spend by Model (Last 24h)",
      "type": "piechart",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 4 },
      "options": { "pieType": "donut" },
      "fieldConfig": {
        "defaults": { "unit": "currencyUSD", "decimals": 4 }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum by (model) (increase(litellm_spend_metric[24h]))",
          "legendFormat": "{{model}}"
        }
      ]
    },
    {
      "id": 4,
      "title": "Cumulative Spend Over Time",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 4 },
      "fieldConfig": {
        "defaults": { "unit": "currencyUSD", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum(litellm_spend_metric)",
          "legendFormat": "Total Spend"
        }
      ]
    },
    {
      "id": 5,
      "title": "Token Usage by Model",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 12 },
      "fieldConfig": {
        "defaults": { "unit": "short", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "sum by (model) (rate(litellm_total_tokens_metric[5m]))",
          "legendFormat": "{{model}}"
        }
      ]
    },
    {
      "id": 6,
      "title": "LLM API p95 Latency by Model",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 12 },
      "fieldConfig": {
        "defaults": { "unit": "s", "custom": { "lineWidth": 2 } }
      },
      "targets": [
        {
          "datasource": { "uid": "blitz-prometheus" },
          "expr": "histogram_quantile(0.95, sum by (le, model) (rate(litellm_llm_api_duration_seconds_bucket[5m])))",
          "legendFormat": "{{model}} p95"
        }
      ]
    }
  ]
}
```

**Step 2: Commit**
```bash
git add infra/grafana/dashboards/litellm-costs.json
git commit -m "feat(08-04): add LiteLLM Costs Grafana dashboard"
```

---

## Plan 08-05: Grafana Alerting

### Task 21: Create Grafana contact point (Telegram)

**Files:**
- Create: `infra/grafana/provisioning/alerting/contact_points.yml`

**Background:** Grafana provisioned alerting uses environment variable interpolation with `${VAR}` syntax in YAML. The `TELEGRAM_BOT_TOKEN` and `GRAFANA_ALERT_CHAT_ID` must be set in `.env` and passed to the Grafana container.

**Step 1: Add Grafana env vars to docker-compose.yml Grafana service**

Read `docker-compose.yml` and modify the `grafana` service environment section to add:
```yaml
  grafana:
    ...
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_ANALYTICS_REPORTING_ENABLED: "false"
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      GRAFANA_ALERT_CHAT_ID: ${GRAFANA_ALERT_CHAT_ID}
```

**Step 2: Create the contact point provisioning file**

```yaml
# infra/grafana/provisioning/alerting/contact_points.yml
apiVersion: 1

contactPoints:
  - orgId: 1
    name: telegram-blitz-alerts
    receivers:
      - uid: telegram-blitz-receiver
        type: telegram
        settings:
          bottoken: "${TELEGRAM_BOT_TOKEN}"
          chatid: "${GRAFANA_ALERT_CHAT_ID}"
          message: |
            🚨 Blitz AgentOS Alert
            {{ range .Alerts }}
            Status: {{ .Status | toUpper }}
            Alert: {{ .Labels.alertname }}
            {{ .Annotations.summary }}
            {{ .Annotations.description }}
            {{ end }}
        disableResolveMessage: false
```

**Step 3: Commit**
```bash
git add infra/grafana/provisioning/alerting/contact_points.yml docker-compose.yml
git commit -m "feat(08-05): add Grafana Telegram contact point provisioning"
```

---

### Task 22: Create alert rules (service down + high error rate)

**Files:**
- Create: `infra/grafana/provisioning/alerting/rules.yml`

**Step 1: Create the alert rules file**

```yaml
# infra/grafana/provisioning/alerting/rules.yml
apiVersion: 1

groups:
  - orgId: 1
    name: blitz-service-alerts
    folder: __Blitz
    interval: 1m
    rules:
      - uid: blitz-backend-down
        title: "Backend Service Down"
        condition: C
        data:
          - refId: A
            queryType: ""
            relativeTimeRange:
              from: 120
              to: 0
            datasourceUid: blitz-prometheus
            model:
              expr: "up{job=\"backend\"} == 0"
              instant: true
              refId: A
          - refId: C
            queryType: ""
            relativeTimeRange:
              from: 120
              to: 0
            datasourceUid: "__expr__"
            model:
              type: classic_conditions
              refId: C
              conditions:
                - type: query
                  evaluator:
                    type: gt
                    params: [0]
                  operator:
                    type: and
                  query:
                    params: [A]
                  reducer:
                    type: last
        noDataState: NoData
        execErrState: Alerting
        for: 1m
        annotations:
          summary: "Backend service is down"
          description: "The FastAPI backend (job=backend) has been unreachable for over 1 minute."
        labels:
          severity: critical
        isPaused: false

      - uid: blitz-litellm-down
        title: "LiteLLM Service Down"
        condition: C
        data:
          - refId: A
            queryType: ""
            relativeTimeRange:
              from: 120
              to: 0
            datasourceUid: blitz-prometheus
            model:
              expr: "up{job=\"litellm\"} == 0"
              instant: true
              refId: A
          - refId: C
            queryType: ""
            relativeTimeRange:
              from: 120
              to: 0
            datasourceUid: "__expr__"
            model:
              type: classic_conditions
              refId: C
              conditions:
                - type: query
                  evaluator:
                    type: gt
                    params: [0]
                  operator:
                    type: and
                  query:
                    params: [A]
                  reducer:
                    type: last
        noDataState: NoData
        execErrState: Alerting
        for: 1m
        annotations:
          summary: "LiteLLM proxy is down"
          description: "LiteLLM proxy (job=litellm) has been unreachable. All LLM calls will fail."
        labels:
          severity: critical
        isPaused: false

      - uid: blitz-high-error-rate
        title: "High API Error Rate"
        condition: C
        data:
          - refId: A
            queryType: ""
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: blitz-prometheus
            model:
              expr: "100 * sum(rate(http_requests_total{status_code=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m]))"
              instant: true
              refId: A
          - refId: C
            queryType: ""
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: "__expr__"
            model:
              type: classic_conditions
              refId: C
              conditions:
                - type: query
                  evaluator:
                    type: gt
                    params: [5]
                  operator:
                    type: and
                  query:
                    params: [A]
                  reducer:
                    type: last
        noDataState: NoData
        execErrState: Alerting
        for: 5m
        annotations:
          summary: "API 5xx error rate above 5%"
          description: "Backend 5xx error rate has exceeded 5% for 5 consecutive minutes."
        labels:
          severity: warning
        isPaused: false
```

**Step 2: Also create a notification policy to route all alerts to Telegram**

```yaml
# infra/grafana/provisioning/alerting/notification_policy.yml
apiVersion: 1

policies:
  - orgId: 1
    receiver: telegram-blitz-alerts
    group_by: ["alertname"]
    group_wait: 30s
    group_interval: 5m
    repeat_interval: 4h
```
Save this to `infra/grafana/provisioning/alerting/notification_policy.yml`.

**Step 3: Commit**
```bash
git add infra/grafana/provisioning/alerting/
git commit -m "feat(08-05): add Grafana alert rules and notification policy (service-down + high error rate → Telegram)"
```

---

### Task 23: End-to-end smoke test

**Step 1: Run the full backend test suite one final time**
```bash
cd /home/tungmv/Projects/hox-agentos/backend
PYTHONPATH=. .venv/bin/pytest tests/ -q
```
Expected: **295+ tests pass, 0 failures**

**Step 2: Start full observability stack**
```bash
cd /home/tungmv/Projects/hox-agentos
docker compose up -d prometheus grafana loki alloy cadvisor
```

**Step 3: Verify all observability services are healthy**
```bash
# Wait ~20 seconds for startup, then:
curl -s http://localhost:9090/-/healthy         # Prometheus
curl -s http://localhost:3100/ready             # Loki
curl -s http://localhost:3001/api/health        # Grafana

# Check Prometheus targets (cadvisor should be up)
curl -s 'http://localhost:9090/api/v1/targets' | python3 -c "
import json,sys
data=json.load(sys.stdin)
for t in data['data']['activeTargets']:
    print(t['labels'].get('job','?'), '->', t['health'])
"
```
Expected: `cadvisor -> up` (backend/litellm targets will be `unknown` until those services start)

**Step 4: Verify Grafana provisioning**
```bash
# Check datasources are provisioned
curl -s -u admin:${GRAFANA_ADMIN_PASSWORD:-blitz_grafana_admin} \
  http://localhost:3001/api/datasources | python3 -c "
import json,sys
for ds in json.load(sys.stdin):
    print(ds['name'], '->', ds['type'])
"
```
Expected:
```
Prometheus -> prometheus
Loki -> loki
```

**Step 5: Verify dashboards are provisioned**
```bash
curl -s -u admin:${GRAFANA_ADMIN_PASSWORD:-blitz_grafana_admin} \
  'http://localhost:3001/api/search?folderTitle=__Blitz' | python3 -c "
import json,sys
for d in json.load(sys.stdin):
    print(d['title'])
"
```
Expected (4 dashboards):
```
Service Health
API Health
Agent Activity
LiteLLM Costs
```

**Step 6: Start backend and verify metrics scraping**
```bash
just backend-bg   # start backend in background
sleep 10
# Check Prometheus has backend metrics
curl -s 'http://localhost:9090/api/v1/query?query=up{job="backend"}' | python3 -c "
import json,sys
r=json.load(sys.stdin)
for v in r['data']['result']:
    print(v['metric']['job'], '->', v['value'][1])
"
```
Expected: `backend -> 1`

**Step 7: Verify /metrics endpoint has custom agent metrics**
```bash
curl -s http://localhost:8000/metrics | grep "blitz_"
```
Expected: Lines containing `blitz_tool_calls_total`, `blitz_memory_ops_total`, etc.

**Step 8: Stop background backend**
```bash
just backend-stop
```

**Step 9: Commit final verification**
```bash
git add .
git status  # should show nothing or just docker-compose.yml if modified in Task 21
git commit -m "docs(08): phase 8 observability complete — all services verified"
```
(Only commit if there are actual uncommitted changes from the smoke test.)

---

## UAT Checklist (for /gsd:verify-work)

After all tasks are complete, the verifier should check:

1. `docker compose up -d prometheus grafana loki alloy cadvisor` — all 5 services start healthy
2. `http://localhost:3001` — Grafana login works with `admin` / value of `GRAFANA_ADMIN_PASSWORD`
3. Grafana → Datasources — Prometheus and Loki both show green "Data source connected"
4. Grafana → Dashboards → `__Blitz` folder — 4 dashboards visible
5. Service Health dashboard — cAdvisor container metrics visible (CPU/memory panels populated)
6. `PYTHONPATH=. .venv/bin/pytest tests/ -q` — 295+ tests, 0 failures
7. `curl http://localhost:8000/metrics | grep blitz_` — custom metrics present
8. `curl http://localhost:9090/api/v1/query?query=up` — backend and litellm show `1`
9. Grafana → Alerting — 3 alert rules visible (Backend Down, LiteLLM Down, High Error Rate)
10. Grafana → Alerting → Contact Points — `telegram-blitz-alerts` contact point visible

---

*Plan: 23 tasks across 5 plan groups*
*Requirements covered: OBSV-01 (Grafana dashboards), OBSV-02 (Loki log aggregation), OBSV-03 (LiteLLM cost tracking)*
*New tests: ~10 (metrics module + memory instrumentation + /metrics endpoint)*
*Files created: 14 new files across infra/ and backend/*
*Files modified: 6 (docker-compose.yml, litellm/config.yaml, main.py, long_term.py, short_term.py, tools.py)*
