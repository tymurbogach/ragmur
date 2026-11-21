# TASKS.md

> Plan único de taskflow. Trabajo en curso aquí; fases completadas resumidas. Git guarda el detalle.

## 1. Objective

- Project purpose: servicio RAG multi-tenant que ingiere documentos, los indexa en Qdrant y responde con citas. Fase 1 sin LLM: buscador con fragmentos más verificación NLI de texto enviado por el cliente.
- Audience: aplicaciones propias (portfolio, lazytripz, chatbot) y revisión humana final de fase 1.

## 2. Current state

- What works: ROADMAP 1.1-1.9 completadas (1.8 cerrada el 2026-11-18: 303 etiquetas NLI, umbrales 0.75/0.5/0.75, matriz reservada publicada); 1.7 con línea base en desarrollo. F01 protocolo NLI congelado. F07 diagnóstico automático EN+ES solo dev. F04 corpus real (88 PDF, tenant público) y copia/restauración/reindex de Skynet verificados el 2026-11-16 (`eval/skynet_reverify_2026-11-16.md`). F06 cierre fase 1 commiteado (`e3bdba1` docs, 2026-11-19; `beab7b1` suite+tabla).
- Refinamiento R (plan 2026-11-19, base `e3bdba1`): solo fase 1, sin cambios de comportamiento, sin fase 2/3, sin dependencias nuevas, sin Skynet, sin Docker/integración esta noche (pruebas para mañana por petición del usuario). 3 exploradores + 2 rondas de crítica cerradas con VERDICT OK.
- Broken or pending work: cierre de fase 1 (F06: `eval/run.py` 4 configuraciones sobre dev y reserva + tabla README). Demo pública descartada (F05e) a petición del usuario el 2026-11-19: 1.9 cierra en privado.
- D7 resuelto en `690533b`: `ROADMAP.md` 1.9 y `HANDOFF.md` reflejan el corpus y la restauración verificados.
- Auditoría de complejidad (2026-11-17, base `690533b`): 4 exploradores por área, verificación del lead y dos rondas de crítica. Aceptados: código muerto (`session_scope`, `verifier_type`), duplicación en middlewares de error y en `store.py`, scripts de eval huérfanos y documentos desfasados. Ejecución en F08 y F09; cambios de contrato en F10 opcional.
- Riesgos de exposición conocidos (evidencia del explorador, base `6cd23b2`): las claves no tienen alcance por ruta; `/docs`, `/redoc` y `/openapi.json` están siempre activos; `/ready` no exige clave y devuelve `dense-1024+nli`; los limitadores son memoria por proceso; el `Dockerfile` corre como root y usa `uv:latest`; `docker-compose.yml` de desarrollo publica PostgreSQL y Qdrant en `0.0.0.0`.
- Git branch: `main`, commits locales sobre `origin/main` (`c9abcaa` plan, `690533b` D7, `1801915` plan refinado y el commit de F05a); sin push.
- Last review: F05c `VERDICT: OK` (2026-11-17); 3 hallazgos bajos + 2 informativos; reparación de tipos aplicada. Antes: F05b `VERDICT: OK`; F09 `VERDICT: OK`; F08 `VERDICT: OK`.
- Existing local changes: ninguna (árbol limpio tras el commit de F05c). Ciclo `run all` cerrado 2026-11-17: F08, F09, F05b y F05c verificadas y commiteadas (443e3dc, a5bf48a, cfbb73b, dbc1e39) sobre 1abaf61; gate global verde en el árbol final. Sin push.
- Required test capabilities and unavailable gates: el gate compartido requiere PostgreSQL y Qdrant en Docker. Skynet (RTX 5080, `ragmur_deploy`) solo con autorización escrita por fase. Sin autorización de push, DNS, firewall, túnel ni apertura de puertos.
- Refinamiento R (2026-11-19, solo local): esta noche solo estático (`ruff`, `mypy`, `grep`, lectura). Gate completo con Docker/PostgreSQL/Qdrant (`alembic`, `pytest -q`, `check_nli_leak`, `pytest -k isolation`) queda para mañana por petición del usuario. Sin Skynet esta noche.
- Model family limits: orquestador Claude; explorador y crítica en OpenCode `muse-spark` (otra familia); revisor como subagente Claude, distinto del escritor OpenCode.

## 3. Architecture and technology

- Languages and frameworks: Python 3.12 con `uv`, FastAPI, Pydantic v2, SQLAlchemy 2.0 sobre `asyncpg`, Alembic, `pydantic-settings`.
- Relevant structure: `api/` importa de `ingestion/`, `retrieval/`, `verification/` y `llm/` (fase 2). `retrieval/store.py` es el único acceso a Qdrant. `llm/provider.py` será el único acceso a LLM.
- Important dependencies: `pypdfium2`, `python-docx`, `langchain-text-splitters` (utilidad), torch 2.12 CPU/CUDA 13, `sentence-transformers`, FastEmbed BM25, Qdrant 1.19 (`sparse modifier=IDF`, IDF acotado por tenant y `owner_id`), bge-m3, bge-reranker-v2-m3, mDeBERTa NLI `b5113eb`.
- Despliegue: `docker-compose.deploy.yml` publica solo la API en `127.0.0.1:8000`; `docker-compose.cuda.yml` añade GPU. Una sola instancia uvicorn; los limitadores no se comparten entre procesos.

## 4. Required rules

- Follow `AGENTS.md`, `ARCHITECTURE.md` and `DECISIONS.md`. No abrir fase 2 hasta cumplir el cierre de 1.9.
- Fase 1 sin LLM. `tenant_id` en toda consulta a Qdrant. Probar aislamiento por tenant y por `owner_id`.
- Only the orchestrator edits this file. Workers report through report files.
- Execution modes create one commit per verified phase.
- Remote operations require an explicit user request: push, PR, Skynet, DNS, firewall, túnel y puertos.
- `eval/results/` versiona solo resúmenes con fecha, commit, corpus, split, revisiones, configuración y hardware. Volcados por consulta fuera de Git.
- Do not commit failing required tests or force-push without authorization.

## 5. Commands

```sh
# install
uv sync --locked
# hasta F05b, los servicios de desarrollo ya solo escuchan en loopback:
POSTGRES_PORT=5432 QDRANT_HTTP_PORT=6333 QDRANT_GRPC_PORT=6334 docker compose up -d
uv run alembic upgrade head
# shared phase gate, run by the orchestrator before every phase commit
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -q
uv run python -m eval.check_nli_leak
# Refinamiento R (2026-11-19, solo local, pruebas para mañana):
# - Esta noche: solo `ruff check`, `format --check`, `mypy` y greps de alcance (qdrant_client, TODO/print, 256). Sin docker/alembic/pytest/Skynet.
# - Mañana (gate completo): `docker compose up -d` + `alembic upgrade head` + `pytest -q` + `check_nli_leak` + `pytest -k "isolation or tenant or owner"`.
# focused phase checks: see each phase
# delivery gate: shared gate + eval/run.py 4 configuraciones + nli_run dev/test congelados + smoke de despliegue
# run the app
uv run uvicorn ragmur.main:app --reload
```

- Medido el 2026-11-16 en CPU Intel Core Ultra 9 285H: `ruff check` pasa, `format --check` 154 ficheros, `mypy` 124 ficheros en 1.2 s con caché.
- `pytest` recoge 239 tests. No se ejecutó en esta planificación para no levantar contenedores con puertos. Última ejecución registrada (F04): 235 passed, 4 skipped. Tiempo sin medir.

