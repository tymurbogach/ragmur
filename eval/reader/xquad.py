"""Descarga fijada, partición y casos del banco XQuAD-es.

XQuAD-es es la parte en español de XQuAD, un conjunto de preguntas con su
respuesta humana sobre párrafos de Wikipedia (formato SQuAD v1.1: artículos
con párrafos, cada párrafo con preguntas y respuestas). En esta fase el
conjunto solo aporta preguntas y respuestas humanas; ningún modelo genera ni
juzga nada aquí.

La descarga queda fijada a un commit concreto del repositorio
`google-deepmind/xquad` (nunca a `master`, que puede cambiar) y se rechaza
cualquier fichero cuyo SHA-256 no coincida. Los datos viven en
`eval/.datasets/`, ignorado por Git. Licencia: CC BY-SA 4.0.

La partición es por artículo (título): se ordenan los títulos, se barajan con
una semilla fija y los 36 primeros son `dev` y los 12 últimos `reserve`. La
reserva queda sellada: `list_cases` se niega a devolverla salvo que se pase
`allow_reserve=True`, y G03a/G04 nunca lo pasan.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATASET_URL = (
    "https://raw.githubusercontent.com/google-deepmind/xquad"
    "/7d30520c717524000f0d9d2f9c10a069acd9d285/xquad.es.json"
)
DATASET_SHA256 = "dcbae93ec3a9f4b9e78fd834a171d6f96c1a875e10e15b7530b7e4ef4971e37e"
DATASET_LICENSE = "CC BY-SA 4.0"
DATASET_RELATIVE_PATH = Path("eval/.datasets/xquad/xquad.es.json")
PARTITION_SEED = 20261121
EXPECTED_ARTICLES = 48
DEV_ARTICLES = 36
DOWNLOAD_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class ReaderCase:
    """Una pregunta con sus respuestas humanas y su párrafo de origen."""

    case_id: str
    article: str
    paragraph_index: int
    question: str
    answers: tuple[str, ...]
    split: str
    document_key: str


def default_dataset_path() -> Path:
    """Ruta del fichero XQuAD-es dentro de `eval/.datasets/`."""
    return DATASET_RELATIVE_PATH


def dataset_sha256(path: Path) -> str:
    """Calcula el SHA-256 del fichero descargado."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def verify_dataset_file(path: Path) -> None:
    """Rechaza el fichero si su huella no coincide con la fijada en código."""
    if dataset_sha256(path) != DATASET_SHA256:
        raise ValueError(f"XQuAD-es hash mismatch for {path}: delete {path} and retry the download")


def download_dataset(
    path: Path | None = None, timeout_seconds: float = DOWNLOAD_TIMEOUT_SECONDS
) -> Path:
    """Descarga XQuAD-es si falta y verifica su huella en ambos casos."""
    target = path if path is not None else default_dataset_path()
    if target.is_file():
        verify_dataset_file(target)
        return target
    logger.info("descargando XQuAD-es desde %s", DATASET_URL)
    with urllib.request.urlopen(DATASET_URL, timeout=timeout_seconds) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != DATASET_SHA256:
        raise ValueError(f"XQuAD-es download hash mismatch for {target}; nothing written, retry")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_name(target.name + ".tmp")
    tmp_path.write_bytes(payload)
    tmp_path.replace(target)
    return target


def load_dataset(path: Path) -> dict[str, Any]:
    """Verifica la huella y carga el JSON en formato SQuAD v1.1."""
    verify_dataset_file(path)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def document_key(article: str, paragraph_index: int) -> str:
    """Identidad legible del documento: un documento Ragmur por párrafo."""
    return f"xquad-es:{article}:{paragraph_index}"


def iter_paragraphs(data: dict[str, Any]) -> list[tuple[str, str]]:
    """Devuelve pares `(document_key, contexto)` en el orden del fichero."""
    output: list[tuple[str, str]] = []
    for article in data.get("data", []):
        title = article["title"]
        for index, paragraph in enumerate(article["paragraphs"]):
            output.append((document_key(title, index), paragraph["context"]))
    return output


def check_article_count(titles: list[str]) -> None:
    """Exige los 48 artículos esperados antes de indexar o partir."""
    found = len(set(titles))
    if found != EXPECTED_ARTICLES:
        raise ValueError(f"XQuAD-es must contain {EXPECTED_ARTICLES} articles, found {found}")


def split_articles(
    titles: list[str], seed: int = PARTITION_SEED, dev_size: int = DEV_ARTICLES
) -> dict[str, str]:
    """Reparte los artículos entre `dev` y `reserve` de forma reproducible."""
    unique = sorted(set(titles))
    if dev_size < 0 or dev_size > len(unique):
        raise ValueError("Invalid dev split size")
    order = list(unique)
    random.Random(seed).shuffle(order)
    return {
        title: ("dev" if position < dev_size else "reserve") for position, title in enumerate(order)
    }


def list_cases(
    data: dict[str, Any],
    split: str,
    *,
    allow_reserve: bool = False,
    seed: int = PARTITION_SEED,
    dev_size: int = DEV_ARTICLES,
) -> list[ReaderCase]:
    """Construye los casos de un split sin abrir nunca la reserva sellada."""
    if split not in ("dev", "reserve"):
        raise ValueError("Split must be dev or reserve")
    if split == "reserve" and not allow_reserve:
        raise ValueError("The reserve split is sealed for this phase")
    mapping = split_articles([article["title"] for article in data.get("data", [])], seed, dev_size)
    cases: list[ReaderCase] = []
    for article in data.get("data", []):
        title = article["title"]
        if mapping[title] != split:
            continue
        for index, paragraph in enumerate(article["paragraphs"]):
            for qa in paragraph["qas"]:
                answers = tuple(
                    dict.fromkeys(
                        text.strip()
                        for text in (item["text"] for item in qa["answers"])
                        if text.strip()
                    )
                )
                cases.append(
                    ReaderCase(
                        case_id=qa["id"],
                        article=title,
                        paragraph_index=index,
                        question=qa["question"],
                        answers=answers,
                        split=split,
                        document_key=document_key(title, index),
                    )
                )
    return cases


def sample_cases(cases: list[ReaderCase], sample_size: int, seed: int) -> list[ReaderCase]:
    """Elige N casos de forma determinista sobre los casos ordenados por id."""
    if sample_size < 1 or sample_size > len(cases):
        raise ValueError("Invalid sample size for the available cases")
    ordered = sorted(cases, key=lambda case: case.case_id)
    return random.Random(seed).sample(ordered, sample_size)
