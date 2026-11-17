# Diseño de exposición pública de la demo

Documento de diseño. Sin código. Sin Compose. Sin Nginx real.
Fija qué se expone, cómo y con qué límites.
La aprobación del diseño queda pendiente antes de F05b.

Decisiones D1-D7 aprobadas por el usuario el 2026-11-16.
Este documento las aplica. No las reabre.
Fase 1 sin LLM. `/answer` no existe en esta fase.

## 1. Alcance

La demo expone búsqueda y verificación sobre un corpus público.
No expone ingesta, ni listado, ni detalle, ni borrado.
No expone PostgreSQL ni Qdrant.
No expone documentación ni estado interno.

Referencias: `ARCHITECTURE.md`, `DECISIONS.md` §3.32,
`docs/runbook-backup-restore.md`,
`eval/skynet_public_corpus_2026-11-13.md`,
`eval/skynet_reverify_2026-11-16.md`,
`benchmarks/gpu-rtx5080-2026-11-10.md`.

La demo es solo API con ejemplos `curl`, sin página y sin CORS (D4).
F05e publica los ejemplos y el `README` de uso externo.

## 2. Modelo de amenazas

### 2.1 Activos

- La clave de demo. Solo vive en el servidor.
- La clave de ingesta existente. Nunca la usa el proxy.
- El token del túnel Cloudflare. Vive fuera de Git.
- Los demás tenants. No pertenecen a la demo.
- Los datos privados por `owner_id`. No pertenecen a la demo.
- La capacidad de GPU. El reranking es el coste dominante.
- Los logs. No deben guardar consultas, cuerpos ni claves.

### 2.2 Actores

- Visitante anónimo. Solo usa las rutas públicas.
- Sonda automatizada. Prueba rutas, métodos y cuerpos.
- Abusador de capacidad. Envía ráfagas y cuerpos grandes.
- Lector de logs. Solo ve lo que el formato registra.

### 2.3 Casos de abuso y control

| Abuso | Control |
|---|---|
| Extracción de la clave | La clave vive en un fichero incluido, nunca en Git. Nginx elimina la cabecera del cliente e inyecta la suya. Ninguna página sirve la clave. No hay CORS. |
| Robo del token del túnel | El token vive en un fichero, nunca en la imagen. Rota en el panel de Cloudflare. Revoca con el interruptor de corte. Ver §6 y §12. |
| Sonda de rutas | Nginx devuelve 404 para todo lo no permitido. Ver §3. `/ready`, `/docs`, `/redoc`, `/openapi.json` y `/v1/documents*` no salen al exterior. |
| Sonda de `owner_id` | El tenant público solo contiene documentos con `owner_id=ue-publico`. Otro `owner_id` devuelve 0 resultados. No reescribe JSON. Ver §5. |
| Sonda de `document_ids` | Los identificadores ajenos o inexistentes no añaden resultados. No revelan su existencia. La app filtra por tenant y `owner_id`. |
| Bomba de cuerpo | `client_max_body_size` en Nginx es 64k. La app limita el JSON a 65536 bytes. El exceso recibe 413. |
| Agotamiento de GPU | Límite por IP en Nginx más topes globales de la app. El exceso recibe 429 o 503 con `Retry-After`. Valores provisionales hasta F05d. Ver §7. |
| Inyección en logs | Nginx no registra cuerpos, cadenas de consulta ni cabeceras con claves. No uses `$request` ni el formato combinado. La app no registra texto de consulta ni claves. Ver §8. |
| Suplantación de IP origen | Nginx solo acepta la IP fija del conector (`set_real_ip_from` = `ipv4_address` del conector) con `real_ip_header CF-Connecting-IP`. Borra `X-Forwarded-For`, `Forwarded` y `CF-Connecting-IP` hacia la app y no usa `ProxyHeaders` ni `FORWARDED_ALLOW_IPS`. Sin conexión desde el conector no existe cabecera fiable. Ver §7. |

## 3. Matriz de rutas

Público a través del proxy:

| Método | Ruta | Resultado |
|---|---|---|
| GET | `/health` | 200. Proceso vivo. |
| POST | `/v1/search` | 200, 401, 413, 422, 429 o 503 según el caso. |
| POST | `/v1/verify` | 200, 401, 413, 422, 429 o 503 según el caso. |

