#!/usr/bin/env bash
# Smoke de la demo por el proxy y en interno. Fuente: docs/demo-design.md §11.
# Sin dependencias nuevas: `curl`, `python3` (stdlib) y `grep`.
#
# Uso:
#   PROXY_BASE=http://127.0.0.1:18082 API_BASE=http://127.0.0.1:18081 \
#   API_KEY=<clave> DEMO_KEY=<clave-inyectada> ./deploy/smoke_demo.sh
#
# Supone la pila demo levantada y un documento indexado en el tenant de la
# clave (ver report de F05b para la secuencia completa). Guarda cuerpos,
# cabeceras y códigos en OUT_DIR. Falla si hay algún 5xx o si alguna
# comprobación no da el código esperado. La prueba de revocación (401) va
# la última porque revoca la clave de demo.
#
# Variables:
#   PROXY_BASE  base del proxy (defecto http://127.0.0.1:18082)
#   API_BASE    base interna de la API (defecto http://127.0.0.1:18081)
#   API_KEY     clave válida del tenant de demo (obligatoria)
#   DEMO_KEY    valor inyectado por nginx (obligatorio, para buscar fugas)
#   OWNER_ID    propietario del corpus (defecto ue-publico)
#   OUT_DIR     directorio de evidencias (defecto logs con fecha bajo /tmp)

set -u -o pipefail

PROXY_BASE="${PROXY_BASE:-http://127.0.0.1:18082}"
API_BASE="${API_BASE:-http://127.0.0.1:18081}"
OWNER_ID="${OWNER_ID:-ue-publico}"
OUT_DIR="${OUT_DIR:-/tmp/opencode/taskflow/ragmur/F05b-codigo/logs/smoke-$(date +%Y%m%dT%H%M%S)}"
API_KEY="${API_KEY:?falta API_KEY}"
DEMO_KEY="${DEMO_KEY:?falta DEMO_KEY}"
MARKER="${MARKER:-smoke-demo}"

PASS=0
FAIL=0
CODES=""

mkdir -p "$OUT_DIR"

log() {
    echo "[smoke] $*" | tee -a "$OUT_DIR/smoke.log"
}

check() {
    local name="$1" expected="$2" actual="$3"
    CODES="${CODES}${name}=${actual} "
    if [ "$expected" = "$actual" ]; then
        PASS=$((PASS + 1))
        log "OK   $name -> $actual"
    else
        FAIL=$((FAIL + 1))
        log "FAIL $name -> $actual (esperado $expected)"
    fi
}

# Petición HTTP que guarda cuerpo y cabeceras; imprime el código.
call() {
    local tag="$1"
    shift
    local code
    code=$(curl -sS -o "$OUT_DIR/${tag}.body" -D "$OUT_DIR/${tag}.headers" \
        -w "%{http_code}" "$@")
    if [ "$code" -ge 500 ] && [ "$code" -le 599 ]; then
        FAIL=$((FAIL + 1))
        log "FAIL $tag -> $code (5xx: ningún 5xx en humo normal)"
    fi
    echo "$code"
}

log "proxy=$PROXY_BASE api=$API_BASE out=$OUT_DIR"

# --- Interno: proceso vivo y recursos listos. ---
code=$(call internal-health "$API_BASE/health")
check "internal /health" 200 "$code"
code=$(call internal-ready "$API_BASE/ready")
check "internal /ready" 200 "$code"

# --- Externo: rutas permitidas. ---
code=$(call ext-health "$PROXY_BASE/health")
check "proxy GET /health" 200 "$code"

