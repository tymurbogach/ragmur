# Runbook copia, restauración y reindexado

Procedimiento repetible para copiar PostgreSQL y originales desde Skynet,
restaurar en proyecto aislado y reconstruir Qdrant.
Sin secretos en Git. Orígenes: `eval/skynet_public_corpus_2026-11-13.md`
y `eval/skynet_restore_check_2026-11-13.md`.
Verificación de equivalencia a nivel `hybrid_search`, sin HTTP sobre la copia.

## 0. Pre-vuelo anti-colisión (obligatorio)

Antes de cualquier comando, comprobar nombre, volúmenes y puertos.
Nunca reutilizar nombre, volumen ni puerto de `ragmur_deploy`.
El proyecto aislado usa nombre, volúmenes y puertos únicos, solo en loopback.

```bash
ssh -o BatchMode=yes skynet-ts docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'
ssh -o BatchMode=yes skynet-ts docker volume ls | grep -E 'ragmur_deploy|skyrestore'
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'
docker compose ls
grep -R 'ragmur_deploy' "$AISLADO_YML"; echo "grep_exit:$?"
# Esperado: 0 ocurrencias, exit 1 de grep.
```

Puertos de ejemplo usados el 2026-11-13 (elegir otros libres si colisionan):

| Recurso | Nombre único 2026-11-13 |
|---|---|
| Proyecto | `ragmur-skyrestore-20261113` |
| Volumen PG | `ragmur-skyrestore-20261113_skyrestore_20261113_pg` |
| Volumen Qdrant | `ragmur-skyrestore-20261113_skyrestore_20261113_qdr` |
| PostgreSQL | `127.0.0.1:15433` |
| Qdrant HTTP / gRPC | `127.0.0.1:16333` / `127.0.0.1:16334` |

Riesgos: `pg_restore --clean` con entorno equivocado restaura sobre el
original. Reparar `storage_path` en origen destruye el despliegue.
Compartir `model_data` contamina la caché. Reutilizar nombre, volumen
o puerto `ragmur_deploy` destruye el original.
Una copia sin instantánea consistente no es atómica.

## 1. SELECT previo en Skynet (solo lectura)

```bash
ssh -o BatchMode=yes skynet-ts docker exec ragmur_deploy-postgres-1 \
  psql -U ragmur -d ragmur -c "SELECT status, count(*) FROM documents GROUP BY status ORDER BY status;"
# Esperado 2026-11-13: una sola fila `indexed|88`.
# Cero en `pending`, `processing`, `deleting`, `failed`.
```

Sin instantánea conjunta entre PostgreSQL, Qdrant y disco.
Solo copiar cuando el conteo sea estable e `indexed` cubra todo.

## 2. Copia en Skynet (solo lectura sobre volúmenes)

`pg_dump` en formato personalizado dentro del contenedor `postgres`,
con la contraseña tomada de su propia variable de entorno remota.
El comando registrado solo contiene el nombre de la variable, nunca el valor.
Originales con `tar -C /app/storage` dentro del contenedor de la API.
Después `docker cp` al equipo. Nada escribe en los volúmenes originales.

```bash
ssh -o BatchMode=yes skynet-ts docker exec ragmur_deploy-postgres-1 \
  sh -c 'pg_dump -Fc -U ragmur -d ragmur -f /tmp/ragmur-pg-20261113.dump'
ssh -o BatchMode=yes skynet-ts docker exec ragmur_deploy-postgres-1 \
  sh -c 'ls -l /tmp/ragmur-pg-20261113.dump && pg_restore -l /tmp/ragmur-pg-20261113.dump | wc -l'
# Esperado 2026-11-13: 32 entradas de catálogo.

ssh -o BatchMode=yes skynet-ts docker exec ragmur_deploy-api-1 \
  sh -c 'tar -C /app/storage -cf /tmp/originals-20261113.tar . && tar -tf /tmp/originals-20261113.tar | wc -l && tar -tf /tmp/originals-20261113.tar | grep -c -v "/$"'
# Esperado 2026-11-13: 90 entradas, 88 ficheros.

ssh -o BatchMode=yes skynet-ts docker cp ragmur_deploy-postgres-1:/tmp/ragmur-pg-20261113.dump 'C:\Users\Timur\ragmur-backup-skynet-2026-11-13\postgres-20261113.dump'
ssh -o BatchMode=yes skynet-ts docker cp ragmur_deploy-api-1:/tmp/originals-20261113.tar 'C:\Users\Timur\ragmur-backup-skynet-2026-11-13\originals-20261113.tar'
ssh -o BatchMode=yes skynet-ts docker exec ragmur_deploy-postgres-1 rm /tmp/ragmur-pg-20261113.dump
ssh -o BatchMode=yes skynet-ts docker exec ragmur_deploy-api-1 rm /tmp/originals-20261113.tar
```

