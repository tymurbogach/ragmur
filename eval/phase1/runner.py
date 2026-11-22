"""Estado, cerrojo y ciclo de vida de las ejecuciones desatendidas.

Una ejecución (``run_id``) vive en ``eval/results/phase1/per_query/<run_id>/``:
``status.json`` con latido, commit, árbol sucio, hardware y configuración,
más un log y un JSON por etapa. Un cerrojo global permite una sola ejecución
a la vez; muerta es PID inexistente y latido de más de 120 s. Solo entonces
se toma el cerrojo y se retiran sus restos.

Códigos de salida: 0 todo bien; 1 fallo duro; 2 infraestructura o ejecución
incompleta; 3 solo falla la calidad o hay fallos conocidos. Precedencia
2, 1, 3, 0. Nunca 0 con una etapa ausente.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eval.phase1 import skynet

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "eval" / "results" / "phase1"
RUNS_DIR = RESULTS_DIR / "per_query"
LOCK_FILE = RUNS_DIR / ".lock"

STAGES = ("static", "ingest", "suite", "nli")
STAGE_TIMEOUTS = {"static": 600.0, "ingest": 1800.0, "suite": 2700.0, "nli": 5400.0}
HEARTBEAT_EVERY = 15.0
DEAD_AFTER = 120.0

EXIT_OK = 0
EXIT_HARD = 1
EXIT_INFRA = 2
EXIT_QUALITY = 3

STAGE_TO_EXIT = {
    "passed": EXIT_OK,
    "quality_failed": EXIT_QUALITY,
    "known_failed": EXIT_QUALITY,
    "hard_failed": EXIT_HARD,
    "infra_error": EXIT_INFRA,
    "incomplete": EXIT_INFRA,
}

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,63}$")


class LockedError(RuntimeError):
    """Otra ejecución viva tiene el cerrojo (sale con código 2)."""


class InfraError(RuntimeError):
    """Fallo de infraestructura dentro del orquestador (sale con código 2)."""


def check_run_id(run_id: str) -> str:
    """Rechaza identificadores que no valen como nombre Docker."""
    if not RUN_ID_RE.match(run_id):
        raise InfraError(f"run_id inválido: {run_id!r}")
    return run_id


def utcnow() -> str:
    """Instante actual en ISO con zona horaria."""
    return datetime.now(UTC).isoformat()


def new_run_id() -> str:
    """Genera un identificador apto para nombres y etiquetas Docker."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{secrets.token_hex(4)}"


def run_dir(run_id: str) -> Path:
    """Directorio de estado de una ejecución."""
    return RUNS_DIR / check_run_id(run_id)


def read_json(path: Path) -> dict[str, Any]:
    """Lee un JSON de estado; si falta, devuelve un diccionario vacío."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(value, dict):
        return {}
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Escribe un JSON de forma atómica (temporal + renombre)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def combine_exit_codes(codes: list[int]) -> int:
    """Aplica la precedencia 2, 1, 3, 0. Sin códigos, es ejecución incompleta."""
    if not codes:
        return EXIT_INFRA
    for wanted in (EXIT_INFRA, EXIT_HARD, EXIT_QUALITY):
        if wanted in codes:
            return wanted
    return EXIT_OK


def stage_to_exit(state: str) -> int:
    """Traduce el estado de una etapa a código de salida."""
    return STAGE_TO_EXIT.get(state, EXIT_INFRA)


def report_exit(status: dict[str, Any], expected: list[str]) -> int:
    """Calcula el código de una ejecución. Una etapa ausente nunca da 0."""
    stages = status.get("stages")
    if not isinstance(stages, dict):
        return EXIT_INFRA
    codes: list[int] = []
    for name in expected:
        entry = stages.get(name)
        if not isinstance(entry, dict):
            return EXIT_INFRA
        codes.append(stage_to_exit(str(entry.get("state", "incomplete"))))
    return combine_exit_codes(codes)


def read_commit() -> str:
    """Devuelve el commit actual o ``unknown`` si Git no responde."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30.0,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return "unknown"


def read_dirty() -> list[str]:
    """Lista los ficheros cambiados sin commitear (vacía si el árbol está limpio)."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain=v1", "-uall"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=30.0,
        ).stdout
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ["<git no disponible>"]
    return [line for line in out.splitlines() if line.strip()]


def hardware_info() -> dict[str, Any]:
    """Registra la máquina que orquesta (no la que calcula en Skynet)."""
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
    }


def is_alive(pid: int) -> bool:
    """Comprueba si un PID existe (sirve para el cerrojo)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def heartbeat_age(status: dict[str, Any]) -> float:
    """Segundos desde el último latido; infinito si no hay latido."""
    raw = status.get("heartbeat")
    if not isinstance(raw, str):
        return float("inf")
    try:
        seen = datetime.fromisoformat(raw)
    except ValueError:
        return float("inf")
    return (datetime.now(UTC) - seen).total_seconds()


