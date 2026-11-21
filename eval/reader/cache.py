"""Caché JSONL de recuperación: una línea por caso más un meta JSON.

La clave de caché resume todo lo que puede cambiar el contenido: huella del
dataset, commit del código y si el árbol estaba sucio, configuración, candidatos,
`top_k`, `rrf_k`, troceado, modelos y revisiones, huella de la configuración
dispersa (BM25: idioma, stemmer, k, b, longitud media), semilla y tamaño de
la muestra, y split. Si cualquier entrada cambia, la clave cambia y se genera
otro fichero en lugar de mezclar resultados de condiciones distintas. Los 16
primeros hex del SHA-256 bastan para nombrar el fichero sin colisiones
prácticas.

La escritura es reanudable: `read_cached_case_ids` indica qué casos ya están
guardados y `prepare` solo recupera los que faltan, anexando al final. Una
última línea truncada (corte a mitad de escritura) se ignora con un WARNING y
se reescribe el fichero sin ella; cualquier otra línea malformada es un error.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from eval.reader.retrieve import ReaderHit, RetrievalResult

logger = logging.getLogger(__name__)


def sparse_metadata_hash(metadata: Mapping[str, Any]) -> str:
    """Resume la configuración BM25 que cambia la recuperación.

    Entra el diccionario completo (idioma, stemmer, `k`, `b`, longitud media,
    versión de FastEmbed, hash de stopwords, longitud máxima de token): todos
    cambian los pesos dispersos. Se usa `models.sparse.metadata` (o el
    `sparse` que guarda `Indexer.metadata()` en la colección) como fuente.
    """
    payload = json.dumps(dict(metadata), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_cache_key(
    *,
    dataset_sha256: str,
    commit: str,
    dirty: bool,
    configuration: str,
    candidates: int,
    top_k: int,
    rrf_k: int,
    chunk_size: int,
    chunk_overlap: int,
    dense_model: str,
    dense_revision: str,
    sparse_model: str,
    sparse_revision: str,
    sparse_metadata_hash: str,
    reranker_model: str,
    reranker_revision: str,
    seed: int,
    sample_size: int,
    split: str,
) -> str:
    """Resume las condiciones de recuperación en 16 hex del SHA-256."""
    fingerprint = {
        "dataset_sha256": dataset_sha256,
        "commit": commit,
        "dirty": dirty,
        "configuration": configuration,
        "candidates": candidates,
        "top_k": top_k,
        "rrf_k": rrf_k,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "dense_model": dense_model,
        "dense_revision": dense_revision,
        "sparse_model": sparse_model,
        "sparse_revision": sparse_revision,
        "sparse_metadata_hash": sparse_metadata_hash,
        "reranker_model": reranker_model,
        "reranker_revision": reranker_revision,
        "seed": seed,
        "sample_size": sample_size,
        "split": split,
    }
    payload = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cache_file_paths(results_dir: Path, cache_key: str) -> tuple[Path, Path]:
    """Rutas del JSONL por caso y del meta JSON junto a él."""
    directory = results_dir / "per_query"
    return (
        directory / f"retrieval-{cache_key}.jsonl",
        directory / f"retrieval-{cache_key}.meta.json",
    )


def result_to_record(result: RetrievalResult) -> dict[str, Any]:
    """Convierte un resultado en una línea JSON del fichero de caché."""
    return {
        "case_id": result.case_id,
        "query": result.query,
        "hits": [
            {
                "rank": hit.rank,
                "chunk_id": str(hit.chunk_id),
                "document_key": hit.document_key,
                "text": hit.text,
                "rerank_score": hit.rerank_score,
            }
            for hit in result.hits
        ],
        "latency_ms": result.latency_ms,
    }


def record_to_result(record: dict[str, Any]) -> RetrievalResult:
    """Reconstruye un resultado desde una línea JSON de la caché."""
    from uuid import UUID

    return RetrievalResult(
        case_id=str(record["case_id"]),
        query=str(record["query"]),
        hits=tuple(
            ReaderHit(
                rank=int(item["rank"]),
                chunk_id=UUID(str(item["chunk_id"])),
                document_key=str(item["document_key"]),
                text=str(item["text"]),
                rerank_score=float(item["rerank_score"]),
            )
            for item in record["hits"]
        ),
        latency_ms=float(record["latency_ms"]),
    )


def read_cached_case_ids(path: Path) -> set[str]:
    """Devuelve los casos ya guardados; vacío si la caché aún no existe.

    La última línea truncada (JSON incompleto por un corte de escritura) se
    ignora con un WARNING y se reescribe el fichero sin ella. Cualquier otra
    línea malformada (JSON roto en el medio o sin `case_id`) es un error
    claro con el número de línea.
    """
    if not path.is_file():
        return set()
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    # Índices de las líneas no vacías, para distinguir la última real.
    non_blank = [index for index, line in enumerate(lines) if line.strip()]
    if not non_blank:
        return set()
    last_index = non_blank[-1]
    done: set[str] = set()
    truncated = False
    for position, index in enumerate(non_blank, 1):
        line = lines[index]
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            if index == last_index:
                logger.warning("ignoring truncated last line in %s: %s", path, exc.msg)
                truncated = True
                continue
            raise ValueError(f"Malformed cache line {position} in {path}: invalid JSON") from exc
        try:
            case_id = str(record["case_id"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed cache line {position} in {path}: missing case_id") from exc
        done.add(case_id)
    if truncated:
        kept = [line for index, line in enumerate(lines) if index != last_index]
        # Quita la línea truncada; conserva el resto tal cual.
        text = "\n".join(kept)
        if text and not text.endswith("\n"):
            text += "\n"
        # Si solo había líneas vacías además de la truncada, deja el fichero vacío.
        if not any(line.strip() for line in kept):
            text = ""
        path.write_text(text, encoding="utf-8")
    return done


def append_results(path: Path, results: list[RetrievalResult]) -> None:
    """Anexa resultados al JSONL sin tocar las líneas ya escritas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        for result in results:
            stream.write(json.dumps(result_to_record(result), ensure_ascii=False) + "\n")


def write_meta(path: Path, meta: dict[str, Any]) -> None:
    """Escribe el meta JSON que documenta las condiciones de la caché."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
