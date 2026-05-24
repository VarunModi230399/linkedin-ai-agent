# Makefile
# Short commands for common development tasks.
# Usage: make <command>
# Example: make dev, make test, make docker-up

.PHONY: install dev test lint format docker-up docker-down clean seed

# ── Setup ─────────────────────────────────────────
install:
	uv sync
	# Installs all dependencies from uv.lock
	# Run this after cloning the repo

# ── Development ───────────────────────────────────
dev:
	uv run uvicorn src.api.app:app --reload --port 8000
	# Starts the FastAPI approval UI
	# --reload means it restarts when you change code

worker:
	uv run celery -A src.worker.celery_app worker --loglevel=info
	# Starts the Celery background worker
	# Picks up and runs queued tasks

beat:
	uv run celery -A src.worker.beat_schedule beat --loglevel=info
	# Starts the Celery scheduler
	# Triggers tasks on cron schedule (6am KB refresh etc.)

agent:
	uv run python scripts/run_agent.py
	# Runs the full LinkedIn AI agent
	# Requires: make dev running in another terminal

seed:
	uv run python scripts/seed_knowledge_base.py
	# Refreshes the Qdrant knowledge base
	# Fetches latest AI content from HN, arXiv, Dev.to, HuggingFace

# ── Quality ───────────────────────────────────────
lint:
	uv run ruff check src/ tests/
	uv run mypy src/
	# Checks code for errors and type issues
	# Run before committing

format:
	uv run ruff format src/ tests/
	# Auto-formats all Python files
	# Fixes spacing, quotes, imports

test:
	uv run pytest tests/ -v
	# Runs all unit and integration tests
	# -v means verbose — shows each test name

evals:
	uv run python evals/run_evals.py
	# Runs quality evaluations on agent output
	# Run before any prompt changes

# ── Docker ────────────────────────────────────────
docker-up:
	docker compose -f docker/docker-compose.yml up -d
	# Starts all 7 Docker containers in background
	# postgres, redis, qdrant, langfuse, api, worker, beat

docker-down:
	docker compose -f docker/docker-compose.yml down
	# Stops all containers
	# Data in volumes is preserved

docker-build:
	docker compose -f docker/docker-compose.yml build
	# Rebuilds the application Docker image
	# Run after adding new dependencies

docker-logs:
	docker compose -f docker/docker-compose.yml logs -f api
	# Shows live logs from the API container
	# Ctrl+C to stop following

docker-ps:
	docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
	# Shows all running containers with their ports

# ── Database ──────────────────────────────────────
db-shell:
	docker exec -it linkedin_agent_postgres psql -U app -d linkedin_agent
	# Opens a PostgreSQL shell
	# Type SQL queries directly
	# \dt to list tables, \q to quit

db-migrate:
	uv run alembic upgrade head
	# Runs any pending database migrations
	# Run after pulling new code that adds tables

db-reset:
	docker exec -it linkedin_agent_postgres psql -U app -d linkedin_agent -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	uv run alembic upgrade head
	# ⚠️  Wipes entire database and recreates tables
	# Only use in development

# ── Cleanup ───────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
	find . -name "celerybeat-schedule*" -delete 2>/dev/null; true
	# Removes compiled Python files and Celery schedule files
	# Keeps repo clean