## 3. Transferencia con `scp` BatchMode

```bash
scp -o BatchMode=yes 'skynet-ts:C:/Users/Timur/ragmur-backup-skynet-2026-11-13/postgres-20261113.dump' /tmp/opencode/ragmur-skynet-restore-2026-11-13/
scp -o BatchMode=yes 'skynet-ts:C:/Users/Timur/ragmur-backup-skynet-2026-11-13/originals-20261113.tar' /tmp/opencode/ragmur-skynet-restore-2026-11-13/
sha256sum /tmp/opencode/ragmur-skynet-restore-2026-11-13/postgres-20261113.dump \
  /tmp/opencode/ragmur-skynet-restore-2026-11-13/originals-20261113.tar
# Comparar con los hashes de origen; deben ser idénticos.
sha256sum -c SHA256SUMS
```

Valores 2026-11-13 (origen = destino):

- `postgres-20261113.dump` (17 277 bytes): `8a8b40b579fecdb37ec563cf562d7edb42ed0a9bfb924665be79fdaecbf40739`
- `originals-20261113.tar` (73 717 760 bytes): `67f192644e2a92586c11633b32ad53a4bcb2395da32d1ef148e04105e4196482`

## 4. Restauración aislada (equipo local)

Proyecto Compose nuevo fuera de Git, solo con `postgres:17-alpine`
y `qdrant/qdrant:v1.19.0`. Sin API. Puertos únicos en loopback.
Verificar antes de arrancar que el fichero no mencione `ragmur_deploy`,
`ragmur_comparison`, `original_data`, `postgres_data`, `qdrant_data`,
`model_data` ni puertos publicados de despliegues existentes.

```bash
docker compose -p ragmur-skyrestore-20261113 -f "$AISLADO_YML" up -d postgres qdrant
pg_restore --clean --if-exists \
  -h 127.0.0.1 -p 15433 -U ragmur -d ragmur \
  /tmp/opencode/ragmur-skynet-restore-2026-11-13/postgres-20261113.dump
psql -h 127.0.0.1 -p 15433 -U ragmur -d ragmur \
  -c "SELECT status, count(*) FROM documents GROUP BY status;"
psql -h 127.0.0.1 -p 15433 -U ragmur -d ragmur \
  -c "SELECT count(*) FROM tenants; SELECT count(*) FROM api_keys WHERE revoked_at IS NULL;"
# Esperado 2026-11-13: `indexed|88`, 4 tenants, 24 claves activas.
# Tamaño 7 878 kB en origen frente a 7 830 kB en copia: recarga limpia normal.
```

## 5. Verificación de originales

```bash
mkdir -p /tmp/opencode/ragmur-skynet-restore-2026-11-13/originals
tar -xf /tmp/opencode/ragmur-skynet-restore-2026-11-13/originals-20261113.tar \
  -C /tmp/opencode/ragmur-skynet-restore-2026-11-13/originals
ls /tmp/opencode/ragmur-skynet-restore-2026-11-13/originals | wc -l
# Esperado: 88 ficheros, 71 MiB.
# Nombres iguales a identificadores: `basename(storage_path) == id` en 88 filas.
```

Comparación exhaustiva `content_sha256` de PostgreSQL contra hash recalculado
de cada fichero. Esperado 2026-11-13: 88 coinciden, 0 distintos, 0 faltantes.
Los 10 documentos con `owner_id = ue-publico` están presentes, todos
`indexed`, con nombres iguales a las claves del manifiesto.

## 6. Reparación de `storage_path` solo en la copia

Las rutas conservadas apuntan a `/app/storage/<uuid>` del contenedor de
Skynet, inservible fuera de allí. Sustituir el prefijo por el directorio
aislado en las 88 filas de la copia. Esperado: 88 reparadas de 88 totales.
Nunca tocar el despliegue original. La ruta debe ser la ruta absoluta de
`STORAGE_DIR` seguida del UUID del documento. No apuntar a otro fichero
ni cambiar el estado. Ver `README.md` y `src/ragmur/ingestion/storage.py`
(`resolve_document_path`: padre igual a raíz, nombre igual a `document_id`).

