# Arquitectura

Qué se construye y con qué contratos. El porqué de cada decisión está en [`DECISIONS.md`](DECISIONS.md); el orden en [`ROADMAP.md`](ROADMAP.md).

Este documento describe el objetivo, no las funciones disponibles. La fase 0 está implementada; la siguiente tarea funcional es 1.1.
La [revisión previa](REVIEW.md) registra las comprobaciones y los puntos pendientes antes de continuar.

## Estructura del repositorio

```
ragmur/
├── src/ragmur/
│   ├── main.py
│   ├── core/
│   │   ├── config.py           # pydantic-settings
│   │   ├── security.py         # resolución de tenant por API key
│   │   └── logging.py
│   ├── api/
│   │   ├── deps.py
│   │   ├── schemas.py
│   │   └── routes/
│   │       ├── health.py
│   │       ├── documents.py
│   │       ├── search.py
│   │       ├── verify.py
│   │       ├── query.py        # fase 2
│   │       └── answer.py       # fase 2
│   ├── ingestion/
│   │   ├── extractors/         # pdf.py (pypdfium2), docx.py, text.py
│   │   ├── storage.py          # fichero original en disco
│   │   ├── chunker.py
│   │   └── pipeline.py
│   ├── retrieval/
│   │   ├── embedder.py         # bge-m3
│   │   ├── sparse.py           # BM25 vía FastEmbed
│   │   ├── store.py            # cliente Qdrant — único punto de acceso
│   │   ├── hybrid.py           # fusión RRF
│   │   ├── reranker.py         # cross-encoder
│   │   └── router.py           # fase 2: reescritura y reintento
│   ├── verification/
│   │   ├── splitter.py
│   │   └── nli.py
│   ├── llm/                    # fase 2
│   │   ├── provider.py         # abstracción LiteLLM
│   │   └── generator.py
│   └── db/
│       ├── models.py
│       ├── session.py           # motor y fábrica de sesiones
│       ├── health.py            # comprobación de conectividad
│       └── migrations/
├── eval/
│   ├── golden_set.yaml
│   ├── run.py
│   └── results/
├── tests/
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```

Dirección de dependencias: `api/` importa de `ingestion/`, `retrieval/`, `verification/` y `llm/`. Nunca al revés. La lógica de dominio no conoce FastAPI.

Dos puntos de estrangulamiento obligatorios, ambos verificables con un test de imports:

- **Qdrant** solo se toca desde `retrieval/store.py`. Ningún otro módulo importa `qdrant_client`.
- **LLM** solo se invoca desde `llm/provider.py`. Ningún módulo importa un SDK de proveedor.

Toda función pública de `store.py` recibe `tenant_id` como primer argumento obligatorio, excepto `create_client()` y `ping()`.
Estas dos funciones solo gestionan la conexión y comprueban el servidor; no pueden leer ni escribir documentos o fragmentos.
Las operaciones de búsqueda, indexado, lectura y borrado conservan el tenant obligatorio, según la regla 8 de [`AGENTS.md`](AGENTS.md).

## Flujo

```
Ingesta
  fichero → extracción → troceado → embedding denso + disperso → Qdrant

Recuperación (fase 1)
  consulta → embedding denso ─┐
           → vector disperso ─┴→ RRF → reranking → fragmentos ordenados

Recuperación agéntica (fase 2)
  consulta → recuperación
           → si la política calibrada detecta evidencia insuficiente: reescritura → reintento → fusión

Respuesta completa (fase 2)
  recuperación agéntica → redacción con LLM → verificación NLI → respuesta con citas
```

## Aislamiento: dos niveles

| Nivel | Campo | Origen | Obligatorio |
|---|---|---|---|
| Aplicación cliente | `tenant_id` | Derivado de la API key, nunca del cuerpo | Sí, en toda consulta |
| Usuario final | `owner_id` | Enviado por la aplicación cliente | No |

`tenant_id` separa aplicaciones (portfolio, lazytripz, chatbot). `owner_id` separa a los usuarios finales **dentro** de una aplicación: es lo que hace que las facturas de un usuario no sean recuperables por otro del mismo tenant.

Una consulta sin `owner_id` recorre todo el espacio del tenant, que es el comportamiento correcto para un corpus compartido como el del portfolio. Una consulta con `owner_id` filtra por `tenant_id AND owner_id`.

**Asunción explícita:** Ragmur confía en que la aplicación cliente envía el `owner_id` correcto, igual que confía en su API key. Autenticar al usuario final es responsabilidad de la aplicación cliente. Ver `DECISIONS.md` §3.8.

Este alcance se aplica también a PostgreSQL, al detalle, al borrado y a la resolución de citas.
Con `owner_id`, los documentos compartidos (`owner_id=null`) tampoco entran en los resultados.
Sin `owner_id`, la API key permite acceder a todos los usuarios del tenant; no es una credencial para entregar al navegador.

