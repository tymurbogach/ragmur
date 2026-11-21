"""Prepara el banco XQuAD-es: descarga, indexa, recupera y cachea.

Flujo: verifica la descarga fijada, indexa todos los párrafos como documentos
del tenant propio (el corpus completo, incluidos los artículos de reserva:
la reserva sellada son sus preguntas, que aquí nunca se leen) y guarda la
recuperación de la muestra `dev` en un JSONL reanudable. Sin LLM.

Ejemplo:
    uv run python -m eval.reader.prepare --split dev --sample-size 100
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
from datetime import UTC, datetime
from pathlib import Path

from eval.reader.cache import (
    append_results,
    build_cache_key,
    cache_file_paths,
    read_cached_case_ids,
    sparse_metadata_hash,
    write_meta,
)
from eval.reader.gitstate import is_dirty_tree as is_dirty_tree
from eval.reader.index import (
    DEFAULT_COLLECTION_SUFFIX,
    READER_TENANT_UUID,
    index_paragraphs,
    reader_collection_name,
)
from eval.reader.retrieve import SUPPORTED_CONFIGURATION, retrieve_case
from eval.reader.xquad import (
    DATASET_LICENSE,
    DATASET_URL,
    PARTITION_SEED,
    check_article_count,
    dataset_sha256,
    default_dataset_path,
    download_dataset,
    iter_paragraphs,
    list_cases,
    load_dataset,
    sample_cases,
)
from eval.run import hardware_info, read_commit
from ragmur.core.config import Settings, get_settings
from ragmur.core.logging import configure_logging
from ragmur.retrieval import store
from ragmur.retrieval.models import load_models

logger = logging.getLogger(__name__)


def build_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Define la interfaz de línea de órdenes de la preparación."""
    parser = argparse.ArgumentParser(description="Prepara el banco de lectura XQuAD-es")
    parser.add_argument("--split", choices=("dev", "reserve"), default="dev")
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=PARTITION_SEED)
    parser.add_argument("--candidates", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--collection-suffix", type=str, default=DEFAULT_COLLECTION_SUFFIX)
    parser.add_argument("--results-dir", type=Path, default=Path("eval/results/reader"))
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--reuse-index", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args(argv)


async def prepare_bank(
    settings: Settings,
    *,
    split: str,
    sample_size: int,
    seed: int,
    candidates: int,
    top_k: int,
    collection_suffix: str,
    results_dir: Path,
    dataset_path: Path | None,
    reuse_index: bool,
    allow_dirty: bool = False,
) -> Path:
    """Descarga, indexa, recupera los casos que faltan y devuelve la caché."""
    if not collection_suffix:
        raise ValueError("Preparation requires a non-empty --collection-suffix")
    if candidates < 1 or top_k < 1 or top_k > candidates:
        raise ValueError("Preparation requires 1 <= top_k <= candidates")
    dirty = is_dirty_tree()
    if dirty and not allow_dirty:
        raise RuntimeError(
            "Refusing to run with a dirty tree (src/eval); "
            "commit the changes or retry with --allow-dirty"
        )
    target = dataset_path if dataset_path is not None else default_dataset_path()
    download_dataset(target)
    data = load_dataset(target)
    titles = [article["title"] for article in data.get("data", [])]
    check_article_count(titles)
    paragraphs = iter_paragraphs(data)
    cases = list_cases(data, split)
    selected = sample_cases(cases, sample_size, seed)
    models = await asyncio.to_thread(load_models, settings)
    client = store.create_client(settings.qdrant_url, settings.health_timeout_seconds)
    try:
        await store.ping(client)
        collection = reader_collection_name(settings, collection_suffix)
        mapping = await index_paragraphs(
            models=models,
            settings=settings,
            client=client,
            collection=collection,
            tenant_id=READER_TENANT_UUID,
            paragraphs=paragraphs,
            reuse_index=reuse_index,
        )
        sparse_hash = sparse_metadata_hash(models.sparse.metadata)
        commit = read_commit()
        cache_key = build_cache_key(
            dataset_sha256=dataset_sha256(target),
            commit=commit,
            dirty=dirty,
            configuration=SUPPORTED_CONFIGURATION,
            candidates=candidates,
            top_k=top_k,
            rrf_k=settings.rrf_k,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            dense_model=settings.embedding_model,
            dense_revision=settings.embedding_revision,
            sparse_model=settings.bm25_model,
            sparse_revision=settings.bm25_revision,
            sparse_metadata_hash=sparse_hash,
            reranker_model=settings.reranker_model,
            reranker_revision=settings.reranker_revision,
            seed=seed,
            sample_size=sample_size,
            split=split,
        )
        jsonl_path, meta_path = cache_file_paths(results_dir, cache_key)
        done = read_cached_case_ids(jsonl_path)
        now = datetime.now(UTC).isoformat()
        created_at = now
        if meta_path.is_file():
            try:
                existing = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(existing.get("created_at"), str):
                    created_at = str(existing["created_at"])
            except (OSError, ValueError):
                created_at = now
        meta: dict[str, object] = {
            "cache_key": cache_key,
            "created_at": created_at,
            "updated_at": now,
            "dataset": {
                "url": DATASET_URL,
                "sha256": dataset_sha256(target),
                "license": DATASET_LICENSE,
                "path": str(target),
                "articles": len(set(titles)),
                "paragraphs": len(paragraphs),
            },
            "commit": commit,
            "dirty": dirty,
            "configuration": SUPPORTED_CONFIGURATION,
            "candidates": candidates,
            "top_k": top_k,
            "rrf_k": settings.rrf_k,
            "sparse_metadata_hash": sparse_hash,
            "sparse_metadata": dict(models.sparse.metadata),
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "models": {
                "dense_model": settings.embedding_model,
                "dense_revision": settings.embedding_revision,
                "sparse_model": settings.bm25_model,
                "sparse_revision": settings.bm25_revision,
                "reranker_model": settings.reranker_model,
                "reranker_revision": settings.reranker_revision,
            },
            "sample": {
                "split": split,
                "seed": seed,
                "sample_size": sample_size,
                "cases": len(selected),
            },
            "collection": collection,
            "tenant": str(READER_TENANT_UUID),
            "hardware": hardware_info(settings),
        }
        write_meta(meta_path, meta)
        document_keys = {str(document_id): key for key, document_id in mapping.items()}
        pending = [case for case in selected if case.case_id not in done]
        logger.info(
            "recuperando casos pendientes",
            extra={"pending": len(pending), "cached": len(done), "cache_key": cache_key},
        )
        for case in pending:
            result = await retrieve_case(
                case=case,
                models=models,
                settings=settings,
                client=client,
                collection=collection,
                tenant_id=READER_TENANT_UUID,
                document_keys=document_keys,
                candidates=candidates,
                top_k=top_k,
            )
            append_results(jsonl_path, [result])
        latencies = _read_latencies(jsonl_path)
        if latencies:
            ordered = sorted(latencies)
            meta["retrieval_latency_ms"] = {
                "count": len(ordered),
                "p50": statistics.median(ordered),
                "p95": ordered[max(0, (len(ordered) * 95 + 99) // 100 - 1)],
            }
            meta["updated_at"] = datetime.now(UTC).isoformat()
            write_meta(meta_path, meta)
        return jsonl_path
    finally:
        await client.close()


def _read_latencies(jsonl_path: Path) -> list[float]:
    """Lee las latencias guardadas para resumirlas en el meta."""
    if not jsonl_path.is_file():
        return []
    latencies: list[float] = []
    with jsonl_path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                latencies.append(float(json.loads(line)["latency_ms"]))
            except (ValueError, KeyError, TypeError):
                continue
    return latencies


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada sin `print`: el resultado va al log."""
    args = build_arguments(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    path = asyncio.run(
        prepare_bank(
            settings,
            split=args.split,
            sample_size=args.sample_size,
            seed=args.seed,
            candidates=args.candidates,
            top_k=args.top_k,
            collection_suffix=args.collection_suffix,
            results_dir=args.results_dir,
            dataset_path=args.dataset_path,
            reuse_index=args.reuse_index,
            allow_dirty=args.allow_dirty,
        )
    )
    logger.info("caché de recuperación escrita en %s", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
