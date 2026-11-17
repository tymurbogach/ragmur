# TASKS.md

> Plan único de taskflow. Trabajo en curso aquí; fases completadas resumidas. Git guarda el detalle.

## 1. Objective

- Project purpose: servicio RAG multi-tenant que ingiere documentos, los indexa en Qdrant y responde con citas. Fase 1 sin LLM: buscador con fragmentos más verificación NLI de texto enviado por el cliente.
- Audience: aplicaciones propias (portfolio, lazytripz, chatbot) y revisión humana final de fase 1.

## 2. Current state

- What works: ROADMAP 1.1-1.6 completadas; 1.7 con línea base en desarrollo. F01 protocolo NLI congelado. F07 diagnóstico automático EN+ES solo dev. F04 corpus real (88 PDF, tenant público) y copia/restauración/reindex de Skynet verificados el 2026-11-16 (`eval/skynet_reverify_2026-11-16.md`).
- Broken or pending work: F02 BLOCKED por 0/300 pares humanos; F03 depende de F02. Umbrales NLI provisionales 0.75/0.50/0.75. Sin demo pública ni endurecimiento de exposición (F05). Fase 1 abierta.
- D7 resuelto en `690533b`: `ROADMAP.md` 1.9 y `HANDOFF.md` reflejan el corpus y la restauración verificados.
- Auditoría de complejidad (2026-11-17, base `690533b`): 4 exploradores por área, verificación del lead y dos rondas de crítica. Aceptados: código muerto (`session_scope`, `verifier_type`), duplicación en middlewares de error y en `store.py`, scripts de eval huérfanos y documentos desfasados. Ejecución en F08 y F09; cambios de contrato en F10 opcional.
- Riesgos de exposición conocidos (evidencia del explorador, base `6cd23b2`): las claves no tienen alcance por ruta; `/docs`, `/redoc` y `/openapi.json` están siempre activos; `/ready` no exige clave y devuelve `dense-1024+nli`; los limitadores son memoria por proceso; el `Dockerfile` corre como root y usa `uv:latest`; `docker-compose.yml` de desarrollo publica PostgreSQL y Qdrant en `0.0.0.0`.
- Git branch: `main`, commits locales sobre `origin/main` (`c9abcaa` plan, `690533b` D7, `1801915` plan refinado y el commit de F05a); sin push.
- Last review: F05a reintento, tercera revisión `VERDICT: OK` (2026-11-17); 9 hallazgos menores pasados a F05b. Hallazgos bajos de F07 anotados sin reparar.
- Existing local changes: ninguno tras el commit de F05a.
- Required test capabilities and unavailable gates: el gate compartido requiere PostgreSQL y Qdrant en Docker. Skynet (RTX 5080, `ragmur_deploy`) solo con autorización escrita por fase. Sin autorización de push, DNS, firewall, túnel ni apertura de puertos.
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
# hasta F05b, publicar los servicios de desarrollo solo en loopback:
POSTGRES_PORT=127.0.0.1:5432 QDRANT_HTTP_PORT=127.0.0.1:6333 QDRANT_GRPC_PORT=127.0.0.1:6334 docker compose up -d
uv run alembic upgrade head
# shared phase gate, run by the orchestrator before every phase commit
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest -q
uv run python -m eval.check_nli_leak
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

- Debate de la auditoría (2026-11-17): una ronda más una de cierre con `critica`. Parada: la ronda 2 no añadió hallazgos.
  - A2 (validación de `owner_id` duplicada) se descarta: los mensajes 422 difieren por ruta y forman parte del contrato.
  - B4 (`store.py`) limita los helpers a `document_ids` y parámetros dispersos; `corpus_filter` y `result_filter` quedan intactos.
  - A9 (candado global de modelos) extiende F05c y F05d con carga mixta y `INFERENCE_MAX_REQUESTS` como profundidad de cola.
  - A6 exige bytes y cabeceras idénticos por middleware; C1 actualiza el docstring que lo cita; D5 revisa todas las referencias a `HANDOFF.md`.
