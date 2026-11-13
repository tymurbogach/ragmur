# TASKS.md

> Plan único de taskflow. Resúmenes breves; Git guarda el detalle.

## 1. Objective

- Project purpose: servicio RAG multi-tenant que ingiere documentos, los indexa en Qdrant y responde con citas. Fase 1 sin LLM: buscador con fragmentos más verificación NLI de texto enviado por el cliente.
- Audience: aplicaciones propias (portfolio, lazytripz, chatbot) y revisión humana final de fase 1.

## 2. Current state

- What works: 1.1-1.6 completadas. 1.7 línea base en desarrollo. F01 protocolo congelado. F07 diagnóstico auto dev-local: manifiesto 35 docs (26 dev/9 test, IDs `eua-*`), 300 ES + 300 EN dev (100/100/100, `gold:false`), anti-fuga verde, NLI CPU ES recall 0.18 / EN 0.26, falso respaldo 0.03 Wilson [0.0138,0.0639]. Umbrales siguen provisionales 0.75/0.5/0.75; nada calibra ni cierra 1.8.
- Broken or pending work: faltan 300 pares humanos (0/300); F02 sigue BLOCKED. 1.9 sin corpus versionado, sin demo pública, sin endurecimiento, sin runbook versionado.
- Git branch: `main`, ahead 59 sobre `origin/main` (sin push autorizado).
- Last review: revisión F07 2026-11-13: 16 tests en fichero (12 ejecutan comportamiento, 2 estáticos); sin bloqueos para diagnóstico; 3 hallazgos bajos (umbral guarda 0.2/0.3, código muerto weak, anti-test frágil) anotados sin reparar en fase.
- Existing local changes tras F07: quedan `M README.md, ROADMAP.md` ajenos y `??` viejos en `eval/` (se trian en F04).
- Required test capabilities and unavailable gates: solo CPU local Intel Core Ultra 9 285H para este ciclo; nada de Skynet/5080. Docker PG+Qdrant locales, modelos fijados (bge-m3, reranker `953dc6f`, NLI `b5113eb`). Sin exposición pública autorizada. Sin autorización de push/demo/DNS/firewall.

## 3. Architecture and technology

- Languages and frameworks: Python 3.12 `uv`, FastAPI, Pydantic v2, SQLAlchemy 2.0 `asyncpg`, Alembic, `pydantic-settings`.
- Relevant structure: `api/` -> `ingestion/`, `retrieval/`, `verification/`, `llm/` (fase 2); `retrieval/store.py` único acceso Qdrant (`tenant_id` primero salvo `create_client`/`ping`); `llm/provider.py` único acceso LLM (fase 2).
- Important dependencies: `pypdfium2`, `python-docx`, `langchain-text-splitters` (utilidad), torch 2.12 CPU/CUDA13, `sentence-transformers`, `FastEmbed` BM25 (`language` explícito), Qdrant 1.19 (`sparse modifier=IDF`, IDF acotado por tenant+owner), bge-reranker-v2-m3, `mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`.

## 4. Required rules

- Follow `AGENTS.md`, `ARCHITECTURE.md`, `DECISIONS.md`; no abrir fase 2 hasta cerrar 1.1-1.8 más suite, despliegue con corpus real, demo y README con cifras.
- Fase 1 sin LLM. `tenant_id` en toda consulta Qdrant; `owner_id` subdivide. Aislamiento probado por tenant y por `owner_id`.
- Execution modes create one commit per verified phase. No push, PR, publicación, despliegue ni apertura de puertos sin petición explícita.
- `eval/results/` solo resúmenes versionados con fecha, commit, corpus, split, revisiones, config, hardware/concurrencia. Volcados por consulta a `/tmp`, fuera de Git.
- Do not commit failing required tests.

## 5. Commands

```sh
uv sync --locked
docker compose up -d
uv run alembic upgrade head
uv run uvicorn ragmur.main:app --reload
# shared phase gate (lead, árbol integrado, antes de cada commit de fase):
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -q
# focused phase checks: ver cada fase
# delivery gate: shared gate + eval/run.py 4 configs + nli_run/nli_thresholds dev+test + comprobaciones Skynet BatchMode
```

Shared gate runtime aún no medido en este plan; registrar tiempo al ejecutar. Requiere Docker PG+Qdrant reales; inferencia real (no mocks) para aceptación.

## 6. Phase plan

| Phase | Title | Status |
|-------|-------|--------|
| F01 | Protocolo NLI y congelación de dataset | Completed |
| F02 | Calibración de umbrales solo en dev | BLOCKED |
| F03 | Evaluación ciega única en reserva (cierra 1.8) | Pending |
| F04 | Corpus real y runbook copia/restore/reindex | Pending |
| F05 | Diseño proxy demo y endurecimiento | Pending |
| F06 | Cierre fase 1: suite, README y marcas | Pending |
| F07 | Diagnóstico sintético EN+ES solo dev local | Completed |