Mecanismo Nginx exigido (lo implementa F05b):

- Tres ubicaciones exactas: `location = /health`, `location = /v1/search`, `location = /v1/verify`.
- Ubicación por defecto: `location / { return 404; }`.
- Dentro de cada ubicación exacta, comprueba el método y devuelve 404 para otros métodos. Este 404 lo emite Nginx; la petición nunca llega a FastAPI.
- No uses `limit_except`: responde 403 y permite HEAD junto a GET de forma implícita.
- Usa `proxy_pass` con URI fija (por ejemplo `proxy_pass http://api:8000/v1/search;`).
- La URI fija evita reenviar la URI cruda del cliente.
- Nginx compara el `$uri` normalizado, no la petición cruda.
- Impide redirecciones 307 de FastAPI que filtren el `Host` interno: sin barra final pública y sin reenvío de URI cruda.

Todo lo demás devuelve 404 en el proxy:

- `GET /ready` → 404 fuera. Solo interno.
- `GET /docs` → 404 fuera.
- `GET /redoc` → 404 fuera.
- `GET /openapi.json` → 404 fuera.
- `/v1/documents` y subrutas, todos los métodos → 404 fuera.
- Métodos no listados en rutas permitidas → 404 fuera.
- Rutas desconocidas → 404 fuera.

Tras revocar la clave de demo, las rutas públicas responden 401.
El cuerpo mayor que 64k responde 413 desde Nginx o desde la app.

Interno en `127.0.0.1:8000`:

- `GET /health` → 200.
- `GET /ready` → 200 con modelos listos, 503 si falta una dependencia.

Si el proxy falla, cierra. No redirige al interior.
Si la app cae, el proxy no sirve corpus alternativo.

## 4. Topología

Esta sección aplica solo a Cloudflare Tunnel.
Si se elige Tailscale Funnel, F05b define su topología propia antes de exponer.

El conector del túnel solo abre conexiones de salida.
No se abre ningún puerto de entrada.
PostgreSQL y Qdrant no publican puertos.
Nginx y la API comparten la red interna con PostgreSQL y Qdrant.
El conector solo alcanza a Nginx, nunca a la API ni a los datos.
Esta última frase está por verificar en F05b.

```text
internet
  |
  v
borde del proveedor del túnel (TLS público)
  |
  | túnel saliente desde Skynet
  v
conector del túnel (servicio compose en Skynet)
  |
  v
red edge: conector -> nginx
  |
  v
nginx (servicio compose)
  |
  v
red internal: nginx + api:8000 + postgres + qdrant
```

Reglas:

- Dos redes: `edge` (conector + nginx) e `internal` (nginx + api + postgres + qdrant).
- El conector corre en Skynet, junto a la pila.
- Nginx habla con `api:8000` por nombre de servicio.
- Nginx escucha en la interfaz de su contenedor dentro de compose.
- Solo un enlace opcional con el anfitrión usa `127.0.0.1`.
- PostgreSQL y Qdrant solo viven en la red `internal`.
- La API escucha en `127.0.0.1:8000` hacia el exterior del compose.
- El túnel declara una sola regla de ingreso hacia Nginx.
- El túnel cierra el resto con `http_status:404`.
- Por verificar en F05b con humo dentro del contenedor del conector: `api:8000`, `qdrant:6333`, `postgres:5432` y `host.docker.internal:8000` deben fallar; solo Nginx responde.

Esta segmentación es lo que hace seguro el `real_ip` de §7:
nada excepto el conector puede alcanzar a Nginx.

## 5. Invariante del tenant

La clave de demo pertenece al tenant público.
El tenant público solo contiene documentos del manifiesto.
Todos llevan `owner_id=ue-publico`.
La ingesta en este tenant solo ocurre por la API interna en `127.0.0.1:8000` según el runbook.
Nunca ocurre por la vía pública.

Origen del tenant: `eval/skynet_public_corpus_2026-11-13.md:58-71`.
Ese cuadro lista exactamente los 10 `document_id` del manifiesto.
Tenant en Skynet: `skynet-public-corpus-2026-11-13`.
Contenido verificado: 10 documentos, 1395 puntos.
Reverificación: `eval/skynet_reverify_2026-11-16.md:205-207`.