## 6. Plan debate

- Rounds: boceto ciego más dos rondas con `critica`. Parada: la ronda 2 no añadió hallazgos bloqueantes ni mayores.
- Cambio adoptado: el tenant público dedicado es el control principal; fijar `owner_id` pasa a defensa en profundidad.
- Cambio adoptado: proxy inverso simple con lista permitida de método y ruta, sin servicio Python BFF ni reescritura de JSON.
- Cambio adoptado: tras el proxy, los limitadores de la app actúan como tope global; el límite por IP vive solo en nginx.
- Cambio adoptado: nginx y el conector de túnel son dependencias nuevas (regla 9); F05a los justifica y fija versiones.
- Cambio adoptado: dos perfiles de smoke, externo vía proxy e interno en `127.0.0.1:8000`.
- Cambio adoptado: revisar `diagnostic`, declarar CORS cerrado y usar solo consultas del split dev en la carga.
- Corrección a la crítica: la restauración de Skynet ya está verificada (F04, `6cd23b2`); el riesgo se retiró.
- Decisiones del usuario (2026-11-16): aprobadas D1-D7 según la recomendación.
  - D1: tenant público dedicado y proxy simple; sin alcance por clave ni migración.
  - D2: nginx con versión fijada.
  - D3: túnel saliente sin puerto entrante. F05a compara Cloudflare Tunnel y Tailscale Funnel; el proveedor se confirma al aprobar el diseño.
  - D4: demo solo API con ejemplos `curl`.
  - D5: `/docs`, `/redoc`, `/openapi.json` y `/ready` se bloquean solo en el proxy; sin cambios de código.
  - D6: F05a propone un objetivo p95 de `/v1/search` con rerank en RTX 5080 a partir de `benchmarks/gpu-rtx5080-2026-11-10.md`; el valor se confirma al aprobar el diseño y se mide en F05d.
  - D7: corregir `ROADMAP.md` 1.9 y `HANDOFF.md` en un commit `docs:` antes del commit de F05a.

- Debate del refinamiento R (2026-11-19, base `e3bdba1`): 3 exploradores (código/docs/calidad) + 2 rondas con `critica`. Parada: ronda 2 VERDICT OK sin bloqueantes nuevos.
  - B1 aceptado: `_tenant_filter` keyword-only pasa a cambio atómico 6 líneas + gate de aislamiento mañana.
  - B2 aceptado: R01 excluye `TASKS.md` (solo el orquestador la edita).
  - B3 aceptado: split R02a (solo comentarios) vs R02b (renames+`*`+const, gate completo mañana); esta noche cero commits.
  - M1-M7 aceptados: DECISIONS append-only, REVIEW intacto, demo-design congelado, ROADMAP con sufijo, OWNER const aislada de F10-A8, sin reword de logs, cero diff en `.github/` esta noche.
  - m1 aplicado: `SCROLL_PAGE_SIZE` y f-string de `embedder` van a R02b (código), R02a queda solo comentarios.
  - A2 (validación de `owner_id` duplicada) se descarta: los mensajes 422 difieren por ruta y forman parte del contrato.
  - B4 (`store.py`) limita los helpers a `document_ids` y parámetros dispersos; `corpus_filter` y `result_filter` quedan intactos.
  - A9 (candado global de modelos) extiende F05c y F05d con carga mixta y `INFERENCE_MAX_REQUESTS` como profundidad de cola.
  - A6 exige bytes y cabeceras idénticos por middleware; C1 actualiza el docstring que lo cita; D5 revisa todas las referencias a `HANDOFF.md`.
- Decisiones del usuario (2026-11-17): solo cambios que preservan comportamiento; retirar `HANDOFF.md` y marcar `REVIEW.md` como histórico; mover los scripts huérfanos a `eval/_archive_ai/`; orden F05a, F08, F09, F05b.
- Hallazgos descartados con motivo: B3 (DECISIONS 3.21); B7 falso (`budget - stride >= 1`); A7 (límites `gt=0`); B11 y B13 (DECISIONS 3.19, contenedor Linux); D1 (`Dockerfile:26` copia `eval`); B1 y B2 (identidad de chunks sin datos de evaluación); B6, B8 y B12 (rendimiento sin medir); A3, A4 y B14 (bajo valor, versiones fijadas); D6 (`LEARNING.md` lo usa la skill); `eval/_archive_ai` (lo usan `check_nli_leak` y tests); A5, A8 y A10 cambian el contrato (F10).

- Debate fase G (2026-11-21, base `b5847fd`): explorador (LiteLLM 1.108.2, XQuAD/MLQA/NoMIRACL, reutilización de `eval/run.py`) + crítica ronda 1 `BLOCKED` (5 bloqueantes, 4 mayores, 3 menores).
  - Aceptados B1 (tope de llamadas, sin fallback, parada en 401/402), B2 (`provider.py` obligatorio y test de imports), B3 (delta y faithful-EM; contrafactual emparejado sobre la misma caché en vez de tenant aparte, porque el IDF va por tenant), B4 (LLM solo lector; prompt, semilla y muestra congelados; partición `reserve`), M1-M4, m1-m3.
  - Ronda 2 `VERDICT: OK`: B1-B4, M1, M3 y m1-m3 resueltos; B5 rechazo justificado de forma condicional (tope duro, fail-closed, sin G05). Nuevos aceptados: N1 URL de XQuAD fijada a commit, N2 congelar temperatura y clave de caché, m1 `per_query/` fuera de Git, m2 guardia de unicidad del contrafactual, m3 G01 commitea el trío de documentos.
  - B5 aceptado en parte: G03 se parte en G03a y G03b y G05 en una subfase por dataset. Rechazado no ejecutar G04 esta noche: el usuario pidió resultados para mañana, y el piloto está limitado a 260 llamadas, es solo dev, no se publica y queda pendiente de revisión humana.

## 7. Phase plan

| Phase | Title | Status |
|-------|-------|--------|
| F01 | Protocolo NLI y congelación de dataset | Completed |
| F02 | Calibración de umbrales solo en dev | Completed 2026-11-18 |
| F03 | Evaluación ciega única en reserva (cierra 1.8) | Completed 2026-11-18 |
| F04 | Corpus real y runbook copia/restore/reindex | Completed |
| F05a | Diseño de exposición pública | Completed (diseño aprobado 2026-11-17) |
| F08 | Limpieza de código sin cambio de comportamiento | Completed |
| F09 | Limpieza de documentación y eval | Completed |
| F05b | Endurecimiento local del despliegue | Completed |
| F05c | Arnés de carga y abuso en CPU local | Completed |
| F05d | Despliegue privado en Skynet y medición GPU | Completed 2026-11-19 |
| F05e | Exposición pública de la demo | Discarded (sin demo pública, decisión usuario 2026-11-19) |
| F06 | Cierre fase 1: suite, README y marcas | Completed 2026-11-19 |
| F07 | Diagnóstico sintético EN+ES solo dev local | Completed |
| F10 | Cambios de contrato de errores (A5, A8) | Optional, sin programar |
| R01 | Refinamiento docs: contradicciones F05e | Completed |
| R02a | Refinamiento código: solo comentarios | Completed |
| R02b | Refinamiento código: renames+const (con gate) | Completed 2026-11-21 |
| R03 | Higiene: verificación estática + CI tags | Completed (solo lectura) |
| G01 | Abrir fase 2: regla 2, DECISIONS y ROADMAP (sin código) | Completed 2026-11-21 |
| G02 | 2.1a Proveedor LLM mínimo (`llm/provider.py` sobre LiteLLM) | Completed 2026-11-21 |
| G03a | 2.1b Datos, ingesta y caché de recuperación | Completed 2026-11-21 |
| G03b | 2.1b Lector, puntuación y controles | Completed 2026-11-21 |
| G04 | 2.1b Piloto: 100 preguntas XQuAD-es con controles de memoria | Pending |
| G05 | 2.1b Escalado masivo, una subfase por dataset | Pending (tras revisión humana del piloto) |

