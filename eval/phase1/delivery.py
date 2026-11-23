"""Informe en español sencillo, paquete público de fallos y explicador (C06).

El runner ya decidió la nota (JSON + código de salida) antes de llamar aquí.
Este módulo solo presenta:

- ``informe.md``: verde, rojo, «no probado», fallos conocidos y siguiente
  decisión, en español sencillo.
- ``fallos-publicos.json``: hasta 50 fallos elegidos con semilla. Solo lleva
  motivos de etapa y detalles sintéticos; nunca sellados, secretos ni datos
  privados. Si aparece un marcador sellado, falla cerrado.
- ``explicacion.md``: salida de ``opencode run --agent critica`` (solo
  lectura, con plazo), rotulada como que no cambia la nota.

La salida del explicador nunca se reinyecta: con el agente caído o con una
respuesta que dice «todo aprobado», el JSON, el informe y el código no
cambian.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from eval.phase1 import runner
from eval.phase1.runner import EXIT_INFRA, EXIT_OK, write_json

PACKAGE_SEED = 20261123
PACKAGE_MAX = 50
EXPLAINER_TIMEOUT_S = 600.0
EXPLAINER_LABEL = "no cambia la nota"

# Marcadores que nunca pueden salir en el paquete: conjuntos sellados de
# evaluación (ver TASKS.md §3 y §4) y secretos. Si aparece uno, se falla
# cerrado en lugar de publicar.
SEALED_MARKERS = (
    "test.csv",
    "dev.json",
    "test.json",
    "reserve",
    "XQuAD",
    "SQAC",
    "InferES",
    "temas 6",
    "tema 6",
)
SECRET_MARKERS = (
    "rgm_",
    "PRIVATE KEY",
    "POSTGRES_PASSWORD",
    "API_KEY_HMAC_SECRET",
    "sk-ant-",
    "sk-proj-",
)
SECRET_KEY_HINTS = ("secret", "password", "token", "clave", "hmac")

# Fallos ya conocidos: se miden, no se arreglan en este ciclo. D8 es el
# contrato actual (sin dueño se busca en todo el tenant), no un defecto.
KNOWN_DEFECTS = (
    ("D1", "La petición a Qdrant no filtra por tenant; filtra después. Sin fugas medidas."),
    ("D2", "Un DOCX se rechaza entero si cabecera, pie o tabla tienen texto."),
    ("D3", "El estilo de título del Word español «Ttulo1» no se detecta."),
    ("D4", "Un «#» dentro de un bloque de código Markdown se toma por título."),
    ("D5", "Algunos fragmentos empiezan a mitad de palabra."),
    ("D6", "El divisor de frases rompe «Dr.», aísla «[1]» y junta listas."),
    ("D7", "Una contradicción en cualquier fragmento gana al apoyo."),
    ("D8", "Sin dueño se busca en todos los usuarios del tenant. Es el contrato actual."),
)

EXIT_ADVICE = {
    0: "Todo verde. Se puede pasar a la ejecución completa (C07).",
    1: "Hay un fallo duro: el instrumento mide mal o algo se rompió. Hay que parar.",
    2: "Falló la infraestructura: no dice nada de la calidad. Se reintenta.",
    3: "La calidad falla y está publicada en rojo, pero hay que decidir en U01.",
}


def _stage_entries(summary: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Normaliza quick (checks) y full (stages) a una lista de etapas."""
    raw = summary.get("checks")
    if not isinstance(raw, dict):
        raw = summary.get("stages")
    if not isinstance(raw, dict):
        return []
    entries: list[tuple[str, dict[str, Any]]] = []
    for name, entry in raw.items():
        if isinstance(entry, dict):
            entries.append((str(name), entry))
    return entries


