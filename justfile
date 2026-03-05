# Blitz AgentOS — task runner
# Usage: just <recipe>   (run `just` to list all recipes)
#
# Common workflows:
#
#   Full Docker with hot reload (recommended):
#     just dev-local-build   ← run once (or after dep changes)
#     just dev-local         ← start everything; code changes apply without rebuild
#     just dev-local-down    ← stop
#
#   Hybrid — infra in Docker, backend/frontend on host:
#     just stack             ← start infra + workers in Docker
#     just backend           ← in terminal 1 (hot reload)
#     just frontend          ← in terminal 2 (HMR)
#     just stop              ← stop host processes
#
#   Or use tmux to do the hybrid mode automatically:
#     just dev               ← opens infra/backend/frontend in tmux panes

BACKEND_DIR  := "backend"
FRONTEND_DIR := "frontend"
LOCAL_COMPOSE := "-f docker-compose.yml -f docker-compose.local.yml"

# List all available recipes
default:
    @just --list

# ── Dev Mode: Full Docker with hot reload ─────────────────────────────────────
# Backend image bakes the .venv; frontend Dockerfile.dev installs node_modules into the image.
# Build dev images — run once on first use, or after pyproject.toml / package.json changes
dev-local-build:
    docker compose {{LOCAL_COMPOSE}} build backend frontend

# Backend: --reload; Frontend: HMR; Workers: source-mounted (restart after changes).
# Prerequisite: run `just dev-local-build` once before first use.
# Start full stack in Docker with hot reload — no rebuilds needed on source-code changes
dev-local:
    docker compose {{LOCAL_COMPOSE}} up -d

# Stop the dev-local stack
dev-local-down:
    docker compose {{LOCAL_COMPOSE}} down

# Restart celery workers after scheduler/worker code changes (no rebuild needed)
dev-local-restart-workers:
    docker compose {{LOCAL_COMPOSE}} restart celery-worker celery-worker-default

# ── Dev Mode: Hybrid (infra in Docker, backend/frontend on host) ──────────────
# Use: just stack → just backend (terminal 1) → just frontend (terminal 2)
# Start infra + celery workers in Docker (run backend/frontend on host separately)
stack:
    docker compose up -d postgres redis litellm mcp-crm prometheus grafana loki alloy cadvisor celery-worker celery-worker-default

# Start infra + backend + frontend in split tmux panes (requires tmux)
dev:
    #!/usr/bin/env bash
    set -e
    if ! command -v tmux &>/dev/null; then
        echo "tmux not found — start manually:"
        echo "  just stack     # Docker infra + workers"
        echo "  just backend   # in one terminal"
        echo "  just frontend  # in another terminal"
        exit 0
    fi
    tmux new-session -d -s blitz -n infra 'just stack && docker compose logs -f' 2>/dev/null || true
    tmux new-window -t blitz -n backend 'cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload'
    tmux new-window -t blitz -n frontend 'cd {{FRONTEND_DIR}} && NODE_EXTRA_CA_CERTS="certs/keycloak.crt" pnpm dev'
    tmux select-window -t blitz:backend
    tmux attach-session -t blitz

# ── Host: Backend (FastAPI / uvicorn) ─────────────────────────────────────────
# Start backend on host with hot reload (port 8000)
backend:
    cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Start backend in background — writes PID to .backend.pid
backend-bg:
    cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload & echo $! > ../.backend.pid
    @echo "Backend started (PID $(cat .backend.pid))"

# Stop background backend process
backend-stop:
    @if [ -f .backend.pid ]; then \
        kill $(cat .backend.pid) 2>/dev/null && echo "Backend stopped" || echo "Backend already stopped"; \
        rm -f .backend.pid; \
    else \
        pkill -f "uvicorn main:app" 2>/dev/null && echo "Backend stopped" || echo "No backend process found"; \
    fi

# Force-kill all uvicorn processes on port 8000 (including Docker container)
backend-kill:
    #!/usr/bin/env bash
    set -e
    docker compose stop backend 2>/dev/null || true
    pkill -9 -f "uvicorn main:app" 2>/dev/null || true
    pkill -9 -f "python.*main:app" 2>/dev/null || true
    fuser -k 8000/tcp 2>/dev/null || true
    rm -f .backend.pid 2>/dev/null || true
    echo "Backend killed"

# ── Host: Frontend (Next.js / pnpm) ───────────────────────────────────────────
# NODE_EXTRA_CA_CERTS trusts Keycloak's self-signed cert for NextAuth token refresh
# Start frontend on host with HMR (port 3000)
frontend:
    cd {{FRONTEND_DIR}} && NODE_EXTRA_CA_CERTS="certs/keycloak.crt" pnpm dev

# Start frontend in background — writes PID to .frontend.pid
frontend-bg:
    cd {{FRONTEND_DIR}} && NODE_EXTRA_CA_CERTS="certs/keycloak.crt" pnpm dev & echo $! > ../.frontend.pid
    @echo "Frontend started (PID $(cat .frontend.pid))"

# Stop background frontend process
frontend-stop:
    @if [ -f .frontend.pid ]; then \
        kill $(cat .frontend.pid) 2>/dev/null && echo "Frontend stopped" || echo "Frontend already stopped"; \
        rm -f .frontend.pid; \
    else \
        pkill -f "next dev" 2>/dev/null && echo "Frontend stopped" || echo "No frontend process found"; \
    fi