- Decisiones del usuario (2026-11-17): solo cambios que preservan comportamiento; retirar `HANDOFF.md` y marcar `REVIEW.md` como histórico; mover los scripts huérfanos a `eval/_archive_ai/`; orden F05a, F08, F09, F05b.
- Hallazgos descartados con motivo: B3 (DECISIONS 3.21); B7 falso (`budget - stride >= 1`); A7 (límites `gt=0`); B11 y B13 (DECISIONS 3.19, contenedor Linux); D1 (`Dockerfile:26` copia `eval`); B1 y B2 (identidad de chunks sin datos de evaluación); B6, B8 y B12 (rendimiento sin medir); A3, A4 y B14 (bajo valor, versiones fijadas); D6 (`LEARNING.md` lo usa la skill); `eval/_archive_ai` (lo usan `check_nli_leak` y tests); A5, A8 y A10 cambian el contrato (F10).

## 7. Phase plan

| Phase | Title | Status |
|-------|-------|--------|
| F01 | Protocolo NLI y congelación de dataset | Completed |
| F02 | Calibración de umbrales solo en dev | BLOCKED |
| F03 | Evaluación ciega única en reserva (cierra 1.8) | Pending |
| F04 | Corpus real y runbook copia/restore/reindex | Completed |
| F05a | Diseño de exposición pública | Verificada; pendiente de aprobación del usuario |
| F08 | Limpieza de código sin cambio de comportamiento | Pending |
| F09 | Limpieza de documentación y eval | Pending |
| F05b | Endurecimiento local del despliegue | Pending |
| F05c | Arnés de carga y abuso en CPU local | Pending |
| F05d | Despliegue privado en Skynet y medición GPU | Pending (autorización A) |
| F05e | Exposición pública de la demo | Pending (autorización B) |
| F06 | Cierre fase 1: suite, README y marcas | Pending |
| F07 | Diagnóstico sintético EN+ES solo dev local | Completed |
| F10 | Cambios de contrato de errores (A5, A8) | Optional, sin programar |

### F02: Calibración de umbrales solo en dev

- Objective: fijar `supported/weak/contradiction` solo con dev.
- Tasks:
  - [ ] Ejecutar `nli_run` solo en dev con chunks reales e inferencia real.
  - [ ] Explorar umbrales con `nli_thresholds.py`; publicar matriz dev y tasa de respaldo falso con Wilson.
  - [ ] Congelar umbrales; no modificar la configuración sin decisión registrada.
- Dependencies: F01 y 300 pares humanos (100/100/100) con doble anotación y adjudicación.
- Acceptance criteria: umbrales congelados con informe dev versionado (matriz 3x3, `recall_supported>=0.5`, hardware, revisión `b5113eb`, commit, hash del corpus).
- Required tests: `uv run python -m eval.nli_run --dataset eval/eu_nli_dev.yaml --split dev`, `uv run python -m eval.nli_thresholds ...`, unitarios NLI.
- Test evidence: no run. `eval/eu_nli_dev.yaml` contiene 0 pares; `check_nli_leak` avisa "sin pares todavía".
- Review verdict: none.
- Files changed: none.
- Risks: n pequeña da Wilson ancho. La anotación humana queda fuera del alcance de los agentes.
- Status: BLOCKED. No lanzar escritor hasta que existan los 300 pares humanos.

### F03: Evaluación ciega única en reserva (cierra 1.8)

- Objective: medir una vez con parámetros congelados y cerrar la verificación.
- Tasks:
  - [ ] Una sola ejecución de `nli_run` sobre test; `nli_run` rechaza una segunda ejecución.
  - [ ] Publicar matriz test, respaldo falso con Wilson, `recall_supported`, hardware, revisión y commit.
  - [ ] Versionar solo resúmenes; `--details` con texto va a `/tmp`.