def collect_failures(summary: dict[str, Any]) -> list[dict[str, str]]:
    """Junta candidatos de fallo públicos: motivos y detalles sintéticos.

    Nunca incluye texto de consultas, citas, identificadores de conjuntos ni
    volcados por consulta: solo el nombre de la etapa, la clase de fallo y un
    motivo corto.
    """
    candidates: list[dict[str, str]] = []
    for name, entry in _stage_entries(summary):
        state = str(entry.get("state", ""))
        if state in ("passed",):
            continue
        reason = str(entry.get("reason", entry.get("state", "")))[:300]
        candidates.append({"stage": name, "kind": state or "unknown", "detail": reason})
        if name == "ingest" and isinstance(entry.get("summary"), dict):
            issues = entry["summary"].get("issues")
            if isinstance(issues, list):
                for issue in issues:
                    if isinstance(issue, dict):
                        candidates.append(
                            {
                                "stage": "ingest",
                                "kind": str(issue.get("kind", "issue"))[:40],
                                "detail": str(issue.get("detail", ""))[:200],
                            }
                        )
    candidates.sort(key=lambda item: (item["stage"], item["kind"], item["detail"]))
    return candidates


def build_package(summary: dict[str, Any], seed: int = PACKAGE_SEED) -> dict[str, Any]:
    """Elige hasta 50 fallos con semilla fija (repetible)."""
    candidates = collect_failures(summary)
    rng = random.Random(seed)
    failures = candidates if len(candidates) <= PACKAGE_MAX else rng.sample(candidates, PACKAGE_MAX)
    return {
        "mode": summary.get("mode", "unknown"),
        "run_id": summary.get("run_id", ""),
        "exit_code": summary.get("exit_code"),
        "seed": seed,
        "failures": failures,
        "note": (
            "Paquete público para el explicador. No cambia ninguna nota: "
            "la nota ya la puso el programa (ver informe.md)."
        ),
    }


def check_package_clean(package: dict[str, Any]) -> list[str]:
    """Devuelve la lista de violaciones (sellados o secretos) del paquete."""
    text = json.dumps(package, ensure_ascii=False)
    violations = [f"sellado: {marker}" for marker in SEALED_MARKERS if marker in text]
    violations += [f"secreto: {marker}" for marker in SECRET_MARKERS if marker in text]
    return violations


