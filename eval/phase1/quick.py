"""Modo quick de C06: comprobación rápida sin Skynet ni LLM.

Cuatro comprobaciones locales, todas sin Docker (``DOCKER_HOST`` prohibido):

1. Estática: ruff, formato, mypy y el control anti-fuga NLI.
2. Puerta sin servicios: el subconjunto de pytest de la puerta compartida.
3. Ingesta: 10.000 documentos sintéticos por el troceador y los
   extractores reales, con semilla fija.
4. Defectos conocidos: D1-D7 en ``xfail`` estricto y D8 como contrato.

Nunca llama a Skynet, a un LLM ni al explicador. La salida es un resumen
JSON con su código (0 bien, 1 fallo duro, 2 infraestructura).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from eval.phase1 import ingest, runner, stages
from eval.phase1.runner import write_json

QUICK_SEED = ingest.SEED
QUICK_DOCS = 10_000
QUICK_PER_FORMAT_VALID = 100
QUICK_PER_FORMAT_BAD = 100
QUICK_TIMEOUTS = {
    "static": 600.0,
    "gate": 600.0,
    "ingest": 1200.0,
    "defects": 600.0,
}

# La llamada 2 de la puerta compartida: todo pytest salvo lo que necesita
# servicios (PostgreSQL, Qdrant) o red. Copiada de TASKS.md §5.
GATE_IGNORES = (
    "tests/retrieval",
    "tests/api/routes/test_health.py",
    "tests/api/routes/test_documents.py",
    "tests/api/test_rate_limit.py",
    "tests/test_auth.py",
    "tests/eval/reader/test_isolation.py",
    "tests/ingestion/test_recovery.py",
    "tests/ingestion/test_document_model.py",
    "tests/ingestion/test_instance_lock.py",
)


def gate_command() -> list[str]:
    """Orden de la puerta sin servicios (llamada 2 de la puerta)."""
    cmd = ["uv", "run", "pytest", "-q"]
    for ignored in GATE_IGNORES:
        cmd.append(f"--ignore={ignored}")
    return cmd


def gate_env() -> dict[str, str]:
    """Entorno de la puerta: sin Docker local, sin red de modelos, con secretos falsos."""
    env = dict(os.environ)
    env["DOCKER_HOST"] = "unix:///nonexistent"
    env["HF_HUB_OFFLINE"] = "1"
    env["API_KEY_HMAC_SECRET"] = "test-only-hmac-secret"
    env["DATABASE_URL"] = "postgresql+asyncpg://x:x@127.0.0.1:59999/x"
    env["QDRANT_URL"] = "http://127.0.0.1:59998"
    return env


def defects_command(out_xml: Path) -> list[str]:
    """Orden de los defectos conocidos: locales, sin servicios, con junit."""
    return ["uv", "run", "pytest", "-q", "tests/known_defects", f"--junitxml={out_xml}"]


def run_gate(directory: Path, timeout: float = QUICK_TIMEOUTS["gate"]) -> dict[str, Any]:
    """Ejecuta la puerta sin servicios y publica su resultado."""
    log_path = directory / "quick-gate.log"
    json_path = directory / "quick-gate.json"
    started = time.time()
    try:
        with log_path.open("wb") as handle:
            completed = subprocess.run(
                gate_command(),
                cwd=runner.REPO_ROOT,
                env=gate_env(),
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return _write(json_path, "infra_error", f"plazo de etapa agotado ({timeout:g} s)", log_path)
    except OSError as exc:
        return _write(json_path, "infra_error", f"no se pudo lanzar la etapa: {exc}", log_path)
    state = "passed" if completed.returncode == 0 else "hard_failed"
    result: dict[str, Any] = {
        "state": state,
        "exit": completed.returncode,
        "elapsed_s": round(time.time() - started, 1),
        "log": str(log_path),
        "json": str(json_path),
    }
    write_json(json_path, result)
    return result


def run_defects(directory: Path, timeout: float = QUICK_TIMEOUTS["defects"]) -> dict[str, Any]:
    """Ejecuta D2-D7 (xfail estricto), D1 y D8 (contratos) y comprueba el reparto."""
    log_path = directory / "quick-defects.log"
    json_path = directory / "quick-defects.json"
    junit_path = directory / "quick-defects-junit.xml"
    started = time.time()
    try:
        with log_path.open("wb") as handle:
            completed = subprocess.run(
                defects_command(junit_path),
                cwd=runner.REPO_ROOT,
                env=gate_env(),
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return _write(json_path, "infra_error", f"plazo de etapa agotado ({timeout:g} s)", log_path)
    except OSError as exc:
        return _write(json_path, "infra_error", f"no se pudo lanzar la etapa: {exc}", log_path)
    try:
        counts = stages.parse_junit(junit_path)
    except Exception as exc:
        return _write(json_path, "infra_error", f"sin junit de defectos: {exc}", log_path)
    failed = int(counts.get("failed", -1))
    skipped = int(counts.get("skipped", -1))
    passed = int(counts.get("passed", -1))
    if completed.returncode != 0 or failed != 0:
        state, reason = "hard_failed", f"defectos con fallo real (salida {completed.returncode})"
    elif skipped < 6 or passed < 2:
        state = "hard_failed"
        reason = (
            f"reparto inesperado: {passed} pasados y {skipped} saltos "
            "(se esperan 6 xfail y al menos D1+D8)"
        )
    else:
        state, reason = "passed", f"D2-D7 reproducidos ({skipped} saltos) y D1+D8 en verde"
    result: dict[str, Any] = {
        "state": state,
        "reason": reason,
        "exit": completed.returncode,
        "counts": counts,
        "elapsed_s": round(time.time() - started, 1),
        "log": str(log_path),
        "json": str(json_path),
    }
    write_json(json_path, result)
    return result


def _write(json_path: Path, state: str, reason: str, log_path: Path) -> dict[str, Any]:
    """Guarda un resultado mínimo de infraestructura."""
    result: dict[str, Any] = {
        "state": state,
        "reason": reason,
        "log": str(log_path),
        "json": str(json_path),
    }
    write_json(json_path, result)
    return result


def run_ingest_quick(
    directory: Path,
    seed: int = QUICK_SEED,
    docs: int = QUICK_DOCS,
    valid_each: int = QUICK_PER_FORMAT_VALID,
    bad_each: int = QUICK_PER_FORMAT_BAD,
    timeout: float = QUICK_TIMEOUTS["ingest"],
) -> dict[str, Any]:
    """Pasa la ingesta sintética por el código real con tamaño de quick."""
    deadline = time.time() + timeout
    out_dir = directory / "quick-ingest"
    log_path = directory / "quick-ingest.log"
    json_path = directory / "quick-ingest.json"
    started = time.time()
    with log_path.open("w", encoding="utf-8") as handle:
        handle.write(f"seed={seed} docs={docs} valid_each={valid_each} bad_each={bad_each}\n")
    try:
        summary = ingest.run_stage(seed, docs, valid_each, bad_each, out_dir, 60.0)
    except Exception as exc:
        return _write(json_path, "infra_error", f"infraestructura: {exc}", log_path)
    if time.time() > deadline:
        return _write(json_path, "infra_error", "plazo de etapa agotado", log_path)
    state, reason = stages.map_ingest_summary(summary)
    if summary.get("issues"):
        state = "hard_failed"
    result: dict[str, Any] = {
        "state": state,
        "reason": reason,
        "exit": 1 if state == "hard_failed" else 0,
        "elapsed_s": round(time.time() - started, 1),
        "summary": summary,
        "log": str(log_path),
        "json": str(json_path),
    }
    write_json(json_path, result)
    return result


def run(
    directory: Path,
    seed: int = QUICK_SEED,
    docs: int = QUICK_DOCS,
    valid_each: int = QUICK_PER_FORMAT_VALID,
    bad_each: int = QUICK_PER_FORMAT_BAD,
) -> dict[str, Any]:
    """Ejecuta las cuatro comprobaciones y escribe el resumen con su código."""
    directory.mkdir(parents=True, exist_ok=True)
    static = stages.run_static(directory)
    gate = run_gate(directory)
    ingested = run_ingest_quick(directory, seed, docs, valid_each, bad_each)
    defects = run_defects(directory)
    states = [str(part.get("state", "infra_error")) for part in (static, gate, ingested, defects)]
    codes = [runner.stage_to_exit(state) for state in states]
    code = runner.combine_exit_codes(codes)
    summary: dict[str, Any] = {
        "mode": "quick",
        "exit_code": code,
        "seed": seed,
        "docs": docs,
        "checks": {"static": static, "gate": gate, "ingest": ingested, "defects": defects},
    }
    write_json(directory / "quick.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Define la línea de órdenes del modo quick."""
    parser = argparse.ArgumentParser(prog="python -m eval.phase1.quick")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=QUICK_SEED)
    parser.add_argument("--docs", type=int, default=QUICK_DOCS)
    parser.add_argument("--per-format-valid", type=int, default=QUICK_PER_FORMAT_VALID)
    parser.add_argument("--per-format-bad", type=int, default=QUICK_PER_FORMAT_BAD)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Lanza el quick, escribe el resumen y sale con su código."""
    args = build_parser().parse_args(argv)
    summary = run(args.out, args.seed, args.docs, args.per_format_valid, args.per_format_bad)
    sys.stdout.write(f"exit={summary['exit_code']} seed={summary['seed']} docs={summary['docs']}\n")
    return int(summary["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