SEARCH_BODY="{\"query\": \"etiqueta ecol${MARKER}ogica de la UE\", \"top_k\": 3}"
code=$(call ext-search \
    -X POST "$PROXY_BASE/v1/search" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: rgm_bogus_reemplazada-por-el-proxy" \
    --data-binary "$SEARCH_BODY")
check "proxy POST /v1/search con clave falsa (se ignora)" 200 "$code"

code=$(call ext-search-nokey \
    -X POST "$PROXY_BASE/v1/search" \
    -H "Content-Type: application/json" \
    --data-binary "$SEARCH_BODY")
check "proxy POST /v1/search sin clave (inyecta la suya)" 200 "$code"

CHUNK_ID=$(python3 -c "
import json
try:
    doc = json.load(open('$OUT_DIR/ext-search.body'))
    print(doc['results'][0]['chunk_id'] if doc.get('results') else '')
except Exception:
    print('')
")
if [ -z "$CHUNK_ID" ]; then
    FAIL=$((FAIL + 1))
    log "FAIL sin resultados de búsqueda: no se puede probar /v1/verify"
else
    VERIFY_BODY="{\"answer\": \"La etiqueta ecol${MARKER}ogica existe.\", \"chunk_ids\": [\"$CHUNK_ID\"]}"
    code=$(call ext-verify \
        -X POST "$PROXY_BASE/v1/verify" \
        -H "Content-Type: application/json" \
        --data-binary "$VERIFY_BODY")
    check "proxy POST /v1/verify" 200 "$code"
fi

# --- Externo: aislamiento por propietario y por documento. ---
code=$(call ext-owner-ajeno \
    -X POST "$PROXY_BASE/v1/search" \
    -H "Content-Type: application/json" \
    --data-binary "{\"query\": \"etiqueta\", \"owner_id\": \"nadie-inexistente\"}")
check "proxy owner_id inexistente" 200 "$code"
python3 - "$OUT_DIR/ext-owner-ajeno.body" >>"$OUT_DIR/smoke.log" <<'EOF'
import json, sys
doc = json.load(open(sys.argv[1]))
n = len(doc.get("results", []))
print(("OK   owner_id inexistente -> 0 resultados" if n == 0
       else f"FAIL owner_id inexistente -> {n} resultados"))
EOF
if grep -q "^FAIL owner_id" "$OUT_DIR/smoke.log"; then FAIL=$((FAIL + 1)); else PASS=$((PASS + 1)); fi

code=$(call ext-doc-ajeno \
    -X POST "$PROXY_BASE/v1/search" \
    -H "Content-Type: application/json" \
    --data-binary '{"query": "etiqueta", "document_ids": ["00000000-0000-4000-8000-000000000000"]}')
check "proxy document_ids ajenos" 200 "$code"
python3 - "$OUT_DIR/ext-doc-ajeno.body" >>"$OUT_DIR/smoke.log" <<'EOF'
import json, sys
doc = json.load(open(sys.argv[1]))
n = len(doc.get("results", []))
print(("OK   document_ids ajenos -> 0 resultados" if n == 0
       else f"FAIL document_ids ajenos -> {n} resultados"))
EOF
if grep -q "^FAIL document_ids" "$OUT_DIR/smoke.log"; then FAIL=$((FAIL + 1)); else PASS=$((PASS + 1)); fi

# --- Externo: cuerpo grande (límite 64k en nginx y en la app). ---
python3 - "$OUT_DIR/big.json" <<'EOF'
import json, sys
json.dump({"query": "x" * 70000, "top_k": 1}, open(sys.argv[1], "w"))
EOF
code=$(call ext-big \
    -X POST "$PROXY_BASE/v1/search" \
    -H "Content-Type: application/json" \
    --data-binary "@$OUT_DIR/big.json")
check "proxy cuerpo >64k" 413 "$code"

# --- Externo: rutas denegadas (404 del proxy, sin llegar a la app). ---
denied_get="/ready /docs /redoc /openapi.json /v1/documents /v1/search /v1/search/ //v1/search /V1/SEARCH /v1/search%2F..%2Fdocuments"
for path in $denied_get; do
    tag="denied-$(echo "$path" | tr -c 'a-zA-Z0-9' '_')"
    # shellcheck disable=SC2086
    code=$(call "$tag" --path-as-is "$PROXY_BASE$path")
    check "proxy GET $path" 404 "$code"
done
code=$(call denied-post-documents -X POST "$PROXY_BASE/v1/documents")
check "proxy POST /v1/documents" 404 "$code"
code=$(call denied-head-health -I "$PROXY_BASE/health")
check "proxy HEAD /health" 404 "$code"
code=$(call denied-head-search -I "$PROXY_BASE/v1/search")
check "proxy HEAD /v1/search" 404 "$code"
code=$(call denied-options-search -X OPTIONS "$PROXY_BASE/v1/search")
check "proxy OPTIONS /v1/search" 404 "$code"

# --- Externo: ráfaga por IP (429 de nginx con Retry-After, antes del tope). ---
BURST_DIR="$OUT_DIR/burst"
mkdir -p "$BURST_DIR"
BURST_BODY='{"query": "etiqueta", "top_k": 1}'
log "ráfaga: 30 POST concurrentes a /v1/search"
for i in $(seq 1 30); do
    curl -sS -o "$BURST_DIR/$i.body" -D "$BURST_DIR/$i.headers" -w "%{http_code}" \
        -X POST "$PROXY_BASE/v1/search" \
        -H "Content-Type: application/json" \
        --data-binary "$BURST_BODY" >"$BURST_DIR/$i.code" 2>/dev/null &
done
wait
N429=0
N5XX=0
NRETRY=0
for i in $(seq 1 30); do
    c=$(cat "$BURST_DIR/$i.code")
    if [ "$c" = "429" ]; then
        N429=$((N429 + 1))
        if grep -qi "^retry-after:" "$BURST_DIR/$i.headers"; then NRETRY=$((NRETRY + 1)); fi
    fi
    if [ "$c" -ge 500 ] && [ "$c" -le 599 ]; then N5XX=$((N5XX + 1)); fi
done
log "ráfaga: 429=$N429 con_retry_after=$NRETRY 5xx=$N5XX"
if [ "$N429" -ge 1 ] && [ "$N429" -eq "$NRETRY" ] && [ "$N5XX" -eq 0 ]; then
    PASS=$((PASS + 1))
    log "OK   ráfaga limitada por nginx con Retry-After y sin 5xx"
else
    FAIL=$((FAIL + 1))
    log "FAIL ráfaga: 429=$N429 retry=$NRETRY 5xx=$N5XX"
fi

# --- Fugas en respuestas: la clave nunca viaja hacia el cliente. ---
if grep -rF --include="*.body" --include="*.headers" --include="*.code" -l -- "$DEMO_KEY" "$OUT_DIR" | grep -v big.json; then
    FAIL=$((FAIL + 1))
    log "FAIL la clave aparece en respuestas o cabeceras guardadas"
else
    PASS=$((PASS + 1))
    log "OK   la clave no aparece en respuestas ni cabeceras"
fi

# --- Revocación: la última, porque corta la demo. ---
KEY_ID="${KEY_ID:?falta KEY_ID (key_id de la clave de demo para revocarla)}"
if command -v uv >/dev/null 2>&1 && [ -n "${DATABASE_URL:-}" ] && [ -n "${HMAC_SECRET:-}" ]; then
    # La CLI exige el esquema asyncpg; admite el URL plano por comodidad.
    CLI_URL="$DATABASE_URL"
    case "$CLI_URL" in
        postgresql://*) CLI_URL="postgresql+asyncpg://${CLI_URL#postgresql://}" ;;
    esac
    DATABASE_URL="$CLI_URL" API_KEY_HMAC_SECRET="$HMAC_SECRET" \
        uv run python -m ragmur.cli revoke-key "$KEY_ID" >>"$OUT_DIR/smoke.log" 2>&1
    code=$(call ext-revoked \
        -X POST "$PROXY_BASE/v1/search" \
        -H "Content-Type: application/json" \
        --data-binary "$SEARCH_BODY")
    check "proxy tras revocar la clave de demo" 401 "$code"
else
    log "AVISO revocación omitida (falta uv, DATABASE_URL o HMAC_SECRET)"
fi

log "códigos: $CODES"
log "resultado: pass=$PASS fail=$FAIL"
echo "$CODES" >"$OUT_DIR/codes.txt"
if [ "$FAIL" -ne 0 ]; then
    log "SMOKE ROJO"
    exit 1
fi
log "SMOKE VERDE"
