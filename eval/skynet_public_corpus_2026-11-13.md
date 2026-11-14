# Corpus público UE en Skynet — 2026-11-13

Informe reproducible de la carga de un corpus real en el despliegue privado de
Skynet. No contiene secretos: ni claves de API, ni HMAC, ni contraseñas.
La credencial del tenant nuevo quedó guardada solo en Skynet, con ACL
restringida, y nunca se transmitió fuera de ese equipo.

La tarea 1.8 continúa pendiente de evaluación humana. Este informe no cierra
el roadmap ni marca nada como revisado por humanos.

## 1. Conexión con Skynet (solo lectura, BatchMode)

- `ssh -o BatchMode=yes skynet-ts` funciona sin contraseña (clave pública).
- Equipo `SKYNET`, Windows 10.0.26300.9974.
- Docker 29.9.3, Compose v5.7.0.
- Proyecto privado `ragmur_deploy`, tres contenedores en marcha con más de
  43 horas de actividad:
  - `ragmur_deploy-api-1` (imagen `ragmur_deploy-api:latest`, id corto
    `f3502a33`), `127.0.0.1:8000->8000`, estado sano.
  - `ragmur_deploy-postgres-1` (`postgres:17-alpine`), sano.
  - `ragmur_deploy-qdrant-1` (`qdrant/qdrant:v1.19.0`), en marcha.
- El compose activo usa `EMBEDDING_DEVICE: cuda` (variante con GPU).

## 2. Servicio: versión, salud y capacidad

- `GET /health` → `{"status": "ok"}`.
- `GET /ready` → `ok`, con dependencias `postgres 17.11`, `qdrant 1.19.0`
  y modelos `dense-1024+nli`.
- `GET /openapi.json` → título `Ragmur`, versión `0.1.0`, rutas `/health`,
  `/ready`, `/v1/documents`, `/v1/documents/{document_id}`, `/v1/search`,
  `/v1/verify`. El despliegue admite ingesta, búsqueda y verificación.
- GPU `NVIDIA GeForce RTX 5080` (16 303 MiB): 14 329 MiB libres,
  utilización 0 % antes de la carga.
- RAM: 64 649 180 KiB totales, 35 573 448 KiB libres.
- Disco C:: 122 872 483 840 bytes libres (más de 100 GiB).
- Límites del servicio (configuración del código, sin cambios):
  subida máxima 20 MiB, máximo 500 páginas por PDF, timeout de extracción
  120 s, ingesta como máximo 8 trabajos y 2 activos.

## 3. Selección del corpus (10 PDF, split dev, CC BY 4.0)

Fuente: `eval/eu_manifest.yaml` (24 documentos, 18 de desarrollo y 6 de
prueba reservada, partición fijada el 2026-11-12).

Criterios aplicados:

1. Solo `split: dev`. Excluidos los 6 de `split: test` y cualquier
   partición reservada o de holdout.
2. Solo `license: CC BY 4.0`, que permite uso comercial con atribución.
   Excluidos 4 documentos de desarrollo con permiso genérico de
   reutilización (`Ficha informativa sanitaria`, `Energía limpia para
   todos los europeos`, `Premios a la inspiración rural 2021`,
   `Una Unión que se esfuerza por lograr más resultados`), cuya redacción
   no declara uso comercial de forma explícita.
3. Cada fichero por debajo de 20 MiB y de 500 páginas.
4. Cobertura temática variada con 10 documentos (dentro del rango 8–12).

Documentos cargados (claves estables del manifiesto):