La CLI solo gestiona tenants y claves y nunca ingiere ni sirve documentos
(`create-tenant`, `issue-key`, `revoke-key`, `reindex`, `delete-tenant` en `src/ragmur/cli.py:53-69`).
El corpus se cargó con `POST /v1/documents` contra `127.0.0.1:8000`
(`eval/skynet_public_corpus_2026-11-13.md:111-113`).
Por eso la frase anterior cita la API interna, no la CLI.

La clave existente `skynet-ingest-2026-11-13` es la clave de ingesta.
El proxy nunca la usa.
Emite una clave de demo dedicada con `issue-key` sobre el mismo tenant.
Si la clave de demo se filtra, revócala; la clave de ingesta sigue intacta.

Comprueba el invariante antes de exponer y tras cada ingesta.
Si un conteo no es el esperado, detén la exposición.

Documentos fuera del manifiesto o de otro propietario.
Los hashes no se copian a mano.
Los genera F05b desde el manifiesto.
Contrato de generación:

- Entradas: `eval/eu_manifest.yaml` y la lista de los 10 `document_id` en `eval/skynet_public_corpus_2026-11-13.md:58-71`.
- Regla de selección: usa exactamente esos 10 `document_id`. Corresponden a `split: dev`, `license: CC BY 4.0`, fichero bajo 20 MiB y bajo 500 páginas, según §3 de ese informe.
- Salida: las tres consultas SQL de este apartado con los hashes ya rellenos.
- Autocomprobación: el script falla salvo que emita exactamente 10 hashes de 64 caracteres hexadecimales cada uno.

```sql
SELECT count(*)
FROM documents
WHERE tenant_id = '<uuid-del-tenant-publico>'
  AND (
    owner_id IS DISTINCT FROM 'ue-publico'
    OR content_sha256 NOT IN (:expected_hashes)
  );
-- Esperado: 0.
-- Tablas y columnas según src/ragmur/db/models.py.
-- :expected_hashes son los 10 sha256 de eval/eu_manifest.yaml para los 10 document_id citados arriba.
```

El tenant contiene exactamente 10 documentos:

```sql
SELECT count(*)
FROM documents
WHERE tenant_id = '<uuid-del-tenant-publico>';
-- Esperado: 10.
-- Detecta un documento extra aunque su hash esté en el manifiesto.
```

La clave de demo pertenece al tenant público y sigue activa:

```sql
SELECT count(*)
FROM api_keys
WHERE key_id = '<demo-key-id-publico>'
  AND tenant_id = '<uuid-del-tenant-publico>'
  AND revoked_at IS NULL;
-- Esperado: 1.
-- Columnas reales según src/ragmur/db/models.py: key_id, tenant_id, revoked_at.
-- Ejecuta esta consulta junto a la de documentos.
```

Lista también las filas infractoras antes de corregir.
Si hay alguna, revoca la exposición hasta limpiar el tenant.

## 6. Clave

La clave de demo vive en un fichero incluido, nunca en Git.
Nginx elimina la cabecera `X-API-Key` del cliente.
Nginx inyecta su propia cabecera hacia la API.

Sin `envsubst`: la variable quedaría visible en `docker inspect` y en `/proc/1/environ`.
En su lugar, monta un fichero de solo lectura con la línea de cabecera:

- El fichero contiene la línea `proxy_set_header X-API-Key <clave>;`.
- Cada una de las tres ubicaciones exactas lo trae con su propio `include`.
- Nunca uses `include` a nivel de servidor: la ubicación por defecto `location /` no lleva clave.
- En Skynet (Windows con Docker Desktop) el modo del anfitrión no viaja al contenedor. Entrégalo como secreto de Compose o como montaje de solo lectura y fija el modo dentro del contenedor. Nginx lo lee al recargar la configuración con sus trabajadores.
- Rota al sustituir el fichero y recargar Nginx.

El token del túnel Cloudflare es otro secreto:

- Vive en un fichero, nunca en la imagen.
- Rota en el panel de Cloudflare.
- Revoca en el interruptor de corte de §12.

