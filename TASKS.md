# TASKS.md

> Plan único de taskflow. Trabajo en curso aquí; fases completadas resumidas. Git guarda el detalle: el plan anterior completo está en `git show f35ee93:TASKS.md`.

## 1. Objective

- Project purpose: servicio RAG multi-tenant que ingiere documentos, los indexa y responde con citas. Fase 1: buscador y verificador, sin LLM.
- Current cycle (C): poner a prueba la fase 1 con tests grandes que un agente lanza solo, antes de darla por cerrada del todo. Petición del usuario del 2026-11-22.
- Outcome: una orden ejecuta todas las pruebas, deja un informe en español sencillo y un agente explica los fallos. La nota la pone siempre un programa.
- Audience: el usuario (junior). Informes con palabras sencillas, pocas cifras y cada término explicado.

## 2. Current state

- Git branch: `main`, base del plan `f35ee93`, 14 commits por delante de `origin/main`. Sin push, por tanto CI no los ha probado.
- What works (medido el 2026-11-22 sobre `f35ee93`):
  - Suite completa con PostgreSQL y Qdrant desechables en Skynet: 376 passed, 6 skipped, 0 failed.
  - Troceador: 100.000 documentos inventados, 0 pérdidas de texto, spans erróneos o dueños erróneos.
  - Aislamiento a escala, sobre `store.py` con Qdrant real: 15.944 preguntas, 956.640 resultados de búsqueda y 31.888 lecturas cruzadas por id, 0 fugas entre tenants o dueños.
- Search baseline (mismo día, prototipo, RTX 5080, 5.226 documentos, 11.788 fragmentos, 30 candidatos, documento correcto entre los 5 primeros):
  - Híbrida: 83,2 % en total. Tras el reranker: 88,2 % en total (14.067/15.944), XQuAD-es 98,7 % (896/908), SQAC 87,6 % (13.171/15.036). Latencia sin HTTP p50 210 ms, p95 225 ms.
  - De los 1.877 fallos, en 1.328 el documento no llega a los 30 candidatos.
  - SQAC se escribió para leer con el texto delante: muchas preguntas no se entienden solas («¿Dónde despegó el avión?»). Su cifra en bruto no es una nota de aprobado.
  - Hay fallos reales: «¿Qué significan las siglas CAF?» no recupera su documento aunque solo 2 de 5.226 contienen «CAF».
- What fails (mismo día, prototipo, solo datos de práctica, no son cifras publicables):
  - Verificador, InferES train temas 1-5 sin `Automated`, 3.124 pares, RTX 5080: exactitud 58,5 %, recall de apoyo 57,6 %, recall de contradicción 59,2 %, respaldo falso 7,0 %.
  - Verdades marcadas como contradichas: 5,1 % con 1 texto, 11,1 % con 3, 14,1 % con 5.
  - 4.236 de 6.562 fragmentos de continuación empiezan a mitad de palabra.
  - Examen ciego de 150 pares: Ragmur 56,0 %, Muse Spark 73,3 %, GLM Flash 77,3 %. Los dos agentes coinciden en 136 y en 30 de esos contradicen a los humanos. Un agente no sirve de juez.
- Known defects without repair (reproducirlos es de C02, arreglarlos no es de este ciclo):
  - D1 `store.py` `retrieve_points`: la petición a Qdrant no filtra por tenant (regla 3); filtra después. El filtro posterior dio 0 fugas en el prototipo; el defecto de la petición sigue.
  - D2 DOCX rechazado entero si cabecera, pie o tabla tienen texto.
  - D3 Estilo de título del Word español `Ttulo1` no detectado.
  - D4 `#` dentro de un bloque de código Markdown se toma por título.
  - D5 Fragmentos que empiezan a mitad de palabra.
  - D6 El divisor de frases rompe «Dr.», aísla `[1]` y junta listas.
  - D7 `/verify`: una contradicción en cualquier fragmento gana al apoyo.
  - D8 Sin `owner_id` se busca en todos los usuarios del tenant. Es el contrato actual: se fija con un test y se lleva a decisión.