- Dependencies: F02.
- Acceptance criteria: informe test versionado; casillas 1.8 listas para marcar en F06.
- Required tests: `uv run python -m eval.nli_run --dataset eval/eu_nli_test.yaml --split test` una vez; gate compartido.
- Test evidence: no run.
- Review verdict: none.
- Files changed: `eval/results/nli-eu-test-*.json`, `eval/NLI.md`.
- Risks: reabrir test para otro umbral quema la reserva.
- Status: Pending

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
- Status: verificada y con commit (`F05a: design public demo exposure`). Pendiente de la aprobación del usuario, que se registra aquí con fecha antes de F05b.
- Recomendaciones para el reintento (guardadas 2026-11-16, aplicadas el 2026-11-17):
  - Quitar los hashes literales del documento. La SQL del invariante se genera desde `eval/eu_manifest.yaml` con un script de F05b; la copia manual los corrompió.
  - N2: marcar "por verificar" que el conector no alcanza la API; smoke dentro del contenedor del conector: `api:8000`, `qdrant:6333`, `postgres:5432` y `host.docker.internal:8000` deben fallar.
  - N3: IP fija del conector (`ipv4_address`) como único `set_real_ip_from`, o prohibir el enlace de nginx al host mientras corre el túnel.
  - N4: Skynet es Windows: secreto como Docker secret o volumen con modo fijado dentro del contenedor; rotación de logs dentro de un contenedor o con el driver `local`.
  - N5: topología de Funnel (host, `proxy_protocol`) o declarar que la sección 4 solo aplica a Cloudflare.
  - N6: redacción (CLI, "fuera de Git" repetido, línea 58, origen del 404 en `POST /v1/search`); `include` de la clave dentro de cada una de las tres `location` exactas.
  - Revisión nueva tras el reintento; si sale limpia, presentar el diseño al usuario para aprobarlo.

### F08: Limpieza de código sin cambio de comportamiento

- Objective: quitar código muerto y duplicación verificada sin alterar respuestas, contratos ni resultados de evaluación.
- Tasks:
  - [ ] A1: borrar `session_scope` (`src/ragmur/db/session.py:58`); es su única aparición en el repositorio.
  - [ ] B9: borrar `verifier_type` (`src/ragmur/verification/nli.py:133`) y el import que quede sin uso.
  - [ ] A6: un helper de respuesta de error para `json_limit.py`, `upload_limit.py` e `inference_limit.py`. Antes, capturar en tests los bytes y cabeceras actuales; después, compararlos.
  - [ ] B4: helpers compartidos en `store.py` para validar `document_ids` y construir `SparseVector` y `SearchParams` entre `branch_search` y `hybrid_search`. `corpus_filter` y `result_filter` no cambian.
  - [ ] B5: test que fija las dos políticas: `_checked_payload` falla ante un punto fuera de alcance y `retrieve_points` lo omite.
- Dependencies: F05a con commit.
- Acceptance criteria: gate compartido verde con PostgreSQL y Qdrant reales; mismos conteos de tests más los nuevos; cuerpos y cabeceras de error idénticos; tests de IDF acotado por tenant y `owner_id` y de aislamiento verdes; `git grep` de `session_scope` y `verifier_type` vacío.
- Required tests: gate compartido; `pytest tests/api/test_json_limit.py tests/api/test_upload_limit.py tests/api/test_inference_limit.py tests/retrieval/test_hybrid.py -q`; `pytest -q -k "isolation or tenant or owner"`.
- Test evidence: no run.
- Review verdict: none.
- Files changed: `src/ragmur/db/session.py`, `src/ragmur/verification/nli.py`, `src/ragmur/api/{json_limit,upload_limit,inference_limit}.py` y un módulo de helper, `src/ragmur/retrieval/store.py`, tests correspondientes.
- Risks: `store.py` aplica el filtro de tenant; un helper mal acotado cambia IDF o filtra mal. Revisor con foco en la regla 8 y DECISIONS 3.14.
- Status: Pending

### F09: Limpieza de documentación y eval

