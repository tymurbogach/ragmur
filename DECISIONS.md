# Contexto de diseño

Registro de las decisiones tomadas durante el diseño de Ragmur, con sus alternativas descartadas y el motivo. Sirve para que quien retome el proyecto —persona o agente— entienda **por qué** el sistema es como es y no vuelva a abrir discusiones ya cerradas.

Este documento no sustituye a `ARCHITECTURE.md` (qué se construye) ni a `ROADMAP.md` (en qué orden). Explica el razonamiento detrás de ambos.

---

## 1. Objetivo del proyecto

Ragmur es un proyecto de portfolio con un objetivo doble:

- **Técnico:** un servicio RAG reutilizable, consumido por varias aplicaciones propias (portfolio personal, lazytripz, chatbot con datos personales) desde una única instancia multi-tenant.
- **Profesional:** demostrar competencia en RAG con capas de calidad medibles, en un mercado donde abundan las demos superficiales.

La segunda condiciona el diseño más de lo que parece: **el proyecto debe producir cifras, no impresiones.** De ahí que la evaluación sea una tarea de primer nivel y no un extra.

## 2. Origen del alcance

El punto de partida fueron tres "proyectos RAG" presentados como opciones alternativas:

1. RAG con búsqueda híbrida, reranking y verificación de citas.
2. RAG multimodal con OCR y extracción de documentos degradados.
3. RAG agéntico con router de recuperación y reescritura de consultas.

**Decisión: no son tres proyectos alternativos, sino tres capas del mismo sistema con dependencia entre sí.** La opción 3 opera sobre los resultados de la 1; la opción 2 alimenta el índice del que bebe la 1. De ahí el orden de fases: núcleo → agéntico → multimodal.

Motivo del orden: construir lógica agéntica sobre una recuperación deficiente produce resultados igual de malos pero más caros y más difíciles de depurar.

## 3. Decisiones y alternativas descartadas

### 3.1 Orden de fases

**Decidido:** núcleo de recuperación → capa agéntica → ingesta multimodal. Estrictamente secuencial, sin solapamiento.

**Descartado:** empezar por lo agéntico (más vistoso) o por la ingesta multimodal (más aparatoso). La ingesta multimodal es ingeniería de datos, no RAG, y absorbe semanas peleando con parseo de PDF sin aportar aprendizaje de recuperación.

### 3.2 Momento de integrar el LLM

**Decidido:** el sistema final ejecuta el LLM **dentro** de Ragmur (endpoint `/answer`). La fase 1 se construye sin LLM como etapa intermedia deliberada.

**Motivo:** con generación activa desde el principio, un resultado incorrecto no permite distinguir si falló la recuperación o el modelo. Midiendo primero la recuperación aislada se obtiene una línea base sobre la que atribuir cualquier cambio posterior.

**Punto que causó confusión durante el diseño y conviene dejar fijado:** "sin LLM en fase 1" describe una etapa, no un principio del proyecto. Los endpoints sin generación (`/search`, `/query`) permanecen tras la fase 2 como interfaz de bajo nivel y como base de la suite de evaluación, no como modo de uso principal.

### 3.3 Verificación de citas sin LLM

La verificación de citas requiere una afirmación redactada que contrastar. Al no generar texto en fase 1, se resolvió exponiendo `POST /v1/verify`: el cliente envía un texto redactado más los `chunk_ids` citados, y Ragmur devuelve un veredicto por frase.

**Decidido:** verificador basado en un modelo NLI (`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`, ver §7), que clasifica pares (premisa, hipótesis) como entailment / neutral / contradiction.

**Descartado:** usar un LLM como verificador por defecto. Un LLM verificando a otro LLM introduce el mismo riesgo de alucinación que se pretende eliminar, además de coste y dependencia externa.

**Limitaciones asumidas y documentadas:**
- La segmentación en frases aproxima la descomposición en afirmaciones atómicas, que un LLM haría mejor.
- El contexto del modelo NLI es limitado (~512 tokens); los fragmentos largos se recorren por ventanas conservando la puntuación máxima.
- Los chunks difieren de las premisas de entrenamiento NLI; los umbrales se calibran en desarrollo y se evalúan con datos reservados.
- Una referencia anafórica puede causar falsos `unsupported`. Añadir la frase anterior es una hipótesis que debe evaluarse antes de activarla.

La fase 2 añade `verifier=llm` como modo alternativo y **mide el grado de acuerdo entre ambos verificadores**. Esa comparación es un resultado del proyecto, no un detalle de implementación.

### 3.4 Multi-tenancy desde el primer día

**Decidido:** `tenant_id` propagado desde la API key hasta el filtro de Qdrant, implementado en la fase 1.

**Motivo:** el requisito real es servir a varios proyectos propios con corpus separados desde una única instancia. Añadir aislamiento a posteriori obliga a reindexar todo el corpus.

**Descartado:** una colección de Qdrant por tenant. Multiplica el consumo de memoria y complica el mantenimiento sin aportar aislamiento efectivo adicional frente a una colección única con índice de payload sobre `tenant_id`.

Ver también 3.8: el tenant por sí solo no cubre el aislamiento entre usuarios finales.

### 3.5 Sin frameworks RAG de alto nivel

**Decidido:** pipeline escrito a mano. Única excepción, `langchain-text-splitters` como utilidad aislada de troceado.

**Motivo:** el pipeline es corto, y escribirlo directamente mantiene cada paso explícito, depurable y explicable. Para el objetivo profesional del proyecto, "implementado sin framework" pesa más que "invocada una función de librería".

