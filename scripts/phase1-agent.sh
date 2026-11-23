#!/usr/bin/env bash
# scripts/phase1-agent.sh [quick|full] — una orden para las pruebas de fase 1.
#
# Impide la suspensión del equipo, lanza las pruebas, espera, genera el
# informe y (solo en full) llama al explicador.
#
# - quick: estático + puerta sin servicios + 10.000 documentos + defectos
#   conocidos. Nunca usa Skynet ni LLM y nunca llama al explicador.
# - full: todas las etapas del runner y después el explicador con plazo.
#
# El código de salida es siempre el de las pruebas (quick o report), nunca el
# del explicador: su salida no cambia ninguna nota.
#
# Ganchos de prueba (solo para tests, no cambian el uso normal):
# PHASE1_AGENT_RUNNER_CMD, PHASE1_AGENT_QUICK_CMD, PHASE1_AGENT_DELIVERY_CMD,
# PHASE1_AGENT_EXPLAINER_CMD, PHASE1_AGENT_QUICK_OUTDIR, PHASE1_AGENT_POLL_SLEEP,
# PHASE1_AGENT_EXPLAINER_TIMEOUT, PHASE1_AGENT_NO_INHIBIT,
# QUICK_DOCS, QUICK_VALID_EACH, QUICK_BAD_EACH.
set -u

export DOCKER_HOST=unix:///nonexistent

MODE="${1:-}"
if [[ "$MODE" != "quick" && "$MODE" != "full" ]]; then
  echo "uso: scripts/phase1-agent.sh [quick|full]" >&2
  exit 2
fi

cd "$(dirname "$0")/.." || exit 2

runner_cmd="${PHASE1_AGENT_RUNNER_CMD:-uv run python -m eval.phase1}"
quick_cmd="${PHASE1_AGENT_QUICK_CMD:-uv run python -m eval.phase1.quick}"
delivery_cmd="${PHASE1_AGENT_DELIVERY_CMD:-uv run python -m eval.phase1.delivery}"
explainer_cmd="${PHASE1_AGENT_EXPLAINER_CMD:-opencode run --agent critica --archived}"
POLL_SLEEP="${PHASE1_AGENT_POLL_SLEEP:-60}"
EXPLAINER_TIMEOUT="${PHASE1_AGENT_EXPLAINER_TIMEOUT:-600}"
read -ra RUNNER <<< "$runner_cmd"
read -ra QUICK <<< "$quick_cmd"
read -ra DELIVERY <<< "$delivery_cmd"
read -ra EXPLAINER <<< "$explainer_cmd"

INHIBIT=()
if [[ -z "${PHASE1_AGENT_NO_INHIBIT:-}" ]] && command -v systemd-inhibit >/dev/null 2>&1; then
  INHIBIT=(systemd-inhibit --what=idle:sleep:handle-lid-switch --who=ragmur --why="taskflow fase 1")
fi

if [[ "$MODE" == "quick" ]]; then
  STAMP="$(date -u +%Y%m%dT%H%M%S)"
  OUTDIR="${PHASE1_AGENT_QUICK_OUTDIR:-eval/results/phase1/per_query/quick-${STAMP}}"
  mkdir -p "$OUTDIR"
  QUICK_ARGS=(--out "$OUTDIR")
  [[ -n "${QUICK_DOCS:-}" ]] && QUICK_ARGS+=(--docs "$QUICK_DOCS")
  [[ -n "${QUICK_VALID_EACH:-}" ]] && QUICK_ARGS+=(--per-format-valid "$QUICK_VALID_EACH")
  [[ -n "${QUICK_BAD_EACH:-}" ]] && QUICK_ARGS+=(--per-format-bad "$QUICK_BAD_EACH")
  "${INHIBIT[@]}" "${QUICK[@]}" "${QUICK_ARGS[@]}"
  QUICK_CODE=$?
  "${DELIVERY[@]}" quick --dir "$OUTDIR"
  echo "informe: ${OUTDIR}/informe.md"
  exit "$QUICK_CODE"
fi

RUN_ID="$("${INHIBIT[@]}" "${RUNNER[@]}" start)"
echo "run_id: ${RUN_ID}"
while true; do
  STATUS_OUT="$("${RUNNER[@]}" status "$RUN_ID")" || { echo "$STATUS_OUT"; exit 2; }
  echo "$STATUS_OUT"
  case "$STATUS_OUT" in
    *"estado: done "*|*"estado: cancelled "*)
      break
      ;;
  esac
  sleep "$POLL_SLEEP"
done
REPORT_JSON="eval/results/phase1/per_query/${RUN_ID}/report.json"
mkdir -p "$(dirname "$REPORT_JSON")"
"${INHIBIT[@]}" "${RUNNER[@]}" report "$RUN_ID" > "$REPORT_JSON"
EXIT_CODE=$?
echo "exit: ${EXIT_CODE} (${REPORT_JSON})"
read -r INFORME _PACKAGE <<< "$("${DELIVERY[@]}" final --run "$RUN_ID")"
echo "informe: ${INFORME}"
RUNDIR="$(dirname "$INFORME")"
PHASE1_AGENT_EXPLAINER_CMD="${EXPLAINER[*]}" "${DELIVERY[@]}" explain --dir "$RUNDIR" --timeout "$EXPLAINER_TIMEOUT" || true
echo "explicacion: ${RUNDIR}/explicacion.md"
exit "$EXIT_CODE"
