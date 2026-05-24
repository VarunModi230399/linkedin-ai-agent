# LinkedIn AI Agent — Architecture

## System Overview

A production-grade AI agent that generates, critiques, and publishes
LinkedIn posts to a Company Page using LangGraph and OpenAI.

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Agent framework | LangGraph | Stateful directed graph |
| LLM | GPT-4o / GPT-4o-mini | Content generation |
| Vector DB | Qdrant | RAG knowledge base |
| Database | PostgreSQL | Posts, metrics, checkpoints |
| Task queue | Celery + Redis | Background jobs |
| API | FastAPI | Approval UI backend |
| Observability | Langfuse | LLM tracing |
| Container | Docker | All services |

## Agent Flow

pick_pillar → generate_ideas → select_idea → research →
draft → critique → refine (max 2x) → human_approval →
schedule → publish → track

## Key Design Decisions

- GPT-4o for draft/critique (quality-critical)
- GPT-4o-mini for ideation/research (cost-optimised)
- PostgreSQL checkpointer for crash recovery
- Human approval gate mandatory for first 3 months
- Option-B citation style (natural source references)