### R01: Refinamiento docs (contradicciones F05e, sin comportamiento)

- Outcome: `README:8` privado verificado + descarte 3.33; `ARCHITECTURE:5` + banner 623-631; `ROADMAP:62,66,72` sufijo sin borrado; `DECISIONS 3.26/3.30` append-only. Historia intacta (`REVIEW:62`, `demo-design` interior, `TASKS.md` del diff intactos).
- Test evidence (orquestador, árbol integrado, solo estático esta noche): `ruff check` exit 0; `format --check` exit 0 (162 ficheros); `mypy` exit 0 (128 ficheros). Sin `pytest`/Docker/Skynet por petición (mañana). Logs en `/tmp/opencode/taskflow/ragmur/R01-gate/`.
- Review verdict: VERDICT: OK (revisión R01; 1 baja + 3 informativas, ninguna bloqueante; `README:49` como mejora futura).
- Files changed: `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `DECISIONS.md`.
- Risks: ninguno abierto. Gate completo + `grep pendiente/demo` + enlaces 24/24 quedan para mañana.
- Status: Completed.

### R02a: Refinamiento código solo comentarios (cero diff ejecutable)

- Outcome: docstrings anti-regresión en 6 ficheros (`error_response` bytes F10, `storage` lock, `config` bm25, `extractors` Raises, `config` lazy torch, `deps` lifespan, `store` relectura). Prohibidos intactos (sin SCROLL, renames, `*`, const, logs, handlers, TASKS/.github).
- Test evidence (orquestador, solo estático): `ruff check` exit 0; `format --check` exit 0 (162); `mypy` exit 0 (128). Sin pytest/Docker esta noche. Logs en `/tmp/opencode/taskflow/ragmur/R02a-gate/`.
- Review verdict: VERDICT: OK (0 bloqueantes; 2 informativos sin cambio).
- Files changed: `src/ragmur/api/deps.py`, `src/ragmur/api/error_response.py`, `src/ragmur/core/config.py`, `src/ragmur/ingestion/extractors/core.py`, `src/ragmur/ingestion/storage.py`, `src/ragmur/retrieval/store.py`.
- Risks: ninguno. Gate completo mañana.
- Status: Completed.

### R02b: Renames + keyword-only + const

- Outcome: `_tenant_filter(tenant_id, *, ...)` con 4 llamadas nombradas; `first→batch_document`, `_find_label→_find_label_index`, `choose→choose_separator_end`; `OWNER_ID_MAX_LENGTH=256` (una definición en `db/models.py`, usada en API y CHECK con el mismo SQL) y `SCROLL_PAGE_SIZE=256`. Tarea del embedder no aplica (no hay cadena descriptiva). `documents.py:118-133` intacto.
- Test evidence (orquestador, 2026-11-21, PostgreSQL 17 y Qdrant 1.19 locales): `alembic` 0; `ruff` 0; `format` 162; `mypy` 128 OK; `pytest` 242 passed 4 skipped; aislamiento 13 passed 1 skipped; `check_nli_leak` verde. Logs en `/tmp/opencode/taskflow/ragmur/R02b-gate/`.
- Review verdict: auto-verificación del orquestador sobre el diff completo (41+/26-), sin cambio de comportamiento ni contrato (regla roles §review).
- Status: Completed.

### G01: Abrir fase 2 (documentación, sin código)

- Outcome: regla 2 de `AGENTS.md` reescrita (LLM solo como lector bajo prueba en `eval/`; `/search` y `/verify` sin LLM); `DECISIONS.md` 3.34 con justificación de `litellm==1.108.2` y alternativas descartadas; `ROADMAP.md` 2.1 partida en 2.1a/2.1b/2.1c sin borrar casillas y nota 2.4 actualizada.
- Test evidence (orquestador): `ruff` 0, `format` 162, `mypy` 128 OK, `check_nli_leak` verde, grep de secretos 0; diff limitado a los 3 ficheros. Logs en `/tmp/opencode/taskflow/ragmur/G01-gate/`.
- Review verdict: auto-verificación del orquestador (solo documentación, sin comportamiento).
- Status: Completed 2026-11-21.

### G02: 2.1a Proveedor LLM mínimo

- Outcome: `litellm==1.108.2` fijada; `Settings` con `llm_model`, `llm_api_key`, `llm_api_base`, `llm_timeout_seconds`, `llm_max_tokens`, `llm_max_retries` (≤5) y `llm_extra_headers` (oculto en `repr`); `llm/provider.py` con `complete()`, `Completion(attempts, latency_ms del intento con éxito)`, errores propios y red final que envuelve toda excepción de LiteLLM; reintentos solo ante timeout, 429, conexión y 5xx con backoff acotado a 10 s; mapa de costes local (`LITELLM_LOCAL_MODEL_COST_MAP`). Test estático de imports (también `importlib`/`__import__`).
- Hallazgo: LiteLLM 1.108.2 no trae `opencode_go/`. OpenCode Go va por `openai/<modelo>` + `https://opencode.ai/zen/go/v1` + cabecera `x-opencode-session`. Su política limita el uso a tráfico de agentes de código y comparte cupo de 5 h y semanal: el banco masivo usa modelo local (DECISIONS 3.34).
- Test evidence (orquestador): `alembic` 0; `ruff` 0; `format` 167; `mypy` 133 OK; `pytest` 268 passed 5 skipped; aislamiento 13+1; `check_nli_leak` verde; secretos 0; `uv sync --locked` 0. Smoke real `pytest -m llm_live`: Ollama local `ollama_chat/gemma3:4b` 1 passed (8 s, CPU); OpenCode Go `openai/glm-5.3-flash` 1 passed. Logs en `/tmp/opencode/taskflow/ragmur/G02r2-gate/`.
- Review verdict: ronda 1 "VERDICT: BLOCKED — copying `.env.example` with the empty `LLM_EXTRA_HEADERS=` stops `Settings()` from loading, and LiteLLM errors outside `litellm.APIError` (for example `NotFoundError`) reach callers unwrapped." Reparación acotada (2 rondas de escritor). Ronda 2: "VERDICT: OK — all earlier findings are fixed; the two new findings are minor test-hygiene issues and do not block the commit."
- Later work (menor): aislar de variables `LLM_*` del entorno `test_env_example_loads` y `test_no_extra_headers_by_default`; test que proteja `LITELLM_LOCAL_MODEL_COST_MAP`.
- Entorno añadido: contenedor `ragmur-ollama-eval` (`ollama/ollama:0.40.14`, `sha256:ebaef4f4…`, solo `127.0.0.1:11434`, volumen `ragmur_ollama_eval`) con `gemma3:4b` (`68ceab7e468a`).
- Status: Completed 2026-11-21.

### G03a: 2.1b Datos, ingesta y caché de recuperación