### F02: Calibración de umbrales solo en dev

- Objective: fijar `supported/weak/contradiction` solo con dev.
- Tasks:
  - [ ] Ejecutar `nli_run` solo dev con chunks reales e inferencia real.
  - [ ] Explorar umbrales con `nli_thresholds.py`, publicar matriz dev y tasa respaldo falso + Wilson.
  - [ ] Congelar umbrales; no modificar config de Ragmur salvo decisión registrada.
- Dependencies: F01.
- Acceptance criteria: umbrales congelados con informe dev versionado (matriz 3x3, `recall_supported>=0.5`, hardware, revisión `b5113eb`, commit, hash corpus).
- Required tests: `uv run python -m eval.nli_run --dataset eval/eu_nli_dev.yaml --split dev`, `uv run python -m eval.nli_thresholds ...`, unitarios NLI.
- Test evidence: no run. Bloqueo verificado por el lead en F01: `eval/eu_nli_dev.yaml` contiene `[]` con `PENDING HUMAN REVIEW` (0 pares); `check_nli_leak` avisa "sin pares todavía". Ejecutar calibración ahora violaría la regla de no calibrar sin verdad humana.
- Files changed: ninguno en F02.
- Risks: n pequeña -> Wilson ancho; InferES/SciFact solo diagnóstico. Riesgo principal: anotación humana de 300 pares fuera del alcance de agentes.
- Status: BLOCKED — faltan 300 pares humanos (100/100/100) con doble anotación + adjudicación. No lanzar escritor hasta que existan.

### F03: Evaluación ciega única en reserva (cierra 1.8)

- Objective: medir una vez con parámetros congelados y cerrar verificación.
- Tasks:
  - [ ] Una sola ejecución `nli_run` sobre test; `nli_run` debe rechazar segunda ejecución.
  - [ ] Publicar matriz test, tasa respaldo falso + Wilson, `recall_supported`, hardware/revisión/commit.
  - [ ] Solo resúmenes en Git; `--details` con texto a `/tmp`.
- Dependencies: F02.
- Acceptance criteria: informe test versionado; casillas 1.8 listas para marcar en F06.
- Required tests: `uv run python -m eval.nli_run --dataset eval/eu_nli_test.yaml --split test` (una vez), `pytest -q` con Docker.
- Test evidence: no run.
- Files changed: `eval/results/nli-eu-test-*.json`, `eval/NLI.md`.
- Risks: reabrir test para otro umbral quema la reserva.
- Status: Pending

### F04: Corpus real y runbook copia/restore/reindex

- Objective: dejar datos y recuperación repetibles sin secretos en Git.
- Tasks:
  - [ ] Versionar informes Skynet 2026-11-13 redactados (sin secretos) y manifiesto 10 PDF CC BY con atribución, SHA, páginas/caracteres.
  - [ ] Triar `eval/`: versionar manifiestos, scripts, formularios y resúmenes; ignorar volcados por consulta y archivar borradores AI no revisados.
  - [ ] Runbook `pg_dump` custom + `tar -C /app/storage` + `scp` BatchMode + `pg_restore --clean` en proyecto aislado + `reindex --all` con API detenida + reparación `storage_path`.
  - [ ] Verificar 88 `indexed`, 4 tenants, 24 claves, 88/88 `content_sha256`, 1712 puntos (`dense-1024 cosine`, `sparse modifier=idf`, índices `tenant_id(is_tenant)/owner_id/document_id`), búsqueda híbrida tenant+`ue-publico` top-5 mismo doc (págs 15-16 etiqueta ecológica).
- Dependencies: F01 (trazabilidad); ejecución técnica independiente de F02/F03 pero cierre global espera a F03.
- Acceptance criteria: conteos origen=destino, hashes origen=destino, búsqueda equivalente documentada; sin tocar volúmenes/puertos originales; sin HTTP sobre copia salvo HMAC propio.
- Required tests: `pg_restore -l`, `tar -tf`, `sha256sum`, `reindex --all` en aislado, `hybrid_search` 30 candidatos, `pytest -q -k "isolation or tenant or owner"`.
- Test evidence: no run.
- Files changed: `eval/skynet_public_corpus_*.md`, `eval/skynet_restore_check_*.md`, runbook docs, `eval/results/*` resúmenes.
- Risks: reutilizar nombre/volumen/puerto `ragmur_deploy` destruye original; CPU válida para calidad, no para latencia GPU.
- Status: Pending

### F05: Diseño proxy demo y endurecimiento

