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
| C01 | Runner desatendido y suite completa en Skynet | Pending |
| C02 | Documentos raros y defectos conocidos | Pending |
| C03 | Verificador con miles de frases | Pending |
| C04 | Búsqueda y aislamiento con 16.000 preguntas | Pending |
| C05 | Servicio real de principio a fin y bajo carga | Pending |
| C06 | Una orden y un agente que explica | Pending |
| C07 | Ejecución completa e informe base | Pending |
| U01-U03 | Decisiones, arreglos y examen final | Not scheduled (usuario) |
| G05 | Escalado del lector de fase 2 | Not scheduled (usuario) |
| F10 | Cambios de contrato de errores | Not scheduled (usuario) |

### C01: Runner desatendido y suite completa en Skynet

- Objective: lanzar pruebas largas que sobreviven a la shell y no tocan el Docker local.
- Tasks:
  - [ ] `eval/phase1/`: `start [--only <etapas>]`, `status <run_id>`, `report <run_id>`, `cancel <run_id>`. `start` desacopla el proceso y vuelve en menos de 5 s.
  - [ ] Estado en `eval/results/phase1/per_query/<run_id>/`: `status.json` con latido, log y JSON por etapa, commit, árbol sucio, hardware y configuración.
  - [ ] Cerrojo de una ejecución con PID y latido cada 15 s. Muerta = PID inexistente y latido de más de 120 s. Solo entonces se toma el cerrojo y se retiran los restos con su etiqueta.
  - [ ] `start --resume <run_id>`: solo con la ejecución muerta y el mismo commit y configuración. Conserva etapas completas y casos puntuados; recrea contenedores e índice.
  - [ ] Plazo por etapa y limpieza en éxito, fallo y cancelación.
  - [ ] Los dos `conftest` de Qdrant comparten un ayudante. Con `RAGMUR_TEST_SSH_HOST` usa Skynet y un túnel. Sin ella conserva el comportamiento de CI.
  - [ ] Etapas `static` y `suite`, con PostgreSQL y Qdrant desechables y migraciones.
- Dependencies: none.
- Owned files: `eval/phase1/`, `tests/eval/phase1/`, los dos `conftest` y su ayudante, `.gitignore` (solo si `eval/results/**/per_query/` y `eval/.datasets/` no bastan).
- Acceptance criteria:
  - Códigos de salida: 0 todo bien; 1 fallo duro; 2 infraestructura o ejecución incompleta; 3 solo falla la calidad o hay fallos conocidos. Precedencia 2, 1, 3, 0. Nunca 0 con una etapa ausente.
  - La suite completa da 0 failed, al menos 376 passed y ningún skip nuevo respecto a los 6 registrados.
  - Un `docker` falso al principio de `PATH` demuestra 0 llamadas locales.
  - El proceso sigue tras morir quien lo lanzó. `cancel` deja 0 contenedores, redes y túneles de ese `run_id`.
- Required tests: puerta compartida; tests de los cuatro códigos, cerrojo y limpieza; suite real en Skynet; cancelación real.
- Status: Pending

### C02: Documentos raros y defectos conocidos

- Objective: romper la ingesta a gran escala y convertir cada defecto conocido en un test.
- Tasks:
  - [ ] Etapa `ingest`: 100.000 documentos con semilla fija por el troceador; 1.000 válidos y 1.000 vacíos, truncados o corruptos de cada formato (TXT, MD, DOCX, PDF) por los extractores. DOCX con `python-docx`; PDF mínimo con stdlib, como `tests/ingestion/test_extractors.py`.
  - [ ] Un test por D1-D7 que describe el comportamiento correcto, en `xfail` estricto. Un test normal que fija D8.
- Dependencies: C01.
- Owned files: `eval/phase1/`, `tests/eval/phase1/`, `tests/known_defects/`.
- Acceptance criteria:
  - Detecta con un fallo inyectado: pérdida de texto, span o dueño erróneo, cuelgue y excepción no controlada. Un fallo real se publica como fallo duro con su semilla; no impide completar C02.
  - Cada `xfail` falla por su aserción, no por preparación. El informe lo muestra como «fallo conocido», nunca como aprobado.
  - La etapa, con sus ficheros generados, tarda menos de 30 min en el portátil.
- Required tests: puerta compartida; tests de los detectores con un fallo inyectado; suite completa.
- Status: Pending

### C03: Verificador con miles de frases

- Objective: medir el verificador con etiquetas humanas y la misma lógica del servicio.
- Tasks:
  - [ ] Descarga atómica y con huella en `eval/.datasets/`, solo de esta lista cerrada, fichero a fichero:
    - `https://huggingface.co/datasets/PlanTL-GOB-ES/SQAC/resolve/f9928e8819596a601b8887cc5f8598b15d589a82/train.json`
    - `https://huggingface.co/datasets/venelin/inferes/resolve/c371a1915e6902b40182b2ae83c5ec7fe5e6cbd2/train.csv`
    - XQuAD-es con `eval.reader.xquad.download_dataset`. Ese fichero único trae la reserva: filtrar siempre con `list_cases(data, "dev")`.
  - [ ] Prohibido `git clone`, `snapshot_download`, `load_dataset` de Hugging Face y cualquier descarga de un repositorio de datos entero.
  - [ ] Etapa `nli` en la RTX 5080: matrices por tipo y con 1, 3 y 5 textos (distractores de otro tema, semilla fija), con intervalos de Wilson.
  - [ ] Selección congelada: filas de `train.csv` con `Topic` 1-5 y premisa e hipótesis no vacías, en orden del fichero, sin deduplicar. Etiquetas con `eval.inferes.LABELS`. Cifra principal: `Anno_Type != "Automated"`.
  - [ ] Distractores con este algoritmo exacto. `P` es la lista seleccionada en su orden (incluye `Automated`), `n = len(P) = 4602`, `id` es la columna `ID` y `t` es `Topic`:

    ```python
    j = int(hashlib.sha256(p.id.encode()).hexdigest(), 16) % n
    chosen = []
    while len(chosen) < 4:
        q = P[j % n]
        j += 37
        while q.t == p.t or q.premise in [c.premise for c in chosen]:
            q = P[j % n]
            j += 1
        chosen.append(q)
    # k textos: [p] + chosen[:k - 1]
    ```

  - [ ] Línea base trivial solo con la forma de la frase, para detectar fugas de etiqueta.
- Dependencies: C01.
- Owned files: `eval/phase1/`, `tests/eval/phase1/`.
- Acceptance criteria:
  - 4.602 pares, 3.124 en la cifra principal. Vector de test: `1968` elige `2428, 5511, 4367, 2559`; `2148` elige `4488, 793, 632, 93`.
  - Cada celda queda a ±5 casos (columnas supported, weak, unsupported, contradicted):

    | Etiqueta humana | 1 texto | 3 textos | 5 textos |
    |---|---|---|---|
    | supported | 774, 92, 409, 68 | 746, 88, 360, 149 | 728, 92, 334, 189 |
    | unsupported | 29, 14, 133, 50 | 32, 17, 108, 69 | 32, 17, 99, 78 |
    | contradicted | 96, 44, 495, 920 | 98, 55, 421, 981 | 98, 54, 393, 1010 |

  - Un test demuestra que el cargador rechaza los sellados y cualquier URL fuera de la lista sin hacer ninguna petición de red.
  - Un test y la comprobación previa de cada ejecución fallan si hay `dev.json`, `test.json` o `test.csv` de esos conjuntos bajo `eval/.datasets/`, o una pregunta de la reserva en `prepared/`.
  - La regla de veredicto coincide con `/verify` en un test de paridad que llama a la ruta.
  - Referencias existentes, solo diagnósticas: respaldo falso ≤5 %, Wilson superior ≤10 %, recall de apoyo ≥50 %. Si no se cumplen, calidad en rojo y salida 3.
- Required tests: puerta compartida; tests del cargador, métricas y paridad; etapa real en Skynet.
- Status: Pending

### C04: Búsqueda y aislamiento con 16.000 preguntas