- Outcome: `eval/reader/` (`xquad`, `index`, `retrieve`, `cache`, `prepare`). XQuAD-es fijado al commit `7d30520c` con SHA-256 `dcbae93e…` y descarga atómica; partición por artículo (semilla 20261121): 36 `dev` (908 preguntas) y 12 `reserve` sellada (`allow_reserve`). Se indexan los 240 párrafos (los de reserva solo como ruido) en el tenant `ragmur.eval.reader.xquad-es` y la colección `*_eval_reader`, con 800/120 y `chunk_id` determinista. Recuperación `hybrid_rerank` con el mismo camino que `eval/run.py`. Clave de caché con dataset, commit, árbol sucio (`src`, `eval`, `pyproject.toml`, `uv.lock`), configuración, `candidates`, `top_k`, `rrf_k`, hash completo de BM25, troceado, modelos, semilla, muestra y split; `prepare` se niega con árbol sucio salvo `--allow-dirty`. Meta con hardware y latencias.
- Plan adjustment: la caché de 100 casos del piloto se genera tras este commit, como primer paso de G04 (la clave incluye el commit).
- Test evidence (orquestador): `alembic` 0; `ruff` 0; `format` 181; `mypy` 147 OK; `pytest` 314 passed 5 skipped; aislamiento 14+1 (incluye tenant señuelo en ambos sentidos y owners A↔B con Qdrant real); `tests/eval/reader` 46 passed; `check_nli_leak` verde; secretos limpio (incluye ficheros sin seguimiento). Smoke real: 240 párrafos indexados y caché de 5 casos en 4 min 40 s en CPU. Logs en `/tmp/opencode/taskflow/ragmur/G03a-final-gate/`.
- Review verdict: ronda 1 "VERDICT: OK — no blocking findings; fix majors 1-2 before generating the 100-case cache, because G04 freezes its key." Reparación acotada de M1-M3 y m1-m7. Ronda 2 "VERDICT: OK — all requested majors and minors are fixed; the new findings are minor and do not block the commit." El orquestador aplicó 3 arreglos de una línea pedidos por la ronda 2 (hash BM25 completo, rutas `:/` y ficheros de dependencias en el control de árbol sucio, mensaje de descarga).
- Later work (menor): conftest de Qdrant duplicado entre `tests/retrieval` y `tests/eval/reader`; fijar la lista de 12 artículos de reserva como regresión; el test de reutilización de `Indexer` solo busca texto.
- Status: Completed 2026-11-21.

### G03b: 2.1b Lector, puntuación y controles

- Outcome: `eval/reader/{reader,scoring,run,gitstate}.py` y prompts congelados `reader_v1.md` (`c949c3e371a7…`) y `reader_v1_nocontext.md` (`18f6a3962b0b…`), con ejemplos emparejados y contexto delimitado y escapado. Toda llamada va por `provider.complete`. `run_id` incluye caché, semilla, hash de prompts y modelo; la reanudación rechaza registros incompatibles y reintenta errores de proveedor. `--max-calls` obligatorio (cuenta intentos), parada limpia ante 401/402, rechazo de árbol sucio salvo `--allow-dirty` (resumen `-smoke`). Normalización ES `[^\w\s]|_` y coincidencia por palabra completa. EM principal; F1, `faithful_EM`, `contains_match` con tope, abstención, `parse_error` en denominadores, reparto recuperación/lector; control sin fragmentos con delta y contaminados; contrafactual emparejado con sustituto del mismo tipo y guardas; Wilson 95 %. Muestra de revisión con fragmento principal.
- Test evidence (orquestador): `alembic` 0; `ruff` 0; `format` 190; `mypy` 154 OK; `pytest` 377 passed 5 skipped; `tests/eval/reader` 109 passed; aislamiento 14+1; `check_nli_leak` verde; secretos limpio. Smoke final real (gemma3:4b, CPU, 5 casos, prompt definitivo): sin errores de parseo ni de proveedor; resúmenes en `/tmp/opencode/taskflow/ragmur/G03b-smoke/` (fuera de Git). Seco del piloto: 230 trabajos (100+100+30), 43 descartes por sustituto ya presente, sin déficit.
- Review verdict: ronda 1 "VERDICT: BLOCKED. Resume ignores prompt and model changes, so the planned smoke rerun after the prompt edit would silently reuse old answers under the new prompt SHA (B1)." Reparación acotada de B1, M1-M6, m1-m9 y decisiones P1-P3. Ronda 2 "VERDICT: OK. B1 and every earlier major are fixed, and nothing here invalidates the 230-call G04 pilot; fix N1 before freezing the prompt SHA." N1 aplicado por el orquestador (ejemplo sin contexto pasa a un hecho común; SHA fijado en test).
- Límites declarados para G04: las clases de sustituto (numérico, propio, común) son gruesas y el contrafactual será sobre todo exploratorio; `gemma3:4b` responde con frases largas pese a los ejemplos.
- Later work (menor): partir el contrafactual por `gold_kind`; clase `parse_error` en el contrafactual; registrar `substitute_source` o quitar el repliegue a otros artículos (0/30 en el piloto); registrar `timeout`, `max_tokens` y `max_retries` en el resumen.
- Status: Completed 2026-11-21.

### G04: 2.1b Piloto XQuAD-es (solo dev, sin publicar)

- Objective: primera medición real, pequeña, para revisión humana antes de escalar.
- Tasks:
  - [x] Generar con árbol limpio la caché de las 100 preguntas: `retrieval-f32e8ee3980ba2ac` (commit `e998d2c`, `dirty: false`, `hybrid_rerank`, `candidates` 30, `top_k` 5, `rrf_k` 2, 800/120; recuperación CPU p50 9,8 s, p95 11,0 s, Intel Core Ultra 9 285H).
  - Métricas fijadas antes del piloto (no se ajustan con sus resultados): EM principal; `contains_match` secundaria con tope `min(oro+3, 2×oro)` tokens; contrafactual `reads_context` (sustituto contenido, original no, con tope), `uses_memory` (original contenido), `both`, `other`; sustituto del mismo tipo (numérico, nombre propio, común).
  - [ ] Congelar antes de ejecutar: prompt v1 (SHA-256), semilla, 100 preguntas de `dev`, modelo por id, temperatura 0 y clave de la caché de recuperación. Registrarlo en esta sección. Si el humo de G03b falla, G04 no arranca.
  - [ ] Pasada con fragmentos, pasada sin fragmentos sobre las mismas 100 y 30 contrafactuales; `--max-calls 260`.
  - [ ] Resumen versionado; muestra de 30 respuestas para revisión humana en `per_query/` (fuera de Git).
- Acceptance criteria: resumen completo con etapas declaradas; revisión humana pendiente declarada; ninguna cifra en README; `reserve` sin abrir.
- Required tests: gate compartido.
- Status: Pending.

### G05: 2.1b Escalado masivo (una fase por dataset)

- G05a XQuAD-es `dev` completo; G05b NoMIRACL-es (mide abstención, no EM); G05c SciFact como lector NLI (va contra etiquetas humanas, no EM); G05d modelo local fijado (LM Studio u Ollama en la 5080).
- Status: Pending; empieza solo después de que el usuario revise el piloto. Prohibido de noche sin humano: G05, presupuestos, fallback, `PUT /v1/config/llm`, Skynet, README, abrir `reserve`.

### R03: Higiene estática + CI tags (lectura)

