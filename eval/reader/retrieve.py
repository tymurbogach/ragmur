"""Recuperación del banco: híbrida con reranking, sin LLM.

Sigue el mismo camino que `eval/run.py::run_configuration` para la
configuración `hybrid_rerank`: búsqueda híbrida (densa + BM25 con fusión RRF)
sobre `candidates` candidatos y reordenación con el cross-encoder, cortando a
`top_k`. Es la única configuración del banco en esta fase.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from uuid import UUID

from eval.reader.xquad import ReaderCase
from ragmur.core.config import Settings
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels

SUPPORTED_CONFIGURATION = "hybrid_rerank"


@dataclass(frozen=True, slots=True)
class ReaderHit:
    """Un fragmento recuperado y reordenado para un caso."""

    rank: int
    chunk_id: UUID
    document_key: str
    text: str
    rerank_score: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Toda la respuesta de recuperación guardada en caché para un caso."""

    case_id: str
    query: str
    hits: tuple[ReaderHit, ...]
    latency_ms: float


async def retrieve_case(
    *,
    case: ReaderCase,
    models: EmbeddingModels,
    settings: Settings,
    client: store.AsyncQdrantClient,
    collection: str,
    tenant_id: UUID,
    document_keys: dict[str, str],
    owner_id: str | None = None,
    candidates: int = 30,
    top_k: int = 5,
) -> RetrievalResult:
    """Recupera y reordena los fragmentos para la pregunta del caso."""
    if candidates < 1 or top_k < 1 or top_k > candidates:
        raise ValueError("Retrieval requires 1 <= top_k <= candidates")
    started = time.perf_counter()
    dense = await asyncio.to_thread(
        models.dense.embed, [case.question], settings.embedding_batch_size
    )
    sparse = await asyncio.to_thread(models.sparse.query_embed, case.question)
    fused = await store.hybrid_search(
        tenant_id,
        client,
        collection,
        dense[0],
        sparse.indices,
        sparse.values,
        owner_id=owner_id,
        document_ids=None,
        candidates=candidates,
        rrf_k=settings.rrf_k,
    )
    if models.reranker is None:
        raise RuntimeError("Reranker is required for the hybrid_rerank configuration")
    scores = await asyncio.to_thread(
        models.reranker.score,
        case.question,
        [str(point.payload["text"]) for point in fused],
        settings.reranker_batch_size,
    )
    ranked = sorted(zip(fused, scores, strict=True), key=lambda pair: pair[1], reverse=True)[:top_k]
    hits: list[ReaderHit] = []
    for rank, (point, score) in enumerate(ranked, 1):
        document_id = str(point.payload["document_id"])
        if document_id not in document_keys:
            raise RuntimeError("Retrieval returned a point outside the indexed corpus")
        hits.append(
            ReaderHit(
                rank=rank,
                chunk_id=point.id,
                document_key=document_keys[document_id],
                text=str(point.payload["text"]),
                rerank_score=score,
            )
        )
    return RetrievalResult(
        case_id=case.case_id,
        query=case.question,
        hits=tuple(hits),
        latency_ms=(time.perf_counter() - started) * 1000.0,
    )
