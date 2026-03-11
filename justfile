# Blitz AgentOS — simplified task runner
# Usage: just <command> [service1 service2 ...]
# All commands default to ALL services if none specified
#
# Examples:
#   just up                    # Start all services
#   just up backend frontend   # Start only backend and frontend
#   just down                  # Stop all services
#   just rebuild frontend      # Rebuild and restart frontend
#   just reset                 # DESTRUCTIVE: wipe all data and restart

LOCAL_COMPOSE := "-f docker-compose.yml -f docker-compose.local.yml"

# List all available recipes
[private]
default:
    @just --list

# ── Core Commands ─────────────────────────────────────────────────────────────

# Start services (default: all)
up *services:
    #!/usr/bin/env bash
    if [ -z "{{services}}" ]; then
        docker compose {{LOCAL_COMPOSE}} up -d
    else
        docker compose {{LOCAL_COMPOSE}} up -d {{services}}
    fi

# Stop services (default: all)
down *services:
    #!/usr/bin/env bash
    if [ -z "{{services}}" ]; then
        docker compose {{LOCAL_COMPOSE}} down
    else
        docker compose {{LOCAL_COMPOSE}} stop {{services}}
    fi

# Alias for down
stop *services:
    just down {{services}}

# Restart without rebuild (default: all)
restart *services:
    #!/usr/bin/env bash
    if [ -z "{{services}}" ]; then
        docker compose {{LOCAL_COMPOSE}} restart
    else
        docker compose {{LOCAL_COMPOSE}} restart {{services}}
    fi

# Rebuild and restart (default: all)
rebuild *services:
    #!/usr/bin/env bash
    if [ -z "{{services}}" ]; then
        docker compose {{LOCAL_COMPOSE}} build
        docker compose {{LOCAL_COMPOSE}} up -d
    else
        docker compose {{LOCAL_COMPOSE}} build {{services}}
        docker compose {{LOCAL_COMPOSE}} up -d --no-deps {{services}}
    fi

# Build only, don't start (default: all)
build *services:
    #!/usr/bin/env bash
    if [ -z "{{services}}" ]; then
        docker compose {{LOCAL_COMPOSE}} build
    else
        docker compose {{LOCAL_COMPOSE}} build {{services}}
    fi

# DESTRUCTIVE: Stop all, remove ALL volumes, start fresh
reset:
    #!/usr/bin/env bash
    echo "⚠️  WARNING: This will DESTROY all data including database volumes!"
    echo "   Press Ctrl+C within 3 seconds to cancel..."
    sleep 3
    echo ""
    echo "🗑️  Stopping and removing all containers and volumes..."
    docker compose {{LOCAL_COMPOSE}} down -v
    echo ""
    echo "🚀 Starting fresh..."
    docker compose {{LOCAL_COMPOSE}} up -d
    echo ""
    echo "✅ Reset complete."
    echo "   Run 'just migrate' to re-apply database schema."

# ── Status & Debugging ────────────────────────────────────────────────────────

# Show status
ps:
    docker compose {{LOCAL_COMPOSE}} ps

# Tail logs (default: all services, or specific service: just logs backend)
logs *service:
    #!/usr/bin/env bash
    if [ -z "{{service}}" ]; then
        docker compose {{LOCAL_COMPOSE}} logs -f
    else
        docker compose {{LOCAL_COMPOSE}} logs -f {{service}}
    fi

# ── Database ──────────────────────────────────────────────────────────────────

# Run Alembic migrations
migrate:
    cd backend && .venv/bin/alembic upgrade head

# Open PostgreSQL shell
db:
    docker compose exec postgres psql -U blitz -d blitz