- Outcome: `qdrant_client` import solo en `store.py:20` (`deps.py:16` solo comentario); sin `TODO`/`print(` en `src/tests/eval/run.py`; `.gitignore` cubre `models/`, `storage/`, `.env`; nada de `models/ storage/` rastreado. CI tags (`checkout@v7`) y `gc` de `eval/.pdf_cache` quedan para mañana con red (cero diff en `.github/` esta noche).
- Test evidence (orquestador, solo lectura): `git grep qdrant_client`, `git grep TODO/print`, `git check-ignore models storage .env`. Logs en `/tmp/opencode/taskflow/ragmur/R03-gate/`. Sin `pytest`/Docker.
- Review verdict: auto-verificación sin revisor (sin cambios de comportamiento ni diff; regla roles §review).
- Files changed: ninguno (solo este registro en `TASKS.md`).
- Risks: ninguno. `actions/checkout@v7` por verificar con red mañana.
- Status: Completed.

### F02: Calibración de umbrales solo en dev

- Objective: fijar `supported/weak/contradiction` solo con dev.
- Tasks:
  - [x] Ejecutar `nli_run` solo en dev con chunks reales e inferencia real (233 pares, CPU, 2026-11-18).
  - [x] Explorar umbrales con `nli_thresholds.py`; publicar matriz dev y tasa de respaldo falso con Wilson (recall 41/74, falso apoyo 12/159).
  - [x] Congelar umbrales 0.75/0.5/0.75; no modificar la configuración sin decisión registrada.
- Dependencies: F01 y 303 pares humanos revisados (99/100/104 + 5 descartadas sustituidas) con doble anotación y adjudicación.
- Acceptance criteria: umbrales congelados con informe dev versionado (matriz 3x3, `recall_supported>=0.5`, hardware, revisión `b5113eb`, commit, hash del corpus).
- Required tests: `uv run python -m eval.nli_run --dataset eval/eu_nli_dev.yaml --split dev`, `uv run python -m eval.nli_thresholds ...`, unitarios NLI.
- Test evidence: `eval/results/nli-eu-dev-2026-11-18.json` (dev 233: apoyo 41/74, falso apoyo 12/159).
- Review verdict: 0.75 único elegible (0.85/0.90/0.95 con recall <0.5). Sin cambios de configuración.
- Files changed: `eval/eu_nli_dev.yaml`, `eval/eu_nli_test.yaml`, `eval/results/nli-eu-dev-2026-11-18.json`, `eval/results/nli-eu-test-2026-11-18.json`, `ROADMAP.md`, `README.md`, `eval/NLI.md`, `eval/EU_CORPUS.md`.
- Risks: n pequeña da Wilson ancho. La anotación humana queda fuera del alcance de los agentes.
- Status: Completed 2026-11-18.

### F03: Evaluación ciega única en reserva (cierra 1.8)

- Objective: medir una vez con parámetros congelados y cerrar la verificación.
- Tasks:
  - [x] Una sola ejecución de `nli_run` sobre test (70 pares, 2026-11-18); reserva abierta una vez.
  - [x] Publicar matriz test, respaldo falso con Wilson, `recall_supported`, hardware, revisión y commit.
  - [x] Versionar solo resúmenes; `--details` con texto va a `/tmp`.
- Dependencies: F02.
- Acceptance criteria: informe test versionado; casillas 1.8 marcadas.
- Required tests: `nli_run` sobre test una vez; gate compartido.
- Test evidence: `eval/results/nli-eu-test-2026-11-18.json` (apoyo 19/25, contradichas 19/21, falso apoyo 2/45, Wilson [1,2%, 14,8%]).
- Review verdict: Wilson superior 14,8% no permite afirmar tasa <10% en producción; limitación publicada.
- Files changed: `eval/results/nli-eu-test-2026-11-18.json`, `eval/NLI.md`.
- Risks: reabrir test para otro umbral quema la reserva.
- Status: Completed 2026-11-18

### F05a: Diseño de exposición pública

- Objective: fijar qué se expone, cómo y con qué límites antes de tocar código o Skynet. El usuario aprueba el diseño.
- Tasks:
  - [ ] Escribir `docs/demo-design.md`: modelo de amenazas, matriz de rutas y autenticación, topología y plan de vuelta atrás con interruptor de corte.
  - [ ] Rutas públicas: `GET /health`, `POST /v1/search`, `POST /v1/verify`. El proxy devuelve 404 para el resto, incluidos `/ready`, `/docs`, `/redoc`, `/openapi.json` y `/v1/documents*`.
  - [ ] Invariante: la clave de demo pertenece a un tenant que solo contiene documentos del manifiesto. Definir su comprobación SQL.
  - [ ] Clave: secreto en fichero del servidor fuera de Git; el proxy elimina `X-API-Key` del cliente e inyecta la suya. Rotación y revocación con la CLI.
  - [ ] Límites: por IP en nginx (`limit_req`, `limit_conn`, `client_max_body_size`); límite por clave e `INFERENCE_MAX_REQUESTS` como tope global. Sin `X-Forwarded-For` ni `ProxyHeaders`. Valores provisionales hasta F05d.
  - [ ] Logs: sin cuerpos, consultas ni claves; política de retención de IP. Revisar productores de `diagnostic`.
  - [ ] CORS: API sin middleware CORS; una página estática, si se elige, se sirve en el mismo origen.
  - [ ] Justificar nginx y el conector de túnel frente a alternativas (regla 9) con versiones fijadas.
  - [ ] Comparar Cloudflare Tunnel y Tailscale Funnel (D3) y proponer el objetivo p95 (D6).
  - [ ] Añadir `DECISIONS.md` 3.32 y una sección de despliegue público en `ARCHITECTURE.md`.