- Phase status: la fase 1 figura cerrada desde el 2026-11-21 y las reglas no cambian en este ciclo. La fase 2 queda sin programar hasta el informe de C07. Reabrir formalmente la fase 1 es U01.
- Open risks inherited:
  - Rotar `POSTGRES_PASSWORD` y `API_KEY_HMAC_SECRET` de Skynet (vistos en logs, F05d) y la clave de OpenCode Go (pasó por el chat). Sin confirmar.
  - Revisión humana del piloto G04, pendiente.
  - La reserva NLI de 70 pares está quemada y filtra la etiqueta por la forma. El golden set da recall 1,0 y no discrimina.
- Pendientes menores heredados, fuera de este ciclo:
  - R03: verificar `actions/checkout@v7` con red y limpiar `eval/.pdf_cache`.
  - F05d: la imagen de repliegue de 8,5 GB sigue en Skynet.
  - Exposición: claves sin alcance por ruta; `/docs`, `/redoc`, `/openapi.json` y `/ready` sin clave; limitadores por proceso. Aceptable solo con la API privada.
  - G02, G03a, G03b y G04: mejoras menores en `git show f35ee93:TASKS.md` («Later work»).
- Required test capabilities: `ssh -o BatchMode=yes skynet-ts`, Docker en Skynet, RTX 5080 con 8 GiB de VRAM libres.
- Model family limits: en OpenCode todos los roles usan Muse Spark (`models.json`). Crítica y revisión van en sesiones nuevas.
- Existing local changes at planning: solo `TASKS.md`.

## 3. Architecture and technology

- Stack: Python 3.12 con `uv`, FastAPI, Pydantic v2, SQLAlchemy 2.0 sobre `asyncpg`, Alembic, Qdrant 1.19, bge-m3, BM25, bge-reranker-v2-m3, mDeBERTa NLI `b5113eb`.
- `retrieval/store.py` es el único acceso a Qdrant. `llm/provider.py` es el único acceso a un LLM. La API no importa `litellm`.
- Pieza nueva `eval/phase1/`: orquesta pruebas deterministas. No importa `llm/` ni invoca agentes.
- Pieza nueva `scripts/phase1-agent.sh`: herramienta de desarrollo fuera del servicio y de `eval/`. Pide al runner el informe y, después, a un agente de solo lectura que lo explique.
- Cómputo: el portátil hace lo estático y los tests unitarios. Skynet hace PostgreSQL, Qdrant y GPU en contenedores desechables.
- Imágenes en Skynet, sin build ni pull por SSH: `ragmur_deploy-api:latest`, `qdrant/qdrant:v1.19.0`, `postgres:17-alpine`. El código del commit se copia al contenedor.
- Modelos: volumen `ragmur_deploy_model_data`, siempre de solo lectura.
- Receta de Skynet (probada de principio a fin el 2026-11-22 en 43 s, con `P=ragmur-p1-<run_id>`):
  1. `docker network create --label ragmur.p1.run=<run_id> $P-net`. Guardar antes los ids de `ragmur_deploy*`.
  2. `docker run --rm -d` de `$P-pg` (`--tmpfs /var/lib/postgresql/data`, usuario, clave y base de prueba) y de `$P-q`, los dos en esa red.
  3. `docker run --rm -d --init --name $P-api --network $P-net --memory 10g --tmpfs /app/storage:mode=1777 -p 127.0.0.1::8000 -v ragmur_deploy_model_data:/app/models:ro -w /tmp` con `-e` de `HF_HUB_OFFLINE=1`, `MODEL_CACHE_DIR=/app/models/huggingface`, `STORAGE_DIR=/app/storage`, `EMBEDDING_DEVICE`, `API_KEY_HMAC_SECRET` de prueba, `DATABASE_URL` y `QDRANT_URL` hacia `$P-pg` y `$P-q`, `PYTHONPATH=/tmp/code/src`, imagen `ragmur_deploy-api:latest` y orden `sleep`. Para GPU, añadir `--gpus all`.
  4. `docker exec $P-api mkdir -p /tmp/code`; `tar -czf - src alembic.ini eval/__init__.py eval/phase1 eval/.datasets/phase1/prepared | ssh skynet-ts "docker exec -i $P-api tar --no-same-owner --no-overwrite-dir -xzf - -C /tmp/code"`.
  5. Con `docker exec -w /tmp/code`: `/app/.venv/bin/alembic upgrade head`, `python -m ragmur.cli create-tenant`, `issue-key` (no imprimir la clave) y `uvicorn ragmur.main:app`. El Python es `/app/.venv/bin/python`.
  6. Túnel `ssh -N -L` al puerto que da `docker port`. Al acabar: `docker stop` de los tres, `docker network rm` y comparar los ids de `ragmur_deploy*`.
  - Dónde corre cada cosa:
    - Portátil: orquesta, descarga, usa `eval/inferes.py` y `eval/reader/xquad.py` y escribe en `eval/.datasets/phase1/prepared/` solo los casos de práctica. Ese directorio es lo único de los datos que viaja.
    - Contenedor `$P-api`: cálculo de `nli` y `search` sobre los ficheros preparados, con `PYTHONPATH=/tmp/code/src:/tmp/code`. No importa cargadores de datasets.
    - `service`: el cliente corre en el portátil por el túnel y la API en el contenedor.
  - Trabajos largos con `docker exec -d` y log dentro del contenedor. Recoger ficheros con `docker exec ... base64`.
  - Etapas GPU en serie. Exigir 8 GiB de VRAM libres antes de cada una; si faltan, esperar hasta 15 min y salir con 2.