- Objective: que la documentación y `eval/` reflejen el código actual, sin cambiar comportamiento.
- Tasks:
  - [ ] C1: mover `eval/numeric_signal_eval.py` a `eval/_archive_ai/`; actualizar el docstring de `numeric_signal_stress_eval.py:7`.
  - [ ] C2: mover `eval/nli_sentence_window_run.py` a `eval/_archive_ai/`; `sentence_windows.py` y su test se quedan.
  - [ ] C3 y C4: notas en `eval/NLI.md` (adaptadores externos sin `document_id`) y docstrings cruzados en `metrics.py` y `scifact_metrics.py`.
  - [ ] D2: marcar en `README.md` las filas LiteLLM y RAGAS como fase 2 pendiente.
  - [ ] D3: quitar de `ARCHITECTURE.md` la frase de fase 0 sobre `/health` y `/ready`.
  - [ ] D12: separar en el árbol de `ARCHITECTURE.md` lo que existe (fase 1) de lo previsto (fase 2).
  - [ ] D4: encabezado de documento histórico en `REVIEW.md` (fecha y base `58cd7ee`).
  - [ ] D5: retirar `HANDOFF.md`. Llevar al runbook o al README los datos de Skynet vigentes (proyecto `ragmur_deploy`, nota del gestor de credenciales, overlay CUDA). `git grep HANDOFF` limpio antes de borrar.
  - [ ] D8: indicar en `README.md` que el Compose de despliegue fija `EMBEDDING_DEVICE=cpu` y el overlay CUDA lo cambia.
  - [ ] D11: listar `eval/eu_nli_holdout2_manifest_draft.yaml` como borrador en `eval/EU_CORPUS.md`; `eval/annotation_forms/` se queda (F02).
- Dependencies: F05a con commit (comparte `ARCHITECTURE.md`).
- Acceptance criteria: gate compartido verde; `check_nli_leak` verde; `git grep` de las rutas movidas y de `HANDOFF` solo encuentra `eval/_archive_ai/`, resultados archivados o menciones históricas en `TASKS.md`; enlaces relativos de los documentos tocados válidos.
- Required tests: gate compartido; `uv run python -m eval.check_nli_leak`; comprobación de enlaces relativos.
- Test evidence: no run.
- Review verdict: none.
- Files changed: `eval/`, `README.md`, `ARCHITECTURE.md`, `REVIEW.md`, `HANDOFF.md` (borrado), `docs/runbook-backup-restore.md`. El orquestador actualiza las referencias en `TASKS.md`.
- Risks: mover scripts rompe imports de tests si alguno los usa; el gate lo detecta.
- Status: Pending

### F05b: Endurecimiento local del despliegue

- Objective: aplicar el diseño aprobado en el repositorio y probarlo solo en local, sin Skynet.
- Tasks:
  - [ ] `Dockerfile`: usuario no root con UID fijo y versión fijada de la imagen `uv`; conservar `HEALTHCHECK`.
  - [ ] `docker-compose.yml` de desarrollo: PostgreSQL y Qdrant solo en `127.0.0.1`.
  - [ ] `docker-compose.demo.yml` según `docs/demo-design.md`: redes `edge` e `internal`, conector con `ipv4_address` fija, nginx sin puertos publicados al host mientras corre el túnel; configuración en `deploy/nginx/`; clave por `include` desde un secreto de Compose fuera de Git, sin `envsubst`.
  - [ ] Script que genera las consultas del invariante desde los 10 `document_id` de `eval/skynet_public_corpus_2026-11-13.md:58-71` y sus hashes en `eval/eu_manifest.yaml`; falla salvo 10 hashes de 64 hex.
  - [ ] Hallazgos menores de la revisión 3 de F05a: (1) redactar "la CLI nunca sube documentos" (`demo-design.md:164`, `:249`); (2) quitar 404 de las filas POST de la matriz (`:67-68`); (3) la regla de selección da 14 documentos: usar solo los 10 ids listados (`:184`); (4) "las dos consultas" son tres (`:185`); (5) el conteo exige `status = 'indexed'` (`:201-209`); (6) el fichero de clave lo lee el proceso maestro de nginx; comprobar su modo con `stat` dentro del contenedor y si Compose respeta `mode` fuera de Swarm (`:239`); (7) reescribir la frase de `:58`; (8) si el smoke del conector alcanza `host.docker.internal:8000`, quitar el puerto de host de la API mientras corre el túnel o usar ingress gestionado localmente (`:112`, `:145`); (9) no fijar `FORWARDED_ALLOW_IPS`; nginx borra `X-Forwarded-For` y `Forwarded` (`:294-297`).
  - [ ] Cambios de código solo si F05a los decide (D5).
  - [ ] Test de `diagnostic`: los avisos de extracción no contienen texto del documento.
  - [ ] Smoke externo vía proxy: rutas permitidas 200; rutas denegadas 404; `X-API-Key` del cliente ignorada; `document_ids` ajenos dan 0 resultados; cuerpo grande 413; ráfaga por IP 429 de nginx con `Retry-After` antes del tope de la app; ningún 5xx.
  - [ ] Smoke interno en `127.0.0.1:8000`: `/health` 200 y `/ready` 200.