- Dependencies: F04. Independiente de F02 y F03.
- Acceptance criteria: diseño coherente con D1-D6; proveedor de túnel (D3) y objetivo p95 (D6) propuestos con su compromiso; el commit no cambia código. La aprobación del usuario se registra aquí con fecha antes de F05b.
- Required tests: revisión del documento contra `ARCHITECTURE.md` y `DECISIONS.md`; `uv run ruff check .` sin cambios de código.
- Test evidence: lead 2026-11-16 sobre el diff de F05a (solo documentación): `ruff check` exit 0; `format --check` 155 ficheros; `mypy` 124 OK; `check_nli_leak` exit 0; sin diff en `src`, `tests`, `eval`, `pyproject.toml`, `uv.lock`, `Dockerfile` ni compose desde `6cd23b2`; secret grep 0. `pytest` no ejecutado: sin cambios de código.
- Review verdict: ronda 1: "VERDICT: BLOCKED. Behind the tunnel, nginx sees only the connector's address, so the per-IP limit that D1 and TASKS §6 rely on becomes one global bucket. M1-M5 must also be fixed before F05b." Reparación acotada aplicada; ronda 2 confirma B1, M1, M2, M4, M5 y m1-m7 resueltos y M3 parcial. Ronda 2: "VERDICT: BLOCKED. 8 of the 10 manifest hashes in the invariant SQL (`docs/demo-design.md:183-190`) are corrupted, so the main tenant control fires on every correct tenant and cannot detect an extra document." Lead lo reprodujo: 8 hashes sin coincidencia en `eval/eu_manifest.yaml`, 6 con longitud distinta de 64. Pendientes N2 (conector frente a `host.docker.internal:8000` sin verificar), N3-N6 menores. Reintento acotado (2026-11-17, escritor nuevo, base `1801915`): hashes literales sustituidos por un contrato de generación en F05b con `:expected_hashes`, autocomprobación de 10 hashes de 64 hex y conteo exacto; fuente de los 10 documentos `eval/skynet_public_corpus_2026-11-13.md:58-71`; N2-N6 resueltos. Ronda 3: "VERDICT: OK". El revisor comprobó los 10 `document_id` contra `eval/eu_manifest.yaml`, las columnas de `api_keys` y que D1-D6, DECISIONS 3.32 y ARCHITECTURE concuerdan. Sus 9 hallazgos menores pasan a F05b.
- Test evidence (reintento): lead 2026-11-17 sobre el árbol integrado: `ruff check` exit 0; `format --check` exit 0, 155 ficheros; `mypy` exit 0, 124 ficheros; `check_nli_leak` exit 0; sin diff en código, tests, eval, dependencias, `Dockerfile` ni compose desde `6cd23b2`; `grep -nE '[0-9a-f]{40,}' docs/demo-design.md` sin resultados; secret grep 0. `pytest` no ejecutado: sin cambios de código.
- Files changed: `docs/demo-design.md`, `DECISIONS.md`, `ARCHITECTURE.md`, `TASKS.md`.
- Risks: ocultar botones no es un control. Si la clave llega al navegador, el modelo `owner_id` deja de proteger.
- Status: Completed. Diseño aprobado por el usuario el 2026-11-17. Commit `1abaf61` (`F05a: design public demo exposure`). F05b desbloqueada.
- Recomendaciones para el reintento (guardadas 2026-11-16, aplicadas el 2026-11-17):
  - Quitar los hashes literales del documento. La SQL del invariante se genera desde `eval/eu_manifest.yaml` con un script de F05b; la copia manual los corrompió.
  - N2: marcar "por verificar" que el conector no alcanza la API; smoke dentro del contenedor del conector: `api:8000`, `qdrant:6333`, `postgres:5432` y `host.docker.internal:8000` deben fallar.
  - N3: IP fija del conector (`ipv4_address`) como único `set_real_ip_from`, o prohibir el enlace de nginx al host mientras corre el túnel.
  - N4: Skynet es Windows: secreto como Docker secret o volumen con modo fijado dentro del contenedor; rotación de logs dentro de un contenedor o con el driver `local`.
  - N5: topología de Funnel (host, `proxy_protocol`) o declarar que la sección 4 solo aplica a Cloudflare.
  - N6: redacción (CLI, "fuera de Git" repetido, línea 58, origen del 404 en `POST /v1/search`); `include` de la clave dentro de cada una de las tres `location` exactas.
  - Revisión nueva tras el reintento; si sale limpia, presentar el diseño al usuario para aprobarlo.

### F08: Limpieza de código sin cambio de comportamiento

- Outcome: A1 (`session_scope`), B9 (`verifier_type`) y su import eliminados; helper `send_error` compartido por los tres middlewares de límite (bytes y cabeceras idénticos); helpers `_require_document_ids`, `_sparse_vector` y `_idf_search_params` en `store.py` con `corpus_filter` y `result_filter` intactos; nuevo `tests/retrieval/test_store_scope.py` blinda `_checked_payload`/`retrieve_points`.
- Test evidence (orquestador, árbol integrado, PostgreSQL 17 y Qdrant propios en `127.0.0.1:5433/6333-6334`; `alembic` con `API_KEY_HMAC_SECRET=test-only-hmac-secret` solo en entorno): `ruff check` exit 0; `format --check` exit 0; `mypy` exit 0 (126 ficheros); `alembic upgrade head` exit 0; `pytest` 237 passed, 4 skipped; subset límites+hybrid 9 passed; `-k "isolation or tenant or owner"` 13 passed, 1 skipped; `check_nli_leak` verde; `git grep session_scope|verifier_type` en `src tests eval` vacío. Logs en `/tmp/opencode/taskflow/ragmur/F08-gate/`.
- Review verdict: "VERDICT: OK — el diff cumple todos los criterios de F08 sin cambios de comportamiento ni de contrato." (revisión 2026-11-17; 5 observaciones menores no bloqueantes).
- Files changed: `src/ragmur/db/session.py`, `src/ragmur/verification/nli.py`, `src/ragmur/api/error_response.py` (nuevo), `src/ragmur/api/{json_limit,upload_limit,inference_limit}.py`, `src/ragmur/retrieval/store.py`, `tests/api/test_{json,upload,inference}_limit.py`, `tests/retrieval/test_store_scope.py` (nuevo).
- Risks: ninguno abierto. `error_response.py` conserva a propósito dos serializaciones históricas; unificarlas cambiaría el contrato (F10).
- Status: Completed.

### F09: Limpieza de documentación y eval

- Outcome: C1/C2 archivados en `eval/_archive_ai/` (con nota en su `README` y docstring C1); C3/C4 notas y docstrings cruzados; D2/D8 marcas fase 2 y `EMBEDDING_DEVICE` en `README.md`; D3/D12 árbol fase 1 vs fase 2 en `ARCHITECTURE.md`; D4 encabezado histórico en `REVIEW.md` (base `58cd7ee`); D5 `HANDOFF.md` borrado con datos Skynet vigentes relocalizados (`ragmur_deploy`, nota de credenciales SSH, overlay CUDA) en `README.md` y `docs/runbook-backup-restore.md`; D11 borrador listado en `eval/EU_CORPUS.md`. Sin cambios en `src/`, `tests/`, dependencias ni `TODO`s. Menciones restantes de `HANDOFF` en `TASKS.md` solo históricas (§2 D7, §6 D7, esta entrada).
- Test evidence (orquestador, árbol integrado, PostgreSQL 17 y Qdrant propios en `127.0.0.1:5433/6333-6334`): `ruff check` exit 0; `format --check` exit 0 (156); `mypy` exit 0 (126); `alembic upgrade head` exit 0; `pytest` 237 passed, 4 skipped; `check_nli_leak` verde; `git grep` rutas movidas solo en `_archive_ai`/resultados/docstring C1; `git grep -i handoff` fuera de `TASKS.md` vacío; enlaces relativos 24/24 OK. Logs en `/tmp/opencode/taskflow/ragmur/F09-gate/`.
- Review verdict: "VERDICT: OK — F09 meets all acceptance criteria with zero behavior/contract change; D5 Skynet data preserved; gate outputs consistent." (revisión 2026-11-17; 2 hallazgos bajos + 1 informativo, todos en artefactos archivados).
- Files changed: `ARCHITECTURE.md`, `README.md`, `REVIEW.md`, `HANDOFF.md` (borrado), `docs/runbook-backup-restore.md`, `eval/NLI.md`, `eval/EU_CORPUS.md`, `eval/metrics.py`, `eval/scifact_metrics.py`, `eval/numeric_signal_stress_eval.py`, `eval/_archive_ai/` (2 scripts movidos + `README.md`).
- Risks: ninguno abierto. Pregunta del writer resuelta por el revisor: 12 entradas del borrador vs 11 IDs `euh2-*` ejecutados no es contradicción (`EU_CORPUS.md:28-30` lo declara borrador).
- Status: Completed.

### F05b: Endurecimiento local del despliegue