- Prototipo de referencia, no es dependencia: `~/.local/share/ragmur/phase1-prototype-20261122/` (`bin/`, `work/code/bench.py`, `out/`). Puede faltar: este plan basta.

### Datos del ciclo

| Conjunto | Origen fijado | Se usa | Sellado |
|---|---|---|---|
| XQuAD-es | `eval/reader/xquad.py` | 908 preguntas dev; todos los párrafos como ruido | preguntas `reserve` |
| SQAC | `PlanTL-GOB-ES/SQAC@f9928e8819596a601b8887cc5f8598b15d589a82`, `train.json` SHA-256 `1d5c76176646e2ae7bdcd8b5ec6f18349102a9363aa25ad7d0e48262d7480d43`, CC BY-SA 4.0 | 15.036 preguntas, 4.986 textos | `dev.json`, `test.json`: ni descargar |
| InferES | `venelin/inferes@c371a1915e6902b40182b2ae83c5ec7fe5e6cbd2`, `train.csv` con el SHA-256 de `eval/inferes.py`, CC BY 4.0 | temas 1-5: 4.602 pares, 3.124 sin `Automated` | `test.csv`: ni descargar; temas 6 y 10 de train: ni evaluar |

## 4. Required rules

- Follow `AGENTS.md`, `ARCHITECTURE.md` and `DECISIONS.md`.
- Only the orchestrator edits this file. Workers report through report files.
- Execution modes create one commit per verified phase, con mensaje semántico e ID: `test: C01 add unattended phase 1 runner`. Nunca atribuir commits a una IA, sin `Co-Authored-By`.
- `run all` ejecuta solo C01-C07. U01-U03, G05 y F10 no son fases pendientes: necesitan una petición expresa del usuario.
- Docker del portátil: prohibido cualquier comando, aunque esté encendido. Exportar siempre `DOCKER_HOST=unix:///nonexistent`. Usar el socket enciende JobPilot, que se conecta a portales de empleo.
- Skynet (autorizado por el usuario el 2026-11-22 para estas pruebas):
  - Crear y borrar solo recursos `ragmur-p1-<run_id>-*`, con etiqueta `ragmur.p1.run=<run_id>`.
  - Puertos solo en `127.0.0.1`. Sin build, pull, prune, DNS, firewall ni cambios de configuración.
  - Nunca parar, modificar ni usar como banco `ragmur_deploy*` o `ragmur-ollama-eval`. Nunca leer sus variables con secretos.