def scrub_value(value: object) -> object:
    """Tacha valores de claves que parecen secretos."""
    if isinstance(value, dict):
        return {
            str(key): ("<tachado>" if _looks_secret(str(key)) else scrub_value(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [scrub_value(item) for item in value]
    return value


def _looks_secret(key: str) -> bool:
    """Indica si el nombre de una clave sugiere un secreto."""
    lowered = key.lower()
    return any(hint in lowered for hint in SECRET_KEY_HINTS)


def write_package(package: dict[str, Any], path: Path) -> Path:
    """Escribe el paquete tras tachar secretos; falla cerrado ante sellados."""
    scrubbed = scrub_value(package)
    assert isinstance(scrubbed, dict)
    violations = check_package_clean(scrubbed)
    if violations:
        raise ValueError(f"paquete no publicable: {'; '.join(violations)}")
    path.write_text(json.dumps(scrubbed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _emoji(state: str) -> str:
    """Color de una etapa: verde, rojo o no probado."""
    if state == "passed":
        return "verde"
    if state in ("pending", "incomplete"):
        return "no probado"
    return "rojo"


def render_informe(summary: dict[str, Any], n_failures: int) -> str:
    """Redacta el informe en español sencillo."""
    mode = str(summary.get("mode", ""))
    run_id = str(summary.get("run_id", summary.get("seed", "")))
    code = summary.get("exit_code")
    lines = [
        "# Pruebas de fase 1",
        "",
        f"Modo: {mode}. Ejecución: {run_id}. Código: {code}.",
        "",
        "El código lo pone un programa, no una persona ni un agente.",
        "0 es todo bien. 1 es fallo duro (hay que parar).",
        "2 es fallo de infraestructura (hay que reintentar).",
        "3 es fallo de calidad publicado en rojo.",
        "",
    ]
    green: list[str] = []
    red: list[str] = []
    untested: list[str] = []
    for name, entry in _stage_entries(summary):
        state = str(entry.get("state", "incomplete"))
        reason = str(entry.get("reason", ""))
        line = f"- {name}: {reason}" if reason else f"- {name}"
        if state == "passed":
            green.append(line)
        elif state in ("pending", "incomplete"):
            untested.append(f"- {name} (no probado)")
        else:
            red.append(line)
    lines.append("## Lo que está verde")
    lines.append("")
    lines.extend(green or ["- Nada todavía."])
    lines.append("")
    lines.append("## Lo que está rojo")
    lines.append("")
    lines.extend(red or ["- Nada."])
    lines.append("")
    lines.append("## No probado")
    lines.append("")
    lines.extend(untested or ["- Todo lo previsto se probó."])
    lines.append("")
    lines.append("## Fallos ya conocidos (medidos, no bloquean)")
    lines.append("")
    lines.append("Son defectos reproducidos a propósito. Que salgan es lo esperado.")
    lines.append("")
    for defect_id, text in KNOWN_DEFECTS:
        lines.append(f"- {defect_id}: {text}")
    lines.append("")
    lines.append("## Siguiente decisión")
    lines.append("")
    advice = EXIT_ADVICE.get(code if isinstance(code, int) else -1, "Código desconocido.")
    lines.append(advice)
    lines.append("")
    lines.append(f"El paquete público lleva {n_failures} fallos para explicar.")
    lines.append("")
    return "\n".join(lines)


def write_informe(summary: dict[str, Any], package: dict[str, Any], path: Path) -> Path:
    """Escribe informe.md a partir del resumen y el paquete."""
    failures = package.get("failures")
    count = len(failures) if isinstance(failures, list) else 0
    path.write_text(render_informe(summary, count), encoding="utf-8")
    return path


def explainer_prompt(package: dict[str, Any]) -> str:
    """Pide al agente crítica una explicación de solo lectura."""
    return (
        "Solo lectura: no cambies código, no ejecutes nada, no abras otros ficheros. "
        "Explica en español sencillo, para una persona que empieza, los fallos de "
        "este paquete. Por cada fallo di qué significa y por qué puede pasar. "
        "No pongas nota, no digas que está todo aprobado si hay fallos, "
        "no pidas ejecutar nada. Tu salida no cambia ninguna nota.\n\n"
        f"Paquete:\n{json.dumps(package, ensure_ascii=False)}"
    )


def run_explainer(
    package: dict[str, Any],
    out_path: Path,
    summary: dict[str, Any] | None = None,
    timeout_s: float = EXPLAINER_TIMEOUT_S,
    explainer_cmd: list[str] | None = None,
) -> dict[str, Any]:
    """Llama al explicador con plazo y escribe explicacion.md. Nunca falla.

    Devuelve ``ok`` (explicó), ``rejected`` (dijo «todo aprobado» con fallos:
    se ignora) o ``unavailable`` (el agente cayó: se deja constancia). En los
    tres casos el JSON, el informe y el código quedan intactos: esta función
    solo escribe explicacion.md.
    """
    cmd = list(explainer_cmd) if explainer_cmd else ["opencode", "run", "--agent", "critica"]
    header = (
        "# Explicación de los fallos\n\n"
        f"Esta explicación **{EXPLAINER_LABEL}**: la puso un programa antes de pedirla.\n\n"
    )
    outcome: dict[str, Any] = {"state": "unavailable", "reason": "sin respuesta"}
    try:
        completed = subprocess.run(
            [*cmd, explainer_prompt(package)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        text = (completed.stdout or "").strip()
        if completed.returncode != 0 or not text:
            outcome = {
                "state": "unavailable",
                "reason": f"el agente salió con {completed.returncode}",
            }
            text = "El explicador no respondió. La nota no cambia: sigue en informe.md."
        elif _claims_all_ok(text, summary):
            outcome = {"state": "rejected", "reason": "dijo «todo aprobado» con fallos"}
            text += "\n\n(Aviso: esta frase no cambia la nota. Ver informe.md.)"
        else:
            outcome = {"state": "ok", "reason": "explicó los fallos"}
        out_path.write_text(header + text + "\n", encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired) as exc:
        outcome = {"state": "unavailable", "reason": f"agente caído o plazo agotado: {exc}"}
        out_path.write_text(
            header + "El explicador no respondió a tiempo. La nota no cambia.\n",
            encoding="utf-8",
        )
    outcome["file"] = str(out_path)
    return outcome


def _claims_all_ok(text: str, summary: dict[str, Any] | None) -> bool:
    """Detecta un «todo aprobado» que contradice fallos o un código no cero."""
    if not re.search(r"todo\s+aprobado", text, re.IGNORECASE):
        return False
    if summary is None:
        return True
    if summary.get("exit_code") not in (0, None):
        return True
    return bool(collect_failures(summary))


def load_summary_for_report(run_dir: Path, mode: str, run_id: str = "") -> dict[str, Any]:
    """Lee quick.json o el estado del runner y lo normaliza para el informe."""
    if mode == "quick":
        payload = json.loads((run_dir / "quick.json").read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("quick.json ilegible")
        return payload
    status = runner.read_status(run_id)
    if not status:
        raise ValueError(f"ejecución desconocida: {run_id}")
    expected = runner.expected_stages(status)
    code = runner.report_exit(status, expected)
    return {
        "mode": "full",
        "run_id": run_id,
        "exit_code": code,
        "commit": status.get("commit", ""),
        "stages": status.get("stages", {}),
    }


def deliver(run_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    """Genera informe.md y fallos-publicos.json. Devuelve rutas y conteos."""
    package = build_package(summary)
    package_path = write_package(package, run_dir / "fallos-publicos.json")
    informe_path = write_informe(summary, package, run_dir / "informe.md")
    failures = package.get("failures")
    return {
        "informe": str(informe_path),
        "package": str(package_path),
        "n_failures": len(failures) if isinstance(failures, list) else 0,
        "exit_code": summary.get("exit_code"),
    }


def build_parser() -> argparse.ArgumentParser:
    """Define la línea de órdenes de entrega (informe, paquete, explicador)."""
    parser = argparse.ArgumentParser(prog="python -m eval.phase1.delivery")
    sub = parser.add_subparsers(dest="command", required=True)
    quick = sub.add_parser("quick", help="informe y paquete de un quick")
    quick.add_argument("--dir", type=Path, required=True)
    final = sub.add_parser("final", help="informe y paquete de un full")
    final.add_argument("--run", required=True)
    final.add_argument("--dir", type=Path, default=None)
    explain = sub.add_parser("explain", help="explicador sobre un paquete ya escrito")
    explain.add_argument("--dir", type=Path, required=True)
    explain.add_argument("--timeout", type=float, default=EXPLAINER_TIMEOUT_S)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: quick, final o explain. El explicador nunca falla."""
    args = build_parser().parse_args(argv)
    started = time.time()
    if args.command == "quick":
        summary = load_summary_for_report(args.dir, "quick")
        summary.setdefault("run_id", args.dir.name)
        outcome = deliver(args.dir, summary)
        write_json(args.dir / "delivery.json", {**outcome, "elapsed_s": time.time() - started})
        sys.stdout.write(f"{outcome['informe']} {outcome['package']}\n")
        code = summary.get("exit_code")
        return int(code) if isinstance(code, int) else EXIT_INFRA
    if args.command == "final":
        run_dir = args.dir or runner.run_dir(args.run)
        summary = load_summary_for_report(run_dir, "full", args.run)
        outcome = deliver(run_dir, summary)
        write_json(run_dir / "delivery.json", {**outcome, "elapsed_s": time.time() - started})
        sys.stdout.write(f"{outcome['informe']} {outcome['package']}\n")
        return EXIT_OK
    package_path = args.dir / "fallos-publicos.json"
    prior: dict[str, Any] | None = None
    candidate = args.dir / "quick.json"
    if candidate.exists():
        try:
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                prior = loaded
        except (OSError, ValueError):
            prior = None
    package = json.loads(package_path.read_text(encoding="utf-8"))
    if not isinstance(package, dict):
        sys.stderr.write("paquete ilegible\n")
        return EXIT_INFRA
    override = os.environ.get("PHASE1_AGENT_EXPLAINER_CMD", "").strip()
    cmd = shlex.split(override) if override else None
    outcome = run_explainer(package, args.dir / "explicacion.md", prior, args.timeout, cmd)
    sys.stdout.write(f"{outcome['state']}: {outcome['reason']}\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