- Outcome: `Dockerfile` con usuario `ragmur` UID 10000 e imagen `uv` fijada+digest (`HEALTHCHECK` intacto); `docker-compose.yml` con PG y Qdrant solo en `127.0.0.1`; `docker-compose.demo.yml` (redes `edge`/`internal`, conector con `ipv4_address` fija y perfil `tunnel`, nginx sin puertos, clave por `include` de secreto Compose, logs con rotación); `deploy/nginx/nginx.conf` (3 ubicaciones exactas + 404 resto, borrado de cabeceras de IP, `real_ip` acotada, 429 con `Retry-After`, `client_max_body_size 64k`, logs sin cuerpos/consultas/claves); `deploy/smoke_demo.sh` (28 comprobaciones); `eval/check_demo_invariant.py` (genera 3 consultas desde los 10 ids + hashes, exige 10 hashes 64hex y `status='indexed'`); test `diagnostic` (4 tests, sin fugas de texto); redacción 1/2/4/7 de F05a aplicada en `docs/demo-design.md`. Sin cambios en `src/`, sin dependencias nuevas, sin secretos en Git.
- Test evidence (orquestador, árbol integrado): `ruff check`/`format` 0; `mypy` 0 (128); `config` deploy+demo 0 puertos y 0 `0.0.0.0`; `alembic` 0; `pytest` 241 passed, 4 skipped (diagnostic 4/4; aislamiento 13+1); `check_nli_leak` verde; secret scan sin secretos nuevos; invariante generación OK + `--check` verde (`0/10/1`) y rojo tras revocar en BD desechable; `nginx -t` OK; smoke re-ejecutado 28/28 con revocación 401 final; sonda edge (DNS irresoluble + L3 con timeout 4s y controles); 0 fugas en cuerpos/cabeceras/logs; pila demolida con `down -v`. Incidencias resueltas sin tocar el repo: `model_data` precalentado necesitó `chown 10000`; la clave inyectada debe ser clave real emitida. Logs en `/tmp/opencode/taskflow/ragmur/F05b-gate/`.
- Review verdict: "VERDICT: OK — el diff cumple todos los criterios de F05b con evidencia verde completa y sin defectos bloqueantes." (revisión 2026-11-17; 1 hallazgo bajo + 2 informativos). Hallazgo bajo aplicado por el orquestador: ejemplo de §5 actualizado (el prefijo `127.0.0.1:` ya vive en `docker-compose.yml`).
- Files changed: `Dockerfile`, `docker-compose.yml`, `docker-compose.demo.yml` (nuevo), `deploy/nginx/nginx.conf` (nuevo), `deploy/smoke_demo.sh` (nuevo), `eval/check_demo_invariant.py` (nuevo), `tests/ingestion/test_diagnostic_no_text.py` (nuevo), `docs/demo-design.md`, `TASKS.md`.
- Risks: F05d debe precalentar `model_data` + `chown` al UID 10000 antes del primer arranque; D3 (ráfaga por IP de visitante) exige túnel real; `Retry-After: 60 always` también en 200 (ruido inofensivo, diseño §7).
- Status: Completed.

### F05c: Arnés de carga y abuso en CPU local

- Outcome: `benchmarks/load.py` (asyncio+httpx+stdlib; perfiles search/mixed; calentamiento, barrido, recuperación, sonda de aislamiento; rechaza reservas; resumen JSON+Markdown) + `benchmarks/test_load.py` (12 tests) + `benchmarks/load-cpu-2026-11-17.md` (CPU Intel Ultra 9 285H, commit `cfbb73b`). Solo 3 ficheros nuevos; sin cambios en `src/`, configuración, límites ni dependencias (httpx/pyyaml ya existían).
- Test evidence (orquestador, árbol integrado): `ruff check`/`format` 0; `mypy` 0 (128; más `mypy benchmarks/load.py` 0 tras reparar 6 avisos fuera del gate); harness 12/12; `pytest` 241 passed, 4 skipped; `check_nli_leak` verde; ejecución viva reducida en pila efímera demolida: 19×200 + 1 error de conexión en calentamiento, `saw_500` False, `capacity_wait` y aislamiento OK. Escritor: tramos search/mixto/interno, 0×500 en 300+ peticiones, 429 nginx y app separados de 503 app, recuperación 200, alien owner 0 resultados. Logs en `/tmp/opencode/taskflow/ragmur/F05c-gate/`.
- Review verdict: "VERDICT: OK — el diff cumple todos los criterios de F05c con evidencia verde completa y sin defectos bloqueantes" (revisión 2026-11-17; 3 hallazgos bajos + 2 informativos, ninguno cambia el servicio). Ronda de reparación aplicada: tipos de `load.py` (mypy limpio), sin cambio de comportamiento.
- Files changed: `benchmarks/load.py`, `benchmarks/test_load.py`, `benchmarks/load-cpu-2026-11-17.md` (nuevos), `TASKS.md`.
- Risks: CPU sin valor público (F05d mide en RTX 5080); verify no expone `timings_ms` (capacity_wait de verify no observable; requiere cambio en `src/` si F05d lo necesita); 503 solo visible en tramo interno (F05d decide tasas con ese dato).
- Status: Completed.

### F05d: Despliegue privado en Skynet y medición GPU

- Objective: llevar el endurecimiento a `ragmur_deploy` y fijar límites con datos de RTX 5080, sin exposición pública.
- Tasks:
  - [x] Copia previa según `docs/runbook-backup-restore.md` y punto de restauración registrado.
  - [x] Actualizar `ragmur_deploy` con la imagen endurecida; `chown` de volúmenes al UID nuevo; API en `127.0.0.1` sin proxy (demo pública descartada; proxy validado 28/28 en F05b).
  - [x] Smoke interno desde Skynet; `pytest -k "isolation or tenant or owner"`; invariante del tenant de demo.
  - [x] Barrido GPU con el arnés de F05c, incluido el perfil mixto; `INFERENCE_MAX_REQUESTS` como profundidad de cola, límite por clave y tasas de nginx por ruta según los datos. Los valores por defecto del código no cambian.
- Dependencies: F05c y autorización escrita A (acceso a Skynet y actualización de `ragmur_deploy`, concedida 2026-11-19).
- Acceptance criteria: smoke verde en Skynet; p50 y p95 por concurrencia en RTX 5080 con hardware; límites justificados por la tabla; restauración posible desde la copia previa.
- Required tests: `ssh -o BatchMode=yes skynet-ts docker ps`; smoke interno; barrido de carga.
- Test evidence (2026-11-19): copia `ragmur-backup-skynet-2026-11-19` en Skynet (dump 17.277 B/32 entradas, originales 73,7 MB con hash idéntico al 2026-11-13); imagen endurecida construida en ThinkPad y cargada por LAN (build por SSH imposible por el gestor de credenciales de Docker Desktop, ver runbook); `whoami=ragmur`, `/health`+`/ready` 200 (`dense-1024+nli`), 88 `indexed`; invariante `0/10/1` con clave temporal dedicada (revocada tras medir); search GPU conc=1 p50 251/p95 293, conc=4 771/859, conc=16/32 saturación con cola ~2,5 s sin 500; verify 143 ms `supported` 0,999; mixto limitado por cuota 60/min (429 con `Retry-After`, 0×500); `pytest -k "isolation or tenant or owner"` 13 passed 1 skipped en pila local; informe `benchmarks/load-gpu-2026-11-19.md`.
- Review verdict: none (pendiente de revisión).
- Files changed: `benchmarks/load-gpu-2026-11-19.md` (nuevo), `docs/demo-design.md` (valores finales), `DECISIONS.md` (3.33), `TASKS.md`, `ROADMAP.md`, `docs/runbook-backup-restore.md` (lección SSH).
- Risks: imagen vieja sin etiqueta (8,5 GB) conservada en Skynet como repliegue hasta F06; secretos de despliegue vistos en logs de la sesión (rotar `POSTGRES_PASSWORD` y `API_KEY_HMAC_SECRET` con reemisión de claves).
- Status: Completed 2026-11-19.

