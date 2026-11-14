# Comprobación de copia y restauración de Skynet — 2026-11-13

Informe de la verificación de una copia actual de PostgreSQL y de los
originales del despliegue privado de Skynet, restaurada de forma aislada,
con reconstrucción de Qdrant según la tarea 1.9 del roadmap.
No contiene secretos: ni claves de API, ni HMAC, ni contraseñas.
Los valores de autenticación usados fueron variables de entorno ya
presentes en cada equipo o ficheros privados fuera de Git con permiso
restringido; ningún valor aparece en este informe ni en los registros.

La tarea 1.8 continúa pendiente de evaluación humana y la tarea 1.9
continúa abierta. Este informe no cierra el roadmap ni marca nada como
revisado por humanos.

## 1. Alcance y límites

Hecho:

- Copia nueva y consistente de PostgreSQL y de originales en Skynet,
  con comprobación de transferencia íntegra al equipo local.
- Restauración aislada en el equipo local con proyecto Compose,
  volúmenes y puertos de loopback nuevos de nombre único.
- Reconstrucción completa de Qdrant con `reindex --all` en CPU y
  verificación de base restaurada, hashes de originales y búsqueda.

No hecho:

- Ningún `reset`, migración ni comando de mantenimiento sobre el
  servicio o los volúmenes originales, ni en Skynet ni en local.
- Ningún cambio en código, configuraciones activas, firewall, DNS,
  puertos publicados ni resultados previos de `eval/`.
- Ningún `push`, PR ni publicación. Sin commits: este fichero es el
  único artefacto nuevo en el repositorio.

## 2. Estado previo y capacidad

- Conexión con Skynet solo por `ssh -o BatchMode=yes skynet-ts`
  (clave pública, sin contraseña).
- Despliegue original intacto antes, durante y después:
  `ragmur_deploy-api-1` (sano), `ragmur_deploy-postgres-1` (sano) y
  `ragmur_deploy-qdrant-1`, todos con más de 43 horas de actividad.
  Volúmenes originales `ragmur_deploy_postgres_data`,
  `ragmur_deploy_qdrant_data`, `ragmur_deploy_original_data` y
  `ragmur_deploy_model_data`, sin tocar.
- Salud del servicio: `GET /health` → `{"status": "ok"}`;
  `GET /ready` → dependencias `postgres 17.11`, `qdrant 1.19.0` y
  modelos `dense-1024+nli` en verde.
- Copias anteriores (`ragmur-backup-c409b39`,
  `ragmur-backup-final-c409b39`, del 11 de noviembre) obsoletas:
  `postgres.dump` de 7 494 bytes y `originals.tar` de 3 072 bytes,
  anteriores al corpus del 13 de noviembre. No servían como copia
  actual, por eso se creó una instantánea nueva.
- Capacidad: disco C: de Skynet con más de 122 GB libres;
  equipo local con 199 GB libres en raíz y puertos de loopback
  18113, 15433, 16333 y 16334 libres para el entorno aislado.

## 3. Mecanismos verificados antes de copiar

- `pg_dump` en formato personalizado dentro del contenedor
  `postgres`, con la contraseña tomada de su propia variable de
  entorno remota (el comando registrado solo contiene el nombre de
  la variable, nunca el valor), seguido de `docker cp` al equipo.
  Solo lectura sobre el volumen original.
- Originales con `tar -C /app/storage` dentro del contenedor de la
  API, seguido de `docker cp`. Solo lectura sobre el volumen.
- Coherencia de instantánea comprobada antes de copiar:
  `SELECT status, count(*)` devolvió una sola fila, `indexed|88`,
  sin trabajos `pending`, `processing`, `deleting` ni `failed`.
  PostgreSQL informaba 7 878 kB y `/app/storage` contenía 88
  ficheros con 71 MiB, coherente con los 10 PDF del corpus público
  más los documentos sintéticos previos.

## 4. Copia creada en Skynet y transferencia

