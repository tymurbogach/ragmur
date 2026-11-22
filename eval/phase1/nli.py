"""Etapa nli C03: verificador con miles de frases en la RTX 5080.

El portátil prepara (descarga cerrada, selección congelada, preparados que
viajan) y el contenedor ``$P-api`` calcula sobre los preparados, sin importar
cargadores de conjuntos. La salida se resume en matrices por tipo y con 1, 3
y 5 textos, con intervalos de Wilson y referencias de calidad diagnósticas.

Sin Skynet no hay GPU y la etapa queda como error de infraestructura.
"""

from __future__ import annotations

import base64
import binascii
import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from eval.phase1 import datasets, nli_data, skynet
from eval.phase1.nli_data import Pair
from eval.phase1.runner import REPO_ROOT, write_json

API_IMAGE = "ragmur_deploy-api:latest"
MODEL_VOLUME = "ragmur_deploy_model_data"
VRAM_REQUIRED_MIB = 8192
VRAM_WAIT_SECONDS = 900.0
POLL_EVERY_SECONDS = 60.0
PREPARED_NAME = "nli.json"


def read_train_rows(path: Path) -> list[dict[str, str]]:
    """Lee las filas de ``train.csv`` en el orden del fichero."""
    with path.open(encoding="utf-8", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def ensure_practice(log: Any) -> dict[str, Path]:
    """Descarga la lista cerrada y devuelve las rutas de los tres ficheros."""
    paths = {
        "inferes": datasets.download_allowed(datasets.INFERES_URL),
        "sqac": datasets.download_allowed(datasets.SQAC_URL),
    }
    from eval.reader import xquad

    xquad_path = xquad.download_dataset()
    paths["xquad"] = xquad_path
    log(f"práctica: inferes={paths['inferes'].stat().st_size} sqac={paths['sqac'].stat().st_size}")
    return paths


def check_vectors(pairs: list[Pair]) -> list[str]:
    """Comprueba los vectores de distractores fijados en el plan."""
    errors: list[str] = []
    by_id = {pair.id: pair for pair in pairs}
    for wanted_id, wanted in nli_data.EXPECTED_VECTORS.items():
        pair = by_id.get(wanted_id)
        if pair is None:
            errors.append(f"vector {wanted_id}: par ausente en la selección")
            continue
        got = tuple(extra.id for extra in nli_data.distractors(pairs, pair, 5)[1:])
        if got != wanted:
            errors.append(f"vector {wanted_id}: {','.join(got)} frente a {','.join(wanted)}")
    return errors


def prepare() -> tuple[list[Pair], Path, list[str]]:
    """Prepara los pares de práctica y escribe el fichero que viaja al contenedor."""
    notes: list[str] = []
    sealed = datasets.sealed_precheck()
    if sealed:
        raise datasets.SealedError("; ".join(sealed))
    paths = ensure_practice(notes.append)
    rows = read_train_rows(paths["inferes"])
    pairs = nli_data.select_pairs(rows)
    notes.append(f"selección: {len(pairs)} pares, principal {len(nli_data.principal_only(pairs))}")
    errors: list[str] = []
    if len(pairs) != nli_data.EXPECTED_TOTAL:
        errors.append(f"{len(pairs)} pares frente a {nli_data.EXPECTED_TOTAL}")
    if len(nli_data.principal_only(pairs)) != nli_data.EXPECTED_PRINCIPAL:
        errors.append("cifra principal distinta de 3124")
    errors.extend(check_vectors(pairs))
    if errors:
        raise ValueError("; ".join(errors))
    prepared = datasets.PREPARED_DIR / PREPARED_NAME
    prepared.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "id": pair.id,
            "premise": pair.premise,
            "hypothesis": pair.hypothesis,
            "label": pair.label,
            "topic": pair.topic,
            "anno": pair.anno,
        }
        for pair in pairs
    ]
    tmp_path = prepared.with_name(prepared.name + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(prepared)
    notes.append(f"preparado: {prepared} ({len(payload)} pares)")
    return pairs, prepared, notes


def gpu_free_mib(host: str) -> int:
    """Lee la VRAM libre de la GPU vía ``nvidia-smi`` (una sola llamada)."""
    out = skynet.remote(
        host, "nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"
    )
    values = [int(line.strip()) for line in out.splitlines() if line.strip().isdigit()]
    if not values:
        raise skynet.SkynetError(f"nvidia-smi sin cifras: {out[:200]!r}")
    return min(values)


def wait_for_gpu(host: str, deadline: float, log: Any) -> None:
    """Espera hasta 15 min a 8 GiB libres; si no, falla como infraestructura."""
    while True:
        free = gpu_free_mib(host)
        log(f"VRAM libre: {free} MiB")
        if free >= VRAM_REQUIRED_MIB:
            return
        if time.time() >= deadline:
            raise skynet.SkynetError(f"solo {free} MiB libres tras la espera")
        time.sleep(POLL_EVERY_SECONDS)


def deploy_snapshot(host: str | None) -> set[str]:
    """Registra los contenedores del despliegue que nunca se deben tocar."""
    out = skynet.remote(host, "docker", "ps", "--format", "{{.ID}},{{.Names}}")
    return {line.strip() for line in out.splitlines() if "ragmur_deploy" in line and line.strip()}


def start_api(host: str, run_id: str, network: str) -> str:
    """Levanta el contenedor de cálculo con GPU y modelos de solo lectura."""
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
        "QDRANT_URL=http://127.0.0.1:6333",
        "-e",
        "PYTHONPATH=/tmp/code/src:/tmp/code",
        API_IMAGE,
        "sleep",
        "7200",
        timeout=180.0,
    )
    return name


