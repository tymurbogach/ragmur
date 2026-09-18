# Ragmur

Ragmur es una arquitectura y un prototipo para un servicio de recuperación
multi-tenant. No es una API RAG lista para producción. Todavía no ofrece
ingesta de documentos, recuperación, respuestas generadas ni endpoints públicos.

## Estado actual

La fase 0 proporciona la base del proyecto: un esqueleto FastAPI, servicios
Docker, migraciones, comprobaciones de salud, linting, tipos y CI. El proyecto
no afirma tener un flujo de recuperación utilizable hasta que la fase 1 esté
completa y evaluada.

La fuente de verdad del trabajo entregado es el [roadmap](ROADMAP.md). La
[arquitectura](ARCHITECTURE.md) y las [decisiones](DECISIONS.md) describen el
diseño objetivo. No son una lista de funcionalidades disponibles.

## Arquitectura objetivo

El sistema objetivo recibe documentos, guarda fragmentos por tenant en Qdrant
y devuelve resultados de recuperación con fuente. Una fase posterior añade
respuestas generadas y verificación de citas. El diseño exige `tenant_id` como
filtro en toda operación del almacén vectorial. Las API keys derivan el tenant.
Los clientes pueden proporcionar `owner_id` para separar a sus usuarios.

El proyecto construye la recuperación antes de la generación con LLM. Este
orden permite medir su calidad antes de que un modelo de lenguaje oculte fallos.

## Desarrollo

```bash
uv sync
docker compose up -d
uv run alembic upgrade head
uv run pytest
uv run ruff check .
uv run mypy
```

Lee [ROADMAP.md](ROADMAP.md) antes de implementar. No construyas una fase
posterior antes de que la fase actual cumpla sus criterios de cierre.

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
