# LinkedIn AI Agent

Production-grade AI agent that generates and publishes LinkedIn posts
to a Company Page using LangGraph, GPT-4o, and RAG.

## Quick Start

\```bash
git clone https://github.com/VarunModi230399/linkedin-ai-agent
cd linkedin-ai-agent
cp .env.example .env
# Fill in your API keys in .env

docker compose -f docker/docker-compose.yml up -d
uv run uvicorn src.api.app:app --reload --port 8000
uv run python scripts/run_agent.py
\```

## Architecture

11-node LangGraph pipeline: ideation → research → draft → 
critique → refine → human approval → publish → analytics

## Stack

Python 3.12 · LangGraph · GPT-4o · Qdrant · PostgreSQL · 
Redis · Celery · FastAPI · Docker · Langfuse

## Status

- Agent pipeline: ✅ Complete
- Approval UI: ✅ Complete  
- LinkedIn publishing: ⏳ Pending MDP approval
- Deployment: Local Docker