- No usar `eval.inferes.main` ni `make_cases`: exigen el `test.csv` sellado.
- Sellados: no descargar, abrir, listar su contenido ni evaluar. El cargador solo conoce los ficheros de práctica y falla cerrado.
- LLM: ningún LLM crea etiquetas, puntúa, cambia un veredicto ni decide una aceptación. El explicador solo recibe el paquete de fallos públicos de práctica.
- Este ciclo no arregla defectos, no cambia `src/`, umbrales, `top_k`, troceado, esquema, reglas ni dependencias. Un fallo de calidad se publica y no bloquea una fase cuyo objetivo es medirlo.
- Tests de defectos conocidos: `xfail(strict=True, raises=AssertionError)` con su ID D1-D7. No se añade otro `xfail` para poner en verde la puerta.
- No push, PR, publication or deployment. No `.env`, secretos, modelos, datasets ni volcados por consulta en Git.

## 5. Commands

```sh
# install
uv sync --locked

# shared phase gate, sin Docker ni red. Son dos llamadas de shell separadas, cada una de menos de 120 s
# llamada 1
export DOCKER_HOST=unix:///nonexistent
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run python -m eval.check_nli_leak
# llamada 2 (53 s; 332 passed, 3 skipped)
export DOCKER_HOST=unix:///nonexistent HF_HUB_OFFLINE=1 API_KEY_HMAC_SECRET=test-only-hmac-secret
export DATABASE_URL=postgresql+asyncpg://x:x@127.0.0.1:59999/x QDRANT_URL=http://127.0.0.1:59998
uv run pytest --ignore=tests/retrieval --ignore=tests/api/routes/test_health.py \
  --ignore=tests/api/routes/test_documents.py --ignore=tests/api/test_rate_limit.py \
  --ignore=tests/test_auth.py --ignore=tests/eval/reader/test_isolation.py \
  --ignore=tests/ingestion/test_recovery.py --ignore=tests/ingestion/test_document_model.py \
  --ignore=tests/ingestion/test_instance_lock.py

# suite completa, desde C01 (unos 9 min)
uv run python -m eval.phase1 start --only suite
uv run python -m eval.phase1 status "$RUN_ID"   # el id lo imprime start

# delivery gate y uso diario, desde C06
scripts/phase1-agent.sh full
```

- Los tests con PostgreSQL o Qdrant quedan fuera de la puerta compartida por tiempo y entorno. La suite completa es obligatoria en C01, C02, C05 y C07.
- Recuento: la suite completa son 382 tests (376 passed, 6 skipped); la puerta ejecuta 335 (332 y 3). Los otros 47 necesitan servicios.
- Trabajos largos: `start` y después `status` cada 60-110 s. La shell de OpenCode corta a los 120 s. El script de C06 se lanza con `nohup` y se sigue igual.
- `quick`: estático, puerta sin servicios, 10.000 documentos de `ingest` y defectos conocidos. Nunca llama a `opencode`. `full`: todas las etapas y después el explicador.

## 6. Plan debate