- Dependencies: F05a aprobada, F08 y F09.
- Acceptance criteria: gate compartido verde; `docker compose -f docker-compose.deploy.yml -f docker-compose.demo.yml config` solo publica en `127.0.0.1`; secret scan `rgm_|hmac|password|BEGIN PRIVATE` 0 en Git; invariante del tenant de demo verde en datos locales; logs del smoke sin consultas, respuestas ni claves.
- Required tests: gate compartido; smoke externo e interno; `nginx -t` en el contenedor; `pytest -q -k "isolation or tenant or owner"`.
- Test evidence: no run.
- Review verdict: none.
- Files changed: `Dockerfile`, `docker-compose.yml`, `docker-compose.demo.yml`, `deploy/nginx/`, tests o script de smoke.
- Risks: el UID no root cambia la propiedad de los volúmenes existentes de Skynet; F05d planifica `chown`. Las pruebas locales levantan contenedores solo en `127.0.0.1`.
- Status: Pending

### F05c: Arnés de carga y abuso en CPU local

- Objective: disponer de un arnés reproducible y comprobar el comportamiento ante abuso, sin fijar límites.
- Tasks:
  - [ ] `benchmarks/load.py` con asyncio y `httpx` (ya en el grupo dev); sin dependencia nueva.
  - [ ] Consultas solo del split dev de recuperación; el arnés rechaza consultas reservadas.
  - [ ] Calentamiento y barrido de concurrencia; registrar p50, p95, códigos, `Retry-After`, RSS, hardware, commit y configuración.
  - [ ] Ejecución local en CPU a través del proxy: 429 y 503 separados, recuperación tras saturación, ningún 500, aislamiento intacto.
  - [ ] Perfil mixto `/v1/search` + `/v1/verify`: un único `models.lock` serializa embeddings, reranker y NLI (`search.py:42,117`, `verify.py:89`); registrar `capacity_wait` por ruta.
- Dependencies: F05b.
- Acceptance criteria: tests unitarios del arnés (percentiles, esquema del resumen, rechazo de reserva); resumen CPU en `benchmarks/` etiquetado con hardware; ningún límite cambiado.
- Required tests: gate compartido; `uv run python -m benchmarks.load` contra la pila local.
- Test evidence: no run.
- Review verdict: none.
- Files changed: `benchmarks/load.py`, tests del arnés, resumen en `benchmarks/`.
- Risks: la latencia en CPU no vale para cifras públicas. La muestra dev es pequeña.
- Status: Pending

### F05d: Despliegue privado en Skynet y medición GPU

- Objective: llevar el endurecimiento a `ragmur_deploy` y fijar límites con datos de RTX 5080, sin exposición pública.
- Tasks:
  - [ ] Copia previa según `docs/runbook-backup-restore.md` y punto de restauración registrado.
  - [ ] Actualizar `ragmur_deploy` con la imagen endurecida; `chown` de volúmenes al UID nuevo; overlay de demo en `127.0.0.1`.
  - [ ] Smoke externo e interno desde Skynet; `pytest -k "isolation or tenant or owner"`; invariante del tenant de demo.
  - [ ] Barrido GPU con el arnés de F05c, incluido el perfil mixto; fijar `INFERENCE_MAX_REQUESTS` como profundidad de cola tras el candado único, límite por clave y tasas de nginx por ruta según los datos. Los valores por defecto del código no cambian.
- Dependencies: F05c y autorización escrita A (acceso a Skynet y actualización de `ragmur_deploy`).
- Acceptance criteria: smoke verde en Skynet; p50 y p95 por concurrencia en RTX 5080 con hardware; límites justificados por la tabla; restauración posible desde la copia previa.
- Required tests: `ssh -o BatchMode=yes skynet-ts docker ps`; smoke externo e interno; barrido de carga.
- Test evidence: no run.
- Review verdict: none.
- Files changed: resumen en `benchmarks/`, `docs/demo-design.md` con valores finales, `README.md` si cambia el uso.
- Risks: actualizar con un nombre de proyecto o volumen erróneo destruye datos; pre-vuelo obligatorio del runbook.
- Status: Pending. Sin autorización A no se ejecuta.

