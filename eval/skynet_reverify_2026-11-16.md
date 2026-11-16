# Reverificación Skynet — 2026-11-16

Reintento de verificación F04 tras Docker Desktop detenido.
Sin secretos: ni claves de API, ni HMAC real, ni contraseñas.
Valores de autenticación solo como nombres de variable o ficheros
privados fuera de Git con permiso 600. Sin HTTP sobre la copia.

Referencias: `ARCHITECTURE.md`, `docs/runbook-backup-restore.md`,
`eval/skynet_public_corpus_2026-11-13.md`,
`eval/skynet_restore_check_2026-11-13.md`.
Fecha de ejecución: 2026-11-16. Commit base: `7950c1b`.
Modo: native. Sin commit (árbol limpio al inicio y al cierre salvo
los dos ficheros nuevos de esta tarea).

## 1. Pre-vuelo anti-colisión

Skynet vía `ssh -o BatchMode=yes skynet-ts` con PowerShell
(`--format` de `docker ps` falla en `cmd.exe`):

- `Get-Service com.docker.service`: `Stopped, Manual`.
  Docker Desktop funciona igual vía contexto `desktop-linux`.
- `docker context ls`: `default` + `desktop-linux *` (vigente).
- `docker ps`: 3 contenedores `ragmur_deploy-*` sanos y estables:
  - `ragmur_deploy-api-1 Up 40s (healthy) 127.0.0.1:8000->8000`
  - `ragmur_deploy-postgres-1 Up 40s (healthy) 5432/tcp`
  - `ragmur_deploy-qdrant-1 Up 40s 6333-6334/tcp`
  - Un minuto después: `Up About a minute` con los dos primeros
    en `(healthy)`. Sin reinicios durante la copia.
- `docker volume ls | Select-String ragmur_deploy|skyrestore`:
  solo los 4 originales (`model`, `original`, `postgres`, `qdrant`
  bajo prefijo `ragmur_deploy`). Nada de `skyrestore` ni `skyreverify`.
- Salud: `GET /health` → `{"status":"ok"}`.
  `GET /ready` → `postgres 17.11`, `qdrant 1.19.0`,
  modelos `dense-1024+nli` en verde.
- Local: `ragmur_comparison-*` (puertos loopback `18080`,
  internos `5432/6333` sin publicar) y `jobpilot-*` en marcha.
  Ningún `ragmur_deploy` local. Volúmenes previos
  `ragmur-skyrestore-20261113_*` conservados, no reutilizados.
- Proyecto aislado NUEVO fuera de Git:
  `/tmp/opencode/ragmur-skyreverify-2026-11-16/compose.isolated.yml`,
  proyecto `ragmur-skyreverify-20261116`, solo `postgres:17-alpine`
  y `qdrant/qdrant:v1.19.0`, sin API:
  - Volumen PG: `ragmur-skyreverify-20261116_skyreverify_20261116_pg`
  - Volumen Qdrant: `ragmur-skyreverify-20261116_skyreverify_20261116_qdr`
  - `127.0.0.1:15434->5432`, `127.0.0.1:16335->6333`,
    `127.0.0.1:16336->6334` (los tres libres según `ss -tln`).
  - `grep -R ragmur_deploy compose.isolated.yml` → exit 1,
    0 ocurrencias. Sin `ragmur_comparison`, `original_data`,
    `postgres_data`, `qdrant_data`, `model_data` ni `publish`.

## 2. Estado estable en Skynet antes de copiar

Dos lecturas separadas 30 s, ambas idénticas:

```text
status  | count
--------+-------
indexed |    88
(1 row)
```

- `SELECT count(*) WHERE status != 'indexed'` → `0`.
- `SELECT count(*) FROM tenants` → `4`.
- `SELECT count(*) FROM api_keys WHERE revoked_at IS NULL` → `24`.
- `pg_database_size` origen: `8066739` bytes.
  Solo se copió con `indexed|88` estable y 0 en otros estados.

## 3. Copia en Skynet (solo lectura)

Dentro de contenedores, nada escribe en volúmenes originales.
Nombres con fecha nueva `20261116`:

```text
docker exec ragmur_deploy-postgres-1 sh -c
  'pg_dump -Fc -U ragmur -d ragmur -f /tmp/ragmur-pg-20261116.dump'
ls -l /tmp/ragmur-pg-20261116.dump → 17277 bytes
pg_restore -l /tmp/ragmur-pg-20261116.dump | wc -l → 32
```

