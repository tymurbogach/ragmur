"""Evalúa SciFact con etiquetas por documento y fragmentos de Ragmur."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import math
import os
import re
import statistics
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from eval.run import hardware_info, read_commit
from eval.scifact_metrics import classify_miss, evaluate_documents
from ragmur.core.config import Settings, get_settings
from ragmur.core.logging import configure_logging
from ragmur.ingestion.chunker import Chunk, split_document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.ingestion.indexer import Indexer
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels, load_models

logger = logging.getLogger(__name__)
ARCHIVE_SHA256 = "536e14446a0ba56ed1398ab1055f39fe852686ecad24a6306c80c490fa8e0165"


def document_id(identifier: str) -> UUID:
    """Genera una identidad estable a partir de la clave del corpus."""
    return uuid5(NAMESPACE_URL, "scifact:" + identifier)


def load_dataset(
    root: Path, split: str
) -> tuple[list[dict[str, str]], dict[str, str], dict[str, dict[str, int]]]:
    """Carga y valida los documentos, consultas y juicios de relevancia."""
    if split not in {"train", "test"}:
        raise ValueError("Unsupported split")
    hashes = {
        "corpus.jsonl": "dec31c8182f3d744c7d2c09423756fd1d17cbef75808db13ba01cc0aab4d1ac6",
        "queries.jsonl": "8ff84a7c903f722981cd8d595c022660140c51867b27608a6d4910db86080313",
        "qrels/train.tsv": "a53f2114831916c096b6c37d9e54da68cef4efdcdbd5ed46533601af972acf1d",
        "qrels/test.tsv": "0864bb985e0ca2367ba217977e72004d549054b2b06666ed9d4825ac7c21284c",
    }
    for path, expected in hashes.items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
            raise ValueError(f"SciFact hash mismatch: {path}")
    docs = [json.loads(line) for line in (root / "corpus.jsonl").read_text().splitlines()]
    queries = {
        row["_id"]: row["text"]
        for row in map(json.loads, (root / "queries.jsonl").read_text().splitlines())
    }
    relevance: dict[str, dict[str, int]] = defaultdict(dict)
    with (root / "qrels" / f"{split}.tsv").open(newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            score = int(row["score"])
            if score > 0:
                relevance[row["query-id"]][str(document_id(row["corpus-id"]))] = score
    identifiers = {row["_id"] for row in docs}
    if len(docs) != 5183 or len(identifiers) != len(docs) or not relevance:
        raise ValueError("Invalid SciFact corpus or relevance judgments")
    if set(relevance) - set(queries):
        raise ValueError("Relevance judgments reference missing queries")
    valid = {str(document_id(identifier)) for identifier in identifiers}
    if any(set(documents) - valid for documents in relevance.values()):
        raise ValueError("Relevance judgments reference missing documents")
    return docs, queries, dict(relevance)


async def index_dataset(
    tenant: UUID,
    collection: str,
    docs: list[dict[str, str]],
    settings: Settings,
    models: EmbeddingModels,
    client: store.AsyncQdrantClient,
) -> int:
    """Indexa el corpus en lotes, sin mezclar documentos en una escritura."""
    indexer = Indexer(client, models, settings)
    await store.ensure_collection(
        tenant, client, collection, models.dense.dimension, indexer.metadata()
    )
    chunks: list[Chunk] = []
    for doc in docs:
        text = (doc.get("title", "") + "\n" + doc["text"]).strip()
        extraction = ExtractionResult(
            [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
        )
        chunks.extend(
            split_document(
                extraction,
                document_id(doc["_id"]),
                tenant,
                None,
                size=settings.chunk_size,
                overlap=settings.chunk_overlap,
            ).chunks
        )
    for start in range(0, len(chunks), settings.index_batch_size):
        batch = chunks[start : start + settings.index_batch_size]
        texts = [chunk.text for chunk in batch]
        dense = await asyncio.to_thread(models.dense.embed, texts, settings.embedding_batch_size)
        sparse = await asyncio.to_thread(models.sparse.embed, texts, settings.embedding_batch_size)
        grouped: dict[UUID, list[store.VectorPoint]] = defaultdict(list)
        for chunk, vector, lexical in zip(batch, dense, sparse, strict=True):
            grouped[chunk.document_id].append(
                store.VectorPoint(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    owner_id=None,
                    filename=f"{chunk.document_id}.txt",
                    text=chunk.text,
                    ordinal=chunk.ordinal,
                    start=chunk.start,
                    end=chunk.end,
                    locator=chunk.locator,
                    dense=vector,
                    sparse_indices=lexical.indices,
                    sparse_values=lexical.values,
                )
            )
        for points in grouped.values():
            await store.upsert_points(tenant, client, collection, points)
        logger.info(
            "Indexados %s de %s fragmentos", min(start + len(batch), len(chunks)), len(chunks)
        )
    return len(chunks)


async def evaluate(
    tenant: UUID,
    collection: str,
    queries: dict[str, str],
    relevance: dict[str, dict[str, int]],
    settings: Settings,
    models: EmbeddingModels,
    client: store.AsyncQdrantClient,
) -> list[dict[str, object]]:
    """Registra candidatos y resultados finales por consulta."""
    details: list[dict[str, object]] = []
    if models.reranker is None:
        raise RuntimeError("Reranker unavailable")
    for query_id in sorted(relevance):
        start = time.perf_counter()
        query = queries[query_id]
        dense = await asyncio.to_thread(models.dense.embed, [query], settings.embedding_batch_size)
        sparse = await asyncio.to_thread(models.sparse.query_embed, query)
        points = await store.hybrid_search(
            tenant,
            client,
            collection,
            dense[0],
            sparse.indices,
            sparse.values,
            owner_id=None,
            document_ids=None,
            candidates=30,
            rrf_k=settings.rrf_k,
        )
        candidates = [str(point.payload["document_id"]) for point in points]
        scores = await asyncio.to_thread(
            models.reranker.score,
            query,
            [str(point.payload["text"]) for point in points],
            settings.reranker_batch_size,
        )
        ranked = [
            str(point.payload["document_id"])
            for point, _ in sorted(
                zip(points, scores, strict=True), key=lambda item: item[1], reverse=True
            )
        ]
        before = evaluate_documents(candidates, relevance[query_id])
        metrics = evaluate_documents(ranked, relevance[query_id])
        details.append(
            {
                "id": query_id,
                "candidates": candidates,
                "ranked": ranked,
                "before_metrics": asdict(before),
                "metrics": asdict(metrics),
                "classification": classify_miss(candidates, ranked, relevance[query_id]),
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        )
    return details


async def check_isolation(
    collection: str, settings: Settings, models: EmbeddingModels, client: store.AsyncQdrantClient
) -> None:
    """Comprueba el aislamiento entre tenants y usuarios sobre Qdrant real."""
    first, second = uuid4(), uuid4()
    test_text = "isolation evaluation canary"
    dense = (
        await asyncio.to_thread(models.dense.embed, [test_text], settings.embedding_batch_size)
    )[0]
    sparse = (
        await asyncio.to_thread(models.sparse.embed, [test_text], settings.embedding_batch_size)
    )[0]
    query = await asyncio.to_thread(models.sparse.query_embed, test_text)
    try:
        for tenant, owner in ((first, "one"), (first, "two"), (second, "one")):
            did = uuid4()
            point = store.VectorPoint(
                id=uuid4(),
                document_id=did,
                owner_id=owner,
                filename="canary.txt",
                text=test_text,
                ordinal=0,
                start=0,
                end=len(test_text),
                locator={"type": "offset", "start": 0, "end": len(test_text)},
                dense=dense,
                sparse_indices=sparse.indices,
                sparse_values=sparse.values,
            )
            await store.upsert_points(tenant, client, collection, [point])
        for tenant, owner in ((first, "one"), (first, "two"), (second, "one")):
            points = await store.hybrid_search(
                tenant,
                client,
                collection,
                dense,
                query.indices,
                query.values,
                owner_id=owner,
                document_ids=None,
                candidates=30,
                rrf_k=settings.rrf_k,
            )
            if (
                len(points) != 1
                or points[0].payload["tenant_id"] != str(tenant)
                or points[0].payload["owner_id"] != owner
            ):
                raise RuntimeError("Tenant or owner isolation failed")
    finally:
        await store.delete_tenant_points(first, client, collection)
        await store.delete_tenant_points(second, client, collection)


def partition_queries(relevance: dict[str, dict[str, int]]) -> dict[str, str]:
    """Separa consultas conectadas por documentos relevantes en el mismo grupo."""
    by_document: dict[str, set[str]] = defaultdict(set)
    for query, labels in relevance.items():
        for document in labels:
            by_document[document].add(query)
    remaining = set(relevance)
    result: dict[str, str] = {}
    while remaining:
        pending = [min(remaining)]
        group: set[str] = set()
        documents: set[str] = set()
        while pending:
            query = pending.pop()
            if query in group:
                continue
            group.add(query)
            remaining.discard(query)
            for document in relevance[query]:
                if document not in documents:
                    documents.add(document)
                    pending.extend(by_document[document] - group)
        digest = hashlib.sha256("\n".join(sorted(documents)).encode("utf-8")).digest()
        partition = "holdout" if int.from_bytes(digest[:8], "big") % 5 == 0 else "dev"
        result.update(dict.fromkeys(group, partition))
    return result


def resolve_commit(detected: str, supplied: str | None) -> tuple[str, str]:
    """Exige una revisión completa y distingue la declarada de la verificada."""
    valid = r"[0-9a-f]{40}"
    if supplied is not None and re.fullmatch(valid, supplied) is None:
        raise ValueError("Source commit must be a full lowercase Git SHA-1")
    if re.fullmatch(valid, detected):
        if supplied is not None and supplied != detected:
            raise ValueError("Source commit does not match the Git checkout")
        return detected, "git"
    if supplied is None:
        raise ValueError("Git revision unavailable; supply --source-commit")
    return supplied, "declared"


async def run(
    root: Path, split: str, partition: str, output: Path, source_commit: str | None = None
) -> None:
    """Ejecuta la prueba en un tenant temporal y guarda sus resultados."""
    commit, commit_source = resolve_commit(read_commit(), source_commit)
    docs, queries, relevance = load_dataset(root, split)
    if split == "test" and partition != "all":
        raise ValueError("The official test split only supports partition all")
    if partition != "all":
        partitions = partition_queries(relevance)
        relevance = {key: value for key, value in relevance.items() if partitions[key] == partition}
    if not relevance:
        raise ValueError("The selected partition is empty")
    settings = get_settings()
    configure_logging(settings.log_level)
    models = load_models(settings)
    client = store.create_client(settings.qdrant_url, settings.health_timeout_seconds)
    tenant = uuid4()
    collection = settings.qdrant_collection + "_scifact_eval"
    initialized = False
    try:
        await store.ensure_collection(
            tenant,
            client,
            collection,
            models.dense.dimension,
            Indexer(client, models, settings).metadata(),
        )
        initialized = True
        await check_isolation(collection, settings, models, client)
        started = time.perf_counter()
        chunks = await index_dataset(tenant, collection, docs, settings, models, client)
        index_seconds = time.perf_counter() - started
        details = await evaluate(tenant, collection, queries, relevance, settings, models, client)
        latencies = sorted(cast(float, row["latency_ms"]) for row in details)
        classifications = Counter(str(row["classification"]) for row in details)
        metric_rows = [cast(dict[str, float], row["metrics"]) for row in details]
        before_rows = [cast(dict[str, float], row["before_metrics"]) for row in details]
        summary = {
            "source": "BEIR SciFact",
            "date": datetime.now(UTC).isoformat(),
            "commit": commit,
            "commit_source": commit_source,
            "hardware": hardware_info(settings),
            "thread_settings": {
                "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
                "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
            },
            "split": split,
            "partition": partition,
            "documents": len(docs),
            "chunks": chunks,
            "queries": len(details),
            "corpus_sha256": hashlib.sha256((root / "corpus.jsonl").read_bytes()).hexdigest(),
            "judgments_sha256": hashlib.sha256(
                (root / "qrels" / f"{split}.tsv").read_bytes()
            ).hexdigest(),
            "device": settings.resolved_device,
            "bm25_language": settings.bm25_language,
            "bm25_disable_stemmer": settings.bm25_disable_stemmer,
            "embedding_batch_size": settings.embedding_batch_size,
            "reranker_batch_size": settings.reranker_batch_size,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "candidates_chunks": 30,
            "result_limit_chunks": 10,
            "classification": dict(classifications),
            "before_reranking": {
                key: statistics.mean(row[key] for row in before_rows)
                for key in ("hit", "recall", "ndcg")
            },
            "ranking": {
                key: statistics.mean(row[key] for row in metric_rows)
                for key in ("hit", "recall", "ndcg")
            },
            "model": settings.embedding_model,
            "model_revision": settings.embedding_revision,
            "reranker_model": settings.reranker_model,
            "reranker_revision": settings.reranker_revision,
            "rrf_k": settings.rrf_k,
            "concurrency": 1,
            "latency_p50_ms": statistics.median(latencies),
            "latency_p95_ms": latencies[math.ceil(len(latencies) * 0.95) - 1],
            "index_seconds": index_seconds,
            "limitations": [
                "Direct retrieval components, not HTTP or PostgreSQL.",
                "Document labels evaluated after cutting to 10 chunks.",
                "SciFact test was previously inspected and is not an independent holdout.",
                "Git identifies the checkout, not uncommitted changes or container images.",
                "Ties and concurrent numerical execution can change rankings across runs.",
            ],
        }
        await asyncio.to_thread(write_results, output, f"{split}-{partition}", summary, details)
    finally:
        try:
            if initialized:
                await store.delete_tenant_points(tenant, client, collection)
        finally:
            await client.close()


def write_results(
    output: Path, split: str, summary: dict[str, object], details: list[dict[str, object]]
) -> None:
    """Guarda el resumen y los resultados por consulta."""
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    (output / f"summary-scifact-{split}-{stamp}.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    per_query = output / "per_query"
    per_query.mkdir(exist_ok=True)
    (per_query / f"scifact-{split}-{stamp}.json").write_text(json.dumps(details, indent=2) + "\n")


def main() -> None:
    """Procesa los argumentos de la evaluación."""
    parser = argparse.ArgumentParser(description="Evalúa SciFact con Ragmur")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "test"), required=True)
    parser.add_argument("--partition", choices=("dev", "holdout", "all"), default="all")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", help="Full Git commit when the checkout is unavailable")
    args = parser.parse_args()
    asyncio.run(run(args.dataset, args.split, args.partition, args.output, args.source_commit))


if __name__ == "__main__":
    main()