`owner_id` es texto opaco y sensible a mayúsculas. Se rechazan valores vacíos o compuestos solo por espacios.
La aplicación cliente deriva este campo de su sesión autenticada y lo incluye en cada operación sobre documentos privados.
Un identificador inexistente y uno fuera del alcance producen el mismo `404` en detalle y borrado.

## Modelo de datos

### PostgreSQL

Acceso mediante SQLAlchemy 2.0 (declarativo tipado) sobre `asyncpg`. Migraciones con Alembic.

```sql
tenants
  id            uuid primary key
  name          text not null
  created_at    timestamptz not null default now()

api_keys
  id            uuid primary key
  tenant_id     uuid not null references tenants(id) on delete cascade
  key_id        text not null unique    -- prefijo público, viaja en la clave
  key_hash      text not null           -- HMAC-SHA256, no bcrypt
  name          text
  created_at    timestamptz not null default now()
  last_used_at  timestamptz
  revoked_at    timestamptz

documents
  id              uuid primary key
  tenant_id       uuid not null references tenants(id) on delete cascade
  owner_id        text                -- null = documento del tenant, no de un usuario
  filename        text not null
  mime_type       text not null
  content_sha256  text not null
  storage_path    text not null   -- fichero original conservado en disco
  status          text not null   -- pending | processing | indexed | failed | unsupported | deleting
  page_count      int             -- null en formatos sin paginación
  chunk_count     int
  error           text
  created_at      timestamptz not null default now()
  updated_at      timestamptz not null default now()

  unique nulls not distinct (tenant_id, owner_id, content_sha256)
  index  (tenant_id, owner_id)

llm_configs                      -- fase 2
  tenant_id     uuid primary key references tenants(id) on delete cascade
  provider      text not null    -- ollama | openai | anthropic | gemini
  model         text not null
  fallback      jsonb
  updated_at    timestamptz not null default now()
```

Las claves de API viven en su propia tabla para permitir rotación, claves distintas por entorno y revocación sin cortar el servicio al tenant. El formato es `rgm_<key_id>_<secret>`: se localiza el registro por `key_id`, que está indexado, y se compara el secreto en tiempo constante.

El hash es HMAC-SHA256 con una clave de servidor. El secreto de cada API key contiene al menos 256 bits aleatorios.
La CLI muestra la clave completa una sola vez; los logs nunca la incluyen. Ver `DECISIONS.md` §3.11.

El parser separa `rgm`, `key_id` y el secreto mediante dos separaciones como máximo; el secreto puede contener `_`.
La revocación afecta a la siguiente petición; no hay caché positiva de autenticación en la fase 1.
Cambiar la clave HMAC del servidor invalida las API keys existentes y requiere reemitirlas.

`content_sha256` se calcula sobre los bytes del fichero. Una segunda subida idéntica dentro del mismo espacio devuelve el documento existente en lugar de duplicar sus chunks, que contaminarían el `top_k` y las cifras de evaluación.

**La unicidad lleva `nulls not distinct` a propósito.** En PostgreSQL dos `NULL` no se consideran iguales dentro de una restricción de unicidad, así que la forma corriente de la restricción no detectaría un duplicado cuando `owner_id` es nulo —es decir, en el caso de un documento del propio tenant, que es justo el del portfolio—. Con la cláusula, los nulos se comparan como iguales y la deduplicación funciona en los dos casos. Requiere PostgreSQL 15 o superior; el proyecto usa 17. En SQLAlchemy se expresa con `postgresql_nulls_not_distinct=True`.

**El fichero original se conserva.** El reindexado relee los bytes desde `storage_path`, bajo el directorio configurable `STORAGE_DIR`.
La deduplicación solo necesita el hash y la fila existente; conservar el original permite reindexar sin otra subida.
La ruta usa identificadores generados por el servidor. `filename` es metadato y nunca determina una ruta del sistema.

**Consecuencia asumida de la unicidad por `owner_id`:** el mismo fichero subido por N usuarios finales de un tenant produce N documentos y N copias de sus chunks. Es el precio del aislamiento —no se puede compartir un documento entre espacios que deben ser opacos entre sí—, pero implica que una consulta a nivel de tenant, sin `owner_id`, puede recibir varios fragmentos idénticos en el `top_k`.

### Qdrant

Colección única `ragmur_chunks` con vectores nombrados:

- `dense` — 1024 dimensiones, distancia coseno (bge-m3)
- `sparse` — vector disperso BM25, **declarado con `modifier=IDF`**

El `modifier=IDF` no es opcional. FastEmbed emite frecuencias de término; el componente IDF —el que da más peso a los términos raros— lo aplica Qdrant en el servidor a partir de las estadísticas de la colección. Sin él, la rama léxica puntúa solo por repetición y pierde exactamente lo que aporta frente a la búsqueda densa. Falla en silencio: el sistema funciona y recupera peor.