- Boceto ciego de la crítica adoptado: arnés desatendido, sellado que falla cerrado, `xfail` estricto solo para defectos reproducidos y ningún LLM con nota.
- Ronda 1 `BLOCKED` (2 bloqueantes, 5 mayores, 4 menores):
  - B1 (C05 sin método): aceptado. Receta en §3, probada en Skynet: migrar, subir, buscar, verificar, aislar y borrar; ids del despliegue iguales y 0 restos.
  - B2 (C07 podía aprobar con fallo duro): aceptado y endurecido. Cualquier salida 1 bloquea C07. C02-C05 solo exigen que el instrumento mida y detecte.
  - M1, M3, M4, M5: aceptados (selección congelada, generador de PDF, latido y reanudación, obligaciones heredadas).
  - M2 (órdenes de OpenCode sin verificar): rechazado con evidencia. El 2026-11-22 `opencode run --agent jefe` cargó Taskflow, usó SSH, escribió su log y lanzó `explora` y `revision` sin intervención; `--agent critica` leyó un paquete ignorado por Git; las dos con salida 0 en OpenCode 2.3.2.
  - m1-m4: aceptados.
- Ronda 2 `BLOCKED` (todo lo anterior resuelto; 2 bloqueantes, 1 mayor, 2 menores), todo aceptado:
  - B1: algoritmo de distractores, vector de test y matrices de 1, 3 y 5 textos.
  - B2: sitio de cálculo fijado; al contenedor solo viajan los casos de práctica preparados.
  - M1: `quick` nunca llama al explicador. Menores: `run_id` y reglas de `.gitignore`.
- Ronda 3, la última (todo lo anterior resuelto; 1 mayor, 0 bloqueantes): "VERDICT: BLOCKED — C03 must pin the download allowlist and sealed-absence test before an unattended `run all`."
  - Aceptado y aplicado tal cual en C03: lista cerrada y test de ausencia. Sin cuarta ronda por el límite de Taskflow: esta última corrección la comprobó solo el orquestador.
- Desacuerdos abiertos: ninguno. Decisiones del usuario: U01-U03.

## 7. Phase plan

| Phase | Title | Status |
|-------|-------|--------|
| C07 | Ejecución completa e informe base | Pending |
| U01-U03 | Decisiones, arreglos y examen final | Not scheduled (usuario) |
| G05 | Escalado del lector de fase 2 | Not scheduled (usuario) |
| F10 | Cambios de contrato de errores | Not scheduled (usuario) |

### C05: Servicio real de principio a fin y bajo carga

- Outcome: etapa `service` en verde contra API aislada en Skynet (código del commit, modelos reales en GPU, migraciones, claves efímeras): 10/10 pasos, salida 0, 234 s. Carga 1/4/16/32 sin 500 (48/48 con 200, recuperación 5/5, 0×429/503/500) y `deploy_equal: true`.
- Verification: puerta del orquestador ruff+mypy+leak OK y pytest 429 passed, 3 skipped, 7 xfailed (+25 tests nuevos: 23 conductuales, 2 estáticos); Skynet `20261123T090237-b29e2e89` service passed y `20261123T090853-1d4f660e` suite 474 passed, 0 failed; ids `ragmur_deploy*` idénticos, 0 restos. `revision` VERDICT: OK (2 menores de texto, deuda de observabilidad del cubo `error`).
- Status: Done

### C06: Una orden y un agente que explica

- Outcome: `scripts/phase1-agent.sh [quick|full]` con inhibición, propagación del código del informe y explicador de solo lectura rotulado «no cambia la nota». `quick` local sin Skynet ni LLM; `full` con stub (el real es C07). `docs/pruebas-fase-1.md` y sección «Pruebas desatendidas» en `LEARNING.md`.
- Verification: puerta del orquestador ruff+mypy+leak OK y pytest 446 passed, 4 skipped, 7 xfailed (+17 tests: adversarios agente-caído y «todo aprobado», paquete fail-closed con semilla y tope 50); `quick` real exit 0 (10 000 docs, 0 fallos); explicador real con paquete pequeño `ok: explicó los fallos`. `revision` VERDICT: OK (inhibición del bucle `full`, `_claims_all_ok` estrecho y `run_id` cosmético como deuda futura).
- Status: Done

### C07: Ejecución completa e informe base

