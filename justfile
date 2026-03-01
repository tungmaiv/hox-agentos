# Blitz AgentOS — task runner
# Usage: just <recipe>   (run `just` to list all recipes)

BACKEND_DIR := "backend"
FRONTEND_DIR := "frontend"

# ── default ───────────────────────────────────────────────────────────────────
# List all available recipes
default:
    @just --list

# ── Docker Compose ────────────────────────────────────────────────────────────
# Start all Docker services (detached)
up:
    docker compose up -d

# Start specific service(s): just up-svc postgres redis
up-svc *services:
    docker compose up -d {{services}}

# Stop all Docker services (keep volumes)
down:
    docker compose down

# Stop all Docker services AND remove volumes (destructive — wipes DB data)
down-v:
    docker compose down -v

# Remove stopped containers and dangling images
clean:
    docker compose down --remove-orphans
    docker image prune -f

# Show live logs for all services (or a specific one: just logs postgres)
logs *service:
    docker compose logs -f {{service}}

# Show status of all services
ps:
    docker compose ps

# Restart all services
restart:
    docker compose restart

# Restart a specific service: just restart-svc backend
restart-svc service:
    docker compose restart {{service}}

# ── Infrastructure groups ──────────────────────────────────────────────────────
# Start core infra only (postgres, redis, litellm, mcp-crm, observability) — no app services
infra:
    docker compose up -d postgres redis litellm mcp-crm prometheus grafana loki alloy cadvisor

# Start Celery workers only (requires infra already running)
workers:
    docker compose up -d celery-worker celery-worker-default

# Stop Celery workers
workers-stop:
    docker compose stop celery-worker celery-worker-default

# Start infra + workers only (no Docker backend/frontend — run those locally)
# Use with: just backend && just frontend
stack:
    docker compose up -d postgres redis litellm mcp-crm prometheus grafana loki alloy cadvisor celery-worker celery-worker-default

# Stop the Docker frontend container (use when running frontend locally)
frontend-docker-stop:
    docker compose stop frontend

# Force-rebuild and restart a single service: just rebuild backend
rebuild service:
    docker compose build {{service}} && docker compose up -d --no-deps {{service}}

# Wipe and restart infra containers + postgres volume (DESTRUCTIVE — loses all DB data)
# Run `just migrate` afterwards to re-apply schema
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

# ── Backend (FastAPI / uvicorn) ───────────────────────────────────────────────
# Start backend dev server (hot reload, port 8000)
backend:
    cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --port 8000 --reload

# Start backend in background (writes PID to .backend.pid)
backend-bg:
    cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --port 8000 --reload & echo $! > ../.backend.pid
    @echo "Backend started (PID $(cat .backend.pid))"

# Stop background backend process
backend-stop:
    @if [ -f .backend.pid ]; then \
        kill $(cat .backend.pid) 2>/dev/null && echo "Backend stopped" || echo "Backend already stopped"; \
        rm -f .backend.pid; \
    else \
        pkill -f "uvicorn main:app" 2>/dev/null && echo "Backend stopped" || echo "No backend process found"; \
    fi

# Kill any uvicorn process on port 8000 (force)
backend-kill:
    #!/usr/bin/env bash
    pkill -9 -f "uvicorn main:app" 2>/dev/null || true
    fuser -k 8000/tcp 2>/dev/null || true
    echo "Backend killed"

# Show backend logs (tail -f on last run, only works with background mode)
backend-log:
    @echo "Hint: use 'just backend' to run in foreground with live output"

# ── Frontend (Next.js / pnpm) ─────────────────────────────────────────────────
# Start frontend dev server (port 3000)
# NODE_EXTRA_CA_CERTS: trusts Keycloak's self-signed cert so NextAuth token refresh works
frontend:
    cd {{FRONTEND_DIR}} && NODE_EXTRA_CA_CERTS="certs/keycloak.crt" pnpm dev

# Start frontend in background (writes PID to .frontend.pid)
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

# Kill any Next.js dev process (force)
frontend-kill:
    #!/usr/bin/env bash
    pkill -9 -f "next dev" 2>/dev/null || true
    fuser -k 3000/tcp 2>/dev/null || true
    echo "Frontend killed"

# ── Shortcuts ─────────────────────────────────────────────────────────────────
# Stop both backend and frontend
stop: backend-stop frontend-stop

# Kill both backend and frontend
kill: backend-kill frontend-kill

# Start infra (Docker) + backend + frontend in separate terminals via tmux
# Requires tmux. Falls back to instructions if not available.
dev:
    #!/usr/bin/env bash
    set -e
    if ! command -v tmux &>/dev/null; then
        echo "tmux not found — start manually:"
        echo "  just up        # Docker services"
        echo "  just backend   # in one terminal"
        echo "  just frontend  # in another terminal"
        exit 0
    fi
    tmux new-session -d -s blitz -n infra 'just up && docker compose logs -f' 2>/dev/null || true
    tmux new-window -t blitz -n backend 'cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --port 8000 --reload'
    tmux new-window -t blitz -n frontend 'cd {{FRONTEND_DIR}} && pnpm dev'
    tmux select-window -t blitz:backend
    tmux attach-session -t blitz

# ── Database ──────────────────────────────────────────────────────────────────
# Run Alembic migrations
migrate:
    cd {{BACKEND_DIR}} && .venv/bin/alembic upgrade head

# Open psql shell
db:
    docker compose exec postgres psql -U blitz -d blitz