def copy_code(host: str, api: str, log_path: Path) -> None:
    """Copia el código y los preparados al contenedor (tubería local, sin shell remota)."""
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
            ssh_code = ssh_proc.wait(timeout=600.0)
            tar_code = tar_proc.wait(timeout=60.0)
        finally:
            for proc in (tar_proc, ssh_proc):
                if proc.poll() is None:
                    proc.kill()
        if tar_code != 0 or ssh_code != 0:
            raise skynet.SkynetError(f"copia de código fallida: tar={tar_code} ssh={ssh_code}")


def container_alive(host: str, api: str) -> bool:
    """Comprueba que el contenedor de cálculo siga en marcha."""
    out = skynet.remote(host, "docker", "ps", "-q", "--filter", f"name={api}")
    return bool(out.strip())


def compute_done(host: str, api: str) -> bool:
    """Comprueba el marcador que el cálculo escribe al terminar."""
    try:
        skynet.remote(host, "docker", "exec", api, "test", "-f", "/tmp/nli-done")
    except skynet.SkynetError:
        return False
    return True


def wait_compute(host: str, api: str, deadline: float, log: Any) -> None:
    """Espera el marcador del cálculo; si el contenedor muere, falla."""
    while time.time() < deadline:
        if compute_done(host, api):
            return
        if not container_alive(host, api):
            raise skynet.SkynetError("el contenedor de cálculo murió antes de terminar")
        log("cálculo en curso...")
        time.sleep(POLL_EVERY_SECONDS)
    raise skynet.SkynetError("plazo del cálculo agotado")


def collect_text(host: str, api: str, path: str) -> str:
    """Recoge un fichero del contenedor en base64 (una sola llamada)."""
    out = skynet.remote(host, "docker", "exec", api, "base64", "-w0", path, timeout=300.0)
    try:
        return base64.b64decode(out).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise skynet.SkynetError(f"no se pudo decodificar {path}: {exc}") from exc


def run_remote(host: str, run_id: str, log: Any, log_path: Path, deadline: float) -> dict[str, Any]:
    """Levanta el contenedor GPU, calcula, recoge y limpia siempre."""
    before = deploy_snapshot(host)
    network = skynet.create_network(host, run_id)
    api = ""
    try:
        wait_for_gpu(host, time.time() + VRAM_WAIT_SECONDS, log)
        api = start_api(host, run_id, network)
        copy_code(host, api, log_path)
        skynet.remote(
            host,
            "docker",
            "exec",
            "-d",
            api,
            "/app/.venv/bin/python",
            "-m",
            "eval.phase1.nli_compute",
            "--prepared",
            "/tmp/code/eval/.datasets/phase1/prepared/nli.json",
            "--out",
            "/tmp/nli-out.json",
            "--log",
            "/tmp/nli-run.log",
        )
        wait_compute(host, api, deadline, log)
        try:
            container_log = skynet.remote(host, "docker", "exec", api, "cat", "/tmp/nli-run.log")
            log(f"contenedor: {container_log.strip()[-2000:]}")
        except skynet.SkynetError:
            log("contenedor: sin log interno")
        payload = json.loads(collect_text(host, api, "/tmp/nli-out.json"))
        if not isinstance(payload, dict):
            raise skynet.SkynetError("salida del cálculo ilegible")
        return payload
    finally:
        if api:
            skynet.stop_container(host, api)
        skynet.remove_network(host, network)
        after = deploy_snapshot(host)
        if after != before:
            raise skynet.SkynetError(
                f"el despliegue cambió: antes {sorted(before)} ahora {sorted(after)}"
            )