Rotación y revocación de la clave de demo usan la CLI existente.
La CLI solo gestiona tenants y claves y nunca ingiere ni sirve documentos.
Emite con `issue-key`. Revoca con `revoke-key`.
Tras revocar, la siguiente petición recibe 401.
Si la clave de demo se filtra, revócala y corta el túnel.
La clave de ingesta `skynet-ingest-2026-11-13` nunca sale por el proxy.

## 7. Límites

Nginx aplica el límite por IP.
La app aplica topes globales.
Todo el tráfico público comparte una clave y una dirección de origen.
Por ello los límites de la app actúan como topes globales.

Detrás del túnel, `remote_addr` es el conector.
Sin corrección, `limit_req` por IP es un cubo global y los logs no guardan la IP del visitante.

Con Cloudflare Tunnel, corrige así:

- Usa `ngx_http_realip_module`.
- Asigna al conector una `ipv4_address` fija en la red `edge`.
- Declara `set_real_ip_from` solo con esa dirección única.
- Usa `real_ip_header CF-Connecting-IP`.
- Fuente: `https://developers.cloudflare.com/fundamentals/reference/http-headers/`.
- Es seguro solo porque nada excepto el conector alcanza a Nginx (ver §4).
- Nota: como defensa adicional, no publiques ningún puerto de Nginx en el anfitrión mientras el túnel corre.

Con Tailscale Funnel en modo HTTP no hay cabecera de IP de cliente.
El límite por IP necesita modo TCP con `--proxy-protocol`, o no está disponible.
F05b fija la opción elegida según el proveedor confirmado.

Nginx propuesto (provisional hasta F05d):

- `limit_req` por IP con `limit_req_status 429`.
- `limit_conn` por IP con `limit_conn_status 429`.
- El valor por defecto 503 choca con el 503 de capacidad de la app.
- Añade `Retry-After` con `always`.
- `client_max_body_size 64k`, igual o menor que `max_json_body_bytes` 65536.

App vigente (`src/ragmur/core/config.py`):

- Límite por clave: 60 peticiones por 60 s.
- Límite previo de autenticación: 120 por 60 s por dirección.
- `INFERENCE_MAX_REQUESTS`: 16 búsquedas y verificaciones a la vez.
- Exceso de inferencia: 503 con `Retry-After`.

Comportamiento tras el proxy:
el limitador previo usa la dirección de conexión.
No confía en `X-Forwarded-For`.
No usa `ProxyHeaders`.
Tras el proxy todas las peticiones comparten origen.
Ese limitador pasa a ser un tope global.
El límite por IP real vive solo en Nginx.
F05d fija los valores finales con datos de GPU.

Si Nginx devuelve 429, no llega a la app.
Si la app devuelve 429, la clave agotó su cuota.
Si la app devuelve 503, la capacidad está llena.
El cliente espera el `Retry-After` y reintenta.

## 8. Logs

Nginx registra sin cuerpos.
Nginx registra sin cadenas de consulta.
Nginx registra sin cabeceras con claves.
Usa `$uri`, no `$request_uri`.
No registres `$request` ni uses el formato combinado: arrastran la cadena de consulta.
No registres `$request_body` ni `$http_x_api_key`.

La app ya omite el texto de consulta.
La app ya omite claves y `owner_id`.
El filtro de acceso retira la consulta (`tests/core/test_logging.py`).
Los errores de `/ready` devuelven detalle genérico.
El detalle crudo solo queda en el log del servidor.

Propuesta de retención de IP: 14 días.
El driver `local` de Docker no rota por tiempo.
F05b configura `local` con `max-size` y `max-file` antes de exponer.
Ese ajuste limita por tamaño, no por días: no garantiza 14 días.
Sin un recolector con borrado a 14 días, reduce la afirmación a "sin retención definida".
Documenta el plazo final en F05d.

TLS termina en el borde de Cloudflare.
Cloudflare ve los cuerpos de petición en claro.
No envíes datos privados por la demo.

Campo `diagnostic`:
lo produce `src/ragmur/ingestion/pipeline.py:77`.
Une avisos del extractor (`src/ragmur/ingestion/extractors/core.py`).
El único aviso actual cuenta páginas con poco texto.
No incluye texto del documento.
No es público porque `/v1/documents*` devuelve 404 fuera.
Si un aviso futuro incluyese texto, revisa este punto antes de exponerlo.

