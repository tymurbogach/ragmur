"""Ejecución reproducible de la evaluación de recuperación.

Ingiere el corpus del manifiesto en una colección de evaluación, ejecuta las
cuatro configuraciones (densa, BM25, híbrida, híbrida + reranking) con el mismo
presupuesto de candidatos y `top_k=10`, y resume recall, hit-rate, MRR, nDCG y
latencias. Usa inferencia real; los modelos simulados solo existen en unitarios.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from eval.dataset import QuerySpec, load_manifest, load_queries, validate_dataset
from eval.metrics import (
    Evidence,
    Hit,
    Locator,
    QueryMetrics,
    compare_recall,
    evaluate_query,
    summarize,
)
from ragmur.core.config import Settings, get_settings
from ragmur.ingestion.chunker import split_document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels, load_models
from ragmur.retrieval.sparse import SparseVector

logger = logging.getLogger(__name__)

EVAL_TENANT_UUID = uuid5(NAMESPACE_DNS, "ragmur.eval.demo")
CONFIGURATIONS = ("dense", "sparse", "hybrid", "hybrid_rerank")


def document_uuid(key: str) -> UUID:
    """Identidad estable del documento dentro de la evaluación."""
    return uuid5(NAMESPACE_DNS, f"ragmur.eval.doc:{key}")


def build_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Define la interfaz de línea de órdenes del evaluador."""
    parser = argparse.ArgumentParser(description="Evalúa la recuperación sobre el golden set")
    parser.add_argument("--manifest", type=Path, default=Path("eval/manifest.yaml"))
    parser.add_argument("--golden", type=Path, default=Path("eval/golden_set.yaml"))
    parser.add_argument("--candidates", type=int, default=30)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--split", choices=("dev", "test", "all"), default="all")
    parser.add_argument("--collection-suffix", type=str, default="_eval")
    parser.add_argument("--results-dir", type=Path, default=Path("eval/results"))
    parser.add_argument("--reuse-index", action="store_true")
    return parser.parse_args(argv)