def lock_is_dead(lock: dict[str, Any]) -> bool:
    """Muerta es PID inexistente Y latido de más de 120 s."""
    pid = lock.get("pid")
    if not isinstance(pid, int):
        return heartbeat_age(lock) > DEAD_AFTER
    return not is_alive(pid) and heartbeat_age(lock) > DEAD_AFTER


def read_lock() -> dict[str, Any]:
    """Lee el cerrojo global; vacío si no hay ninguno."""
    return read_json(LOCK_FILE)


def write_lock(run_id: str, pid: int) -> None:
    """Toma el cerrojo para una ejecución con latido actual."""
    write_json(LOCK_FILE, {"run_id": run_id, "pid": pid, "heartbeat": utcnow()})


def refresh_lock(run_id: str, pid: int) -> None:
    """Actualiza el latido solo si el cerrojo sigue siendo nuestro."""
    current = read_lock()
    if current.get("run_id") == run_id:
        write_json(LOCK_FILE, {"run_id": run_id, "pid": pid, "heartbeat": utcnow()})


def release_lock(run_id: str) -> None:
    """Suelta el cerrojo solo si sigue siendo nuestro."""
    current = read_lock()
    if current.get("run_id") == run_id:
        with contextlib.suppress(FileNotFoundError):
            LOCK_FILE.unlink()