## 9. Túneles comparados y recomendación

| Criterio | Cloudflare con nombre y dominio propio | Cloudflare rápido | Tailscale Funnel |
|---|---|---|---|
| Sentido | Solo salida | Solo salida | Solo salida |
| TLS público | Termina en el borde de Cloudflare | Termina en el borde de Cloudflare | Termina en el nodo Tailscale |
| Dominio | Dominio propio en Cloudflare | Nombre temporal `trycloudflare.com` | Solo `<máquina>.<tailnet>.ts.net` |
| Estabilidad | Nombre estable | Cambia en cada arranque | Estable dentro del tailnet |
| Límites | Cuota del plan | Sin SLA, 200 peticiones en vuelo, resto 429 | Ancho de banda sin cifra pública |
| IP de cliente | `CF-Connecting-IP` con `real_ip` (ver §7) | `CF-Connecting-IP` con `real_ip` (ver §7) | Sin cabecera en HTTP; TCP con `--proxy-protocol`, o sin límite por IP |
| Dónde corre | Conector en Skynet | Conector en Skynet | Funnel en el cliente o nodo Skynet |
| Versión fijada | `cloudflare/cloudflared:2026.11.0` con digest en F05b | No apto para demo estable | `tailscale/tailscale:v1.104.x` con digest en F05b |

Fuentes: `https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/`,
`https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/`,
`https://tailscale.com/kb/1223/tailscale-funnel`,
`https://hub.docker.com/_/nginx`.

Notas de evidencia:

- "No corre en contenedor `userspace`" es INFERENCIA, no hecho verificado.
- La topología mantiene cada conector donde corre: el conector Cloudflare y el nodo Tailscale viven en Skynet, no dentro del contenedor de Nginx.
- F05b fija los digests de `nginx:1.30.6-alpine` y `cloudflared:2026.11.0`, además del de Tailscale si se elige.

Recomendación: usa Cloudflare con nombre y dominio propio.
Motivo: dominio propio, nombre estable, borde con TLS e IP de cliente con `CF-Connecting-IP`.
Descarta el túnel rápido para la demo: el nombre cambia y el límite de 200 en vuelo devuelve 429.
Usa Tailscale Funnel solo si no hay dominio: el dominio queda fijo a `ts.net`, el ancho de banda no tiene cifra pública y el límite por IP exige TCP con `--proxy-protocol`.
El usuario confirma el proveedor al aprobar el diseño.

El conector corre en Skynet.
No corre dentro de Nginx.
No abre puertos de entrada.

## 10. Objetivo p95 propuesto

Objetivo provisional para `POST /v1/search` con rerank:
p95 igual o menor que 1 s en RTX 5080.
Condiciones: `candidates=30`, `top_k=5`, concurrencia 1.
El valor es provisional hasta medir en F05d.

Derivación:

- Evaluación GPU en WSL2: híbrida con rerank p50 163 ms y p95 183 ms.
- Fuente: `benchmarks/gpu-rtx5080-2026-11-10.md:37-42`.
- Prueba HTTP única en Skynet con GPU: total 575 ms (inclusión 71 ms, búsqueda 76 ms, reordenado 416 ms).
- Fuente: `eval/skynet_public_corpus_2026-11-13.md:143-144`.
- Es una sola petición, no un percentil.
- El objetivo 1 s deja margen para proxy, Qdrant y jitter.
- No usa cifras de CPU como referencia pública.

F05d mide p50 y p95 por concurrencia en RTX 5080.
F05d fija entonces los límites finales y confirma o cambia este objetivo.

## 11. Perfiles de smoke

F05b y F05d implementan estos perfiles.
F05e los repite desde fuera.

Externo, a través del proxy:

