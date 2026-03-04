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

# Show clean status of all docker services with summary
ps:
    #!/usr/bin/env bash
    echo ""
    echo "🐳 Docker Compose Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Get all container info and parse
    ALL_CONTAINERS=$(docker compose ps -a --format "table {{"{{"}}.Service{{"}}"}}|{{"{{"}}.State{{"}}"}}|{{"{{"}}.Status{{"}}"}}|{{"{{"}}.Ports{{"}}"}}")
    
    # Counts (use wc -l to avoid issues with grep -c on multiline output)
    RUNNING=$(echo "$ALL_CONTAINERS" | grep "|running|" | wc -l)
    EXITED=$(echo "$ALL_CONTAINERS" | grep "|exited|" | wc -l)
    TOTAL=$(echo "$ALL_CONTAINERS" | grep -v "^$" | wc -l)
    
    # Summary
    echo ""
    echo "  📊 Summary: $RUNNING running | $EXITED stopped | $TOTAL total"
    echo ""
    
    # Running services
    if [ "$RUNNING" -gt 0 ]; then
        echo "  ✅ RUNNING:"
        echo "$ALL_CONTAINERS" | grep "|running|" | while IFS='|' read -r service state status ports; do
            printf "     %-20s | %s\n" "$service" "$status"
        done
        echo ""
    fi
    
    # Stopped services
    if [ "$EXITED" -gt 0 ]; then
        echo "  ⏹️  STOPPED:"
        echo "$ALL_CONTAINERS" | grep "|exited|" | while IFS='|' read -r service state status ports; do
            printf "     %-20s | %s\n" "$service" "$status"
        done
        echo ""
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

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

# Start full stack with hot reload — no rebuilds needed on code change
# Backend: uvicorn --reload watches ./backend; Frontend: pnpm dev HMR
# First run only: docker compose -f docker-compose.yml -f docker-compose.local.yml build frontend
dev-local:
    docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# Stop dev-local stack
dev-local-down:
    docker compose -f docker-compose.yml -f docker-compose.local.yml down

# Force-rebuild and restart a single service: just rebuild backend
rebuild service:
    docker compose build {{service}} && docker compose up -d --no-deps {{service}}

# Force-rebuild using local override (dev): just rebuild-local frontend
rebuild-local service:
    docker compose -f docker-compose.yml -f docker-compose.local.yml build {{service}} && \
    docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --no-deps {{service}}

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
    cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Start backend in background (writes PID to .backend.pid)
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

# Kill any uvicorn process on port 8000 (force) - includes Docker container
backend-kill:
    #!/usr/bin/env bash
    set -e
    echo "Stopping Docker backend container..."
    docker compose stop backend 2>/dev/null || true
    echo "Killing local backend processes..."
    pkill -9 -f "uvicorn main:app" 2>/dev/null || true
    pkill -9 -f "python.*main:app" 2>/dev/null || true
    fuser -k 8000/tcp 2>/dev/null || true
    rm -f .backend.pid 2>/dev/null || true
    echo "Backend killed"

# Rebuild and restart backend Docker container
backend-rebuild:
    docker compose build backend && docker compose up -d --no-deps backend
    @echo "Backend rebuilt and started in Docker"

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

# Kill any Next.js dev process (force) - includes Docker container
frontend-kill:
    #!/usr/bin/env bash
    set -e
    echo "Stopping Docker frontend container..."
    docker compose stop frontend 2>/dev/null || true
    echo "Killing local frontend processes..."
    # Kill various Next.js process patterns
    pkill -9 -f "next dev" 2>/dev/null || true
    pkill -9 -f "next-server" 2>/dev/null || true
    pkill -9 -f "node.*next" 2>/dev/null || true
    # Kill common Next.js ports
    for port in 3000 3001 3002 3003 3004 3005; do
        fuser -k "${port}/tcp" 2>/dev/null || true
    done
    # Clean up PID file if exists
    rm -f .frontend.pid 2>/dev/null || true
    echo "Frontend killed"

# Rebuild and restart frontend Docker container
frontend-rebuild:
    docker compose build frontend && docker compose up -d --no-deps frontend
    @echo "Frontend rebuilt and started in Docker"

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
    tmux new-window -t blitz -n backend 'cd {{BACKEND_DIR}} && PYTHONPATH=. .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload'
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
