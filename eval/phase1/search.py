"""Etapa search C04: busqueda y aislamiento con 16.000 preguntas en la RTX 5080.

El portatil prepara (descarga cerrada, seleccion congelada, preparados que
viajan) y el contenedor ``$P-api`` crea el indice y puntua sobre los
preparados, sin importar cargadores de conjuntos. La salida resume metricas
por etapa y conjunto, mas latencia con su hardware.

Sin Skynet no hay GPU y la etapa queda como error de infraestructura. La
calidad se publica sin umbral: solo fallan el instrumento incompleto, las
cifras distintas de las congeladas y las fugas.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from eval.phase1 import datasets, search_data, skynet
from eval.phase1.nli import deploy_snapshot, wait_for_gpu
from eval.phase1.runner import REPO_ROOT, write_json

API_IMAGE = "ragmur_deploy-api:latest"
MODEL_VOLUME = "ragmur_deploy_model_data"
VRAM_WAIT_SECONDS = 900.0
POLL_EVERY_SECONDS = 60.0
PREPARED_NAME = "search.json"
COLLECTION = "p1search"


def ensure_practice(log: Any) -> dict[str, Path]:
    """Descarga la lista cerrada y devuelve las rutas de los dos ficheros."""
    paths = {"sqac": datasets.download_allowed(datasets.SQAC_URL)}
    from eval.reader import xquad

    paths["xquad"] = xquad.download_dataset()
    log(f"practica: sqac={paths['sqac'].stat().st_size} xquad={paths['xquad'].stat().st_size}")
    return paths


def prepare() -> tuple[
    list[search_data.Doc], list[search_data.Case], dict[str, int], Path, list[str]
]:
    """Prepara documentos y preguntas de practica y escribe lo que viaja al contenedor."""
    notes: list[str] = []
    sealed = datasets.sealed_precheck()
    if sealed:
        raise datasets.SealedError("; ".join(sealed))
    paths = ensure_practice(notes.append)
    from eval.reader import xquad

    xquad_data = xquad.load_dataset(paths["xquad"])
    dev_ids = {case.case_id for case in xquad.list_cases(xquad_data, "dev")}
    sqac_data = json.loads(paths["sqac"].read_text(encoding="utf-8"))
    docs, cases, stats = search_data.build_selection(xquad_data, sqac_data, dev_ids)
    notes.append(f"seleccion: {len(docs)} documentos, {len(cases)} preguntas")
    errors = search_data.check_selection(docs, cases)
    if errors:
        raise ValueError("; ".join(errors))
    prepared = datasets.PREPARED_DIR / PREPARED_NAME
    prepared.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "docs": [doc.to_dict() for doc in docs],
        "cases": [case.to_dict() for case in cases],
        "stats": stats,
    }
    tmp_path = prepared.with_name(prepared.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(prepared)
    notes.append(f"preparado: {prepared} ({len(docs)} documentos, {len(cases)} casos)")
    return docs, cases, stats, prepared, notes


def start_api(host: str, run_id: str, network: str, qdrant: str) -> str:
    """Levanta el contenedor de calculo con GPU y modelos de solo lectura."""
    name = f"{skynet.prefix(run_id)}-api"
    skynet.remote(
        host,
        "docker",
        "run",
        "--rm",
        "-d",
        "--init",
        "--name",
        name,
        "--network",
        network,
        "--label",
        skynet.label(run_id),
        "--memory",
        "10g",
        "--tmpfs",
        "/app/storage:mode=1777",
        "--gpus",
        "all",
        "-v",
        f"{MODEL_VOLUME}:/app/models:ro",
        "-w",
        "/tmp",
        "-e",
        "HF_HUB_OFFLINE=1",
        "-e",
        "MODEL_CACHE_DIR=/app/models/huggingface",
        "-e",
        "STORAGE_DIR=/app/storage",
        "-e",
        "EMBEDDING_DEVICE=cuda",
        "-e",
        "DATABASE_URL=postgresql+asyncpg://ragmur:x@127.0.0.1:5432/x",
        "-e",
        "API_KEY_HMAC_SECRET=test-only-hmac-secret",
        "-e",
        f"QDRANT_URL=http://{qdrant}:6333",
        "-e",
        "PYTHONPATH=/tmp/code/src:/tmp/code",
        API_IMAGE,
        "sleep",
        "14400",
        timeout=180.0,
    )
    return name


def copy_code(host: str, api: str, log_path: Path) -> None:
    """Copia el codigo y los preparados al contenedor (tuberia local, sin shell remota)."""
    skynet.remote(host, "docker", "exec", api, "mkdir", "-p", "/tmp/code")
    with log_path.open("ab") as handle:
        tar_proc = subprocess.Popen(
            [
                "tar",
                "-czf",
                "-",
                "src",
                "alembic.ini",
                "eval/__init__.py",
                "eval/phase1",
                "eval/.datasets/phase1/prepared",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            ssh_proc = subprocess.Popen(
                [
                    "ssh",
                    *skynet.SSH_OPTIONS,
                    host,
                    "docker",
                    "exec",
                    "-i",
                    api,
                    "tar",
                    "--no-same-owner",
                    "--no-overwrite-dir",
                    "-xzf",
                    "-",
                    "-C",
                    "/tmp/code",
                ],
                stdin=tar_proc.stdout,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
            if tar_proc.stdout is not None:
                tar_proc.stdout.close()
            ssh_code = ssh_proc.wait(timeout=900.0)
            tar_code = tar_proc.wait(timeout=60.0)
        finally:
            for proc in (tar_proc, ssh_proc):
                if proc.poll() is None:
                    proc.kill()
        if tar_code != 0 or ssh_code != 0:
            raise skynet.SkynetError(f"copia de codigo fallida: tar={tar_code} ssh={ssh_code}")


def send_resume(
    host: str, api: str, rows: list[dict[str, Any]], iso: dict[str, Any] | None = None
) -> None:
    """Envia las filas ya puntuadas y su iso al contenedor por su entrada estandar.

    El iso viaja junto a las filas para que la reanudacion acumule sondas en
    vez de reiniciarlas; sin iso el contenedor re-sondea lo ya puntuado.
    """
    payload = json.dumps({"rows": rows, "iso": iso}, ensure_ascii=False).encode("utf-8")
    try:
        completed = subprocess.run(
            [
                "ssh",
                *skynet.SSH_OPTIONS,
                host,
                "docker",
                "exec",
                "-i",
                api,
                "tee",
                "/tmp/search-resume.json",
            ],
            input=payload,
            capture_output=True,
            timeout=600.0,
        )
    except OSError as exc:
        raise skynet.SkynetError(f"no se pudo enviar la reanudacion: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise skynet.SkynetError("envio de la reanudacion agotado") from exc
    if completed.returncode != 0:
        raise skynet.SkynetError("el contenedor no acepto la reanudacion")


def compute_done(host: str, api: str) -> bool:
    """Comprueba el marcador que el calculo escribe al terminar."""
    try:
        skynet.remote(host, "docker", "exec", api, "test", "-f", "/tmp/search-done")
    except skynet.SkynetError:
        return False
    return True


def container_alive(host: str, api: str) -> bool:
    """Comprueba que el contenedor de calculo siga en marcha."""
    out = skynet.remote(host, "docker", "ps", "-q", "--filter", f"name={api}")
    return bool(out.strip())


def read_progress(host: str, api: str) -> int:
    """Lee cuantas preguntas lleva puntuadas el contenedor, 0 si aun no informa."""
    try:
        out = skynet.remote(host, "docker", "exec", api, "cat", "/tmp/search-run.log")
    except skynet.SkynetError:
        return 0
    done = 0
    for line in out.splitlines():
        match = re.search(r"puntuadas (\d+) \{", line)
        if match:
            done = max(done, int(match.group(1)))
    return done


def collect_text(host: str, api: str, path: str) -> str:
    """Recoge un fichero del contenedor en base64 (una sola llamada)."""
    out = skynet.remote(host, "docker", "exec", api, "base64", "-w0", path, timeout=300.0)
    try:
        return base64.b64decode(out).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise skynet.SkynetError(f"no se pudo decodificar {path}: {exc}") from exc


def wait_compute(host: str, api: str, directory: Path, deadline: float, log: Any) -> dict[str, Any]:
    """Espera el marcador del calculo y guarda avances cada 500 preguntas.

    El parcial vive en el portatil e incluye filas e iso: si la ejecucion
    muere, la reanudacion con el mismo ``run_id`` lo envia al contenedor
    nuevo y conserva puntuadas y sondas.
    """
    fetched = 0
    partial_path = directory / "search-partial.json"
    while time.time() < deadline:
        if compute_done(host, api):
            payload: dict[str, Any] = json.loads(collect_text(host, api, "/tmp/search-out.json"))
            return payload
        if not container_alive(host, api):
            raise skynet.SkynetError("el contenedor de calculo murio antes de terminar")
        done = read_progress(host, api)
        if done - fetched >= search_data.PROGRESS_EVERY:
            try:
                partial = json.loads(collect_text(host, api, "/tmp/search-out.json"))
                if isinstance(partial, dict) and isinstance(partial.get("rows"), list):
                    snapshot: dict[str, Any] = {"rows": partial["rows"]}
                    if isinstance(partial.get("iso"), dict):
                        snapshot["iso"] = partial["iso"]
                    partial_path.write_text(
                        json.dumps(snapshot, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    fetched = len(partial["rows"])
                    log(f"avance guardado: {fetched} preguntas")
            except skynet.SkynetError as exc:
                log(f"avance no disponible aun: {exc}")
        log("calculo en curso...")
        time.sleep(POLL_EVERY_SECONDS)
    raise skynet.SkynetError("plazo del calculo agotado")


def depth_arguments() -> list[str]:
    """Traduce las variables de entorno de profundidad a opciones del calculo.

    ``RAGMUR_SEARCH_DEPTHS`` (p. ej. ``50,100``) activa la medida de cobertura con
    mas candidatos y ``RAGMUR_SEARCH_RERANK_EVERY`` fija cada cuantas preguntas se
    reordena con cada profundidad. Sin ellas, la etapa mide solo los 30 de siempre.
    """
    depths = os.environ.get("RAGMUR_SEARCH_DEPTHS", "").strip()
    if not depths:
        return []
    every = os.environ.get("RAGMUR_SEARCH_RERANK_EVERY", "10").strip()
    return ["--depths", depths, "--rerank-every", every]


def run_remote(
    host: str, run_id: str, directory: Path, log: Any, log_path: Path, deadline: float
) -> dict[str, Any]:
    """Levanta Qdrant y el contenedor GPU, calcula, recoge y limpia siempre."""
    before = deploy_snapshot(host)
    network = skynet.create_network(host, run_id)
    qdrant = ""
    api = ""
    try:
        wait_for_gpu(host, min(deadline, time.time() + VRAM_WAIT_SECONDS), log)
        qdrant = skynet.run_qdrant(host, run_id, network)
        api = start_api(host, run_id, network, qdrant)
        copy_code(host, api, log_path)
        partial_path = directory / "search-partial.json"
        resume_args: list[str] = []
        if partial_path.is_file():
            snapshot = json.loads(partial_path.read_text(encoding="utf-8"))
            rows = snapshot["rows"]
            send_resume(host, api, rows, snapshot.get("iso"))
            resume_args = ["--resume", "/tmp/search-resume.json"]
            log(f"reanudacion: {len(rows)} preguntas ya puntuadas")
        depth_args = depth_arguments()
        if depth_args:
            log(f"profundidad de candidatos: {' '.join(depth_args)}")
        skynet.remote(
            host,
            "docker",
            "exec",
            "-d",
            api,
            "/app/.venv/bin/python",
            "-m",
            "eval.phase1.search_compute",
            "--prepared",
            "/tmp/code/eval/.datasets/phase1/prepared/search.json",
            "--out",
            "/tmp/search-out.json",
            "--log",
            "/tmp/search-run.log",
            *resume_args,
            *depth_args,
        )
        wait_compute(host, api, directory, deadline, log)
        try:
            container_log = skynet.remote(host, "docker", "exec", api, "cat", "/tmp/search-run.log")
            log(f"contenedor: {container_log.strip()[-2000:]}")
        except skynet.SkynetError:
            log("contenedor: sin log interno")
        payload = json.loads(collect_text(host, api, "/tmp/search-out.json"))
        if not isinstance(payload, dict):
            raise skynet.SkynetError("salida del calculo ilegible")
        return payload
    finally:
        if api:
            skynet.stop_container(host, api)
        if qdrant:
            skynet.stop_container(host, qdrant)
        skynet.remove_network(host, network)
        after = deploy_snapshot(host)
        if after != before:
            raise skynet.SkynetError(
                f"el despliegue cambio: antes {sorted(before)} ahora {sorted(after)}"
            )


def run(
    directory: Path,
    ssh_host: str | None,
    timeout: float = 10800.0,
) -> dict[str, Any]:
    """Ejecuta la etapa search y escribe su log y su JSON."""
    log_path = directory / "search.log"
    json_path = directory / "search.json"
    notes: list[str] = []

    def log(message: str) -> None:
        notes.append(message)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    started = time.time()
    result: dict[str, Any] = {"state": "infra_error", "reason": "sin empezar"}
    try:
        if ssh_host is None:
            raise skynet.SkynetError("sin Skynet no hay GPU para la etapa search")
        _, cases, stats, _, prepare_notes = prepare()
        for note in prepare_notes:
            log(note)
        case_ids = [case.id for case in cases]
        payload = run_remote(
            ssh_host, directory.name, directory, log, log_path, time.time() + timeout
        )
        state, reason, summary = search_data.summarize(case_ids, payload, stats)
        result = {
            "state": state,
            "reason": reason,
            "elapsed_s": round(time.time() - started, 1),
            "summary": summary,
            "log": str(log_path),
            "json": str(json_path),
        }
    except datasets.SealedError as exc:
        result = {
            "state": "hard_failed",
            "reason": f"sellados: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
    except ValueError as exc:
        result = {
            "state": "hard_failed",
            "reason": str(exc),
            "log": str(log_path),
            "json": str(json_path),
        }
    except skynet.SkynetError as exc:
        result = {
            "state": "infra_error",
            "reason": f"infraestructura: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        result = {
            "state": "infra_error",
            "reason": f"infraestructura: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
    result.setdefault("log", str(log_path))
    result.setdefault("json", str(json_path))
    write_json(json_path, result)
    return result


__all__ = [
    "API_IMAGE",
    "COLLECTION",
    "MODEL_VOLUME",
    "POLL_EVERY_SECONDS",
    "PREPARED_NAME",
    "VRAM_WAIT_SECONDS",
    "collect_text",
    "compute_done",
    "container_alive",
    "copy_code",
    "deploy_snapshot",
    "ensure_practice",
    "prepare",
    "read_progress",
    "run",
    "run_remote",
    "send_resume",
    "start_api",
    "wait_compute",
    "wait_for_gpu",
]
