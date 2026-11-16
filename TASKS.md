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
| F04 | Corpus real y runbook copia/restore/reindex | Completed |
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
- Non-objectives: no calibrar NLI ni tocar umbrales `0.75/0.50/0.75`; no `nli_run`/`nli_thresholds`/`eval/run.py` sobre reserva; no proxy/BFF, TLS, firewall, DNS, `publish` ni demo; no marcar 1.9 cerrado ni abrir F05.
- Tasks:
  - [x] Manifiesto `eval/eu_manifest.yaml` + tabla 10 PDF dev CC BY 4.0 con título, autor, `source_url`, licencia, `sha256` completo, bytes, páginas, caracteres, `rights_page`. Excluye 6 test y holdouts.
  - [x] Versionar `eval/skynet_public_corpus_2026-11-13.md` y `eval/skynet_restore_check_2026-11-13.md` redactados, sin secretos.
  - [x] Triar `eval/`: allow `eu_manifest.yaml`, `eu_auto_manifest.yaml`, scripts, formularios, `NLI.md`/`SCIFACT.md`/`EU_CORPUS.md`, resúmenes `eval/results/*.json`; deny `*.dump`, `*.tar`, PDF originales, `.key`, `.env`, volcados por consulta a `/tmp`. Deuda F01 resuelta como inventario verificable de citas NLI a SHAs AI.
  - [x] Runbook en `docs/runbook-backup-restore.md` (flag corregido a `--if-exists`; pre-vuelo PowerShell).
  - [x] Verificar equivalencia documentada a nivel `hybrid_search`, sin HTTP sobre copia.
- Dependencies: F01 (trazabilidad); ejecución técnica independiente de F02/F03 pero cierre global espera a F03.
- Acceptance criteria: `indexed|88` con 0 en otros estados antes de copiar; origen=destino `88 indexed`, `4 tenants`, `24 claves`; `88/88 content_sha256`; `1712` puntos `ragmur_chunks` (`dense-1024 cosine`, `sparse modifier=idf`, índices `tenant_id(is_tenant=true)/owner_id/document_id`); `hybrid_search` tenant corpus + `owner_id=ue-publico` 30 candidatos top-5 `La etiqueta ecológica`, top-1 págs `15-16`; volúmenes/puertos originales intactos; sin HTTP sobre copia.
- Required tests: `SELECT status,count(*)` → `indexed|88`; `pg_restore -l` → 32 entradas; `tar -tf` → 90 entradas/88 ficheros; `sha256sum -c` origen=destino; `reindex --all` CPU API detenida → `Reindexed 88`, 0 `failed/unsupported`; Qdrant collection info 1712 puntos + `idf` + 3 índices; `hybrid_search` top-5 idéntico; `pytest -q -k "isolation or tenant or owner"` verde; `grep ragmur_deploy <compose.aislado>` → 0; secret-scan `rgm_|hmac|password|BEGIN PRIVATE` en `eval/skynet_*.md` → 0.
- Test evidence: verificado 2026-11-16 en vivo. Escritor native `backend`: `SELECT indexed|88` estable x2, 4 tenants, 24 claves; dump 17277 B 32 entradas, tar 73717760 B 90 entradas 88 UUIDs, `sha256sum -c` OK; restore aislado `indexed|88` 4/24; `content_sha256` 88/88/0, `storage_path` 88/88 solo copia, origen intacto; `reindex --all` → `Reindexed 88`; colección 1712 pts `dense-1024 cosine` `sparse modifier=idf` 3 índices, tenant público 1395 pts; `hybrid_search` 30 candidatos top-5 mismo doc top-1 págs 15-16 idéntico GPU, sin HTTP; `pytest -k isolation` 13 passed 1 skipped; secret-scan 0; compose aislado fuera de Git sin API. Lead integrado: `ruff check` pass, `format --check` 154 formatted, `mypy` 124 files OK, `pytest` 235 passed 4 skipped, secret/deny 0 en Git, `check_nli_leak` verde. Revisión final: sin bloqueantes; fase verificada, cierre global a F03.
- Files changed: allow `eval/skynet_*.md`, `eval/eu_manifest.yaml`, `docs/runbook-backup-restore.md`, `eval/results/*` solo resúmenes; deny `*.dump`, `*.tar`, PDF, `.key`, `.env`, detalles en `/tmp`.
- Risks: pre-vuelo anti-colisión obligatorio; `pg_restore --clean` con env erróneo restaura sobre original; copia sin snapshot consistente no es atómica; reparar `storage_path` en origen destruye despliegue; CPU válida para calidad, nunca para latencia; caché `model_data` compartida contamina; reutilizar nombre/volumen/puerto `ragmur_deploy` destruye original. Notas: `Get-Service Stopped` no implica Docker caído si `desktop-linux` responde; el `tar` incluye `.ragmur.lock` (contar UUIDs); Skynet cayó y volvió el 2026-11-16 (Docker detenido, luego sano).
- Status: Completed 2026-11-16.

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

- Next phase: F04 Completed 2026-11-16; F02 sigue BLOCKED hasta 300 humanos; siguiente técnico F05.
- Resume command: `run F05` para diseño proxy demo y endurecimiento, o esperar humanos para `run F02` (desbloquea F03 y cierre global).
- Suggested effort: medium.
- Autorizaciones pendientes: exponer Skynet (firewall/DNS/TLS); hacer `push`/publicar demo y corpus.
