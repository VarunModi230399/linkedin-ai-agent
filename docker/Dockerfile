# docker/Dockerfile
#
# Multi-stage build for the LinkedIn AI Agent.
# Stage 1: install dependencies with uv
# Stage 2: lean production image with non-root user

# ── Stage 1: Builder ──────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install all dependencies into .venv
RUN uv sync --frozen --no-dev --no-editable

# ── Stage 2: Final ────────────────────────────────
FROM python:3.12-slim AS final

WORKDIR /app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY langgraph.json ./

# Set ownership
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Default command — overridden per service in docker-compose
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]