### 3.6 Fusión RRF

**Decidido:** Reciprocal Rank Fusion para combinar la rama densa y la léxica.

**Descartado:** normalizar y sumar scores. Los valores de similitud coseno y BM25 no son comparables, y su calibración es frágil y dependiente del corpus. RRF combina posiciones, no puntuaciones, y funciona sin ajuste.

### 3.7 Lenguaje y stack

**Decidido:** Python 3.12 con FastAPI.

**Motivo:** es el ecosistema de la IA, y FastAPI es el estándar actual para APIs nuevas de este tipo. Complementa la experiencia previa en PHP/Laravel en lugar de sustituirla; el perfil resultante (backend + IA + infraestructura propia) es menos común que el de especialista en un solo lenguaje.

**Contrapartida asumida:** Python concentra una gran oferta de perfiles junior. La diferenciación no viene del lenguaje sino de la especialización: capas de calidad medidas y arquitectura multi-tenant.

---

Las decisiones siguientes se incorporaron tras una revisión del diseño, antes de escribir código.

### 3.8 Segundo nivel de aislamiento: `owner_id`

**Problema detectado.** El requisito de que el usuario final suba sus propios documentos (por ejemplo, facturas) y los consulte "dentro de su propio espacio" no se cumple con `tenant_id` solo. El tenant se deriva de la API key, y la API key la tiene la **aplicación cliente**, no la persona. Si lazytripz tiene N usuarios con facturas privadas, los N comparten `tenant_id` y cualquiera recupera los documentos del resto.

**Descartado:** un tenant por usuario final. Obligaría a un endpoint de aprovisionamiento de tenants, a que la aplicación cliente gestionase N API keys y a custodiar una credencial por usuario. Desproporcionado.

**Decidido:** un campo opcional `owner_id` —texto opaco, definido por la aplicación cliente, típicamente su propio identificador de usuario— que subdivide el espacio del tenant.

- Se acepta en la ingesta y en la búsqueda.
- Si la consulta lo incluye, el filtro de Qdrant es `tenant_id AND owner_id`.
- Si no lo incluye, el filtro es solo `tenant_id`: el tenant ve todo su espacio, que es lo que necesita una aplicación con corpus compartido como el portfolio.

**Asunción explícita:** Ragmur confía en que la aplicación cliente envía el `owner_id` correcto, igual que confía en su API key. La autenticación del usuario final es responsabilidad de la aplicación cliente, no de Ragmur. Este límite es deliberado: llevar la identidad del usuario final dentro de Ragmur exigiría OAuth o JWT propios, y convierte el servicio en un proveedor de identidad, que no es lo que es.

**Motivo de resolverlo ahora y no después:** el mismo que en 3.4. `owner_id` va en el payload de Qdrant, y añadirlo a posteriori obliga a reindexar todo el corpus.

### 3.9 Localizador genérico en lugar de `page`

**Problema detectado.** El diseño original guardaba un número de página por chunk. No es representable fuera del PDF:

- `python-docx` no puede dar número de página: la paginación la calcula el renderizador al maquetar, no está en el XML del documento.
- TXT y Markdown no tienen páginas en absoluto.
- Con chunks de 800 caracteres, un chunk cruza frontera de página con frecuencia, así que un único número de página por chunk es incorrecto incluso en PDF.

**Decidido:** un localizador con tipo, que cada extractor rellena con lo que su formato puede sostener.

```json
{ "locator": { "type": "page",    "start": 4, "end": 5 } }
{ "locator": { "type": "section", "value": "3.2 Plazos", "path": ["3.2 Plazos"], "ordinal": 3 } }
{ "locator": { "type": "offset",  "start": 12040, "end": 12840 } }
```

El consumidor siempre recibe algo con lo que señalar la fuente; qué precisión tenga depende del formato de origen. `documents.page_count` pasa a nullable por el mismo motivo.

### 3.10 Deduplicación por hash de contenido

**Problema detectado.** Subir dos veces el mismo fichero duplica sus chunks en el índice. Los duplicados copan el `top_k`, degradan la recuperación real e **inflan artificialmente el recall del golden set**. Dado que el valor del proyecto son sus cifras, contaminar las cifras es un fallo de primer orden.

**Decidido:** `content_sha256` calculado sobre los bytes del fichero, con unicidad por `(tenant_id, owner_id, content_sha256)`. Una segunda subida idéntica devuelve `200` con el `document_id` existente, en lugar de `202` y un documento nuevo.

### 3.11 Claves de API en tabla propia

**Problema detectado.** El diseño original guardaba `api_key_hash` en la tabla `tenants`, con restricción de unicidad: una clave por tenant, para siempre. Sin rotación, sin claves distintas por entorno, y sin poder revocar una clave filtrada salvo cortando el servicio a esa aplicación.

**Decidido:** tabla `api_keys` separada, con el modelo habitual de token con prefijo público (equivalente a Laravel Sanctum). La clave tiene forma `rgm_<key_id>_<secret>`: se localiza el registro por `key_id`, que está indexado, y se compara el secreto en tiempo constante.

**Decidido también:** el hash es **HMAC-SHA256 con una clave de servidor, no bcrypt ni argon2.** Los algoritmos de hash de contraseñas están diseñados para ser lentos a propósito, porque defienden secretos de baja entropía elegidos por humanos. Una API key es un secreto aleatorio de alta entropía generado por el servidor: no hay ataque de diccionario que frenar, y el coste deliberado (~100 ms) se pagaría en **cada petición** al servicio.

