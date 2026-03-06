# Blitz AgentOS — task runner
# Usage: just <recipe>   (run `just` to list all recipes)
#
# Dev workflow (Docker only — backend and frontend run in containers, not on host):
#
#   just dev-local-build   ← run once (or after dep changes to pyproject.toml / package.json)
#   just dev-local         ← start everything with hot reload; code changes apply without rebuild
#   just dev-local-down    ← stop all services
#
# Worker changes (no hot reload — must restart):
#   just dev-local-restart-workers

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
    docker compose {{LOCAL_COMPOSE}} restart {{service}}

# Show clean status summary of all Docker services
ps:
    #!/usr/bin/env bash
    echo ""
    echo "🐳 Docker Compose Status"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    ALL_CONTAINERS=$(docker compose {{LOCAL_COMPOSE}} ps -a --format "table {{"{{"}}.Service{{"}}"}}|{{"{{"}}.State{{"}}"}}|{{"{{"}}.Status{{"}}"}}|{{"{{"}}.Ports{{"}}"}}")

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
    docker compose {{LOCAL_COMPOSE}} logs -f {{service}}

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
    docker compose {{LOCAL_COMPOSE}} up -d celery-worker celery-worker-default

# Stop Celery workers
workers-stop:
    docker compose {{LOCAL_COMPOSE}} stop celery-worker celery-worker-default

# ── Docker: Build & Rebuild ───────────────────────────────────────────────────
# Rebuild and restart a single service (prod images): just rebuild backend
rebuild service:
    docker compose build {{service}} && docker compose up -d --no-deps {{service}}

# Rebuild and restart a single service (dev-local images): just rebuild-local frontend
rebuild-local service:
    docker compose {{LOCAL_COMPOSE}} build {{service}} && \
    docker compose {{LOCAL_COMPOSE}} up -d --no-deps {{service}}

# Rebuild and restart backend Docker image (dev-local)
backend-rebuild:
    docker compose {{LOCAL_COMPOSE}} build backend && docker compose {{LOCAL_COMPOSE}} up -d --no-deps backend

# Rebuild and restart frontend Docker image (dev-local)
frontend-rebuild:
    docker compose {{LOCAL_COMPOSE}} build frontend && docker compose {{LOCAL_COMPOSE}} up -d --no-deps frontend

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