| # | Título | document_id (manifiesto) | rights_page | sha256 (8 primeros) | bytes | págs. | caracteres |
|---|--------|--------------------------|-------------|---------------------|-------|-------|------------|
| 1 | Breve guía de la UE | 736395fe-fbf9-11f0-8da5-01aa75ed71a1 | 2 | 784f856a… | 5 043 882 | 36 | 41 268 |
| 2 | La UE en 2025 | a43004fd-12ef-11f1-8870-01aa75ed71a1 | 4 | d736f4f5… | 14 376 466 | 119 | 277 091 |
| 3 | La estrategia Global Gateway | a0d2cd8c-1cf9-11f1-8c3a-01aa75ed71a1 | 2 | 4fe9557d… | 3 073 249 | 20 | 34 311 |
| 4 | La etiqueta ecológica de la UE | aaf2a1b7-466e-11f0-b9f2-01aa75ed71a1 | 2 | 0fe7291f… | 6 631 216 | 20 | 38 435 |
| 5 | Opciones de contenido educativo digital | 1fa0183b-dbbe-11f0-8da2-01aa75ed71a1 | 2 | 831584fc… | 11 912 712 | 56 | 132 397 |
| 6 | IA ética en la enseñanza | f692aa0b-17a7-11f1-8870-01aa75ed71a1 | 2 | ab6a2720… | 8 552 892 | 50 | 172 399 |
| 7 | Europa, mejor juntos | 7eee7159-da2b-11f0-8da2-01aa75ed71a1 | 2 | 8ae48a1c… | 13 563 542 | 63 | 127 632 |
| 8 | Monitor de la educación y la formación de 2023 | bc11dbbe-8cda-11ee-8aa6-01aa75ed71a1 | 2 | 8a34cee6… | 1 926 986 | 24 | 47 684 |
| 9 | El presupuesto de Europa | 2acad822-fe54-11f0-8da5-01aa75ed71a1 | 8 | 4afc822d… | 1 399 620 | 8 | 15 676 |
| 10 | Breve guía de la UE, edición 2024 | 6e83d2c4-e503-11ef-bc1c-01aa75ed71a1 | 2 | c259c961… | 6 970 964 | 36 | 41 282 |

Los `sha256`, `bytes`, `pages` y `pdf_url` completos están en
`eval/eu_manifest.yaml`. Las fichas oficiales están en las `source_url`
del manifiesto, bajo `https://op.europa.eu/es/publication-detail/-/publication/…`.

## 4. Verificación previa a la carga (máquina local)

- Los 10 PDF se descargaron de las `pdf_url` oficiales y sus SHA-256
  coinciden exactamente con el manifiesto (10/10).
- Tamaños en bytes idénticos a los del manifiesto (total 73 451 529).
- Páginas verificadas con el mismo extractor del servicio (`pypdfium2`):
  idénticas a las del manifiesto en los 10 documentos.
- Caracteres extraídos por página idénticos a `extracted_chars` en los
  10 documentos (incluidos los avisos de páginas con poco texto ya
  registrados en el manifiesto para `La UE en 2025`, `Global Gateway`,
  `La etiqueta ecológica`, `Europa, mejor juntos` y `Monitor 2023`).
- La página de derechos indicada por `rights_page` contiene la mención
  `CC BY` / `Creative Commons` en los 10 documentos.
- Todos cumplen los límites: cada uno < 20 MiB y ≤ 119 páginas (máximo
  permitido: 500).

## 5. Tenant nuevo y aislamiento de credenciales

- Tenant creado solo con la CLI dentro del contenedor, sin tocar ni
  borrar otros tenants (no se ejecutó ningún `delete-tenant` ni
  `revoke-key`):
  - nombre: `skynet-public-corpus-2026-11-13`
  - id: `cbc8c3fe-1cdb-4e0d-9a7d-a3296884e08a`
- Clave emitida con nombre `skynet-ingest-2026-11-13` y guardada solo en
  Skynet, en `ragmur-deploy\.tenant-skynet-public-corpus-2026-11-13.key`,
  con acceso limitado a `SYSTEM`, `Administradores` y `Timur`. La clave
  completa no aparece en este informe ni salió de Skynet: todas las
  llamadas a la API se ejecutaron en el propio Skynet contra
  `http://127.0.0.1:8000`, sin exponer el puerto a la red.
- El servicio conserva 4 tenants y 24 claves activas en total; solo se
  añadió este tenant y su clave.

## 6. Carga en el servicio privado

- Los 10 PDF se copiaron a Skynet con `scp` (suma verificada en destino:
  10 ficheros, 73 451 529 bytes) y se subieron con `POST /v1/documents`
  (multipart `file` + `owner_id=ue-publico`), siempre contra localhost.