### 3.12 Capa de acceso a PostgreSQL

**Decidido:** SQLAlchemy 2.0 en estilo declarativo tipado, con `asyncpg` como driver y Alembic para migraciones.

**Motivo:** SQLAlchemy 2.0 tiene soporte de tipos real, que es lo que permite que `mypy` cubra también la capa de datos. Alembic es el equivalente directo a las migraciones de Laravel. La decisión estaba implícita en el árbol de directorios (`db/models.py`, `db/migrations/`) y en los comandos documentados, pero sin fijar; se fija aquí.

**Descartado:** `asyncpg` en crudo con SQL manual. Permite migraciones, pero exige mantener más mapeo y contratos de tipos por cuenta propia.

---

Las decisiones siguientes se incorporaron tras una revisión completa del plan contra el estado real de las bibliotecas, antes de abrir la tarea 1.1.

### 3.13 Extractor de PDF: `pypdfium2`, no PyMuPDF

**Problema detectado.** PyMuPDF ofrece AGPL o licencia comercial; el proyecto busca dependencias permisivas y mantiene MIT como licencia prevista.
La [documentación de PyMuPDF](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) describe ambas opciones.
La redacción anterior confundía esta preferencia con una incompatibilidad absoluta entre cualquier uso de AGPL y código propio bajo MIT.

**Decidido:** mantener `pypdfium2`, con licencia permisiva y extracción por página.
La calidad y velocidad sobre el corpus propio se verifican; no se presupone equivalencia con otro extractor.

**Descartado:**
- *Comprar licencia comercial de PyMuPDF a Artifex.* Desproporcionado para un proyecto de portfolio.
- *Cambiar la licencia del proyecto a AGPL.* Resolvería el conflicto legal, pero un proyecto de portfolio bajo AGPL es notablemente menos reutilizable por quien lo lea, que es justo el objetivo profesional del punto 1.
- *`pypdf`.* Alternativa permisiva disponible; no se sustituye el extractor elegido sin evidencia sobre el corpus.

**Reversible con datos.** Si la extracción falla, se comparan alternativas y sus licencias antes de acordar un cambio.
Cambiar la licencia del proyecto no es la única opción posible.

### 3.14 El corpus del IDF se acota al tenant

**Decisión anterior, ahora obsoleta.** El diseño aceptaba como asunción que, con colección única, el IDF sería global sobre todos los tenants y el corpus de uno influiría en la puntuación léxica de otro.

**Ya no hace falta asumirlo.** Qdrant 1.19 —la versión fijada en `docker-compose.yml`— añade un parámetro `idf` en `SearchParams` que acepta un filtro de payload para acotar la población sobre la que se calculan las estadísticas. Se pasa el mismo filtro de tenant que ya lleva la consulta:

```python
models.SearchParams(idf=models.IdfCorpusParams(corpus=tenant_filter))
```

**Consecuencia:** el suelo de `qdrant-client` es `>=1.19` y se comprueba también la capacidad del servidor.
Omitir el parámetro mantiene estadísticas globales; un cliente antiguo no garantiza aceptar un parámetro desconocido sin error.
La implementación debe fallar si no puede aplicar el corpus requerido, no retirar el parámetro para continuar.