- Objective: definir y endurecer demo sin fuga antes de cualquier exposición.
- Tasks:
  - [ ] Diseño: allowlist (`GET /health`, `GET /ready` limitado, `POST /v1/search`, `POST /v1/verify`) y denylist (`POST/DELETE /v1/documents`), proxy/BFF que inyecta `X-API-Key`, `owner_id=ue-publico` fijo, `document_ids` ajenos sin fuga.
  - [ ] Endurecimiento: TLS, firewall, PG/Qdrant solo `127.0.0.1` sin publicar, secretos propios fuera de Git, logs sin contenido privado/secretos, `diagnostic` sin texto privado, `docker-compose.deploy.yml` + overlay CUDA verificados.
  - [ ] Carga/abuso: valores `rate_limit`, `INFERENCE_MAX_REQUESTS`, 429 con `Retry-After` y 503, prueba concurrencia 1 + calentamiento.
- Dependencies: F04.
- Acceptance criteria: diseño aprobado; `curl` localhost health/ready; 401 sin clave/falsa; `owner` inexistente 0 resultados; `compose config` sin `publish` de datos; sin apertura pública hasta autorización escrita separada (DNS/firewall/demo).
- Required tests: `ssh -o BatchMode=yes skynet-ts docker ps`, `curl /health /ready`, `pytest -q -k isolation`, `docker compose config | grep -i publish`, pruebas 429/503.
- Test evidence: no run.
- Files changed: diseño docs, `docker-compose.deploy.yml`, config rate-limit (si cambia, con migración si toca DB).
- Risks: ocultar botones no es control; clave en navegador rompe modelo `owner_id`. Sin diseño no abrir puertos/DNS.
- Status: Pending

### F06: Cierre fase 1: suite, README y marcas

- Objective: declarar fase 1 cerrada solo si todo lo anterior está verde.
- Tasks:
  - [ ] Shared gate completo en árbol integrado + `alembic upgrade head`.
  - [ ] `eval/run.py` 4 configs (densa, BM25, híbrida, híbrida+rerank) sobre dev+reserva con resúmenes versionados.
  - [ ] README tabla final: recall@10 x4, MRR/nDCG híbrida con/sin rerank, latencias p50/p95 con hardware, matriz NLI + respaldo falso con N y Wilson, fecha/commit/corpus/split.
  - [ ] Marcar casillas 1.8/1.9 en `ROADMAP.md` en el mismo commit de cierre.
- Dependencies: F03+F04+F05.
- Acceptance criteria: se cumplen a la vez criterios 1.1-1.8, suite con aislamiento tenant+`owner_id` en verde, servicio con corpus real, demo accesible (tras autorización), README con cifras fechadas. Hasta entonces no se abre fase 2.
- Required tests: shared gate + delivery gate (full `pytest`, `eval/run.py`, `nli_run` dev/test ya congelados, checks Skynet).
- Test evidence: no run.
- Files changed: `README.md`, `ROADMAP.md`, `TASKS.md`, `eval/results/*` resúmenes.
- Risks: muestra poco discriminativa (recall 1.0) debe declararse; no afirmar significación sin incertidumbre.
- Status: Pending

## 7. Completed phases

| Phase | Outcome | Verification | Commit |
|-------|---------|--------------|--------|
| — | 1.1-1.6 + 1.7 línea base heredadas de ROADMAP | Ver ROADMAP/DECISIONS | — |
| F01 | Protocolo congelado, reservas quemadas declaradas, dev/test vacíos, anti-fuga verde | Lead: `ruff check` pass, `mypy` 123 files OK, `pytest tests/eval/test_nli_run+thresholds+check_nli_leak` 20 passed, `check_nli_leak` verde (1200 IDs quemados locales, dev/test 0 pares). Escritor coincide. Sin `nli_run` en fase. Decisión: citas NLI a SHAs AI son declarativas; inventario verificable o purga en F04. Riesgo residual: 6 docs test inspeccionados a nivel borrador. | F01: freeze NLI dataset protocol and anti-leak checks |
| F07 | Diagnóstico auto 300 ES + 300 EN solo dev local, sin calibrar ni cerrar 1.8 | Lead árbol integrado: `ruff check` pass, `format --check` 151 formatted, `mypy` 124 files OK, `pytest tests/eval/` exit 0 verde (134 passed escritor), `check_nli_leak` verde. NLI CPU dev: ES recall 18/100=0.18, EN 26/100=0.26, falso respaldo 6/200=0.03 Wilson [0.0138,0.0639], umbrales intactos, detalles solo scores en /tmp. Revisión: 12 tests ejecutan comportamiento, 2 estáticos; 3 hallazgos bajos no bloqueantes. | F07: add local EN-ES diagnostic NLI datasets |

## 8. Recommended next action

- Next phase: F02 sigue BLOCKED hasta 300 humanos; F04 pendiente.
- Resume command: `run F04` para corpus/runbook, o esperar humanos para `run F02`.
- Suggested effort: medium.
- Autorizaciones pendientes: exponer Skynet (firewall/DNS/TLS); hacer `push`/publicar demo y corpus.