```sql
-- Solo sobre la base aislada (puerto 15433), nunca sobre Skynet.
UPDATE documents
SET storage_path = replace(storage_path, '/app/storage/', '<dir-aislado>/');
-- Verificar: SELECT count(*) FROM documents WHERE storage_path LIKE '<dir-aislado>/%';
```

## 7. Reconstrucción de Qdrant con `reindex --all` y API detenida

La API del proyecto aislado nunca se arranca. El reindexado exige la API
detenida (bloqueo de instancia sobre el directorio aislado y bloqueo
consultivo sobre la base aislada). Variables de entorno apuntando solo al
entorno aislado (puertos 15433/16333, directorio de originales aislado,
`EMBEDDING_DEVICE=cpu`). El HMAC configurado puede ser marcador sin valor
real: el proceso CLI lo valida al arrancar pero no verifica claves.

```bash
DATABASE_URL=postgresql+asyncpg://ragmur:<secreto-aislado>@127.0.0.1:15433/ragmur \
QDRANT_URL=http://127.0.0.1:16333 \
STORAGE_DIR=<dir-aislado> \
EMBEDDING_DEVICE=cpu \
uv run python -m ragmur.cli reindex --all
# Esperado 2026-11-13: `Reindexed 88 documents`, 0 failed, 0 unsupported.
# Estados en base: `indexed|88` con 1 712 fragmentos en total.
```

CPU válida para calidad, nunca para latencia. La reconstrucción de referencia
se hizo en CPU como modo aislado seguro frente a la GPU original
(`EMBEDDING_DEVICE=cuda`, RTX 5080). El roadmap documenta inferencia
verificada en CPU con calidad idéntica a GPU.

Colección `ragmur_chunks` en el Qdrant aislado: 1 712 puntos, vector `dense`
de 1 024 dimensiones con distancia coseno y vector `sparse` declarado con
`modifier=idf`. Índices de payload obligatorios sobre los 1 712 puntos:
`tenant_id` (con `is_tenant=true`), `owner_id` y `document_id`.
El tenant del corpus público reúne 1 395 puntos.

## 8. Verificación de equivalencia a nivel `hybrid_search`, sin HTTP

Sin HTTP sobre la copia: las claves del respaldo dependen del HMAC de Skynet,
desconocido fuera de ese equipo. No se emiten claves ni se prueban `/search`,
`/verify` o `/documents` por HTTP. La búsqueda se verifica en la capa de
recuperación con los mismos filtros (`tenant_id` siempre, `owner_id` si existe,
corpus IDF acotado al tenant).

```python
# Ejemplo ilustrativo, no ejecutable tal cual: requiere cliente, vectores y event loop.
# tenant_id del corpus público, owner_id=ue-publico, 30 candidatos.
# Consulta de referencia: «Que es la etiqueta ecologica de la UE».
puntos = await hybrid_search(
    tenant_id,
    cliente_aislado,
    "ragmur_chunks",
    denso,
    indices_dispersos,
    valores_dispersos,
    owner_id="ue-publico",
    document_ids=None,
    candidates=30,
    rrf_k=2,
)
```

Esperado 2026-11-13: 30 candidatos; los 5 primeros pertenecen a
`La etiqueta ecológica de la UE`; primer resultado en páginas 15–16,
rango denso 1 y léxico 3, idéntico al observado en Skynet con GPU.
No se levanta API HTTP sobre la copia.

## 9. Limpieza

```bash
docker compose -p ragmur-skyrestore-20261113 -f "$AISLADO_YML" down
# Sin `-v`: contenedores y red fuera, volúmenes conservados para reinspección.
```

## 10. Límites

- Sin `push`, PR ni publicación. Sin cambios en código, configuración activa,
  firewall, DNS ni puertos publicados.
- Sin borrado de tenant ni reinstalación del despliegue original desde la copia.
- Sin medición de latencia en CPU como cifra de rendimiento.
- Sin `nli_run`, `nli_thresholds` ni `eval/run.py` sobre reserva en esta tarea.
- Sin proxy, demo, TLS, firewall, DNS ni `publish`.