def summarize(pairs: list[Pair], payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Compara celdas (±5), aplica referencias y devuelve estado, motivo y resumen."""
    rows = payload.get("rows")
    if not isinstance(rows, list) or len(rows) != nli_data.EXPECTED_TOTAL:
        got = len(rows) if isinstance(rows, list) else type(rows).__name__
        return "hard_failed", f"cálculo incompleto: {got} pares", {}
    by_id = {str(row.get("id")): row for row in rows if isinstance(row, dict)}
    if len(by_id) != nli_data.EXPECTED_TOTAL:
        return "hard_failed", "identificadores duplicados o ausentes en la salida", {}
    kinds = {pair.id for pair in pairs if pair.anno != "Automated"}
    principal = [by_id[pair_id] for pair_id in kinds if pair_id in by_id]
    if len(principal) != nli_data.EXPECTED_PRINCIPAL:
        return "hard_failed", f"principal {len(principal)} frente a 3124", {}
    for row in principal:
        row["y"] = str(row.get("y"))
    matrices = {key: nli_data.confusion(principal, key) for key in ("v", "v3", "v5")}
    mismatches: list[str] = []
    for key, count in ((1, "v"), (3, "v3"), (5, "v5")):
        mismatches.extend(nli_data.cell_mismatches(matrices[count], key))
    if mismatches:
        return "hard_failed", "; ".join(mismatches[:6]), {"mismatches": mismatches}
    refs = nli_data.quality_refs(matrices["v"])
    baseline_hits = sum(
        1
        for pair in pairs
        if pair.anno != "Automated" and nli_data.baseline_shape(pair.hypothesis) == pair.label
    )
    summary: dict[str, Any] = {
        "device": payload.get("device"),
        "thresholds": payload.get("thresholds"),
        "elapsed_s": payload.get("elapsed_s"),
        "counts": {"total": len(rows), "principal": len(principal)},
        "matrices": {
            key: {human: dict(counter) for human, counter in matrix.items()}
            for key, matrix in matrices.items()
        },
        "refs": refs,
        "baseline_shape_accuracy": baseline_hits / len(principal) if principal else 0.0,
    }
    quality = nli_data.quality_errors(refs)
    if quality:
        return "quality_failed", "; ".join(quality), summary
    return "passed", f"3124 pares, respaldo falso {refs['false_support']:.3f}", summary


def run(
    directory: Path,
    ssh_host: str | None,
    timeout: float = 5400.0,
) -> dict[str, Any]:
    """Ejecuta la etapa nli y escribe su log y su JSON."""
    log_path = directory / "nli.log"
    json_path = directory / "nli.json"
    notes: list[str] = []

    def log(message: str) -> None:
        notes.append(message)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    started = time.time()
    result: dict[str, Any] = {"state": "infra_error", "reason": "sin empezar"}
    try:
        if ssh_host is None:
            raise skynet.SkynetError("sin Skynet no hay GPU para la etapa nli")
        pairs, _, prepare_notes = prepare()
        for note in prepare_notes:
            log(note)
        payload = run_remote(ssh_host, directory.name, log, log_path, time.time() + timeout)
        state, reason, summary = summarize(pairs, payload)
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
    "MODEL_VOLUME",
    "POLL_EVERY_SECONDS",
    "PREPARED_NAME",
    "VRAM_REQUIRED_MIB",
    "VRAM_WAIT_SECONDS",
    "check_vectors",
    "collect_text",
    "compute_done",
    "container_alive",
    "copy_code",
    "deploy_snapshot",
    "ensure_practice",
    "gpu_free_mib",
    "prepare",
    "read_train_rows",
    "run",
    "run_remote",
    "start_api",
    "summarize",
    "wait_compute",
    "wait_for_gpu",
]