- `GET /health` → 200.
- `HEAD /health` → 404.
- `POST /v1/search` válido → 200.
- `POST /v1/verify` válido → 200.
- `GET /ready` → 404.
- `GET /docs` → 404.
- `GET /redoc` → 404.
- `GET /openapi.json` → 404.
- `GET /v1/documents` → 404.
- `POST /v1/documents` → 404.
- `GET /v1/search` → 404.
- `HEAD /v1/search` → 404.
- `OPTIONS /v1/search` → 404.
- `GET /v1/search/` → 404.
- `GET //v1/search` → 404.
- `GET /V1/SEARCH` → 404.
- `GET /v1/search%2F..%2Fdocuments` → 404.
- Petición con `X-API-Key` de cliente → se ignora; el proxy inyecta la suya.
- Cuerpo mayor que 64k → 413.
- Tras revocar la clave de demo → 401.
- Ráfaga por IP → 429 de Nginx con `Retry-After`.
- Ráfagas desde dos IP de cliente distintas → 429 independientes por IP.
- El log de Nginx registra la IP de cada visitante.
- `owner_id` inexistente → 200 con 0 resultados.
- `document_ids` ajenos → 200 con 0 resultados.
- Ningún 5xx en humo normal.

Interno, en `127.0.0.1:8000`:

- `GET /health` → 200.
- `GET /ready` → 200 con modelos listos, 503 si falta dependencia.
- `POST /v1/search` válido → 200.
- `POST /v1/verify` válido → 200.

Desde el contenedor del conector (por verificar en F05b):

- Conexión a `api:8000` → falla.
- Conexión a `qdrant:6333` → falla.
- Conexión a `postgres:5432` → falla.
- Conexión a `host.docker.internal:8000` → falla.
- Conexión a Nginx → éxito.

Guarda los logs del smoke sin consultas ni claves.

## 12. Vuelta atrás e interruptor de corte

Corte en un paso: detén el conector del túnel.
O detén el servicio Nginx de la demo.
La API sigue en privado. Los datos no se tocan.

Pasos:

1. Detén el túnel o Nginx de demo.
2. Comprueba desde fuera que no responde.
3. Si la clave se filtró, revócala con la CLI.
4. Si el token del túnel se filtró, elimina el nombre público en el panel de Cloudflare.
5. Registra la copia previa según `docs/runbook-backup-restore.md` si tocaste Skynet.

Aviso: `docker compose up` vuelve a exponer la demo.
Corta también el compose o retira el servicio antes de dar por cerrado el corte.
No borres tenants para cortar.
No restaures para cortar.
No cambies código para cortar.

## 13. Autorizaciones

- Autorización A, escrita: todo acceso a Skynet y todo cambio en `ragmur_deploy`. Aplica a F05d.
- Autorización B, escrita: DNS, TLS, túnel o firewall y toda exposición pública. Aplica a F05e.
- F05b y F05c en local no exigen A ni B.
- Sin B no se abre la demo.
- Sin A no se toca Skynet.

## 14. Regla 9: dependencias nuevas

Nginx `1.30.6-alpine`:
fija la rama estable 1.30. La 1.30.6 salió el 2026-10-14.
F05b fija su digest.
Justificación: aplica la matriz de rutas, el 404, los límites por IP y el tope de cuerpo en un componente estándar.
Alternativa descartada: Caddy. Menos evidencia operativa reunida para este despliegue.
Alternativa descartada: BFF en Python. Añade código propio y riesgo de reescritura JSON sin aportar control nuevo.

Conector de túnel:
`cloudflare/cloudflared:2026.11.0` o `tailscale/tailscale:v1.104.x` con digest en F05b, según el proveedor confirmado.
Justificación: publica sin abrir puertos de entrada.
El conector solo abre conexiones de salida.
Alternativa descartada: reenvío de puertos. Abre entrada, exige firewall, DNS y TLS propios.

Sin cambios de dependencias Python en este diseño.

## 15. Limitaciones

Este diseño no protege contra todo:

- No evita el agotamiento de GPU si el abuso cabe dentro de los límites.
- La cuota de 60/min por clave la comparten todos los visitantes: pocas IP dentro de su límite por IP pueden agotar la cuota ajena.
- Los otros tres tenants comparten proceso de API, `INFERENCE_MAX_REQUESTS` y modelos: la carga pública degrada su servicio.
- No distingue personas tras una misma IP con NAT.
- No cifra más allá de lo que cifre el proveedor del túnel.
- No oculta que existe una demo ni su dominio.
- No corrige veredictos NLI erróneos.
- No impide que un cliente copie los fragmentos públicos.
- No sustituye la medición de F05d ni el endurecimiento de F05b.
