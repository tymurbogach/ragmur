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
respuestas generadas. La fase 1 ya contempla verificación de texto enviado por el cliente.
El diseño exige `tenant_id` como
filtro en toda operación del almacén vectorial. Las API keys derivan el tenant.
Los clientes pueden proporcionar `owner_id` para separar a sus usuarios.

El proyecto construye la recuperación antes de la generación con LLM. Este
orden permite medir su calidad antes de que un modelo de lenguaje oculte fallos.

## Desarrollo

Si no existe `.env`, copia `.env.example` y ajusta sus valores antes de ejecutar estos comandos.
El Compose actual es para desarrollo local; sus credenciales y puertos publicados no constituyen una configuración de despliegue.

```bash
uv sync --locked
docker compose up -d
uv run alembic upgrade head
uv run pytest
uv run ruff check .
uv run mypy
uv run uvicorn ragmur.main:app --reload
```

Lee [ROADMAP.md](ROADMAP.md) antes de implementar. No construyas una fase
posterior antes de que la fase actual cumpla sus criterios de cierre.

La [revisión previa](REVIEW.md) recoge los ajustes de diseño y las correcciones pendientes del esqueleto.
La siguiente tarea funcional es 1.1, autenticación y tenants.

Si mueves el repositorio, crea un entorno virtual nuevo y ejecuta `uv sync --locked`; sus ejecutables pueden conservar la ruta anterior.
En fase 0, `/health` comprueba PostgreSQL y Qdrant. `/ready`, la ingesta y la búsqueda todavía no están implementados.

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

El pipeline previsto usa componentes explícitos, sin frameworks RAG de alto nivel.
Se admite `langchain-text-splitters` como utilidad aislada; las dependencias pendientes se aprueban al abrir su tarea.

## Documentación

- [`ROADMAP.md`](ROADMAP.md) — fases, tareas y criterios de cierre
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — contratos, modelo de datos y decisiones técnicas
- [`DECISIONS.md`](DECISIONS.md) — por qué el sistema es así, con las alternativas descartadas
- [`AGENTS.md`](AGENTS.md): reglas para agentes de codificación
- [`REVIEW.md`](REVIEW.md): revisión previa, pruebas y puntos pendientes

## Licencia

MIT es la licencia prevista. Falta incorporar el fichero `LICENSE` con su titular antes de publicar una versión.