```text
docker exec ragmur_deploy-api-1 sh -c
  'tar -C /app/storage -cf /tmp/originals-20261116.tar .'
tar -tf | wc -l → 90
tar -tf | grep -c lock → 1
tar -tf | grep -v lock | wc -l → 89 (incluye ./ + 88 originales)
ls /app/storage | wc -l → 88
ls -a /app/storage | wc -l → 91 (88 + . + .. + .ragmur.lock)
```

`docker cp` a `C:/Users/Timur/ragmur-backup-skynet-2026-11-16/`:

| Fichero | Bytes | SHA-256 origen (PowerShell `Get-FileHash`) |
|---|---|---|
| `postgres-20261116.dump` | 17277 | `BDE50318…89B9C21` |
| `originals-20261116.tar` | 73717760 | `67F19264…E4196482` |

El `tar` conserva el tamaño y hash del 2026-11-13
(`73717760`, `67f19264…` idéntico): originales sin cambios.
El volcado mantiene tamaño `17277` y `32` entradas pero su hash
cambia (`BDE50318…` frente a `8A8B40B5…` del día 13): esperado por
cabecera temporal de `pg_dump -Fc`, contenido lógico idéntico
(ver §5: mismos conteos tras restaurar).

Limpieza en origen verificada: `rm` de los dos `/tmp/*.dump|*.tar`
propios; en `postgres:/tmp` se dejan intactos los dos volcados
antiguos de noviembre y el dir `ragmur-eval-comparison`;
en `api:/tmp` no queda ningún `ragmur*` propio.

## 4. Transferencia BatchMode y verificación

```text
scp -o BatchMode=yes
  'skynet-ts:C:/Users/Timur/ragmur-backup-skynet-2026-11-16/postgres-20261116.dump'
  /tmp/opencode/ragmur-skyreverify-2026-11-16/ → exit 0
scp -o BatchMode=yes
  'skynet-ts:C:/Users/Timur/ragmur-backup-skynet-2026-11-16/originals-20261116.tar'
  /tmp/opencode/ragmur-skyreverify-2026-11-16/ → exit 0
sha256sum destino:
bde50318089af8350d44f8e3403f1c073ce2b1b0b9f2af61dae849d289b9c21
67f192644e2a92586c11633b32ad53a4bcb2395da32d1ef148e04105e4196482
sha256sum -c SHA256SUMS → ambos OK (origen = destino).
```

Directorio privado `700`, ficheros `600`, fuera de Git.

## 5. Restauración aislada

```text
docker compose -p ragmur-skyreverify-20261116
  -f compose.isolated.yml up -d postgres qdrant → exit 0
```

Hallazgo de procedimiento: `pg_restore --clean --if-not-exists`
(documentado en runbook y TASKS) no existe; `pg_restore --help`
(17.10 y 18.6) solo ofrece `--if-exists`. Primer intento con la
forma documentada falla con `unrecognized option`. Se restauró con
la forma válida, solo contra la base aislada (`15434`):

```text
pg_restore --clean --if-exists
  -h 127.0.0.1 -p 15434 -U ragmur -d ragmur
  postgres-20261116.dump → exit 0
pg_restore -l postgres-20261116.dump | wc -l → 32
SELECT status,count(*) → indexed|88
SELECT count(*) FROM tenants → 4
SELECT count(*) FROM api_keys WHERE revoked_at IS NULL → 24
pg_database_size copia → 8017587 bytes (7830 KiB)
```

Origen `8066739` frente a copia `8017587`: recarga limpia normal,
conteos idénticos. La API del proyecto aislado nunca se arrancó
(`docker ps | grep skyreverify` solo muestra `postgres` y `qdrant`).

## 6. Originales y reparación solo en copia

```text
tar -xf originals-20261116.tar -C .../originals → exit 0
ls -1 .../originals | wc -l → 88
ls -1 .../originals | grep -E '^[0-9a-f-]{36}$' | wc -l → 88
du -sh → 71M
```

- `basename(storage_path) == id` en `88/88`.
- `content_sha256` recalculado contra PostgreSQL: `88` coinciden,
  `0` distintos, `0` faltantes (script Python con `hashlib`,
  sin exponer secretos en logs).
- `owner_id = ue-publico`: `10` documentos, todos `indexed`,
  con los mismos 8 primeros que el informe del día 13
  (`0d73abdb,36e65054,3ac08a72,4b53ede2,51fb8c40,6a5bfb38,
  7c43fa0a,92d38839,93ad097e,9f1669d0`).

Reparación solo en copia (`15434`, nunca Skynet):

