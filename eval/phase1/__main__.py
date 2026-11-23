"""Línea de órdenes del orquestador: start, status, report y cancel."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from eval.phase1 import runner
from eval.phase1.runner import (
    EXIT_INFRA,
    EXIT_OK,
    STAGES,
    LockedError,
    acquire_lock,
    expected_stages,
    heartbeat_age,
    initial_status,
    is_alive,
    new_run_id,
    read_commit,
    read_dirty,
    read_status,
    report_exit,
    spawn_worker,
    write_status,
)


def _ssh_host() -> str | None:
    """Host de Skynet si la variable está definida, si no None (CI)."""
    host = os.environ.get("RAGMUR_TEST_SSH_HOST", "").strip()
    return host or None


def cmd_start(args: argparse.Namespace) -> int:
    """Crea una ejecución, la desacopla y vuelve en menos de 5 s."""
    only = list(args.only) if args.only else list(STAGES)
    unknown = [name for name in only if name not in STAGES]
    if unknown:
        sys.stderr.write(f"etapa desconocida: {', '.join(unknown)}\n")
        return EXIT_INFRA
    if args.resume:
        return cmd_resume(args.resume, only)
    run_id = new_run_id()
    status = initial_status(run_id, only, read_commit(), read_dirty(), _ssh_host())
    write_status(status)
    try:
        acquire_lock(run_id, os.getpid(), _ssh_host())
    except LockedError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_INFRA
    worker_pid = spawn_worker(run_id)
    status["pid"] = worker_pid
    write_status(status)
    sys.stdout.write(f"{run_id}\n")
    return EXIT_OK


def cmd_resume(run_id: str, only: list[str]) -> int:
    """Reanuda una ejecución muerta con el mismo commit y configuración."""
    status = read_status(run_id)
    if not status:
        sys.stderr.write(f"ejecución desconocida: {run_id}\n")
        return EXIT_INFRA
    pid = status.get("pid")
    alive = isinstance(pid, int) and is_alive(pid)
    if alive or heartbeat_age(status) <= runner.DEAD_AFTER:
        sys.stderr.write("la ejecución no está muerta: no se reanuda\n")
        return EXIT_INFRA
    if read_commit() != status.get("commit"):
        sys.stderr.write("el commit cambió: no se reanuda\n")
        return EXIT_INFRA
    config = status.get("config")
    if not isinstance(config, dict):
        sys.stderr.write("sin configuración guardada: no se reanuda\n")
        return EXIT_INFRA
    saved_stages = [str(n) for n in config.get("stages", [])]
    if set(saved_stages) != set(only):
        sys.stderr.write("la configuración cambió: no se reanuda\n")
        return EXIT_INFRA
    if _ssh_host() != config.get("ssh_host"):
        sys.stderr.write("el destino (Skynet o local) cambió: no se reanuda\n")
        return EXIT_INFRA
    stages = status.get("stages")
    if isinstance(stages, dict):
        for _name, entry in stages.items():
            if isinstance(entry, dict) and entry.get("state") != "passed":
                entry["state"] = "pending"
    status["status"] = "running"
    status["exit_code"] = None
    write_status(status)
    try:
        acquire_lock(run_id, os.getpid(), _ssh_host())
    except LockedError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_INFRA
    worker_pid = spawn_worker(run_id)
    status["pid"] = worker_pid
    write_status(status)
    sys.stdout.write(f"{run_id}\n")
    return EXIT_OK


def cmd_status(run_id: str) -> int:
    """Muestra el estado y el latido de una ejecución."""
    status = read_status(run_id)
    if not status:
        sys.stderr.write(f"ejecución desconocida: {run_id}\n")
        return EXIT_INFRA
    pid = status.get("pid")
    alive = isinstance(pid, int) and is_alive(pid)
    sys.stdout.write(f"run_id: {run_id}\n")
    sys.stdout.write(f"estado: {status.get('status')} salida={status.get('exit_code')}\n")
    sys.stdout.write(f"pid: {pid} vivo={alive} latido_hace_s={heartbeat_age(status):.0f}\n")
    sys.stdout.write(f"commit: {status.get('commit')}\n")
    stages = status.get("stages")
    if isinstance(stages, dict):
        for name, entry in stages.items():
            if isinstance(entry, dict):
                sys.stdout.write(f"  {name}: {entry.get('state')} salida={entry.get('exit')}\n")
    return EXIT_OK


def cmd_report(run_id: str) -> int:
    """Imprime el resumen JSON y sale con el código de la ejecución."""
    status = read_status(run_id)
    if not status:
        sys.stderr.write(f"ejecución desconocida: {run_id}\n")
        return EXIT_INFRA
    expected = expected_stages(status)
    code = report_exit(status, expected)
    summary: dict[str, Any] = {
        "run_id": run_id,
        "exit_code": code,
        "status": status.get("status"),
        "commit": status.get("commit"),
        "dirty": status.get("dirty"),
        "hardware": status.get("hardware"),
        "config": status.get("config"),
        "stages": status.get("stages"),
        "acceptance": _acceptance(status, expected, code),
    }
    sys.stdout.write(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return code


def _acceptance(status: dict[str, Any], expected: list[str], code: int) -> dict[str, Any]:
    """Criterios C01 por etapa: cumplido, no cumplido o no verificado."""
    stages = status.get("stages")
    if not isinstance(stages, dict):
        stages = {}
    static = stages.get("static")
    suite = stages.get("suite")
    suite_counts: dict[str, Any] = {}
    if isinstance(suite, dict) and isinstance(suite.get("counts"), dict):
        suite_counts = suite["counts"]
    ingest = stages.get("ingest")
    nli = stages.get("nli")
    nli_summary: dict[str, Any] = {}
    if isinstance(nli, dict) and isinstance(nli.get("summary"), dict):
        nli_summary = nli["summary"]
    search = stages.get("search")
    search_summary: dict[str, Any] = {}
    if isinstance(search, dict) and isinstance(search.get("summary"), dict):
        search_summary = search["summary"]
    service = stages.get("service")
    service_summary: dict[str, Any] = {}
    if isinstance(service, dict) and isinstance(service.get("summary"), dict):
        service_summary = service["summary"]
    return {
        "static_passed": (static or {}).get("state") == "passed"
        if "static" in expected
        else "not_applicable",
        "ingest_passed": (ingest or {}).get("state") == "passed"
        if "ingest" in expected
        else "not_applicable",
        "suite_zero_failed": suite_counts.get("failed") == 0 if suite_counts else "unverified",
        "suite_passed_min": suite_counts.get("passed", -1) >= 376 if suite_counts else "unverified",
        "suite_skips": suite_counts.get("skipped") if suite_counts else "unverified",
        "nli_passed": (nli or {}).get("state") in ("passed", "quality_failed")
        if "nli" in expected
        else "not_applicable",
        "nli_counts": nli_summary.get("counts") if nli_summary else "unverified",
        "nli_refs": nli_summary.get("refs") if nli_summary else "unverified",
        "search_passed": (search or {}).get("state") == "passed"
        if "search" in expected
        else "not_applicable",
        "search_cases": search_summary.get("metrics", {}).get("n_cases", "unverified")
        if search_summary
        else "unverified",
        "service_passed": (service or {}).get("state") == "passed"
        if "service" in expected
        else "not_applicable",
        "service_steps": service_summary.get("steps", "unverified")
        if service_summary
        else "unverified",
        "service_limited": service_summary.get("limited_429_503", "unverified")
        if service_summary
        else "unverified",
        "service_deploy_equal": service_summary.get("deploy_equal", "unverified")
        if service_summary
        else "unverified",
        "no_missing_stage": all(
            isinstance(stages.get(n), dict) and stages[n].get("state") != "pending"
            for n in expected
        ),
        "exit_code": code,
    }


def cmd_cancel(run_id: str) -> int:
    """Cancela una ejecución y verifica que no queden restos suyos."""
    try:
        outcome = runner.cancel_run(run_id)
    except runner.InfraError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_INFRA
    sys.stdout.write(json.dumps(outcome, indent=2, ensure_ascii=False) + "\n")
    left = (
        list(outcome.get("containers_left", []))
        + list(outcome.get("networks_left", []))
        + list(outcome.get("tunnels_left", []))
    )
    if left:
        sys.stderr.write(f"quedan restos: {left}\n")
        return EXIT_INFRA
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Define la interfaz de línea de órdenes del orquestador."""
    parser = argparse.ArgumentParser(prog="python -m eval.phase1")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="lanza una ejecución desacoplada")
    start.add_argument("--only", nargs="*", choices=list(STAGES), default=None)
    start.add_argument("--resume", default=None)
    for name in ("status", "report", "cancel"):
        child = sub.add_parser(name)
        child.add_argument("run_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada sin print salvo la salida pedida."""
    args = build_parser().parse_args(argv)
    started = time.time()
    if args.command == "start":
        code = cmd_start(args)
        _warn_if_slow(started)
        return code
    if args.command == "status":
        return cmd_status(str(args.run_id))
    if args.command == "report":
        return cmd_report(str(args.run_id))
    if args.command == "cancel":
        return cmd_cancel(str(args.run_id))
    return EXIT_INFRA


def _warn_if_slow(started: float) -> None:
    """Avisa si start tardó 5 s o más (incumple el contrato)."""
    if time.time() - started >= 5.0:
        sys.stderr.write("aviso: start tardó 5 s o más\n")


if __name__ == "__main__":
    sys.exit(main())
