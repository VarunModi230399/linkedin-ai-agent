.PHONY: install dev test lint format docker-up docker-down

install:
	uv sync

dev:
	uvicorn src.api.app:app --reload --port 8000

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/
	mypy src/

format:
	ruff format src/ tests/

docker-up:
	docker compose -f docker/docker-compose.yml up --build

docker-down:
	docker compose -f docker/docker-compose.yml down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete