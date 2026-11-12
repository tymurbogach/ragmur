# Ragmur

Ragmur es un servicio de recuperación multi-tenant con búsqueda híbrida, reranking y verificación de citas.
La fase 1 no genera respuestas: devuelve fragmentos con fuente y verifica texto enviado por el cliente.

## Estado actual

La fase 1 deja el código listo con evaluación reproducible. El despliegue en el homelab y la demo pública quedan pendientes.
El proyecto incluye FastAPI, servicios Docker, migraciones, `/health` y `/ready`,
linting, tipos y CI. Las cifras de recuperación están medidas con `eval/` sobre 35 documentos y 27 consultas.

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
Configura `API_KEY_HMAC_SECRET` con un secreto aleatorio propio antes de arrancar.
Puedes generarlo con `python -c 'import secrets; print(secrets.token_urlsafe(32))'`.
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
La búsqueda híbrida y la verificación funcionan en CPU. Hay un despliegue privado de prueba con GPU en Skynet.

Si mueves el repositorio, crea un entorno virtual nuevo y ejecuta `uv sync --locked`; sus ejecutables pueden conservar la ruta anterior.
`/health` indica proceso vivo sin comprobar dependencias. `/ready` comprueba PostgreSQL, Qdrant y modelos cargados.

La ingesta acepta PDF con texto, DOCX, TXT y Markdown en `POST /v1/documents`.
La petición usa `multipart/form-data`, el campo `file` y un `owner_id` opcional.
Consulta el estado con `GET /v1/documents/{id}` o lista con `GET /v1/documents`.
El estado `indexed` indica que se han confirmado los vectores densos y dispersos.
El servicio carga los modelos al arrancar. La primera ejecución descarga sus revisiones fijadas.
La caché predeterminada está en `models/huggingface` y no se versiona.
La instalación normal usa PyTorch 2.12.0 para CPU. La variante CUDA 13.0 se ha probado con RTX 5080.
`EMBEDDING_DEVICE=auto` selecciona CUDA si PyTorch puede acceder a la GPU; en caso contrario usa CPU.
Para forzar un dispositivo usa `cpu` o `cuda`. Si se fuerza CUDA y no está disponible, el servicio no arranca.
La GPU requiere PyTorch con CUDA, controladores compatibles y acceso del contenedor a la GPU.
La selección se mantiene hasta reiniciar; un fallo posterior de CUDA no cambia el servicio a CPU automáticamente.

El Compose privado usa CPU por defecto. Para construir y arrancar la variante CPU:

```bash
docker compose -f docker-compose.deploy.yml up -d --build
```

Para construir y arrancar la variante CUDA con una GPU compatible:

```bash
docker compose -f docker-compose.deploy.yml -f docker-compose.cuda.yml up -d --build
```

Ambas variantes conservan los mismos volúmenes dentro del mismo proyecto Compose.
El servicio publica la API solo en la interfaz local; configura los secretos antes de arrancar.
Elimina un original con `DELETE /v1/documents/{id}`. Todas estas rutas requieren `X-API-Key`.
La aplicación usa una sola instancia escritora para cada base de datos y directorio de almacenamiento.

Para administrar el acceso desde la máquina del servicio:

```bash
uv run python -m ragmur.cli create-tenant "Mi aplicación"
uv run python -m ragmur.cli issue-key <tenant-uuid> --name desarrollo
uv run python -m ragmur.cli revoke-key <key-id>
```

La emisión muestra la clave completa una sola vez. El `key-id` es el segundo
componente de `rgm_<key-id>_<secret>`. Protege la clave como una contraseña.
Cambiar `API_KEY_HMAC_SECRET` invalida todas las claves existentes; emite otras nuevas.
Las rutas protegidas reciben la clave mediante `X-API-Key`.

`POST /v1/search` recupera fragmentos con búsqueda densa y BM25, y combina sus posiciones mediante RRF.
Usa `query` y, opcionalmente, `owner_id`, `document_ids`, `top_k` y `candidates`.
`rerank` está activado por defecto y puede desactivarse por petición.
La respuesta incluye localizadores y rangos por rama. Sus puntuaciones no son probabilidades.

`POST /v1/verify` puntúa cada frase contra `chunk_ids` autorizados con NLI local.
La evaluación NLI inicial usa pocos ejemplos manuales. No demuestra la calidad sobre documentos reales.
En la prueba reservada detectó dos de tres contradicciones; una quedó como no respaldada.
Consulta los detalles y el hardware en `eval/results/nli-test-2026-11-11.json`.
Devuelve `supported`, `weak`, `unsupported` o `contradicted` con score y mejor evidencia.
Los identificadores ajenos se ignoran; sin evidencia válida todo queda `unsupported`.

## Evaluación de recuperación

Corpus mixto inglés/español de 35 documentos (SQuAD 2.0 y XQuAD) y 27 consultas (20 positivas, 7 negativas; 14 en desarrollo y 13 en prueba).
Medido el 2026-11-10 en CPU sin GPU, con `candidates=30` y `top_k=10`, concurrencia 1.

| Configuración | recall@10 | MRR@10 | nDCG@10 | p50 | p95 |
|---|---|---|---|---|---|
| Densa | 1.0 | 0.975 | 0.982 | 87 ms | 109 ms |
| BM25 | 1.0 | 0.858 | 0.895 | 8 ms | 10 ms |
| Híbrida | 1.0 | 0.975 | 0.982 | 98 ms | 132 ms |
| Híbrida + reranking | 1.0 | 1.0 | 1.0 | 16448 ms | 23725 ms |

Victorias/derrotas/empates en recall@10: 0/0/20 entre híbrida y densa, híbrida y BM25, y reranking frente a híbrida.
La muestra es pequeña y poco discriminativa: las cuatro configuraciones recuperan todas las evidencias a `top_k=10`.
No demuestra una mejora general.
Los resúmenes versionados están en `eval/results/`; los volcados por consulta se ignoran.

```bash
API_KEY_HMAC_SECRET=... uv run python -m eval.run --split all --candidates 30 --top-k 10
```

Para ejecutar la prueba funcional opcional con modelos reales en CPU y Qdrant temporal:

```bash
RAGMUR_REAL_MODEL_TESTS=1 OMP_NUM_THREADS=2 uv run pytest tests/retrieval/test_real_models.py
```

Para reindexar, detén primero la API y ejecuta uno de estos comandos:

```bash
uv run python -m ragmur.cli reindex --document <document-uuid>
uv run python -m ragmur.cli reindex --tenant <tenant-uuid>
uv run python -m ragmur.cli reindex --all
```

Si cambias los modelos o el troceado, usa `--all`. Los comandos parciales rechazan configuraciones distintas.
El reindexado completo elimina primero los puntos de cada tenant y conserva los originales.
Antes del borrado marca los documentos como fallidos. Si se interrumpe, repite `reindex --all`.
Si una fila `deleting` tiene una ruta corrupta, el arranque conserva la fila y registra su identificador.
Detén la API y comprueba el original y el identificador antes de reparar `storage_path` en PostgreSQL.
La ruta debe ser la ruta absoluta de `STORAGE_DIR` seguida del UUID del documento.
No apuntes a otro fichero ni cambies el estado. Reinicia la API para reintentar la limpieza.
Para borrar un tenant con sus puntos y ficheros, detén la API y ejecuta:

```bash
uv run python -m ragmur.cli delete-tenant <tenant-uuid>
```

Las copias de PostgreSQL y `STORAGE_DIR` se hacen con `pg_dump` y copia de ficheros; Qdrant se reconstruye con `reindex --all`.

Para preparar la variante CUDA en una máquina compatible, usa:

```bash
uv sync --locked --no-group cpu --extra cuda
uv run --no-group cpu --extra cuda uvicorn ragmur.main:app
```

Con `EMBEDDING_DEVICE=auto`, comprueba el dispositivo seleccionado en el log de arranque.
CUDA 13.0 requiere un controlador Linux 580.65.06 o posterior para la versión GA.
Inferencia validada en RTX 5080 (`sm_120`, torch cu130, revisiones fijadas): 30 pares de reranking en 0.20 s frente a 6–16 s en CPU. Evaluación completa en GPU (WSL2, mismo corpus y consultas): calidad idéntica a CPU y reranking en p50 163 ms frente a 15856 ms en CPU. Detalle y límites en [gpu-rtx5080-2026-11-10](benchmarks/gpu-rtx5080-2026-11-10.md).
El límite por clave devuelve `429` con `Retry-After`; la ingesta llena y las dependencias caídas devuelven `503`.
`INFERENCE_MAX_REQUESTS` limita las búsquedas y verificaciones admitidas; el exceso recibe `503` con `Retry-After`.
El límite previo de autenticación usa la dirección de conexión, sin confiar en cabeceras reenviadas.
Si hay un proxy, todos sus clientes comparten ese límite salvo que se configure el servidor para identificar sus direcciones.

Para construir el contenedor de CPU:

```bash
docker build -t ragmur:cpu .
docker run --env-file .env -p 8000:8000 -v ragmur-models:/app/models -v ragmur-storage:/app/storage ragmur:cpu
```

Para CUDA en máquina compatible con NVIDIA Container Toolkit:

```bash
docker build --build-arg INSTALL_CUDA=true -t ragmur:cuda .
docker run --gpus all --env-file .env -p 8000:8000 -v ragmur-models:/app/models -v ragmur-storage:/app/storage ragmur:cuda
```

El Compose privado usa CPU por defecto. Añade `docker-compose.cuda.yml` para activar CUDA.
Define `POSTGRES_PASSWORD` y `API_KEY_HMAC_SECRET` en un archivo de entorno privado.
Usa los comandos de Compose de la sección de instalación.
El nombre de proyecto determina los volúmenes: usa el mismo nombre para conservarlos.
El proyecto existente en Skynet se llama `ragmur_deploy`; comprueba su configuración antes de actualizarlo.
La API escucha solo en `127.0.0.1:8000`; PostgreSQL y Qdrant no publican puertos.
Los volúmenes conservan los datos, originales y modelos entre reinicios.

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

MIT. Ver `LICENSE` con titular Tymur Bogach.