**Precisión de alcance:** el corpus incluye también `owner_id` cuando existe, para evitar influencia léxica de otros usuarios del tenant.
El filtro `document_ids` restringe los resultados, pero mantiene las estadísticas del espacio autorizado.
[Referencia de Qdrant 1.19](https://qdrant.tech/blog/qdrant-1.19.x/#per-tenant-idf-statistics).

### 3.15 El fichero original se conserva en disco

**Problema detectado.** El reindexado de 1.4 necesita releer el original y el modelo de datos no indicaba dónde conservarlo.
La deduplicación, por sí sola, requiere el hash y la fila existente; no necesita releer el original.

**Decidido:** los bytes se guardan bajo un `STORAGE_DIR` configurable y la fila de `documents` lleva `storage_path`. El borrado de un documento —y el de un tenant completo— elimina también sus ficheros.

**Descartado:** guardar los bytes en la propia tabla. Simplifica el borrado en cascada, pero infla la base de datos y sus copias de seguridad con contenido que nunca se consulta por SQL.

**Por qué importa ahora:** la tarea 1.7 termina reajustando los parámetros de troceado con los datos de evaluación, lo que regenera todos los chunks. Sin el fichero original, ese reajuste —que está previsto y es el objetivo de la fase— obligaría a volver a subir el corpus entero a mano.

### 3.16 Unicidad de la deduplicación con `owner_id` nulo

**Problema detectado.** La restricción `unique (tenant_id, owner_id, content_sha256)` no detecta duplicados cuando `owner_id` es nulo, porque PostgreSQL no considera iguales dos `NULL` dentro de una restricción de unicidad. `owner_id` es nulo precisamente en los documentos del propio tenant, que es el caso del portfolio: la deduplicación habría fallado en su escenario principal, en silencio, y contaminando las cifras de 1.7 tal como advierte §3.10.

**Decidido:** declarar la restricción con `NULLS NOT DISTINCT` (`postgresql_nulls_not_distinct=True` en SQLAlchemy). Requiere PostgreSQL 15 o superior; el proyecto usa 17.

**Descartado:** una columna generada que sustituya el nulo por una cadena centinela, o dos índices parciales. Ambas funcionan y las dos añaden un artefacto que hay que recordar al leer el esquema, cuando el motor ya ofrece la cláusula exacta.

**Consecuencia asumida.** La unicidad incluye `owner_id`, así que el mismo fichero subido por N usuarios de un tenant produce N copias de sus chunks. Es el precio del aislamiento por usuario final; implica que una consulta a nivel de tenant puede recibir fragmentos idénticos repetidos en el `top_k`.

### 3.17 El idioma de la rama léxica es una decisión, no un valor por omisión

**Problema detectado.** El BM25 de FastEmbed aplica stemming y eliminación de palabras vacías antes de emitir el vector disperso, y su parámetro `language` vale `english` si no se indica. Sobre corpus en español, eso trocea mal las palabras y filtra las vacías del idioma equivocado. Como con `modifier=IDF`, **no lanza ningún error**: recupera peor y solo se detecta midiendo.

**Decidido:** el idioma se declara explícitamente y la elección entra en el alcance de la evaluación de 1.7, comparando `language="spanish"` contra `disable_stemmer=True` sobre el corpus real. Con corpus mixto español/inglés no hay respuesta evidente: un stemmer del idioma equivocado puede ser peor que ninguno.

### 3.18 Los modelos se cargan al arrancar

**Ambigüedad detectada.** «Carga perezosa» aparecía en las convenciones y en la tarea 1.4, mientras 1.9 define `/ready` como «modelos cargados». Son incompatibles: si la carga se difiere a la primera petición, `/ready` no puede decir la verdad, y el orquestador manda tráfico a un proceso cuyas primeras peticiones expirarán esperando decenas de segundos.

**Fijado:** «carga perezosa» significa *una sola vez por proceso y reutilizada entre peticiones*, no *diferida hasta que alguien la pida*. Los modelos se instancian en el `lifespan` y viven en `Resources`. La contrapartida —arranque lento— es exactamente lo que `/ready` existe para comunicar.

### 3.19 Consistencia de la ingesta en una instancia

**Refinamiento:** se mantienen `BackgroundTasks`, PostgreSQL, Qdrant y disco, con una sola instancia escritora en fase 1.
No existe una transacción entre esos tres almacenes; la recuperación tras fallos debe ser explícita.

PostgreSQL determina la disponibilidad mediante `indexed`. Búsqueda y verificación comprueban ese estado antes de exponer texto.
El borrado usa `deleting` y conserva la fila hasta confirmar la limpieza externa; la tarea 1.2 incorpora el estado mediante migración.
Los trabajos interrumpidos, incluidos `pending`, se reconcilian al arrancar; los reintentos son explícitos.

**Alternativas:** una cola durable facilita reintentos automáticos, pero añade infraestructura y una dependencia aún no aprobada.
Versionar generaciones activas permite reindexar sin interrupción, pero esa capacidad sigue fuera de la fase 1.
El reindexado y el borrado de tenant usan mantenimiento con la API detenida.

### 3.20 Métricas sobre evidencias y datos reservados

**Corrección:** recall mide la fracción de evidencias relevantes recuperadas; hit-rate mide si aparece al menos una.
Reordenar conserva recall sobre todos los candidatos, pero puede cambiar recall@10 tras el corte final.

El corpus usa identificadores estables, hashes y evidencias localizadas; los chunks repetidos no generan ganancia adicional.
Las negativas se reportan por separado. Los parámetros se ajustan en desarrollo y se evalúan sobre una partición reservada.
El mismo principio se aplica a los umbrales NLI; el acuerdo de dos modelos no demuestra que sus respuestas sean correctas.

### 3.21 Coste de los rangos por rama

Se conserva RRF nativo y el contrato que expone rangos de las ramas.
`store.py` consulta también cada rama para obtener esos rangos y contabiliza ese coste en la latencia.
Durante escrituras concurrentes, esos diagnósticos no representan una instantánea transaccional; la evaluación usa un corpus inmóvil.

Fusionar en la aplicación evitaría repetir búsquedas, pero cambiaría la decisión de usar RRF nativo.
Eliminar los rangos reduciría el coste y también la observabilidad prevista; ninguna alternativa se introduce de forma implícita.

### 3.22 Veredictos NLI definidos y acotados

Los máximos de entailment y contradiction se conservan por separado; una contradicción sobre umbral tiene precedencia (refinado en §3.36: el apoyo fuerte con margen gana a la contradicción aislada).
Esta política evita declarar respaldo sin advertencia cuando dos fuentes discrepan, aunque puede aumentar falsos negativos.
La evaluación mide ese compromiso y la tasa de respaldo falso.

La entrada tiene límites de tamaño y pares; las ventanas reservan espacio para la hipótesis y los tokens especiales.
Una hipótesis demasiado larga se rechaza, en lugar de comprobar solo una parte sin indicarlo.

### 3.23 Dependencias por tarea

La lista de tecnologías del diseño no autoriza instalar paquetes nuevos. Cada tarea justifica y solicita sus dependencias antes de incorporarlas.
La tarea 1.1 usa la biblioteca estándar y las dependencias actuales; `argparse`, `secrets`, `hmac` y `hashlib` cubren su necesidad.

La tarea 1.2 debe proponer `python-multipart`, `pypdfium2` y `python-docx`, con versiones y licencias verificadas.
Las tareas 1.4, 1.6 y 1.8 proponen su runtime ML y fijan revisiones de modelos; no se instalan en esta revisión.
El troceado y la lectura del conjunto YAML también deben resolver su dependencia concreta antes de implementarse.

### 3.24 Excepciones de conexión y salud en `store.py`

La regla 8 exceptúa únicamente `create_client()` y `ping()` del argumento obligatorio `tenant_id`.
Estas funciones preparan una conexión compartida y comprueban el servidor, sin leer ni escribir documentos o fragmentos.
Exigirles un tenant introduciría un identificador sin función de aislamiento.

Las operaciones de datos mantienen `tenant_id` como primer argumento obligatorio y sus filtros de autorización.
La tarea 1.5 verifica los imports y las firmas; las excepciones no permiten acceso a datos sin tenant.

### 3.25 Estado tras la extracción

La fase 1.2 añade `extracted` para una extracción completada sin índice.
La fase 1.4 vuelve a leer el original y publica `indexed` después de indexar.
Mantener `processing` indicaría un trabajo activo que ya terminó.

La ingesta usa `python-multipart` 0.0.33 para formularios y `pypdfium2` 5.15.2 para PDF.
Usa `python-docx` 1.2.0 para DOCX. Sus licencias son Apache 2.0, BSD-3-Clause y Apache 2.0,
y MIT, respectivamente. `pypdfium2` incluye también las licencias de sus componentes.

### 3.26 Runtime de embeddings

El modo predeterminado usa PyTorch 2.12.0 para CPU, Sentence Transformers 6.2.0 y FastEmbed 0.9.1.
PyTorch ejecuta BGE-M3; Sentence Transformers aplica el modelo denso y su tokenizador.
FastEmbed implementa BM25 y distingue los pesos de documentos y consultas.
Hugging Face Hub descarga revisiones concretas; las dependencias anteriores no ofrecen estas funciones.
La instalación opcional prepara PyTorch 2.12.0 con CUDA 13.0 sin cambiar el controlador del equipo.
La resolución de dependencias se comprobó para ambos modos. La inferencia real solo se ha probado en CPU.
CUDA 13.0 GA requiere el [controlador Linux 580.65.06 o posterior](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html).
La prueba en RTX 5080 y la combinación efectiva de controlador quedan pendientes.
Cierre: GPU validada en Skynet el 2026-11-19; demo pública descartada (ver 3.33).

### 3.27 Búsqueda previa al reranking

La tarea 1.5 usa RRF con `k=2`, el valor predeterminado de Qdrant.
La configuración se registra en la respuesta. No se ajusta sin evaluación.
Desde 1.6, `rerank=true` es el valor inicial; `false` conserva el orden RRF.

### 3.28 Reranking en CPU y CUDA

El reranker usa `BAAI/bge-reranker-v2-m3` con revisión `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`.
Sentence Transformers lo ejecuta como cross-encoder con puntuaciones sin sigmoid.
El modelo tiene licencia Apache 2.0. Las puntuaciones no son probabilidades calibradas.
La medición preliminar en CPU está en `benchmarks/reranking-cpu-2026-11-10.md`.

### 3.29 Evaluación 1.7 con corpus mixto

El golden set usa 35 documentos y 27 consultas de SQuAD 2.0 y XQuAD en inglés y español.
El [resumen de CPU](eval/results/summary-2026-11-10T141148917615Z-all.json) registra parámetros y resultados por etapa.
La línea base es poco discriminativa: las cuatro configuraciones alcanzan recall@10 1.0 en 20 consultas positivas.
Se conservan troceado 800/120 y `top_k` 5 en API. Esta muestra no demuestra una mejora general.

### 3.30 Verificación NLI y umbrales

El verificador usa `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` con revisión `b5113eb38ab63efdd7f280f8c144ea8b13f978ce`.
Los umbrales 0.75/0.5/0.75 son provisionales. La [prueba funcional](eval/results/nli-test-2026-11-11.json) contiene nueve afirmaciones manuales y no justifica una calibración.
Falta evaluar fragmentos reales, incluidas negaciones, cifras, fechas y correferencias, con particiones por documento.
Cierre: umbrales 0.75/0.5/0.75 calibrados en desarrollo y evaluados en reserva el 2026-11-18 (ver `ROADMAP.md` 1.8).

### 3.31 Cierre operativo de la fase 1

`/health` indica proceso vivo y `/ready` comprueba PostgreSQL, Qdrant y modelos cargados. El límite por clave devuelve 429 con `Retry-After`; la capacidad de ingesta y las dependencias caídas devuelven 503. El borrado de tenant exige API detenida y elimina puntos, ficheros y filas. El contenedor instala la rueda CPU por defecto y la variante CUDA con `INSTALL_CUDA=true`, con volúmenes para modelos y `STORAGE_DIR`. Licencia MIT con titular confirmado.

### 3.32 Exposición pública de la demo

**Decidido:** tenant público dedicado (D1) con solo documentos del manifiesto y `owner_id=ue-publico`, más proxy inverso simple con lista permitida (D2 nginx).
La clave de demo es dedicada y se verifica contra `api_keys` (`key_id`, `tenant_id`, `revoked_at`); la clave de ingesta nunca la usa el proxy.
Sin alcances por clave, sin migración, sin BFF en Python.
Rutas públicas: `GET /health`, `POST /v1/search`, `POST /v1/verify`.
Todo lo demás devuelve 404 en el proxy, incluidos `/ready`, `/docs`, `/redoc`, `/openapi.json` y `/v1/documents*` (D5).
Túnel de salida sin puerto entrante; el proveedor se confirma al aprobar el diseño (D3).
Con Cloudflare Tunnel, el proxy recupera la IP del visitante con `CF-Connecting-IP` y `set_real_ip_from` acotado a la dirección única del conector; con Tailscale Funnel en HTTP no hay IP de cliente y el límite por IP exige TCP con `--proxy-protocol` o no existe.
Redes separadas `edge` e `internal`; la clave viaja en un fichero incluido fuera de Git, sin `envsubst`.
Demo solo API con ejemplos `curl`, sin página y sin CORS (D4).
Objetivo p95 provisional para `/search` con rerank en RTX 5080, a medir en F05d (D6).

**Motivo:** el tenant dedicado es el control principal; el proxy solo filtra y limita.
Fijar la versión de nginx y del conector deja el despliegue reproducible.

**Descartado:**
- *Alcances por clave.* Exigiría migración y lógica nueva para un beneficio que ya da el tenant dedicado.
- *BFF en Python.* Añade código propio y reescritura JSON sin control nuevo frente al proxy simple.
- *Caddy.* Alternativa válida, pero con menos evidencia operativa reunida para este despliegue.
- *Reenvío de puertos.* Abre entrada y exige firewall, DNS y TLS propios frente al túnel saliente.

### 3.33 Cierre privado de 1.9 sin demo pública

**Decidido (usuario, 2026-11-19):** la demo pública no es necesaria; 1.9 cierra
en privado. F05e queda descartada. F05d desplegó la imagen endurecida en
Skynet (usuario `ragmur` UID 10000, CUDA) y midió en RTX 5080: `/search` con
rerank p50 251 ms / p95 293 ms (conc=1), p95 859 ms (conc=4), saturación con
cola ordenada desde conc=16 sin 500; `/verify` 143 ms. Límites finales sin
cambiar código: `INFERENCE_MAX_REQUESTS=16`, cuota 60/min por clave, tasas
nginx 5r/s como valor de diseño para una hipotética exposición. Sin plazo de
retención de logs por días (rotación por tamaño). Detalle en
`benchmarks/load-gpu-2026-11-19.md`.

**Motivo:** el uso previsto es privado; exponer no aporta y añade superficie
(GPU, DNS/TLS, túnel). El proxy de F05b queda validado en local por si se
reabre la exposición en el futuro.

### 3.34 Banco de pruebas con agentes lectores

**Decidido (usuario, 2026-11-21):** la fase 1 está cerrada y la fase 2 queda abierta.
`/search` y `/verify` siguen funcionando sin ningún LLM.
En `eval/`, el LLM actúa solo como lector bajo prueba: recibe fragmentos
recuperados y responde sobre ellos. La respuesta correcta sale del dataset o
de la construcción del caso, nunca del LLM. Ningún LLM juzga la aceptación.
Las cifras obtenidas con LLM se publican aparte de las cifras de fase 1.

**Motivo:** la línea base de fase 1 mide solo recuperación. Para medir cuánto
aporta el LLM como lector hace falta un banco donde el contexto esté fijado
de antemano y la puntuación sea contra etiquetas humanas. XQuAD-es abre el
banco; después siguen NoMIRACL-es (abstención) y SciFact como lector NLI.
El modelo local queda fijado para reproducibilidad.

**Contrafactual emparejado.** El control contrafactual usa los mismos
fragmentos de la caché, con la respuesta sustituida por la de otra pregunta
del mismo artículo. No usa un tenant aparte: el IDF se acota por tenant
(ver §3.14), así que otro tenant cambiaría las estadísticas léxicas y el
par dejaría de estar emparejado.

**Descartado:**
- *Generador de conjuntos de prueba de RAGAS.* Depende de LangChain como
  framework, lo que choca con la regla 6. Sirve como métrica en 2.4, no como
  fuente de casos.
- *Agentes de código (Claude, OpenCode) como lectores.* No escalan a miles de
  llamadas y su comportamiento no es reproducible entre versiones. El lector
  es un modelo fijado por identificador, con prompt y semilla congelados.
- *LLM como fuente de etiquetas o como juez de aceptación.* Las etiquetas
  propuestas por IA nunca son verdad: precedente F01 en `eval/NLI.md`, donde
  dos reservas generadas por IA quedaron quemadas y excluidas como oro.
  El acuerdo entre dos modelos tampoco demuestra corrección.

**Dependencia nueva (regla 9): `litellm==1.108.2`.**
Frente a `httpx` directo, LiteLLM ofrece una sola interfaz para
`lm_studio/`, `ollama/` y los proveedores remotos previstos
en 2.1, más el recuento de tokens de uso por petición. Licencia MIT.
Corrección: la versión 1.108.2 no trae ruta `opencode_go/`. OpenCode Go se
usa con prefijo `openai/`, `api_base` de Go y cabecera `x-opencode-session`.
El banco de pruebas usa un modelo local fijo o un proveedor que permita
evaluación por lotes. OpenCode Go solo sirve para humo puntual, salvo que
el usuario decida otra cosa. Go está diseñado para tráfico de agentes de
código. Su uso está monitorizado y el cupo de 5 horas y el semanal son
compartidos.
Peso transitivo: `openai`, `tiktoken`, `tokenizers`, `huggingface-hub`,
`aiohttp`, `boto3` y otros. La versión 1.107.0 quedó marcada como
comprometida por el propio proveedor el 2026-10-21, así que la versión queda
fijada en `uv.lock` y no se acepta un rango abierto.
Medido en `uv.lock`: `filelock` baja de 4.2.10 a 3.32.7, `certifi` sube de
2026.7.22 a 2026.11.20, y `openai` 3.57.0 trae `httpx2`/`httpcore2` (nombres
renombrados por el propio `openai`, conviven con `httpx`/`httpcore`) más
`truststore`.
Arranque sin red: `provider.py` fija `LITELLM_LOCAL_MODEL_COST_MAP=True`
antes de importar `litellm`, así no descarga el mapa de costes de modelos al
importar (verificado en `litellm/__init__.py`: `get_model_cost_map(url=...)`
corre en el import; el propio `get_model_cost_map.py` documenta la variable
como interruptor). Sin `noqa E402`: ruff 0.16.2 exime `os.environ.setdefault`
previo a imports (comprobado: `print()` sí dispara E402, `setdefault` no);
añadir el `noqa` rompería `RUF100` y con él `ruff check`.

## 4. Aclaraciones conceptuales fijadas

Puntos que se aclararon durante el diseño y que conviene no volver a confundir:

| Confusión | Aclaración |
|---|---|
| "Entrenar los embeddings" | Los modelos de embeddings **no se entrenan**. Se usa un modelo preentrenado (bge-m3) para convertir texto en vectores. |
| "La búsqueda vectorial busca palabras literales" | La búsqueda densa opera por **significado**; BM25 es la que opera por coincidencia literal. La búsqueda híbrida combina ambas porque cubren fallos distintos. |
| "La fase 1 no usa IA" | La fase 1 no usa **LLM**. Sí usa modelos: embeddings, cross-encoder de reranking y NLI de verificación. Ninguno requiere GPU; todos funcionan en CPU. |
| "La fase 3 hace falta para subir PDFs" | Ingerir PDF con capa de texto es extracción programática y pertenece a la fase 1. La fase 3 solo resuelve documentos **escaneados o fotografiados**, que carecen de texto extraíble. |
| "Cliente" en la documentación | Significa **aplicación cliente** (la que consume la API), no cliente de pago. |
| "La redacción la hace el cliente" | Cierto **solo en fase 1**. En el estado final, `/answer` redacta dentro de Ragmur. |
| "El tenant aísla a cada usuario" | El tenant aísla a cada **aplicación cliente**. El aislamiento entre usuarios finales de una misma aplicación lo da `owner_id` (ver 3.8). |
| "El reranking no cambia recall@10" | Conserva los candidatos, pero puede cambiar los diez primeros. Se comparan cobertura antes del corte y métricas de salida. |

## 5. Requisitos explícitos

- Desarrollo modular y estrictamente secuencial: no se abre una fase hasta cerrar la anterior por completo, evaluación incluida.
- Proveedor de LLM intercambiable **en caliente**, sin reinicio: modelos locales (Ollama sobre RTX 5080) y remotos (OpenAI, Anthropic, Gemini). Implementado con LiteLLM y configuración por tenant.
- Varios proyectos propios consumiendo la misma instancia con corpus completamente aislados.
- Ingesta de documentos por parte del usuario final (por ejemplo, facturas) consultables dentro de su propio espacio. Resuelto mediante `owner_id` (ver 3.8).

## 6. Criterios de calidad no negociables

1. Ninguna afirmación sobre la calidad de recuperación sin una cifra que la respalde, procedente de `eval/`.
2. Parámetros de troceado, `top_k` y umbrales ajustados con datos de evaluación, nunca por intuición.
3. Todo test de recuperación comprueba el aislamiento entre tenants, y entre `owner_id` dentro de un mismo tenant.
4. Las limitaciones conocidas se documentan en lugar de ocultarse; son parte del resultado del proyecto.
5. Cada cifra identifica su etapa: recall@candidates antes del reranking; recall@10, MRR@10 y nDCG@10 sobre la salida final.
6. Toda cifra de latencia se publica indicando el hardware sobre el que se midió.

## 7. Hardware de referencia

Las mediciones del proyecto se toman sobre el homelab propio: **RTX 5080**, que aloja además Ollama para la fase 2.

Los modelos previstos conservan un modo CPU para reproducibilidad. No hay mediciones propias que demuestren una relación concreta entre latencias CPU y GPU.
El informe registra hardware, precisión, lote y concurrencia, además de versiones.

**Corrección de compatibilidad.** CUDA 12.8 fue una opción inicial para Blackwell, no una restricción permanente.
[PyTorch 2.12](https://pytorch.org/blog/pytorch-2-12-release-blog/) retira esa rueda y recomienda CUDA 13 para Blackwell, con controlador compatible.
La tarea 1.4 fija la combinación validada y una variante CPU para CI; no cambia el controlador del equipo como efecto secundario.

**Modelo NLI.** Se mantiene `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` como candidato inicial.
Su [ficha](https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7) no demuestra superioridad sobre otras variantes en el corpus de Ragmur.

### 3.35 Umbral de respaldo 0.90 (U02-VER iteración 1)

**Decidido:** el umbral de respaldo (`verify_supported_threshold`) sube de 0.75 a 0.90.
Los 125 falsos apoyos de práctica son errores seguros del modelo (respaldo alto, contradicción casi nula, margen mínimo 0,60), así que ningún margen ni rasgo barato los separa de los apoyos correctos; solo el umbral los recorta. Medido en práctica (Skynet, 3124 pares): respaldo falso 0,0702 → 0,0472, recall de apoyo 0,5763 → 0,5048 (suelo 0,50). Las celdas esperadas de `nli_data.py` se recalibran a la nueva conducta en el mismo cambio.

### 3.36 El respaldo fuerte con margen gana a una contradicción aislada (D7)

**Decidido (usuario, 2026-11-24):** en `/verify`, una contradicción sobre su umbral ya no vence siempre. Si el entailment supera el umbral de respaldo (0,90) y aventaja a la contradicción en el margen de conflicto (`verify_conflict_margin`, 0,15 por defecto), el veredicto es `supported`.

**Motivo:** con la precedencia absoluta, una sola fuente ruidosa con contradicción sobre 0,75 envenenaba la frase aunque otra la respaldase con 0,95. Medido en práctica (InferES, matrices de distractores): verdades marcadas como contradichas 5,1 % con un texto, 11,1 % con tres y 14,1 % con cinco. En la fase 2, `/answer` cita varios fragmentos, así que el coste crecía con cada cita añadida.

**Alcance exacto:** con un solo fragmento el margen nunca cambia nada: entailment y contradiction salen de la misma distribución y suman como mucho 1, así que entailment alto obliga a contradicción casi nula. La regla solo actúa con máximos de fragmentos distintos. La cifra principal del arnés (respaldo falso y recall de apoyo sobre la matriz de un texto) queda intacta por construcción; lo que se mide son las matrices de 3 y 5 textos.

**Medido (Skynet, RTX 5080):** suite 493 pasados, 0 fallos y 11 saltos conocidos sobre `4642727` (20261124T025240-5af7e162). Verdades contradichas con 3 textos: 149→138; con 5 textos: 189→174. Respaldo falso y recall de apoyo sin cambio. Celdas de 3 y 5 textos recalibradas al valor medido y verificadas en verde sobre `ac6b273` (20261124T025744-1508a4ad, salida 0); las de 1 texto quedan iguales.

**Coste asumido:** un conflicto real donde el respaldo domina en margen se declara `supported` en lugar de `contradicted`. La contradicción conserva la precedencia cuando el margen no se alcanza.

**Réplicas:** la ruta del servicio y `eval/phase1/nli_data.py` (réplica declarada de la ruta) aplican la misma regla y el test D7 pasa de `xfail` a normal. `eval/nli_run.py` conserva la cadena histórica: es el instrumento del protocolo F01, puntúa cada hipótesis contra una premisa única y allí el margen no puede dispararse.

### 3.37 Las continuaciones empiezan en frontera de palabra (D5)

**Decidido (usuario, 2026-11-24):** el troceador adelanta el inicio de cada continuación hasta la frontera de palabra más cercana dentro del solape, en lugar de cortar en `fin - solape` sin más.

**Motivo:** el 64 % de las continuaciones medidas (4.236 de 6.562, prototipo del 2026-11-22) empezaba a mitad de palabra. Ese prefijo truncado ensucia el embedding denso del fragmento y la premisa que recibe el verificador NLI.

**Límite asumido:** si el solape no contiene ninguna frontera (palabra más larga que la ventana), el inicio queda al final del fragmento anterior. La cobertura del texto normalizado prevalece sobre la frontera de palabra, y la reconstrucción sin pérdida no cambia. El solape efectivo puede quedar por debajo del configurado; es un máximo, no una garantía.

## 8. Trabajo posterior contemplado

Solo tras cerrar las tres fases: servidor MCP sobre Ragmur, ingesta incremental sin downtime, cache de embeddings de consultas frecuentes, panel de administración.

---

## Glosario

- **RAG** — Retrieval-Augmented Generation. Recuperar fragmentos relevantes de un corpus propio y aportarlos como contexto al generar una respuesta.
- **Embedding** — Representación numérica de un texto que permite comparar significados por proximidad vectorial.
- **BM25** — Algoritmo clásico de recuperación léxica, por coincidencia de términos. Sin modelo de por medio.
- **IDF** — *Inverse Document Frequency*. Componente de BM25 que da más peso a los términos raros del corpus que a los frecuentes. Sin él, BM25 puntúa solo por repetición y pierde precisamente lo que aporta frente a la búsqueda densa.
- **Búsqueda híbrida** — Combinación de recuperación densa (semántica) y léxica (BM25).
- **RRF** — Reciprocal Rank Fusion. Fusión de varios rankings por posición en lugar de por puntuación.
- **Cross-encoder** — Modelo que procesa consulta y fragmento conjuntamente para puntuar relevancia con mayor precisión que la comparación de vectores. Se aplica solo a un conjunto reducido de candidatos por su coste.
- **Reranking** — Reordenación de los candidatos recuperados mediante un cross-encoder.
- **NLI** — Natural Language Inference. Clasificación de un par (premisa, hipótesis) como entailment, neutral o contradiction. Base de la verificación de citas.
- **Chunk** — Fragmento en que se divide un documento antes de indexarlo.
- **Tenant** — Espacio aislado dentro del servicio, correspondiente a una aplicación cliente: sus documentos, su índice y su configuración.
- **`owner_id`** — Subdivisión opcional del espacio de un tenant, correspondiente a un usuario final de la aplicación cliente.
- **Localizador** — Referencia a la posición de un chunk dentro de su documento de origen: página, sección o desplazamiento, según lo que el formato permita.
- **recall@k**: fracción de evidencias relevantes distintas recuperadas entre las esperadas, promediada sobre consultas positivas.
- **hit-rate@k**: proporción de consultas positivas con al menos una evidencia relevante entre los primeros k resultados.
- **MRR** — Mean Reciprocal Rank. Media del inverso de la posición del primer resultado correcto. Sensible al orden, no solo a la presencia.
- **nDCG@k** — Normalized Discounted Cumulative Gain. Mide la calidad del orden de los k primeros resultados. Es la métrica adecuada para el reranking, que reordena sin añadir.
- **Golden set** — Conjunto versionado de consultas con su fuente esperada, usado para medir la recuperación de forma reproducible.