### F05e: Exposición pública de la demo

- Objective: abrir la demo por la vía aprobada y comprobarla desde fuera.
- Tasks:
  - [ ] Aplicar la vía de exposición de D3 (túnel saliente o reenvío de puerto con TLS).
  - [ ] Smoke externo desde fuera de la red; probar el interruptor de corte.
  - [ ] Vigilar 429, 503 y errores durante 24 h.
- Dependencies: F05d y autorización escrita B (DNS, TLS, túnel o firewall).
- Acceptance criteria: la URL pública solo responde las rutas permitidas; un escaneo externo solo muestra 443; corte comprobado; casillas de demo de 1.9 listas para F06.
- Required tests: smoke externo; escaneo de puertos externo; prueba de corte.
- Test evidence: no run.
- Review verdict: none.
- Files changed: `docs/demo-design.md`, `README.md`.
- Risks: una exposición sin límites medidos permite agotar la GPU.
- Status: Pending. Sin autorización B no se ejecuta.

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
  - [ ] Gate compartido completo en el árbol integrado más `alembic upgrade head`.
  - [ ] `eval/run.py` con 4 configuraciones (densa, BM25, híbrida, híbrida con rerank) sobre dev y reserva, con resúmenes versionados.
  - [ ] Tabla final en README: recall@10 x4, MRR/nDCG híbrida con y sin rerank, latencias p50/p95 con hardware, matriz NLI y respaldo falso con N y Wilson, fecha, commit, corpus y split.
  - [ ] Marcar las casillas de 1.8 y 1.9 en `ROADMAP.md` en el commit de cierre.
- Dependencies: F03, F04 y F05e.
- Acceptance criteria: criterios 1.1-1.8 cumplidos; suite con aislamiento por tenant y `owner_id` verde; corpus real desplegado; demo accesible; README con cifras fechadas.
- Required tests: gate compartido y gate de entrega.
- Test evidence: no run.
- Review verdict: none.
- Files changed: `README.md`, `ROADMAP.md`, `TASKS.md`, `eval/results/*` resúmenes.
- Risks: la muestra de 1.7 es poco discriminativa (recall 1.0); declararlo y no afirmar significación sin incertidumbre.
- Status: Pending

## 8. Completed phases

| Phase | Outcome | Verification | Commit |
|-------|---------|--------------|--------|
| — | ROADMAP 1.1-1.6 y línea base de 1.7 | Ver `ROADMAP.md` y `DECISIONS.md` | — |
| F01 | Protocolo NLI congelado; reservas quemadas declaradas; dev y test vacíos | `ruff` pass, `mypy` 123 OK, 20 tests NLI passed, `check_nli_leak` verde | F01: freeze NLI dataset protocol and anti-leak checks |
| F07 | Diagnóstico automático 300 ES + 300 EN solo dev; no calibra | `ruff` pass, `mypy` 124 OK, `pytest tests/eval/` verde; ES recall 0.18, EN 0.26, respaldo falso 0.03 Wilson [0.0138, 0.0639] | F07: add local EN-ES diagnostic NLI datasets |
| F04 | Manifiesto del corpus, triage de `eval/`, runbook y copia/restore/reindex de Skynet en entorno aislado | Skynet: `indexed\|88`, `sha256sum -c` OK, `Reindexed 88`, 1712 puntos, `hybrid_search` top-5 idéntico, isolation 13 passed 1 skipped. Lead: `ruff` pass, `mypy` 124 OK, `pytest` 235 passed 4 skipped, secret scan 0 | F04: verify corpus backup restore reindex against Skynet |

## 9. Recommended next action

- Next action: el usuario revisa y aprueba `docs/demo-design.md` (F05a). La aprobación se registra en F05a con fecha.
- Next phase: F08 (no depende de la aprobación de F05a). Después F09 y F05b.
- Resume command: `/taskflow run F08`
- Recommended effort: medium
- Autorizaciones pendientes: A (Skynet, F05d), B (exposición pública, F05e), push.