- Objective: una ejecución íntegra, reproducible y comprensible.
- Tasks:
  - [ ] Con el árbol limpio, `scripts/phase1-agent.sh full` sobre el commit de C06.
  - [ ] Versionar solo el resumen en `eval/results/` y la lista de decisiones para U01.
- Dependencies: C06.
- Owned files: `eval/results/phase1-*.json`, `eval/results/phase1-*.md`.
- Acceptance criteria:
  - Todas las etapas completas. Solo 0 o 3 completan la fase. 2 bloquea: un reintento con `--resume` y, si se repite, parar.
  - 1 bloquea siempre, sin reintento para ocultarlo: registrar el fallo aquí, dejar el informe en el directorio de la ejecución y parar para U01. No añadir `xfail` ni reparar.
  - El informe dice claramente si la calidad falla y no declara cerrada la fase 1.
  - 0 recursos temporales en Skynet, `ragmur_deploy` sano, 0 llamadas al Docker local.
- Required tests: delivery gate.
- Status: Pending

### Not scheduled: requiere al usuario

- U01 Decidir con el informe, o antes si C07 se bloquea: reabrir formalmente la fase 1, notas mínimas antes del examen final (XQuAD-es y SQAC por separado, sin usar SQAC en bruto), arreglos y contrato de D7 y D8.
- U02 Arreglos, una fase por defecto, cada uno con su `xfail` convertido en test normal y medido antes y después. Se planifica tras U01.
- U03 Examen final único con los sellados, con código, umbrales y criterio congelados. Excluye los artículos de XQuAD que ya están en el golden set. Nunca dentro de `run all`.
- G05 Escalado del lector: tras la revisión humana de G04. Datos para reanudar en `git show f35ee93:TASKS.md`, §9.
- F10 A5 (toda excepción da 503) y A8 (duplicado en proceso da 200): solo con decisión expresa.

## 8. Completed phases

