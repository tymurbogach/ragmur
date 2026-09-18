# Ragmur

Ragmur is an architecture and prototype for a multi-tenant retrieval service.
It is not a production-ready RAG API and it does not yet provide document
ingestion, retrieval, generated answers, or public endpoints.

## Current status

Phase 0 provides the project foundation: a FastAPI skeleton, Docker services,
database migrations, health checks, linting, type checks, and CI. The project
does not claim a usable retrieval workflow until Phase 1 is complete and
evaluated.

The source of truth for delivered work is the [roadmap](ROADMAP.md). The
[architecture](ARCHITECTURE.md) and [decisions](DECISIONS.md) describe the
target design. They are not a list of available features.

## Target architecture

The intended system receives documents, stores tenant-scoped chunks in Qdrant,
and returns source-grounded retrieval results. A later phase adds generated
answers and citation verification. The design keeps `tenant_id` as a required
filter for every vector-store operation. API keys derive the tenant. Clients
may provide `owner_id` to separate their own users.

The project deliberately builds retrieval before LLM generation. This order
makes the retrieval quality measurable before a language model can hide its
failures.

## Development

```bash
uv sync
docker compose up -d
uv run alembic upgrade head
uv run pytest
uv run ruff check .
uv run mypy
```

Read [ROADMAP.md](ROADMAP.md) before implementation. Do not build a later
phase before the current phase meets its closure criteria.

## Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.12, `uv` |
| API | FastAPI, Pydantic v2, Uvicorn |
| Base vectorial | Qdrant (vectores densos + dispersos, fusión RRF, multi-tenancy) |
| Metadatos | PostgreSQL, SQLAlchemy 2.0 sobre `asyncpg`, migraciones con Alembic |
| Ingesta | `pypdfium2` (PDF), `python-docx`, texto plano y Markdown |
| Embeddings | bge-m3 (multilingüe, 1024 dim) |
| Léxica | BM25 vía FastEmbed (vectores dispersos, IDF calculado por Qdrant y acotado al tenant) |
| Reranking | bge-reranker-v2-m3 (cross-encoder) |
| Verificación | mDeBERTa-v3-base-xnli-multilingual-nli-2mil7 (NLI) |
| Capa LLM | LiteLLM sobre Ollama, OpenAI, Anthropic, Gemini |
| Evaluación | Golden set propio; RAGAS a partir de la fase 2 |
| Despliegue | Docker Compose |

Sin frameworks RAG de alto nivel: el pipeline está escrito a mano. Única excepción, `langchain-text-splitters` como utilidad aislada de troceado.

## Documentación

- [`ROADMAP.md`](ROADMAP.md) — fases, tareas y criterios de cierre
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — contratos, modelo de datos y decisiones técnicas
- [`DECISIONS.md`](DECISIONS.md) — por qué el sistema es así, con las alternativas descartadas
- [`CLAUDE.md`](CLAUDE.md) — reglas para agentes de codificación

## Licencia

MIT