- Las 10 subidas devolvieron `202` con `duplicate: false`.
- Sondeo posterior con `GET /v1/documents/{id}` hasta estado final:
  los 10 documentos quedaron en `indexed`.

Correspondencia manifiesto → documento en el servicio:

| Manifiesto (8 primeros) | document_id en el servicio | Estado |
|-------------------------|----------------------------|--------|
| 736395fe | 4b53ede2-bb31-46da-94f2-a22726ced4bf | indexed |
| a43004fd | 36e65054-66a0-4ec6-8dfc-2a6b7e3025ea | indexed |
| a0d2cd8c | 51fb8c40-6025-44a9-bb41-81baa18624bd | indexed |
| aaf2a1b7 | 3ac08a72-ea0d-4656-8917-2f08721b17bf | indexed |
| 1fa0183b | 7c43fa0a-6086-4476-8c0f-a752d477937c | indexed |
| f692aa0b | 6a5bfb38-b90b-4176-89b0-96b74c2d4798 | indexed |
| 7eee7159 | 93ad097e-ab16-404a-a192-af7192c556e2 | indexed |
| bc11dbbe | 0d73abdb-58e0-4cb6-81fa-2bbb3e1cdf50 | indexed |
| 2acad822 | 9f1669d0-20d9-4d1c-b52c-f876a8a508ee | indexed |
| 6e83d2c4 | 92d38839-d160-40d5-8d92-58f2a8ca02f7 | indexed |

- `GET /v1/documents?limit=100` con la clave nueva devuelve los 10
  documentos, todos `indexed` y con `owner_id=ue-publico`, sin cursor
  adicional.

## 7. Búsqueda y aislamiento

- `POST /v1/search` con `{"query": "Que es la etiqueta ecologica de la UE",
  "top_k": 5, "owner_id": "ue-publico"}` devolvió 5 fragmentos, todos del
  documento `La etiqueta ecológica de la UE`, con cita de fichero y
  localizador de página (primer resultado: páginas 15–16). Tiempos
  observados: incrustación 71 ms, búsqueda 76 ms, reordenado 416 ms,
  total 575 ms, con GPU.
- Sin clave: `GET /v1/documents` → `401`.
- Con clave falsa bien formada: `POST /v1/search` → `401`.
- Con la clave válida pero `owner_id` inexistente
  (`otro-propietario-inexistente`): 0 fragmentos. El filtro por
  propietario no filtra datos ajenos.
- No se creó ningún tenant de prueba adicional; el aislamiento entre
  tenants lo garantiza el filtro obligatorio por `tenant_id` del
  servicio, ya cubierto por los tests del repositorio.

## 8. Qué no se hizo

- Sin cambios en `src`, configuración, umbrales, firewall, DNS ni en
  otros proyectos o datos ajenos. Solo se añadió un tenant, una clave,
  10 documentos de ese tenant y ficheros de trabajo bajo
  `ragmur-deploy\corpus-skynet-2026-11-13\` en Skynet.
- Sin `push`, PR ni publicación.
- La tarea 1.8 sigue pendiente de evaluación humana: este informe no
  sustituye las 300 etiquetas revisadas ni la calibración reservada, y
  no marca nada como revisado por humanos.

## 9. Reproducibilidad

- Manifiesto: `eval/eu_manifest.yaml` (claves, URL, hashes, derechos).
- Evidencias locales: descargas verificadas por SHA-256 y extracción
  con el mismo `pypdfium2` del servicio.
- Evidencias en Skynet (sin secretos):
  `ragmur-deploy\corpus-skynet-2026-11-13\ingest-results.json`
  (10 `document_id` y estados), `search-check.json` (respuesta de
  búsqueda con citas y tiempos) y `list-check.json` (listado de 10
  documentos indexados).
- Comandos empleados, sin valores secretos: `ssh -o BatchMode=yes
  skynet-ts` + `docker ps` / `docker exec … python -m ragmur.cli
  create-tenant|issue-key` / `Invoke-RestMethod` contra
  `http://127.0.0.1:8000/health|ready|openapi.json` / `curl.exe` contra
  localhost para ingesta, estado, búsqueda y listado.