### F05e: Exposición pública de la demo

- Objective: abrir la demo por la vía aprobada y comprobarla desde fuera.
- Tasks:
  - [ ] Aplicar la vía de exposición de D3 (túnel saliente o reenvío de puerto con TLS).
  - [ ] Smoke externo desde fuera de la red; probar el interruptor de corte.
  - [ ] Vigilar 429, 503 y errores durante 24 h.
- Dependencies: F05d y autorización escrita B (DNS, TLS, túnel o firewall).
- Acceptance criteria: la URL pública solo responde las rutas permitidas; un escaneo externo solo muestra 443; corte comprobado; casillas de demo de 1.9 listas para F06.
- Required tests: smoke externo; escaneo de puertos externo; prueba de corte.
- Test evidence: no run (fase descartada).
- Review verdict: none.
- Files changed: `TASKS.md`, `ROADMAP.md`, `DECISIONS.md` (3.33).
- Risks: ninguno (no se expone nada).
- Status: Discarded 2026-11-19 (decisión del usuario: sin demo pública).

### F10: Cambios de contrato de errores (opcional)

- Objective: decidir si se corrigen dos respuestas que hoy confunden al cliente. No se programa sin decisión expresa del usuario.
- Tasks:
  - [ ] A5: `search.py:41-66` y `verify.py:49-99` convierten cualquier excepción en 503; un error de programación debería dar 500.
  - [ ] A8: `documents.py:118-133` devuelve 200 duplicado si el original está en `pending` o `processing`; podría dar 409 con `Retry-After`.
- Dependencies: decisión del usuario; actualizar `ARCHITECTURE.md` en el mismo commit.
- Status: Optional, sin programar.

### F06: Cierre fase 1: suite, README y marcas

- Objective: declarar la fase 1 cerrada solo si todo lo anterior está verde.
- Tasks:
  - [x] Gate compartido completo en el árbol integrado más `alembic upgrade head`.
  - [x] `eval/run.py` con 4 configuraciones (densa, BM25, híbrida, híbrida con rerank) sobre dev y reserva, con resúmenes versionados.
  - [x] Tabla final en README: recall@10 x4, MRR/nDCG híbrida con y sin rerank, latencias p50/p95 con hardware, matriz NLI y respaldo falso con N y Wilson, fecha, commit, corpus y split.
  - [x] Marcar las casillas de 1.8 y 1.9 en `ROADMAP.md` en el commit de cierre.
- Dependencies: F03, F04 y F05d en privado (F05e descartada 2026-11-19).
- Acceptance criteria: criterios 1.1-1.8 cumplidos; suite con aislamiento por tenant y `owner_id` verde; corpus real desplegado y medido en privado; README con cifras fechadas.
- Required tests: gate compartido y gate de entrega.
- Test evidence (2026-11-19, commit `beab7b1`): `ruff check`/`format`/`mypy` (128) limpios; `alembic upgrade head` OK; `pytest` 242 passed 4 skipped; `check_nli_leak` verde; `eval/run.py` dev (10+4, recall 1.0 x4, rerank MRR/nDCG 1.0, p95 CPU 19 s) y test (10+3, rerank 1.0/1.0, p95 CPU 18,7 s) en `eval/results/summary-2026-11-19T*-{dev,test}.json`; tabla README verificada 8/8 contra los JSON por script.
- Review verdict: auto-verificación con comprobación programática (sin revisor independiente; cambio limitado a resúmenes generados + tabla + marcas).
- Files changed: `README.md`, `ROADMAP.md`, `TASKS.md`, `eval/results/summary-2026-11-19T*-dev.json`, `eval/results/summary-2026-11-19T*-test.json`.
- Risks: la muestra de 1.7 es poco discriminativa (recall 1.0); declararlo y no afirmar significación sin incertidumbre.
- Status: Completed 2026-11-19

## 8. Completed phases

| Phase | Outcome | Verification | Commit |
|-------|---------|--------------|--------|
| — | ROADMAP 1.1-1.6 y línea base de 1.7 | Ver `ROADMAP.md` y `DECISIONS.md` | — |
| F01 | Protocolo NLI congelado; reservas quemadas declaradas; dev y test vacíos | `ruff` pass, `mypy` 123 OK, 20 tests NLI passed, `check_nli_leak` verde | F01: freeze NLI dataset protocol and anti-leak checks |
| F07 | Diagnóstico automático 300 ES + 300 EN solo dev; no calibra | `ruff` pass, `mypy` 124 OK, `pytest tests/eval/` verde; ES recall 0.18, EN 0.26, respaldo falso 0.03 Wilson [0.0138, 0.0639] | F07: add local EN-ES diagnostic NLI datasets |
| F04 | Manifiesto del corpus, triage de `eval/`, runbook y copia/restore/reindex de Skynet en entorno aislado | Skynet: `indexed\|88`, `sha256sum -c` OK, `Reindexed 88`, 1712 puntos, `hybrid_search` top-5 idéntico, isolation 13 passed 1 skipped. Lead: `ruff` pass, `mypy` 124 OK, `pytest` 235 passed 4 skipped, secret scan 0 | F04: verify corpus backup restore reindex against Skynet |
| F08 | Limpieza de código muerto y duplicación sin cambio de comportamiento | `ruff`/`mypy` pass, `pytest` 237 passed 4 skipped, aislamiento 13+1, `check_nli_leak` verde, `VERDICT: OK` | F08: remove dead code and share error/store helpers |
| F09 | Limpieza de documentación y eval, sin cambio de comportamiento | `ruff`/`mypy` pass, `pytest` 237 passed 4 skipped, `check_nli_leak` verde, enlaces 24/24, `HANDOFF` fuera de `TASKS.md` vacío, `VERDICT: OK` | F09: archive orphan eval scripts and update docs |
| F05b | Endurecimiento local del despliegue (proxy, invariante, smoke 28/28) | gate verde, `config` 0 puertos, invariante `0/10/1` + rojo tras revocar, smoke 28/28, sonda edge DNS+L3, 0 fugas, `VERDICT: OK` | F05b: harden local deploy with proxy and invariant |
| F05c | Arnés de carga (asyncio+httpx, perfiles search/mixed, resumen CPU) | harness 12/12, `pytest` 241+4, ejecución viva 19×200 + 0×500, `mypy` benchmarks limpio, `VERDICT: OK` | F05c: add CPU load and abuse harness |

## 9. Recommended next action

- Next action (2026-11-19 noche, automático): R01 Completed (`dec6e12`), R02a Completed (`dd0eda6`), R03 Completed (solo lectura). Mañana con Docker: `run R02b` (renames+`*`+const, gate aislamiento) + gate completo (`pytest -q`, `alembic`, `check_nli_leak`) + CI tags con red. Sin push esta noche.
- Next phase: R02b (Pending, para mañana).
- Resume command: `/taskflow run R02b` (mañana, con Docker disponible)
- Recommended effort: low (R01+R02a), medium (R02b con aislamiento)
- Autorizaciones: ninguna nueva. Sin push, sin Skynet, sin Docker esta noche por petición del usuario. Base `e3bdba1` (ahead 1 sobre `origin/main`).