Directorio nuevo y privado en Skynet (fuera de Git):
`C:\Users\Timur\ragmur-backup-skynet-2026-11-13\`

| Fichero | Tamaño (bytes) | SHA-256 |
|---|---|---|
| `postgres-20261113.dump` | 17 277 | `8A8B40B5…F40739` |
| `originals-20261113.tar` | 73 717 760 | `67F19264…E4196482` |

Comprobaciones en origen sin secretos: el `tar` lista 90 entradas
(88 ficheros más entradas de directorio) y `pg_restore -l` sobre el
volcado lista 32 entradas de catálogo.

Transferencia al equipo local con `scp` en BatchMode al directorio
privado `/tmp/opencode/ragmur-skynet-restore-2026-11-13/` (fuera de
Git). Hashes recalculados en destino, idénticos a los de origen
(verificación completa en minúsculas):

- `67f192644e2a92586c11633b32ad53a4bcb2395da32d1ef148e04105e4196482`
- `8a8b40b579fecdb37ec563cf562d7edb42ed0a9bfb924665be79fdaecbf40739`

## 5. Restauración aislada (equipo local)

Proyecto Compose nuevo `ragmur-skyrestore-20261113` en fichero
privado fuera de Git, solo con `postgres:17-alpine` y
`qdrant/qdrant:v1.19.0`. Validación estricta previa al arranque:
el fichero no menciona `ragmur_deploy`, `ragmur_comparison`,
`original_data`, `postgres_data`, `qdrant_data`, `model_data` ni
ningún puerto publicado de los despliegues existentes.

| Recurso | Nombre nuevo y único |
|---|---|
| Proyecto | `ragmur-skyrestore-20261113` |
| Volumen PG | `ragmur-skyrestore-20261113_skyrestore_20261113_pg` |
| Volumen Qdrant | `ragmur-skyrestore-20261113_skyrestore_20261113_qdr` |
| PostgreSQL | `127.0.0.1:15433` |
| Qdrant HTTP / gRPC | `127.0.0.1:16333` / `127.0.0.1:16334` |

La API del proyecto aislado nunca se arrancó, de modo que el
reindexado cumplió el requisito de mantenimiento con la API
detenida (bloqueo de instancia sobre el directorio aislado y
bloqueo consultivo sobre la base aislada, sin contienda posible
con ningún servicio).

Restauración con `pg_restore --clean --if-not-exists` sobre la
base vacía del volumen nuevo, resultado sin errores:

| Medida | Origen (Skynet) | Copia restaurada |
|---|---|---|
| Documentos `indexed` | 88 | 88 |
| Tenants | 4 | 4 |
| Claves activas | 24 | 24 |
| Tamaño de base | 7 878 kB | 7 830 kB |

La diferencia de tamaño es el efecto normal de una recarga limpia;
los conteos son idénticos.

## 6. Verificación de originales

Extracción del `tar` al directorio privado: 88 ficheros, 71 MiB,
nombres iguales a los identificadores de documento
(`basename(storage_path) == id` en las 88 filas).

- Comparación exhaustiva de `content_sha256` de PostgreSQL contra
  el hash recalculado de cada fichero: **88 coinciden, 0 distintos,
  0 faltantes**.
- Los 10 documentos con `owner_id = ue-publico` están presentes,
  todos en estado `indexed`, con nombres iguales a las claves del
  manifiesto (`736395fe…`, `a43004fd…`, `a0d2cd8c…`, `aaf2a1b7…`,
  `1fa0183b…`, `f692aa0b…`, `7eee7159…`, `bc11dbbe…`, `2acad822…`,
  `6e83d2c4…` más la extensión `.pdf`).

Reparación documentada sobre la copia: las rutas conservadas
apuntaban a `/app/storage/<uuid>` (ruta del contenedor de Skynet),
inservible fuera de allí. Siguiendo el procedimiento de reparación
de `storage_path` del README, se sustituyó el prefijo por el
directorio aislado en las 88 filas de la copia (88 reparadas de 88
totales). El despliegue original conserva sus rutas intactas.

## 7. Reconstrucción de Qdrant

Comando de mantenimiento de la tarea 1.4 sobre la copia, con la
API detenida y variables de entorno apuntando solo al entorno
aislado (puertos 15433/16333, directorio de originales aislado,
`EMBEDDING_DEVICE=cpu`). El HMAC configurado fue un marcador sin
valor real, suficiente para validar la configuración del proceso
CLI, que no verifica claves.

- Resultado: `Reindexed 88 documents`, sin fallos ni
  `unsupported`. Estados en base: `indexed|88` con 1 712 fragmentos
  en total.
- Colección `ragmur_chunks` en el Qdrant aislado: 1 712 puntos,
  vector `dense` de 1 024 dimensiones con distancia coseno y vector
  `sparse` declarado con `modifier=idf` (el ajuste silencioso
  crítico de la rama léxica, preservado).
- Índices de payload obligatorios presentes sobre los 1 712
  puntos: `tenant_id` (con `is_tenant=true`), `owner_id` y
  `document_id`.
- El tenant del corpus público (`cbc8c3fe-…`, publicado en el
  informe del corpus) reúne 1 395 puntos; una muestra por scroll
  muestra el payload esperado (tenant, documento de
  `Europa, mejor juntos`, `owner_id=ue-publico`, nombre de fichero
  y texto con localizador de página).

Modo CPU frente a la GPU del original: el despliegue de Skynet usa
`EMBEDDING_DEVICE=cuda` con RTX 5080; la reconstrucción se hizo en
CPU como modo aislado seguro. El roadmap documenta inferencia
verificada en CPU con calidad idéntica a GPU, por lo que la
sustitución es válida para esta comprobación.

## 8. Búsqueda sobre el índice reconstruido

Búsqueda híbrida (densa + BM25 con corpus IDF acotado al tenant,
fusión RRF) con el tenant del corpus y `owner_id=ue-publico`,
misma consulta que la comprobación en Skynet:
«Que es la etiqueta ecologica de la UE», 30 candidatos.

- 30 candidatos recuperados; los 5 primeros pertenecen todos al
  documento `La etiqueta ecológica de la UE`.
- Primer resultado: páginas 15–16, rango denso 1 y léxico 3,
  idéntico al primer resultado observado en Skynet (páginas 15–16
  del mismo documento, también con GPU).
- La prueba se ejecutó a nivel de la capa de recuperación
  (`hybrid_search` con filtros de autorización), no por HTTP con
  reranking: demuestra que el índice reconstruido recupera el
  contenido correcto con los mismos filtros de aislamiento.

## 9. Limpieza y estado final

- Temporales propios eliminados de los contenedores originales de
  Skynet (`/tmp/ragmur-pg-20261113.dump` y
  `/tmp/originals-20261113.tar`); los volcados antiguos de
  noviembre en `/tmp` del contenedor postgres se dejaron intactos
  por no ser artefactos de esta tarea.
- Proyecto aislado detenido y red eliminados con
  `docker compose down` (sin `-v`): contenedores y red fuera,
  volúmenes con los datos restaurados conservados bajo sus nombres
  verificados para una posible reinspección.
- Despliegues preexistentes intactos al cierre: los tres
  contenedores `ragmur_deploy-*` en Skynet siguen en marcha y
  sanos con `indexed|88`; los proyectos locales `ragmur` y
  `ragmur_comparison` siguen en marcha.
- Copia privada conservada en Skynet
  (`ragmur-backup-skynet-2026-11-13`) y en el directorio local
  fuera de Git (volcado, `tar`, originales extraídos, fichero
  Compose, evidencias y contraseñas aisladas con permiso 600).

## 10. Limitaciones

- La reconstrucción se hizo en CPU; no se midió latencia de GPU
  ni se repite aquí la comparación de rendimiento RTX 5080 frente
  a CPU, ya documentada en `benchmarks/`.
- No se levantó una API HTTP sobre la copia: las claves del
  respaldo dependen del HMAC de Skynet, desconocido fuera de ese
  equipo, de modo que no se emitieron claves ni se probaron
  `/search`, `/verify` o `/documents` por HTTP. La búsqueda se
  verificó en la capa de recuperación con los mismos filtros.
- No se probó el borrado de tenant ni la reinstalación del
  despliegue original a partir de la copia; la copia queda
  disponible para ello cuando se decida.
- Este informe no afirma el cierre de 1.8 (faltan las 300
  etiquetas revisadas y la calibración reservada) ni de 1.9
  (faltan demo pública y endurecimiento de red).