```sql
UPDATE documents
SET storage_path = replace(storage_path, '/app/storage/',
  '/tmp/opencode/ragmur-skyreverify-2026-11-16/originals/');
-- 88 reparadas de 88 totales
```

Origen intacto antes y después: `88` filas con
`storage_path LIKE '/app/storage/%'` en Skynet.

## 7. Reindexado con API detenida (CPU)

Variables solo al entorno aislado (puertos `15434/16335`,
directorio de originales aislado, `EMBEDDING_DEVICE=cpu`).
El secreto HMAC configurado fue un marcador sin valor real;
el CLI lo valida al arrancar pero no verifica claves.

```text
uv run python -m ragmur.cli reindex --all
→ Reindexed 88 documents (exit 0), 0 failed, 0 unsupported
SELECT status,count(*) → indexed|88
SELECT sum(chunk_count) → 1712
```

Colección `ragmur_chunks` en Qdrant aislado (`16335`):

- `points_count 1712`, `indexed_vectors_count 1712`,
  `status green`, `segments 8`.
- `dense 1024 Cosine`, `sparse modifier idf`.
- Índices obligatorios presentes en los `1712` puntos:
  `tenant_id (is_tenant true)`, `owner_id`, `document_id`.
- Tenant público `cbc8c3fe-…` reúne `1395` puntos
  (`10` documentos, `sum(chunk_count) 1395`);
  resto `316+0+1 = 317`; total `1712`. Sin HTTP sobre la copia.

## 8. Equivalencia a nivel `hybrid_search`, sin HTTP

Solo capa de recuperación, mismos filtros (`tenant_id` siempre,
`owner_id` cuando existe, corpus IDF acotado al tenant).
Tenant público + `owner_id=ue-publico`, consulta de referencia
«Que es la etiqueta ecologica de la UE», `candidates 30`, `rrf_k 2`,
dispositivo `cpu`:

- `30` candidatos recuperados.
- Top-5 todos del mismo documento `3ac08a72-…`
  (`aaf2a1b7-…pdf`, La etiqueta ecológica de la UE).
- Top-1: `páginas 15–16`, `dense_rank 1`, `sparse_rank 3`,
  idéntico al observado en Skynet con GPU.
- Detalle top-5 (sin texto, solo citas):
  `15–16 (1/3)`, `17–18 (21/1)`, `17–17 (29/2)`,
  `1–2 (2/-)`, `5–6 (5/6)`.
- Volcado completo por consulta solo en `/tmp`
  (`/tmp/skyreverify_hybrid_top30_summary.json`), no en Git.

No se levantó API HTTP sobre la copia: las claves del respaldo
dependen del HMAC de Skynet, desconocido fuera de ese equipo.

## 9. Pruebas enfocadas y búsquedas de secretos

```text
  `uv run pytest -k "isolation or tenant or owner"`
→ 13 passed, 1 skipped, 225 deselected (exit 0)
grep sobre el Compose aislado → exit 1, 0 ocurrencias.
Búsqueda de secretos exigida sobre `eval/skynet_*.md` → 0.
```

`uv run alembic upgrade head` sobre el árbol principal exige
secreto de entorno y falla sin él (`Field required`); no bloquea
esta tarea porque los tests enfocados crean su propio esquema
aislado. La base aislada `15434` ya quedó restaurada por
`pg_restore`, no por migraciones.

## 10. Limpieza y estado final

- Proyecto aislado detenido con `down` sin `-v` para posible
  reinspección: contenedores y red fuera, volúmenes
  `ragmur-skyreverify-20261116_*` conservados con los datos
  restaurados. Proyectos `ragmur` y `ragmur_comparison` intactos.
- Despliegues originales intactos: 3 contenedores `ragmur_deploy-*`
  en marcha y sanos, `indexed|88`, volúmenes originales sin tocar.
- Copia privada en Skynet (`ragmur-backup-skynet-2026-11-16`) y en
  local fuera de Git (volcado, `tar`, originales, Compose, `SHA256SUMS`,
  secretos aislados con `600`).
- Deny cumplido: ningún `*.dump`, `*.tar`, PDF, `.key`, `.env` ni
  Compose con secretos en Git; volcados por consulta solo en `/tmp`.
  Sin commitear (modo native: cambios sin commit para el jefe).

## 11. Límites

Sin calibrar NLI ni tocar umbrales `0.75/0.50/0.75`; sin
`nli_run`, `nli_thresholds` ni `eval/run.py` sobre reserva;
sin proxy/BFF, TLS, firewall, DNS, `publish` ni demo; sin push;
sin medición de latencia en CPU como cifra de rendimiento;
CPU válida solo para calidad.