def acquire_lock(run_id: str, pid: int, ssh_host: str | None) -> dict[str, Any] | None:
    """Toma el cerrojo o falla con ``LockedError`` si hay una ejecución viva.

    Devuelve el cerrojo anterior cuando se toma sobre una ejecución muerta, para
    que quien llama retire sus restos. No toca recursos ajenos: solo los de la
    ejecución muerta, por su etiqueta.
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    previous = read_lock()
    if previous and not lock_is_dead(previous):
        holder = previous.get("run_id")
        raise LockedError(f"la ejecución {holder} tiene el cerrojo y sigue viva")
    if previous:
        old_id = str(previous.get("run_id", ""))
        if old_id:
            old_status = read_json(run_dir(old_id) / "status.json")
            old_host: str | None = None
            config = old_status.get("config")
            if isinstance(config, dict) and config.get("ssh_host"):
                host_value = config.get("ssh_host")
                old_host = str(host_value) if host_value else None
            skynet.cleanup_run(old_host or ssh_host, old_id)
            try:
                old_pids = [int(p) for p in old_status.get("tunnels", [])]
            except (TypeError, ValueError):
                old_pids = []
            _kill_pids(old_pids)
    write_lock(run_id, pid)
    return previous or None


def _kill_pids(pids: list[int]) -> list[int]:
    """Mata PIDs locales (túneles) y devuelve los que siguen vivos."""
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            continue
    deadline = time.time() + 10.0
    pending = [p for p in pids if is_alive(p)]
    while pending and time.time() < deadline:
        time.sleep(0.5)
        pending = [p for p in pids if is_alive(p)]
    for pid in pending:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            continue
    return [p for p in pids if is_alive(p)]


def read_status(run_id: str) -> dict[str, Any]:
    """Lee el estado de una ejecución; vacío si no existe."""
    return read_json(run_dir(run_id) / "status.json")


def write_status(status: dict[str, Any]) -> None:
    """Guarda el estado con marca de actualización."""
    status["updated_at"] = utcnow()
    run_id = str(status.get("run_id", ""))
    write_json(run_dir(run_id) / "status.json", status)


def initial_status(
    run_id: str,
    only: list[str],
    commit: str,
    dirty: list[str],
    ssh_host: str | None,
) -> dict[str, Any]:
    """Crea el estado inicial de una ejecución."""
    return {
        "run_id": run_id,
        "phase": "phase1",
        "status": "running",
        "pid": None,
        "heartbeat": utcnow(),
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "commit": commit,
        "dirty": dirty,
        "hardware": hardware_info(),
        "config": {
            "stages": list(only),
            "timeouts": {name: STAGE_TIMEOUTS[name] for name in only},
            "ssh_host": ssh_host,
        },
        "stages": {
            name: {"state": "pending", "exit": None, "log": None, "json": None} for name in only
        },
        "tunnels": [],
        "exit_code": None,
    }


def spawn_worker(run_id: str) -> int:
    """Lanza el trabajador desacoplado: sobrevive a quien lo lanzó.

    Sesión propia, sin entrada y con salida a fichero: el padre vuelve en
    menos de 5 s y el hijo sigue aunque muera la shell.
    """
    check_run_id(run_id)
    log = run_dir(run_id) / "worker.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab") as handle:
        proc = subprocess.Popen(
            [sys.executable, "-m", "eval.phase1.worker", run_id],
            cwd=REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    return proc.pid


def expected_stages(status: dict[str, Any]) -> list[str]:
    """Etapas previstas por la configuración de la ejecución."""
    config = status.get("config")
    if isinstance(config, dict) and isinstance(config.get("stages"), list):
        names = [str(n) for n in config["stages"]]
        return [n for n in names if n in STAGES]
    return []


class Heartbeat(threading.Thread):
    """Hilo que refresca el latido cada 15 s en estado y cerrojo."""

    def __init__(self, run_id: str) -> None:
        super().__init__(daemon=True, name=f"heartbeat-{run_id}")
        self._run_id = run_id
        self._stop = threading.Event()

    def stop(self) -> None:
        """Pide la parada del hilo."""
        self._stop.set()

    def run(self) -> None:
        pid = os.getpid()
        while not self._stop.wait(HEARTBEAT_EVERY):
            try:
                status = read_status(self._run_id)
                if not status:
                    continue
                status["heartbeat"] = utcnow()
                write_status(status)
                refresh_lock(self._run_id, pid)
            except OSError:
                continue


def run_worker(run_id: str) -> int:
    """Bucle del trabajador: etapas en orden, con plazo y limpieza."""
    from eval.phase1 import stages

    check_run_id(run_id)
    status = read_status(run_id)
    if not status:
        return EXIT_INFRA
    status["pid"] = os.getpid()
    status["heartbeat"] = utcnow()
    status["status"] = "running"
    write_status(status)
    refresh_lock(run_id, os.getpid())
    beat = Heartbeat(run_id)
    beat.start()
    try:
        for name in expected_stages(status):
            entry = status["stages"][name]
            if entry.get("state") == "passed":
                continue  # reanudación: conserva etapas completas
            entry["state"] = "running"
            status["heartbeat"] = utcnow()
            write_status(status)
            try:
                if name == "static":
                    result = stages.run_static(run_dir(run_id))
                elif name == "ingest":
                    result = stages.run_ingest(run_dir(run_id))
                elif name == "suite":
                    config = status.get("config")
                    suite_host: str | None = None
                    if isinstance(config, dict) and config.get("ssh_host"):
                        suite_host = str(config["ssh_host"])
                    result = stages.run_suite(run_dir(run_id), suite_host, _note_tunnels(run_id))
                elif name == "nli":
                    config = status.get("config")
                    nli_host: str | None = None
                    if isinstance(config, dict) and config.get("ssh_host"):
                        nli_host = str(config["ssh_host"])
                    result = stages.run_nli(run_dir(run_id), nli_host)
                else:
                    result = {
                        "state": "infra_error",
                        "reason": f"etapa desconocida: {name}",
                    }
            except Exception as exc:
                # Una etapa nunca tumba al trabajador: queda como error de infraestructura.
                result = {"state": "infra_error", "reason": f"excepción: {exc}"}
            entry.update(result)
            entry["state"] = str(result.get("state", "infra_error"))
            status["heartbeat"] = utcnow()
            write_status(status)
        status["exit_code"] = report_exit(status, expected_stages(status))
        status["status"] = "done"
        status["heartbeat"] = utcnow()
        write_status(status)
        return int(status["exit_code"])
    finally:
        beat.stop()
        release_lock(run_id)


def _note_tunnels(run_id: str) -> Any:
    """Devuelve un registrador de túneles para la etapa en curso."""

    def note(pids: list[int]) -> None:
        status = read_status(run_id)
        if not status:
            return
        known = [int(p) for p in status.get("tunnels", []) if isinstance(p, int)]
        for pid in pids:
            if pid not in known:
                known.append(pid)
        status["tunnels"] = known
        write_status(status)

    return note


def cancel_run(run_id: str) -> dict[str, Any]:
    """Cancela una ejecución y verifica que no queden restos suyos."""
    check_run_id(run_id)
    status = read_status(run_id)
    if not status:
        raise InfraError(f"ejecución desconocida: {run_id}")
    pid = status.get("pid")
    worker_alive = isinstance(pid, int) and is_alive(pid)
    if worker_alive and isinstance(pid, int):
        _kill_pids([pid])
    config = status.get("config")
    host: str | None = None
    if isinstance(config, dict) and config.get("ssh_host"):
        host = str(config["ssh_host"])
    tunnel_pids = [int(p) for p in status.get("tunnels", []) if isinstance(p, int)]
    tunnels_left = _kill_pids(tunnel_pids)
    cleaned = skynet.cleanup_run(host, run_id)
    # Segunda pasada: con --rm los contenedores se van al pararlos.
    leftovers = skynet.list_resources(host, run_id)
    stages = status.get("stages")
    if isinstance(stages, dict):
        for entry in stages.values():
            if isinstance(entry, dict) and entry.get("state") == "running":
                entry["state"] = "incomplete"
                entry["reason"] = "cancelada por el usuario"
    status["status"] = "cancelled"
    status["heartbeat"] = utcnow()
    status["exit_code"] = report_exit(status, expected_stages(status))
    write_status(status)
    release_lock(run_id)
    return {
        "worker_was_alive": worker_alive,
        "cleaned": cleaned,
        "tunnels_left": tunnels_left,
        "containers_left": leftovers["containers"],
        "networks_left": leftovers["networks"],
    }