def read_commit() -> str:
    """Devuelve el commit actual o `unknown` si no hay Git disponible."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def hardware_info(settings: Settings) -> dict[str, object]:
    """Registra el hardware y el entorno de la ejecución."""
    cuda_available = False
    cuda_name: str | None = None
    torch_version = "unknown"
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            cuda_name = str(torch.cuda.get_device_name(0))
        torch_version = str(torch.__version__)
    except Exception:
        pass
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "device": settings.embedding_device,
        "torch_version": torch_version,
        "cuda_available": cuda_available,
        "cuda_device_name": cuda_name,
        "omp_threads": os.environ.get("OMP_NUM_THREADS"),
        "concurrency": 1,
    }


def read_text(path: Path) -> str:
    """Lee un fichero de texto en el hilo actual."""
    return path.read_text(encoding="utf-8")


def _manifest_hash(path: Path) -> str:
    """Calcula el hash del manifiesto sin bloquear el bucle de eventos."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def index_corpus(
    models: EmbeddingModels,
    settings: Settings,
    collection: str,
    manifest_path: Path,
    tenant_id: UUID,
    reuse_index: bool,
) -> dict[str, UUID]:
    """Trocea, embebe y publica el corpus de evaluación en Qdrant."""
    manifest = load_manifest(manifest_path)
    client = store.create_client(settings.qdrant_url, settings.health_timeout_seconds)
    try:
        await store.ping(client)
        from ragmur.ingestion.indexer import Indexer

        indexer = Indexer(client, models, settings)
        await store.ensure_collection(
            tenant_id, client, collection, models.dense.dimension, indexer.metadata()
        )
        if not reuse_index:
            await store.delete_tenant_points(tenant_id, client, collection)
        mapping: dict[str, UUID] = {}
        for document in manifest.documents:
            doc_id = document_uuid(document.key)
            mapping[document.key] = doc_id
            if reuse_index:
                count = await store.count_document_points(tenant_id, client, collection, doc_id)
                if count > 0:
                    continue
            else:
                await store.delete_document_points(tenant_id, client, collection, doc_id)
            resolved = (manifest_path.parent / document.path).resolve()
            text = await asyncio.to_thread(read_text, resolved)
            extraction = ExtractionResult(
                [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
            )
            chunked = split_document(
                extraction,
                doc_id,
                tenant_id,
                document.owner_id,
                size=settings.chunk_size,
                overlap=settings.chunk_overlap,
            )
            if not chunked.chunks:
                raise RuntimeError(f"Document {document.key} has no chunks")
            for start in range(0, len(chunked.chunks), settings.index_batch_size):
                batch = chunked.chunks[start : start + settings.index_batch_size]
                texts = [chunk.text for chunk in batch]
                dense = await asyncio.to_thread(
                    models.dense.embed, texts, settings.embedding_batch_size
                )
                sparse = await asyncio.to_thread(
                    models.sparse.embed, texts, settings.embedding_batch_size
                )
                points = [
                    store.VectorPoint(
                        id=chunk.id,
                        document_id=doc_id,
                        owner_id=document.owner_id,
                        filename=Path(document.path).name,
                        text=chunk.text,
                        ordinal=chunk.ordinal,
                        start=chunk.start,
                        end=chunk.end,
                        locator=chunk.locator,
                        dense=dense_vector,
                        sparse_indices=sparse_vector.indices,
                        sparse_values=sparse_vector.values,
                    )
                    for chunk, dense_vector, sparse_vector in zip(batch, dense, sparse, strict=True)
                ]
                await store.upsert_points(tenant_id, client, collection, points)
        return mapping
    finally:
        await client.close()


def hit_from_payload(payload: dict[str, object]) -> Hit:
    """Convierte el payload de Qdrant en evidencia recuperada."""
    from typing import cast

    document_id = UUID(str(payload["document_id"]))
    locator = cast(Locator, payload["locator"])
    text = payload["text"]
    if not isinstance(text, str):
        raise RuntimeError("Qdrant returned a point without text")
    return Hit(document_id=document_id, locator=locator, text=text)


def expected_evidences(query: QuerySpec, mapping: dict[str, UUID]) -> list[Evidence]:
    """Resuelve las claves del golden set a UUID de la ingesta actual."""
    from typing import cast

    evidences: list[Evidence] = []
    for item in query.expected:
        doc_id = mapping[item.document]
        locator = cast(Locator, item.locator.model_dump())
        evidences.append(
            Evidence(
                evidence_id=item.evidence_id,
                document_id=doc_id,
                locator=locator,
                quote=item.quote,
            )
        )
    return evidences


async def run_configuration(
    configuration: str,
    models: EmbeddingModels,
    settings: Settings,
    client: store.AsyncQdrantClient,
    collection: str,
    tenant_id: UUID,
    queries: list[QuerySpec],
    mapping: dict[str, UUID],
    candidates: int,
    top_k: int,
) -> tuple[dict[str, QueryMetrics], list[float], dict[str, dict[str, object]]]:
    """Ejecuta una configuración sobre todas las consultas y mide su latencia."""
    metrics: dict[str, QueryMetrics] = {}
    latencies: list[float] = []
    details: dict[str, dict[str, object]] = {}
    for query in queries:
        started = time.perf_counter()
        dense: list[list[float]] | None = None
        sparse: SparseVector | None = None
        if configuration in ("dense", "hybrid", "hybrid_rerank"):
            dense = await asyncio.to_thread(
                models.dense.embed, [query.query], settings.embedding_batch_size
            )
        if configuration in ("sparse", "hybrid", "hybrid_rerank"):
            sparse = await asyncio.to_thread(models.sparse.query_embed, query.query)
        assert dense is not None or sparse is not None
        candidate_hits: list[Hit] = []
        if configuration == "dense":
            assert dense is not None
            points = await store.branch_search(
                tenant_id,
                client,
                collection,
                branch="dense",
                dense=dense[0],
                sparse_indices=[],
                sparse_values=[],
                owner_id=query.scope.owner_id,
                document_ids=None,
                limit=candidates,
            )
            candidate_hits = [hit_from_payload(point.payload) for point in points]
        elif configuration == "sparse":
            assert sparse is not None
            points = await store.branch_search(
                tenant_id,
                client,
                collection,
                branch="sparse",
                dense=[],
                sparse_indices=sparse.indices,
                sparse_values=sparse.values,
                owner_id=query.scope.owner_id,
                document_ids=None,
                limit=candidates,
            )
            candidate_hits = [hit_from_payload(point.payload) for point in points]
        elif configuration in ("hybrid", "hybrid_rerank"):
            assert dense is not None and sparse is not None
            fused = await store.hybrid_search(
                tenant_id,
                client,
                collection,
                dense[0],
                sparse.indices,
                sparse.values,
                owner_id=query.scope.owner_id,
                document_ids=None,
                candidates=candidates,
                rrf_k=settings.rrf_k,
            )
            candidate_hits = [hit_from_payload(point.payload) for point in fused]
        else:
            raise ValueError(f"Unknown configuration: {configuration}")
        result_hits = list(candidate_hits[:top_k])
        if configuration == "hybrid_rerank" and candidate_hits:
            if models.reranker is None:
                raise RuntimeError("Reranker is required for the hybrid_rerank configuration")
            scores = await asyncio.to_thread(
                models.reranker.score,
                query.query,
                [hit.text for hit in candidate_hits],
                settings.reranker_batch_size,
            )
            ranked = sorted(
                zip(candidate_hits, scores, strict=True), key=lambda pair: pair[1], reverse=True
            )
            result_hits = [hit for hit, _ in ranked[:top_k]]
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        latencies.append(elapsed_ms)
        expected = expected_evidences(query, mapping)
        query_metrics = evaluate_query(expected, candidate_hits, result_hits)
        metrics[query.id] = query_metrics
        details[query.id] = {
            "expected": len(expected),
            "candidates": len(candidate_hits),
            "results": len(result_hits),
            "latency_ms": elapsed_ms,
            "recall_candidates": query_metrics.recall_candidates,
            "recall_at_10": query_metrics.recall_at_10,
            "hit_rate_at_10": query_metrics.hit_rate_at_10,
            "mrr_at_10": query_metrics.reciprocal_rank_at_10,
            "ndcg_at_10": query_metrics.ndcg_at_10,
        }
    return metrics, latencies, details


def write_json(path: Path, value: object) -> None:
    """Escribe un JSON con codificación UTF-8."""
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


async def evaluate(
    settings: Settings,
    manifest_path: Path,
    golden_path: Path,
    candidates: int,
    top_k: int,
    split: str,
    collection: str,
    results_dir: Path,
    reuse_index: bool,
) -> Path:
    """Orquesta indexado, calentamiento, medición y escritura del resumen."""
    manifest = load_manifest(manifest_path)
    all_queries = load_queries(golden_path, manifest)
    validate_dataset(all_queries)
    if split == "all":
        queries = all_queries
    else:
        queries = [query for query in all_queries if query.split == split]
    if candidates < top_k or top_k != 10:
        raise ValueError("Evaluation requires 1 <= top_k <= candidates with top_k=10")
    models = await asyncio.to_thread(load_models, settings)
    mapping = await index_corpus(
        models, settings, collection, manifest_path, EVAL_TENANT_UUID, reuse_index
    )
    client = store.create_client(settings.qdrant_url, settings.health_timeout_seconds)
    try:
        if queries:
            warm = queries[0]
            dense = await asyncio.to_thread(
                models.dense.embed, [warm.query], settings.embedding_batch_size
            )
            sparse = await asyncio.to_thread(models.sparse.query_embed, warm.query)
            await store.hybrid_search(
                EVAL_TENANT_UUID,
                client,
                collection,
                dense[0],
                sparse.indices,
                sparse.values,
                owner_id=warm.scope.owner_id,
                document_ids=None,
                candidates=candidates,
                rrf_k=settings.rrf_k,
            )
            if models.reranker is not None:
                await asyncio.to_thread(
                    models.reranker.score,
                    warm.query,
                    ["calentamiento"],
                    settings.reranker_batch_size,
                )
        per_config_metrics: dict[str, dict[str, QueryMetrics]] = {}
        per_config_latencies: dict[str, list[float]] = {}
        per_config_details: dict[str, dict[str, dict[str, object]]] = {}
        for configuration in CONFIGURATIONS:
            config_metrics, config_latencies, config_details = await run_configuration(
                configuration,
                models,
                settings,
                client,
                collection,
                EVAL_TENANT_UUID,
                queries,
                mapping,
                candidates,
                top_k,
            )
            per_config_metrics[configuration] = config_metrics
            per_config_latencies[configuration] = config_latencies
            per_config_details[configuration] = config_details
        summaries: dict[str, object] = {}
        for configuration in CONFIGURATIONS:
            ordered = [per_config_metrics[configuration][query.id] for query in queries]
            result = summarize(ordered, per_config_latencies[configuration])
            summaries[configuration] = {
                "positives": result.positives,
                "negatives": result.negatives,
                "recall_candidates": result.recall_candidates,
                "recall_at_10": result.recall_at_10,
                "hit_rate_at_10": result.hit_rate_at_10,
                "mrr_at_10": result.mrr_at_10,
                "ndcg_at_10": result.ndcg_at_10,
                "latency_p50_ms": result.latency_p50_ms,
                "latency_p95_ms": result.latency_p95_ms,
            }
        comparisons: dict[str, object] = {}
        pairs = [
            ("hybrid_vs_dense", "hybrid", "dense"),
            ("hybrid_vs_sparse", "hybrid", "sparse"),
            ("rerank_vs_hybrid", "hybrid_rerank", "hybrid"),
        ]
        for name, left, right in pairs:
            wins, losses, ties = compare_recall(per_config_metrics[left], per_config_metrics[right])
            comparisons[name] = {"wins": wins, "losses": losses, "ties": ties}
        manifest_hash = await asyncio.to_thread(_manifest_hash, manifest_path)
        corpus_hash = manifest_hash
        golden_hash = await asyncio.to_thread(_manifest_hash, golden_path)
        summary = {
            "date": datetime.now(UTC).isoformat(),
            "commit": read_commit(),
            "corpus": {
                "manifest": str(manifest_path),
                "golden": str(golden_path),
                "manifest_sha256": corpus_hash,
                "golden_sha256": golden_hash,
                "documents": len(manifest.documents),
                "queries": len(queries),
                "positives": sum(1 for query in queries if query.expected),
                "negatives": sum(1 for query in queries if not query.expected),
                "partition": split,
                "dev_queries": sum(1 for query in all_queries if query.split == "dev"),
                "test_queries": sum(1 for query in all_queries if query.split == "test"),
            },
            "models": {
                "dense_model": settings.embedding_model,
                "dense_revision": settings.embedding_revision,
                "sparse_model": settings.bm25_model,
                "sparse_revision": settings.bm25_revision,
                "sparse_language": settings.bm25_language,
                "sparse_disable_stemmer": settings.bm25_disable_stemmer,
                "sparse_k": settings.bm25_k,
                "sparse_b": settings.bm25_b,
                "sparse_avg_len": settings.bm25_avg_len,
                "reranker_model": settings.reranker_model,
                "reranker_revision": settings.reranker_revision,
            },
            "configuration": {
                "chunk_size": settings.chunk_size,
                "chunk_overlap": settings.chunk_overlap,
                "candidates": candidates,
                "top_k": top_k,
                "rrf_k": settings.rrf_k,
                "collection": collection,
                "tenant": str(EVAL_TENANT_UUID),
            },
            "hardware": hardware_info(settings),
            "summaries": summaries,
            "comparisons": comparisons,
        }
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S%fZ")
        await asyncio.to_thread(results_dir.mkdir, parents=True, exist_ok=True)
        summary_path = results_dir / f"summary-{timestamp}-{split}.json"
        await asyncio.to_thread(write_json, summary_path, summary)
        per_query_dir = results_dir / "per_query" / f"{timestamp}-{split}"
        await asyncio.to_thread(per_query_dir.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(write_json, per_query_dir / "details.json", per_config_details)
        logger.info(
            "evaluación completada",
            extra={"summary": str(summary_path), "split": split, "queries": len(queries)},
        )
        return summary_path
    finally:
        await client.close()


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada sin `print`: el resultado va al log y al resumen."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_arguments(argv)
    settings = get_settings()
    collection = f"{settings.qdrant_collection}{args.collection_suffix}"
    if args.candidates < args.top_k or args.candidates < 1:
        raise ValueError("Evaluation requires 1 <= top_k <= candidates")
    if args.top_k != 10:
        raise ValueError("The four configurations use top_k=10")
    path = asyncio.run(
        evaluate(
            settings,
            args.manifest,
            args.golden,
            args.candidates,
            args.top_k,
            args.split,
            collection,
            args.results_dir,
            args.reuse_index,
        )
    )
    logger.info("resumen escrito en %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