| Phase | Outcome | Verification | Commit |
|-------|---------|--------------|--------|
| F01-F03 | Protocolo NLI, umbrales 0,75/0,5/0,75 y reserva de 70 pares abierta una vez | Resúmenes `nli-eu-*-2026-11-18.json`; reserva quemada | `F01: freeze NLI dataset protocol and anti-leak checks` y cierre del 2026-11-18 |
| F04 | Corpus real de 88 PDF, copia, restauración y reindexado | 88 indexed; aislamiento 13 passed | `F04: verify corpus backup restore reindex against Skynet` |
| F05a-F05d | Diseño, endurecimiento, carga y despliegue privado en Skynet | smoke 28/28; `benchmarks/load-gpu-2026-11-19.md` | `1abaf61`, `cfbb73b`, `dbc1e39` y cierre del 2026-11-19 |
| F05e | Demo pública descartada | Decisión del usuario, DECISIONS 3.33 | not created |
| F06 | Cierre documental de fase 1 | 242 passed, 4 skipped | `e3bdba1`, `beab7b1` |
| F07-F09 | Diagnóstico NLI, limpieza de código y documentos | 237 passed, revisiones OK | `F07`, `F08`, `F09` en Git |
| R01-R03 | Refinamiento sin cambio de comportamiento | 242 passed | `55ab54b` y anteriores |
| G01 | Apertura de fase 2 | puerta estática | `f3b0aa7` |
| G02 | Proveedor LLM mínimo | 268 passed, 5 skipped | `fddc583` |
| G03a | Datos, índice y caché del lector | 314 passed, 5 skipped | `e998d2c` |
| G03b | Lector, puntuación y controles; prompts congelados | 377 passed, 5 skipped | `6ed6abd` |
| G04 | Piloto de 100 preguntas; revisión humana pendiente | EM 25/100; respuesta en top 5 99/100 | `4d6f2e6` |
| C01 | Runner desatendido `eval/phase1` (start/status/report/cancel, cerrojo PID+latido, resume) y suite real en Skynet | Puerta: ruff+mypy+leak OK; pytest 353 passed, 3 skipped. Skynet `20261122T214759-e6adfcbf` salida 0 (static + suite 398 passed, 0 failed, 5 skipped conocidos), 0 llamadas Docker local, cancel+resume con 0 restos, deploy ids intactos. `revision` VERDICT: OK | `test: C01 add unattended phase 1 runner` |
| C02 | Ingesta a gran escala (100k docs, 0 problemas, ~34 s) y D1-D7 en xfail estricto + D8 normal | Puerta: 370 passed, 3 skipped, 7 xfailed. Skynet `20261122T222105-e2182582` salida 0 (static+ingest+suite 415 passed, 0 failed, 12 skipped = 7 xfail + 5 entorno), 0 restos. `revision` VERDICT: OK | `test: C02 add large-scale ingest and known-defect tests` |
| C03 | Verificador NLI (4602 pares, 3124 principal, celdas exactas) con calidad en rojo | Puerta: 380 passed, 3 skipped, 7 xfailed. Skynet `20261122T225810-d8096e78` salida 3 (medición válida: respaldo falso 0,070, Wilson 0,083, recall 0,576), 48,9 s cuda, 0 restos, deploy intacto. `revision` VERDICT: OK | `test: C03 add NLI verifier measurement stage` |
| C04 | Búsqueda y aislamiento (15944 casos, 0 fugas, doc@5 rerank 90,9 %) con resume que conserva iso | Puerta: 404 passed, 3 skipped, 7 xfailed. Skynet `20261122T231916-ac7c2dc4` salida 0 (índice 167 s, búsqueda 5186 s, p50 217,9 ms). Revisión 1 BLOCKED por resume-iso, reparación con parcial {rows,iso} + re-sondeo legacy. Revisión 2 VERDICT: OK | `test: C04 add large-scale search and isolation stage` |
| C06 | Una orden y un agente que explica (script + informe + explicador de solo lectura) | Puerta: 446 passed, 4 skipped, 7 xfailed. `quick` real exit 0 (10 000 docs, 0 fallos); explicador real `ok`. `revision` VERDICT: OK | `test: C06 add one-command runner and read-only explainer` |

## 9. Recommended next action

- Next phase: C07 (ejecución `full` real sobre el commit de C06; dura horas, lanzar con inhibición y seguir con `status`).
- C01 cerrada el 2026-11-22: `skynet-ts` es host Windows con Docker en modo Linux (motor `linux/amd64`, runtime `nvidia`, VRAM libre ~9,9 GiB); el shell remoto es `cmd` (sin `head/grep`, sin `;`): usar llamadas SSH separadas o `powershell`. Red `ragmur-p1-*` y ciclo run/exec/stop/rm verificados con 0 restos. Hallazgos menores de revisión (sufijo de skips, contraseña en argv de ssh, sin espera tras SIGKILL) quedan como deuda no bloqueante fuera de este ciclo.
- Ensayo en solo lectura del 2026-11-22 con `opencode run --agent jefe`: entendió fases, exclusiones, puerta y bloqueo de C07 sin ayuda.
- Resume command: `/taskflow run all` (solo C01-C07). Una fase: `/taskflow run C01`.
- Sin estar delante, desde una terminal del usuario:

```sh
cd ~/Projects/ragmur
mkdir -p ~/.local/share/ragmur
nohup systemd-inhibit --what=idle:sleep:handle-lid-switch --who=ragmur --why="taskflow fase 1" \
  opencode run --agent jefe --title "Ragmur: tests de fase 1" \
  "Carga la skill taskflow y ejecuta run all según TASKS.md: solo C01-C07. Apruebo ese plan y sus commits locales. Sin push." \
  > ~/.local/share/ragmur/taskflow-fase1.log 2>&1 &
tail -f ~/.local/share/ragmur/taskflow-fase1.log
```

- Recommended effort: high.
