"""Descarga cerrada y comprobación de sellados para la fase 1 (C03).

Solo existen tres ficheros de práctica descargables, fichero a fichero, con su
huella SHA-256 verificada antes y después de escribir. Cualquier otra URL se
rechaza sin tocar la red. Los sellados (``dev.json``, ``test.json`` y
``test.csv`` bajo ``eval/.datasets/``) y las preguntas de la reserva en
``prepared/`` hacen fallar la comprobación previa de cada ejecución.

``eval/.datasets/`` está ignorado por Git: los datos nunca se commitean.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = REPO_ROOT / "eval" / ".datasets"
PREPARED_DIR = DATASETS_DIR / "phase1" / "prepared"

SQAC_URL: Final[str] = (
    "https://huggingface.co/datasets/PlanTL-GOB-ES/SQAC/resolve/"
    "f9928e8819596a601b8887cc5f8598b15d589a82/train.json"
)
INFERES_URL: Final[str] = (
    "https://huggingface.co/datasets/venelin/inferes/resolve/"
    "c371a1915e6902b40182b2ae83c5ec7fe5e6cbd2/train.csv"
)
SQAC_SHA256: Final[str] = "1d5c76176646e2ae7bdcd8b5ec6f18349102a9363aa25ad7d0e48262d7480d43"
INFERES_SHA256: Final[str] = "6e7fcef798b3d37522588dbcb5c88e574139aae4cb334fc163168744f12bbe7c"

ALLOWED: Final[dict[str, tuple[str, str]]] = {
    SQAC_URL: ("sqac/train.json", SQAC_SHA256),
    INFERES_URL: ("inferes/train.csv", INFERES_SHA256),
}
SEALED_NAMES: Final[tuple[str, ...]] = ("dev.json", "test.json", "test.csv")
DOWNLOAD_TIMEOUT_SECONDS: Final[float] = 300.0


class SealedError(RuntimeError):
    """Hay datos sellados o reserva donde solo cabe práctica."""


def allowed_target(url: str) -> tuple[Path, str]:
    """Devuelve destino y huella de una URL permitida, sin tocar la red."""
    entry = ALLOWED.get(url)
    if entry is None:
        raise ValueError(f"URL fuera de la lista cerrada: {url}")
    relative, sha256 = entry
    return DATASETS_DIR / relative, sha256


def sha256_file(path: Path) -> str:
    """Calcula la huella SHA-256 de un fichero."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify_file(path: Path, sha256: str) -> None:
    """Rechaza el fichero si su huella no coincide con la fijada."""
    if sha256_file(path) != sha256:
        raise ValueError(f"huella distinta en {path}: borrar y reintentar")


def download_allowed(url: str, timeout_seconds: float = DOWNLOAD_TIMEOUT_SECONDS) -> Path:
    """Descarga un fichero de la lista cerrada de forma atómica y con huella.

    Si el destino ya existe, solo verifica su huella. La escritura usa un
    temporal y un renombre: nunca queda un fichero a medias con el nombre final.
    """
    target, sha256 = allowed_target(url)
    if target.is_file():
        verify_file(target, sha256)
        return target
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != sha256:
        raise ValueError(f"huella de descarga distinta para {target}; nada escrito")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(target.name + ".tmp")
    tmp_path.write_bytes(payload)
    tmp_path.replace(target)
    return target


def find_sealed_files(datasets_dir: Path | None = None) -> list[str]:
    """Lista sellados bajo los datos: dev.json, test.json o test.csv."""
    root = DATASETS_DIR if datasets_dir is None else datasets_dir
    found: list[str] = []
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name in SEALED_NAMES:
            found.append(str(path))
    return found


def find_reserve_in_prepared(reserve_ids: set[str], prepared_dir: Path | None = None) -> list[str]:
    """Busca preguntas de la reserva dentro de los ficheros preparados."""
    root = PREPARED_DIR if prepared_dir is None else prepared_dir
    found: list[str] = []
    if not reserve_ids or not root.is_dir():
        return found
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        hits = _scan_ids(payload, reserve_ids)
        found.extend(f"{path.name}:{hit}" for hit in sorted(hits))
    return found


def _scan_ids(payload: object, reserve_ids: set[str]) -> set[str]:
    """Recoge los identificadores de reserva presentes en un JSON."""
    hits: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in ("id", "case_id", "question_id", "doc", "document_key") and isinstance(
                value, str
            ):
                if value in reserve_ids:
                    hits.add(value)
            else:
                hits |= _scan_ids(value, reserve_ids)
    elif isinstance(payload, list):
        for item in payload:
            hits |= _scan_ids(item, reserve_ids)
    elif isinstance(payload, str) and payload in reserve_ids:
        hits.add(payload)
    return hits


def sealed_precheck(
    datasets_dir: Path | None = None,
    prepared_dir: Path | None = None,
    reserve_ids: set[str] | None = None,
) -> list[str]:
    """Comprueba que no haya sellados ni reserva en preparados.

    Devuelve la lista de problemas (vacía si todo está en orden). Si se
    conocen los identificadores de la reserva de XQuAD-es, también se rastrean
    dentro de ``prepared/``; si no, solo se revisan los nombres sellados.
    """
    errors = [f"sellado bajo eval/.datasets/: {path}" for path in find_sealed_files(datasets_dir)]
    if reserve_ids is None:
        reserve_ids = load_reserve_ids()
    errors.extend(
        f"pregunta de reserva en prepared/: {hit}"
        for hit in find_reserve_in_prepared(reserve_ids, prepared_dir)
    )
    return errors


def load_reserve_ids() -> set[str]:
    """Devuelve los identificadores de la reserva de XQuAD-es, si está descargado."""
    try:
        from eval.reader import xquad
    except ImportError:
        return set()
    path = xquad.default_dataset_path()
    if not path.is_file():
        return set()
    data = xquad.load_dataset(path)
    return {case.case_id for case in xquad.list_cases(data, "reserve", allow_reserve=True)}


def assert_no_sealed() -> None:
    """Falla cerrado si hay sellados o reserva en preparados."""
    errors = sealed_precheck()
    if errors:
        raise SealedError("; ".join(errors))


__all__ = [
    "ALLOWED",
    "DATASETS_DIR",
    "DOWNLOAD_TIMEOUT_SECONDS",
    "INFERES_SHA256",
    "INFERES_URL",
    "PREPARED_DIR",
    "SEALED_NAMES",
    "SQAC_SHA256",
    "SQAC_URL",
    "SealedError",
    "allowed_target",
    "assert_no_sealed",
    "download_allowed",
    "find_reserve_in_prepared",
    "find_sealed_files",
    "load_reserve_ids",
    "sealed_precheck",
    "sha256_file",
    "verify_file",
]