**El corpus del IDF se acota al tenant.** Con una colección única, las estadísticas de IDF son por defecto globales, así que el vocabulario de un tenant distorsionaría la rareza de los términos de otro. Qdrant 1.19 —la versión fijada en `docker-compose.yml`— permite acotar la población sobre la que se calculan mediante un filtro de payload, de modo que el IDF refleje la rareza dentro del espacio del solicitante. El parámetro vive en `SearchParams`:

```python
# `tenant_filter` es el mismo filtro que ya lleva la consulta.
models.SearchParams(idf=models.IdfCorpusParams(corpus=tenant_filter))
```

Se aplica desde `retrieval/store.py` en la consulta dispersa, incluidos sus prefetches.
El corpus incluye `tenant_id` y también `owner_id` cuando existe; `document_ids` restringe resultados, no las estadísticas del espacio.
El suelo de `qdrant-client` es `>=1.19`. El arranque comprueba la compatibilidad del servidor y falla si falta esta capacidad.
No se permite retirar el parámetro para continuar con estadísticas globales. [Referencia de Qdrant 1.19](https://qdrant.tech/blog/qdrant-1.19.x/#per-tenant-idf-statistics).

Payload:

```json
{
  "tenant_id": "uuid",
  "owner_id": "u_4471",
  "document_id": "uuid",
  "filename": "contrato.pdf",
  "locator": { "type": "page", "start": 4, "end": 4 },
  "position": 17,
  "text": "..."
}
```

Índices de payload obligatorios sobre `tenant_id` (con `is_tenant=True`, que además reorganiza el almacenamiento por tenant), sobre `owner_id` y sobre `document_id`. Sin ellos, el filtrado degrada el rendimiento al crecer la colección. El de `document_id` no es opcional aunque no participe en el aislamiento: lo usan el borrado de un documento —que elimina sus puntos por filtro— y el parámetro `document_ids` de `/v1/search`.

Se descarta una colección por tenant: multiplica el consumo de memoria y complica el mantenimiento sin aportar aislamiento adicional real.

### Localizador

Los chunks guardan un localizador con tipo. Cada extractor rellena el que su formato puede sostener:

```json
{ "locator": { "type": "page",    "start": 4, "end": 5 } }
{ "locator": { "type": "section", "value": "3.2 Plazos", "path": ["3.2 Plazos"], "ordinal": 3 } }
{ "locator": { "type": "offset",  "start": 12040, "end": 12840 } }
```

| Formato | Tipo de localizador |
|---|---|
| PDF | `page` — `start` y `end` porque un chunk puede cruzar la frontera de página |
| DOCX | `section` si hay encabezados, `offset` si no. **No `page`:** la paginación la calcula el renderizador al maquetar, no está en el fichero |
| Markdown | `section` a partir del encabezado más cercano; `offset` si no hay encabezado |
| TXT | `offset` |

El consumidor siempre recibe algo con lo que señalar la fuente; la precisión depende del formato de origen.

Las páginas empiezan en 1 y su intervalo es inclusivo. Los offsets cuentan caracteres Unicode desde 0 y usan `[start, end)`.
Los offsets se refieren al texto extraído normalizado, no a bytes del PDF o DOCX.
La extracción fija saltos de línea y separadores de página antes del troceado y conserva un mapa hacia los localizadores.
Los chunks de tipo `section` no cruzan secciones; el localizador incluye la ruta de encabezados y su ordinal para resolver títulos repetidos.

El troceador conserva spans del texto normalizado. La prueba de reconstrucción elimina el solape mediante esos spans.
Concatenar chunks directamente duplica el solape y no es una prueba válida de conservación del texto.

### Identidad de los chunks

`chunk_id` es válido dentro de una sesión de consulta: identifica un punto de Qdrant y sirve para encadenar `/search` con `/verify`. **No es estable entre reindexados.** Cambiar los parámetros de troceado —que es justo lo que hace la tarea 1.7 con los datos de evaluación— regenera todos los chunks con identificadores nuevos. Un consumidor que quiera guardar una cita debe guardar `document_id` + `locator`, no `chunk_id`.

## Contratos de API

Las rutas `/v1/*` requieren `X-API-Key`. El tenant se deriva de la clave; un campo de entrada `tenant_id` se rechaza.
Los esquemas rechazan campos desconocidos. Los límites de texto, listas, subida y concurrencia son configuración validada al arrancar.

| Condición | HTTP |
|---|---|
| Clave ausente, inválida o revocada | `401` |
| Recurso inexistente o fuera del alcance | `404` |
| Operación incompatible con el estado actual | `409` |
| Subida demasiado grande | `413` |
| Formato de fichero no admitido | `415` |
| Campo o combinación de campos inválidos | `422` |
| Cuota de peticiones agotada | `429`, con `Retry-After` |
| Dependencia caída o capacidad de trabajos agotada | `503`, con `Retry-After` cuando proceda |

Los errores incluyen un código estable y un mensaje seguro. No exponen rutas internas, secretos ni excepciones del driver.
La respuesta de validación tampoco refleja contenido privado ni credenciales.

`/health` y `/ready` no requieren API key. En fase 0, `/health` comprueba las dependencias; `/ready` todavía no existe.
La tarea 1.9 separa proceso vivo (`/health`) de recursos preparados (`/ready`) y limita el detalle público.

### `POST /v1/documents`

Multipart: `file`, y opcionalmente `owner_id`.

Respuesta `202` — documento aceptado, ingesta en curso:

```json
{ "document_id": "uuid", "status": "pending" }
```

El `202` se envía después de conservar el fichero y confirmar la fila en PostgreSQL.
Incluye `Location: /v1/documents/{document_id}` para consultar el estado.
La tarea recibe identificadores y abre su propia sesión; no conserva el `UploadFile` ni la sesión de la petición.

Respuesta `200` — el fichero ya existe en este espacio (mismo `content_sha256`):

```json
{ "document_id": "uuid", "status": "indexed", "duplicate": true }
```

`indexed` es solo un ejemplo: una subida duplicada devuelve el estado real, también `pending`, `processing`, `failed` o `unsupported`.
No reintenta una ingesta fallida. El reintento usa el comando de reindexado de 1.4, con el mismo `document_id`.
Si el documento está en `deleting`, la subida devuelve `409` hasta completar el borrado.
Dos subidas concurrentes se resuelven mediante la restricción de unicidad; la perdedora devuelve la fila ganadora y limpia su temporal.

### `GET /v1/documents` · `GET /v1/documents/{id}` · `DELETE /v1/documents/{id}`

Las tres rutas aceptan `owner_id` como filtro. El listado usa un cursor opaco y un `limit` acotado por configuración.
El orden es estable por `(created_at, id)`; la respuesta contiene `items` y `next_cursor`.
El detalle devuelve estado, contadores y error seguro, sin `storage_path`.

El borrado devuelve `204` solo cuando desaparecen los puntos, el fichero y la fila.
Si hay una ingesta activa, devuelve `409`; si falla una dependencia, devuelve `503` y conserva `deleting` para reintentar.
Repetir el borrado durante `deleting` continúa la limpieza; después de completarlo, devuelve `404`.

### `POST /v1/search` — fase 1

Recuperación directa, sin capa agéntica ni generación.

```json
{
  "query": "condiciones de entrega",
  "top_k": 5,
  "candidates": 30,
  "rerank": true,
  "owner_id": "u_4471",
  "document_ids": ["uuid"]
}
```

`candidates` limita la lista tras RRF y antes del reranking. Se valida `1 <= top_k <= candidates` y los máximos configurados.
Cada rama recupera inicialmente hasta `candidates` puntos. Sus límites se registran en cada evaluación.
`document_ids` omitido no restringe documentos; una lista vacía es inválida y nunca equivale a buscar en todo el tenant.
Los identificadores ajenos o inexistentes no añaden resultados ni revelan su existencia.

El filtro de autorización se aplica en cada rama, en la fusión y en la lectura por identificadores.
Los resultados se comprueban contra documentos `indexed` en PostgreSQL antes de devolver texto o evaluar citas.
Si esta comprobación falla, la petición devuelve `503`; nunca omite la comprobación para continuar.

```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "filename": "contrato.pdf",
      "locator": { "type": "page", "start": 4, "end": 4 },
      "text": "...",
      "score": 0.87,
      "score_type": "reranker",
      "dense_rank": 2,
      "sparse_rank": 1
    }
  ],
  "timings_ms": { "embed": "...", "search": "...", "rerank": "..." }
}
```

`score_type` distingue `rrf` de `reranker`. Ninguno representa una probabilidad calibrada de respuesta correcta.
La consulta nativa de fusión no debe asumirse como fuente de los rangos originales.
`store.py` obtiene también las listas de cada rama para calcular `dense_rank` y `sparse_rank`, con filtros y límites idénticos.
Los rangos empiezan en 1 y valen `null` si el punto no aparece en esa lista.
Estas consultas adicionales cuentan en la latencia; durante ingesta concurrente, los rangos son diagnósticos y no forman una instantánea transaccional.

El reranker puntúa los mismos candidatos y después corta a `top_k`; puede cambiar tanto el orden como los fragmentos finales.
`rerank=false` corta directamente la lista RRF. Las pruebas comparan el conjunto completo antes del corte.

Una búsqueda top-k puede devolver candidatos aunque la respuesta no exista en el corpus.
La fase 1 no promete abstención hasta calibrar y evaluar una política explícita; un score RRF no basta para decidirla.

`timings_ms` contiene números no negativos en milisegundos, nunca cadenas en respuestas reales.
Se miden con reloj monotónico e incluyen espera de capacidad y tiempo total, además de embedding, búsqueda y reranking.
Los ejemplos contienen marcadores hasta disponer de mediciones. Ver "Rendimiento" más abajo.

### `POST /v1/verify` — fase 1

```json
{
  "answer": "El plazo de entrega es de 48 horas y el transporte va incluido.",
  "chunk_ids": ["uuid-1", "uuid-2"],
  "owner_id": "u_4471"
}
```

Los `chunk_ids` se resuelven aplicando el mismo filtro que la búsqueda: `tenant_id` siempre, y `owner_id` si se envía. Un `chunk_id` que no pertenezca al espacio del solicitante se ignora en lugar de puntuarse. Sin esto, `/verify` sería un oráculo con el que sondear fragmentos ajenos dentro del mismo tenant.

```json
{
  "claims": [
    { "text": "El plazo de entrega es de 48 horas.", "verdict": "supported",    "score": 0.94, "best_chunk_id": "uuid-1" },
    { "text": "El transporte va incluido.",         "verdict": "contradicted", "score": 0.88, "best_chunk_id": "uuid-2" }
  ],
  "summary": { "supported": 1, "weak": 0, "unsupported": 0, "contradicted": 1 }
}
```

Cuatro veredictos, según umbrales configurables:

| Veredicto | Significado |
|---|---|
| `supported` | La fuente respalda la afirmación (entailment por encima del umbral) |
| `weak` | Respaldo por debajo del umbral, sin contradicción |
| `unsupported` | Ninguna fuente dice nada al respecto (neutral) |
| `contradicted` | Alguna fuente afirma lo contrario (contradiction) |

`contradicted` se separa de `unsupported` a propósito: son fallos de gravedad muy distinta, y el modelo NLI ya distingue las tres clases. Colapsarlos tiraría la señal más valiosa del verificador.

La decisión se calcula por frase sobre todas las parejas válidas de chunk y ventana:

1. Obtén máximos separados de entailment y contradiction, junto con la evidencia que produce cada máximo.
2. Si contradiction supera su umbral, devuelve `contradicted`, incluso si otra fuente respalda la frase.
3. Si entailment supera su umbral de respaldo, devuelve `supported`.
4. Si entailment supera el umbral inferior de respaldo, devuelve `weak`.
5. En los demás casos, devuelve `unsupported`.

Los umbrales cumplen `0 <= weak_threshold < supported_threshold <= 1`; el umbral de contradicción también pertenece a `[0, 1]`.
`score` es el máximo de contradicción para `contradicted` y el máximo de entailment para los otros veredictos.
`best_chunk_id` identifica su evidencia; es `null` para `unsupported`.
Sin chunks autorizados y disponibles, todas las frases son `unsupported`, con `score=0` y `best_chunk_id=null`.

Se rechazan texto vacío, listas vacías y entradas que superen los límites configurados de frases, chunks o pares NLI.
Los IDs repetidos se deduplican. La hipótesis completa y los tokens especiales cuentan en el límite del modelo.
No se trunca silenciosamente una hipótesis que no cabe: se devuelve `422`.
El mapa de etiquetas se lee de la configuración del modelo, no de un orden de logits supuesto.

Los veredictos son estimaciones del modelo. NLI puede fallar, y concatenar la frase anterior puede alterar el significado evaluado.
La mitigación de correferencia se compara con la frase aislada en 1.8 antes de activarla.

### `POST /v1/query` — fase 2

Igual que `/search` pero con router agéntico. Añade a la respuesta:

```json
{
  "rewritten_queries": ["experiencia con Docker", "administración de servidores"],
  "attempts": 2
}
```

### `POST /v1/answer` — fase 2

Endpoint principal del servicio.

```json
{
  "query": "¿Cuál es el plazo de entrega?",
  "verifier": "nli",
  "top_k": 5,
  "owner_id": "u_4471"
}
```

```json
{
  "answer": "El plazo de entrega estándar es de 48 horas.",
  "citations": [
    {
      "chunk_id": "uuid-1",
      "document_id": "uuid",
      "filename": "contrato.pdf",
      "locator": { "type": "page", "start": 4, "end": 4 }
    }
  ],
  "verification": { "supported": 1, "weak": 0, "unsupported": 0, "contradicted": 0 },
  "rewritten_queries": [],
  "provider": "ollama/qwen3:8b",
  "timings_ms": { "retrieval": "...", "generation": "...", "verification": "..." }
}
```

### `PUT /v1/config/llm` — fase 2

```json
{ "provider": "ollama", "model": "qwen3:8b", "fallback": null }
```

Aplica en la siguiente petición, sin reinicio del servicio. `provider` y `model` se validan contra una lista permitida: llegan desde la API y determinan a quién se factura.

## Decisiones técnicas

Resumen. El razonamiento completo, con las alternativas descartadas, está en [`DECISIONS.md`](DECISIONS.md).

### El LLM se integra en la fase 2, no en la 1

El sistema final ejecuta el LLM dentro de Ragmur. La fase 1 se construye sin él por una razón de método: con generación activa, un resultado incorrecto no permite distinguir si falló la recuperación o el modelo. Midiendo primero la recuperación aislada se obtiene una línea base sobre la que atribuir cualquier cambio posterior.

Los endpoints sin generación permanecen tras la fase 2 como interfaz de bajo nivel y como base de la suite de evaluación.

### Sin frameworks RAG de alto nivel

No se usan LangChain ni LlamaIndex como framework. El pipeline es corto y escribirlo directamente mantiene cada paso explícito y depurable. Se admite `langchain-text-splitters` como utilidad aislada.

### Extracción de PDF con `pypdfium2`, no con PyMuPDF

Se mantiene `pypdfium2` por su licencia permisiva y su extracción por página. La calidad se comprueba sobre el corpus del proyecto.
PyMuPDF ofrece [AGPL o licencia comercial](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).
La decisión evita incorporar esas condiciones; no implica que todo uso de AGPL sea incompatible con código propio bajo MIT.
Ver `DECISIONS.md` §3.13.

### El idioma de la rama léxica es configuración, no un valor por omisión

El BM25 de FastEmbed aplica stemming y eliminación de palabras vacías antes de emitir el vector disperso, y su parámetro `language` vale `english` si no se indica otra cosa. Sobre un corpus en español, eso trocea mal las palabras y deja pasar las vacías del idioma equivocado. Igual que con `modifier=IDF`, **no lanza ningún error**: recupera peor y solo se detecta midiendo.

El valor se declara explícitamente y forma parte de lo que la tarea 1.7 evalúa: con corpus mixto español/inglés hay que comparar `language="spanish"` contra `disable_stemmer=True`, porque un stemmer de un idioma aplicado al otro puede ser peor que ninguno.

Los documentos usan `embed`; las consultas usan `query_embed`. Sus pesos son distintos en la [implementación de FastEmbed](https://github.com/qdrant/fastembed/blob/main/fastembed/sparse/bm25.py).
La configuración registra modelo, versión, idioma, stopwords, stemmer, `k`, `b` y `avg_len`.
Cambiar la tokenización o los pesos documentales requiere reindexar; no se mezclan configuraciones dentro de una colección.

### Fusión RRF en lugar de combinación de scores

Los scores de similitud coseno y BM25 no son comparables; normalizarlos requiere calibración frágil y dependiente del corpus. RRF combina posiciones, no puntuaciones, y funciona sin ajuste. Qdrant lo implementa de forma nativa.

### Verificación por NLI

Un modelo NLI clasifica pares (premisa, hipótesis) como entailment, neutral o contradiction.
La ejecución local evita tarifas por API, pero consume recursos y puede clasificar mal una afirmación.

Se mantiene `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` como candidato inicial.
Su [ficha](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7) documenta evaluación multilingüe y limitaciones de los datos traducidos.
Su rendimiento en Ragmur y la comparación con otras variantes requieren evaluación propia.

Limitaciones asumidas:

1. La segmentación en frases aproxima la descomposición en afirmaciones atómicas, que un LLM realizaría mejor.
2. El contexto del modelo es limitado (~512 tokens); los fragmentos largos se recorren por ventanas conservando la puntuación máxima.
3. Los chunks difieren de las premisas de los conjuntos NLI; los umbrales se calibran en desarrollo y se evalúan con datos reservados.
4. Una frase con referencia anafórica puede producir falsos `unsupported`. Concatenar la frase anterior es una hipótesis que debe evaluarse.

La fase 2 añade `verifier=llm` como alternativa y mide el grado de acuerdo entre ambos. Esa comparación es un resultado del proyecto.

### bge-m3 para embeddings

Multilingüe (corpus mixto español/inglés), buen rendimiento en recuperación, ejecutable en CPU. La interfaz `embedder.py` aísla la decisión por si conviene migrar a embeddings por API.

### Multi-tenancy desde el inicio, en dos niveles

`tenant_id` se propaga desde la API key hasta el filtro de Qdrant; `owner_id` subdivide el espacio del tenant por usuario final. Todo test de búsqueda comprueba ambos aislamientos. Los dos campos viven en el payload de Qdrant, así que introducirlos más tarde obligaría a reindexar el corpus completo.

### Los modelos se cargan al arrancar, no en la primera petición

«Carga perezosa» en este proyecto significa *una sola vez por proceso y reutilizada entre peticiones*, no *diferida hasta que alguien la necesite*. Los modelos se instancian en el `lifespan` de FastAPI y viven en `Resources`, junto al motor de base de datos y al cliente de Qdrant.

La razón es `/ready`: si el chequeo respondiera 200 con los modelos aún sin cargar, el orquestador mandaría tráfico y las primeras peticiones expirarían esperando decenas de segundos de carga. Diferir la carga hasta la primera consulta hace imposible que `/ready` diga la verdad. La contrapartida es un arranque lento, que es exactamente lo que `/ready` existe para comunicar.

### Ingesta, fallos y consistencia

La fase 1 mantiene `BackgroundTasks`, con un único proceso de API y una única instancia escritora sobre sus almacenes.
La [guía de FastAPI](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat) distingue estas tareas de una cola de trabajo independiente.
No hay garantía de ejecución tras un reinicio; una cola durable requiere una decisión posterior y aprobación de dependencias.

Se limita tanto el número de trabajos aceptados como el de trabajos activos.
Un semáforo de ejecución no limita por sí solo las tareas que esperan ni el espacio que consumen sus ficheros.
La inferencia y la extracción no bloquean el event loop; sus límites de concurrencia también se aplican a búsqueda y verificación.

PDFium no admite llamadas simultáneas desde varios hilos, ni siquiera sobre documentos distintos.
La extracción PDF usa un proceso aislado y terminable para hacer efectivo el timeout sin bloquear la API.
Un timeout sobre una espera asíncrona no detiene por sí solo una función nativa en otro hilo.
[Restricción de PDFium](https://pypdfium2.readthedocs.io/en/stable/python_api.html#incompatibility-with-threading).

| Estado | Condición |
|---|---|
| `pending` | Fichero persistido y fila confirmada; trabajo aceptado |
| `processing` | Extracción, troceado o indexado en curso |
| `indexed` | Todos los lotes confirmados por Qdrant y estado confirmado en PostgreSQL |
| `failed` | Error recuperable; original conservado para reintento explícito |
| `unsupported` | Contenido que esta fase no puede procesar, con motivo explícito |
| `deleting` | Borrado iniciado; fila conservada hasta completar la limpieza externa |

PostgreSQL determina qué documentos pueden exponerse. No existe una transacción conjunta entre PostgreSQL, Qdrant y el disco.
El estado `indexed` solo se publica tras confirmar todos los lotes; búsqueda y verificación excluyen los demás estados.
Un fallo parcial puede reducir temporalmente el número de resultados, pero no convierte una ingesta incompleta en un documento disponible.

Antes de aceptar tráfico tras un reinicio, se reconcilian todos los documentos `pending` y `processing` de la instancia anterior.
Se marcan `failed`, se limpian sus puntos parciales y se conserva el original; los documentos `deleting` completan su borrado.
Esta política requiere la instancia única indicada arriba; una comparación por antigüedad no basta para coordinar varios procesos.

Cada operación sobre un documento se serializa. El borrado no puede competir con una tarea que vuelva a insertar sus puntos.
El orden del borrado es: confirmar `deleting`, borrar puntos con confirmación, borrar original y borrar fila.
Si falla un paso, se conserva la fila y se repite la operación de forma idempotente.
Los temporales y originales sin fila se reconcilian al arrancar, solo dentro de `STORAGE_DIR` y con una antigüedad mínima configurada.

El reindexado y el borrado completo de un tenant son comandos de mantenimiento con la API detenida en fase 1.
El reindexado limpia puntos anteriores y parciales antes de escribir; cada lote conserva sus IDs durante los reintentos de la misma ejecución.
El borrado de tenant elimina puntos y ficheros antes de eliminar sus filas; una cascada SQL no limpia almacenes externos.

Las subidas tienen límites de bytes, páginas, texto extraído y expansión de DOCX comprimidos.
La validación combina firma, estructura y decodificación; TXT y Markdown no tienen una firma MIME inequívoca.
Los PDF mixtos requieren detectar páginas sin texto útil y emitir un diagnóstico; una portada vacía no basta para declarar un escaneado.

## Rendimiento

Hardware de referencia del proyecto: **RTX 5080** en homelab, que aloja además Ollama para la fase 2.

La fase 1 conserva un modo CPU para reproducibilidad. El rendimiento relativo de CPU y GPU requiere mediciones sobre el pipeline real.
Cada ejecución registra CPU, GPU, RAM, VRAM, controlador, versiones, precisión, tamaños de lote y concurrencia.

La RTX 5080 usa Blackwell (`sm_120`). La tarea 1.4 fija una combinación compatible de PyTorch, rueda CUDA y controlador.
CUDA 12.8 fue una opción inicial, pero no es la única: [PyTorch 2.12 retira esa rueda y ofrece CUDA 13](https://pytorch.org/blog/pytorch-2-12-release-blog/).
La selección se declara en `pyproject.toml`, con variante CPU para CI, y se valida con inferencia real de cada modelo.
El contenedor debe exponer la GPU mediante NVIDIA Container Toolkit; una imagen cuyo nombre incluya CUDA no garantiza compatibilidad.

Regla: toda cifra de `timings_ms` publicada indica sobre qué hardware se midió. Los ejemplos de este documento llevan `"..."` hasta que existan mediciones reales.

## Evaluación

`eval/golden_set.yaml`:

```yaml
- id: q001
  split: test
  scope: { tenant: demo, owner_id: null }
  query: "¿Cuál es el plazo de entrega estándar?"
  expected:
    - evidence_id: delivery-term
      document: contrato-proveedor
      locator: { type: page, start: 4, end: 4 }
      quote: "El plazo máximo de suministro es de 48 horas."
  note: "aparece como 'plazo máximo de suministro'; la palabra entrega no consta"

- id: q014
  split: test
  scope: { tenant: demo, owner_id: null }
  query: "¿Cuál es la penalización por retraso?"
  expected: []
  note: "negativa: el contrato no menciona penalizaciones. El sistema debe no recuperar nada relevante"
```

`document` referencia una clave estable del manifiesto del corpus, que registra el SHA-256 y la procedencia de cada fichero.
El evaluador resuelve esas claves a los UUID de cada ingesta; un nombre de fichero o `chunk_id` no es una referencia estable.
`quote` identifica la evidencia dentro del localizador; compartir página no convierte cualquier fragmento en relevante.
Un chunk debe contener la cita completa tras normalizar espacios y saltos de línea, dentro del documento y localizador esperado.
Las citas se eligen cortas y suficientes para respaldar la respuesta; los casos ambiguos requieren revisión manual antes de comparar configuraciones.

`expected` enumera unidades de evidencia relevantes. Cada unidad cuenta una sola vez aunque aparezca en varios chunks con solape.
Una lista vacía identifica una consulta negativa; se excluye del denominador de recall, MRR y nDCG y se reporta por separado.
Sin una política de abstención, se inspeccionan sus candidatos, pero no se publica una tasa de rechazo como capacidad del sistema.

El campo `note` documenta por qué una consulta es difícil, y evita que el golden set degenere en casos triviales que siempre pasan.

### Qué métrica mide qué etapa

| Etapa | Métrica | Motivo |
|---|---|---|
| Recuperación antes del corte final | recall@candidates | Mide la cobertura disponible para el reranker |
| Salida de cada configuración | recall@10, hit-rate@10, MRR@10, nDCG@10 | Mide cobertura y orden de los resultados finales |
| Petición completa | latencia p50 y p95 | Incluye espera, filtros y diagnósticos, con hardware y concurrencia |

Por consulta positiva, `recall@k = evidencias relevantes distintas recuperadas / evidencias relevantes esperadas`.
`hit-rate@k` vale 1 si aparece al menos una evidencia y 0 si no aparece ninguna; el informe promedia por consulta.
MRR@10 usa el inverso de la primera posición relevante, o 0; nDCG@10 usa relevancia binaria y descuento logarítmico.
Los resultados que repiten una evidencia ya cubierta aportan ganancia 0 y conservan su posición.
Para nDCG, cada posición acredita como máximo una evidencia nueva; si hay varias, se elige por `evidence_id` ascendente.
Su ranking ideal contiene `min(10, número de evidencias esperadas)` aciertos. Recall sí cuenta todas las evidencias distintas cubiertas.

Reordenar no cambia recall sobre todos los candidatos, pero sí puede cambiar recall@10 al modificar cuáles entran en los diez primeros.
Las cuatro configuraciones usan `top_k=10`, el mismo corpus, filtros y presupuesto de candidatos; el valor de API por defecto sigue en 5.

Se ejecuta sobre las cuatro configuraciones —densa, BM25, híbrida, híbrida + reranking— para atribuir la mejora a cada capa.

Con 25–30 consultas, una muestra pequeña limita la precisión, especialmente después de separar desarrollo, prueba y negativas.
Se reportan el tamaño efectivo y las victorias, derrotas y empates por consulta, además del promedio.
No se afirma significación estadística a partir de una mejora agregada sin analizar su incertidumbre.

Antes de ajustar parámetros, el conjunto se separa en desarrollo y prueba reservada, con casos positivos y negativos en ambos.
Los ajustes usan desarrollo; la prueba reservada se ejecuta con parámetros congelados. Una muestra pequeña produce resultados exploratorios, no garantías generales.
La partición NLI evita compartir documentos o afirmaciones casi duplicadas entre calibración y prueba.

Los resúmenes guardan commit, hash del corpus, partición, revisiones de modelos, configuración y número de consultas positivas y negativas.
El evaluador selecciona cada rama mediante interfaces internas de recuperación; no necesita un parámetro público adicional en `/search`.
La latencia se mide después de calentar modelos, con repeticiones y sin ingesta concurrente; el tiempo de arranque se reporta aparte.
Los objetivos de calidad y latencia se fijan tras la línea base de desarrollo, antes de consultar la prueba reservada.