# Force-kill all Next.js processes (including Docker container)
frontend-kill:
    #!/usr/bin/env bash
    set -e
    docker compose stop frontend 2>/dev/null || true
    pkill -9 -f "next dev" 2>/dev/null || true
    pkill -9 -f "next-server" 2>/dev/null || true
    pkill -9 -f "node.*next" 2>/dev/null || true
    for port in 3000 3001 3002 3003 3004 3005; do
        fuser -k "${port}/tcp" 2>/dev/null || true
    done
    rm -f .frontend.pid 2>/dev/null || true
    echo "Frontend killed"

# Stop both backend and frontend host processes
stop: backend-stop frontend-stop

# Force-kill both backend and frontend host processes
kill: backend-kill frontend-kill

# ── Docker: Manage ────────────────────────────────────────────────────────────
# Start all Docker services (detached)
up:
    docker compose up -d

# Start specific service(s): just up-svc postgres redis
up-svc *services:
    docker compose up -d {{services}}

# Stop all Docker services (keep volumes)
down:
    docker compose down

# Stop all Docker services and remove volumes — DESTRUCTIVE, wipes DB data
down-v:
    docker compose down -v

# Restart all services
restart:
    docker compose restart

# Restart a specific service: just restart-svc backend
restart-svc service:
    docker compose restart {{service}}

# Show clean status summary of all Docker services
ps:
    #!/usr/bin/env bash
    echo ""
    echo "🐳 Docker Compose Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    ALL_CONTAINERS=$(docker compose ps -a --format "table {{"{{"}}.Service{{"}}"}}|{{"{{"}}.State{{"}}"}}|{{"{{"}}.Status{{"}}"}}|{{"{{"}}.Ports{{"}}"}}")

    RUNNING=$(echo "$ALL_CONTAINERS" | grep "|running|" | wc -l)
    EXITED=$(echo "$ALL_CONTAINERS" | grep "|exited|" | wc -l)
    TOTAL=$(echo "$ALL_CONTAINERS" | grep -v "^$" | wc -l)

    echo ""
    echo "  📊 Summary: $RUNNING running | $EXITED stopped | $TOTAL total"
    echo ""

    if [ "$RUNNING" -gt 0 ]; then
        echo "  ✅ RUNNING:"
        echo "$ALL_CONTAINERS" | grep "|running|" | while IFS='|' read -r service state status ports; do
            printf "     %-20s | %s\n" "$service" "$status"
        done
        echo ""
    fi

    if [ "$EXITED" -gt 0 ]; then
        echo "  ⏹️  STOPPED:"
        echo "$ALL_CONTAINERS" | grep "|exited|" | while IFS='|' read -r service state status ports; do
            printf "     %-20s | %s\n" "$service" "$status"
        done
        echo ""
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

# Tail logs for all services, or a specific one: just logs postgres
logs *service:
    docker compose logs -f {{service}}

# Remove stopped containers and dangling images
clean:
    docker compose down --remove-orphans
    docker image prune -f

# ── Docker: Service Groups ────────────────────────────────────────────────────
# Start core infra only — postgres, redis, litellm, MCPs, observability (no app services)
infra:
    docker compose up -d postgres redis litellm mcp-crm prometheus grafana loki alloy cadvisor

# Start Celery workers only (requires infra already running)
workers:
    docker compose up -d celery-worker celery-worker-default

# Stop Celery workers
workers-stop:
    docker compose stop celery-worker celery-worker-default

# Stop the Docker frontend container (use when switching to running frontend on host)
frontend-docker-stop:
    docker compose stop frontend

# ── Docker: Build & Rebuild ───────────────────────────────────────────────────
# Rebuild and restart a single service (prod images): just rebuild backend
rebuild service:
    docker compose build {{service}} && docker compose up -d --no-deps {{service}}

# Rebuild and restart a single service (dev-local images): just rebuild-local frontend
rebuild-local service:
    docker compose {{LOCAL_COMPOSE}} build {{service}} && \
    docker compose {{LOCAL_COMPOSE}} up -d --no-deps {{service}}

# Rebuild and restart backend Docker image (prod)
backend-rebuild:
    docker compose build backend && docker compose up -d --no-deps backend

# Rebuild and restart frontend Docker image (prod)
frontend-rebuild:
    docker compose build frontend && docker compose up -d --no-deps frontend

# Run `just migrate` afterwards to re-apply schema.
# Wipe infra containers + postgres volume then restart — DESTRUCTIVE, loses all DB data
infra-reset:
    #!/usr/bin/env bash
    set -e
    echo "Stopping infra containers..."
    docker compose stop postgres redis litellm mcp-crm prometheus grafana loki alloy cadvisor
    docker compose rm -f postgres redis litellm mcp-crm prometheus grafana loki alloy cadvisor
    echo "Removing postgres data volume..."
    docker volume rm hox-agentos_postgres_data 2>/dev/null || echo "(volume already gone)"
    echo "Starting fresh infra..."
    docker compose up -d postgres redis litellm mcp-crm prometheus grafana loki alloy cadvisor
    echo ""
    echo "Done. Run 'just migrate' to re-apply the schema."

# ── Database ──────────────────────────────────────────────────────────────────
# Run Alembic migrations
migrate:
    cd {{BACKEND_DIR}} && .venv/bin/alembic upgrade head

# Open a psql shell
db:
    docker compose exec postgres psql -U blitz -d blitz