- Objective: medir si encuentra el texto correcto y demostrar que no mezcla clientes a escala.
- Tasks:
  - [ ] Etapa `search`: 5.226 documentos, 15.944 preguntas, 800/120, 30 candidatos, RRF y reranker configurados.
  - [ ] Cifras por etapa (densa, BM25, híbrida, reranker) y por conjunto: documento y fragmento con la respuesta a 1, 5 y 10, MRR y latencia con hardware.
  - [ ] Tenant señuelo con los mismos textos y dos dueños. En cada pregunta: búsqueda propia, búsqueda del otro dueño y lecturas cruzadas por id. Control positivo y fuga inyectada.
  - [ ] Progreso cada 500 preguntas y reanudación con el mismo `run_id`.
- Dependencies: C01, C03 (cargador).
- Owned files: `eval/phase1/`, `tests/eval/phase1/`.
- Acceptance criteria:
  - 15.944 casos puntuados, sin descartes silenciosos. 11.788 fragmentos con la configuración actual.
  - El detector caza la fuga inyectada. Una fuga real es salida 1, se registra con su caso y no impide completar C04.
  - La calidad de búsqueda se publica sin umbral inventado. U01 fija el umbral.
- Required tests: puerta compartida; tests de métricas y del detector de fugas; etapa completa en Skynet.
- Status: Pending

### C05: Servicio real de principio a fin y bajo carga

- Objective: probar por HTTP lo que los bancos llaman por dentro.
- Tasks:
  - [ ] Etapa `service`: API aislada en Skynet con el código del commit, modelos reales, migraciones y claves de prueba generadas.
  - [ ] Subir TXT, MD, DOCX y PDF; esperar indexado; buscar; verificar; deduplicar; borrar; reiniciar; repetir con otro tenant y otro dueño; borrar el tenant.
  - [ ] Carga mixta con `benchmarks/load.py` a concurrencia 1, 4, 16 y 32, y recuperación posterior, por el túnel, con `--base-url`, claves de prueba y solo consultas dev.
- Dependencies: C01.
- Owned files: `eval/phase1/`, `tests/eval/phase1/`.
- Acceptance criteria:
  - Todos los pasos se ejecutan y se puntúan. Paso incorrecto, fuga, 500 o dato borrado que reaparece: salida 1, registrado, sin impedir completar C05. Los 429 y 503 se cuentan aparte.
  - `ragmur_deploy` sigue sano y con el mismo id de contenedor antes y después.
- Required tests: puerta compartida; etapa real en Skynet; suite completa.
- Status: Pending

### C06: Una orden y un agente que explica

- Objective: que el usuario o cualquier agente lo lance todo con una orden.
- Tasks:
  - [ ] `scripts/phase1-agent.sh [quick|full]`: impide la suspensión, lanza, espera, genera el informe y llama al explicador. `quick` no usa Skynet ni LLM.
  - [ ] `report`: `informe.md` en español sencillo con verde, rojo, «no probado», fallos conocidos y siguiente decisión. Paquete de hasta 50 fallos públicos elegidos con semilla.
  - [ ] Explicador: `opencode run --agent critica`, solo lectura, con plazo. Su salida va a `explicacion.md`, rotulada «no cambia la nota».
  - [ ] `docs/pruebas-fase-1.md`: cómo lanzar, mirar, parar y entender el resultado. Ampliar `LEARNING.md` sin duplicados.
- Dependencies: C01-C05.
- Owned files: `scripts/phase1-agent.sh`, `eval/phase1/`, `tests/eval/phase1/`, `docs/pruebas-fase-1.md`, `LEARNING.md`.
- Acceptance criteria:
  - Con el agente caído o con una respuesta que dice «todo aprobado», el JSON, el informe y el código de salida no cambian.
  - El paquete no contiene sellados, secretos ni datos privados.
  - El script propaga el código del runner.
- Required tests: puerta compartida; `quick` real; agente falso adversario; por separado de `quick`, una prueba real del explicador con un paquete pequeño.
- Status: Pending

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

## 9. Recommended next action

- Next phase: C01.
- Primer paso al ejecutar: que `TASKS.md` sea el único cambio local es lo esperado, no un bloqueo. Hacer commit solo de ese fichero con `docs: record approved phase 1 test plan`. Después, un `HEAD` distinto de `f35ee93` es normal.
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
