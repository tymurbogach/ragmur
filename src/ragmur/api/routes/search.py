"""Búsqueda híbrida dentro del espacio autorizado."""

import asyncio
import math
import time
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from ragmur.api.deps import CurrentTenant, ResourcesDep
from ragmur.api.schemas import SearchHit, SearchRequest, SearchResponse
from ragmur.core.config import get_settings
from ragmur.db.models import Document
from ragmur.retrieval import store

router = APIRouter(prefix="/v1", tags=["search"])


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest, tenant_id: CurrentTenant, resources: ResourcesDep, http_request: Request
) -> SearchResponse:
    """Recupera candidatos y confirma que los documentos están indexados."""
    started = float(http_request.state.request_started)
    settings = get_settings()
    if len(request.query) > settings.search_max_query_chars:
        raise HTTPException(422, detail="Query too long")
    if request.candidates > settings.search_max_candidates:
        raise HTTPException(422, detail="Too many candidates")
    if (
        request.document_ids is not None
        and len(request.document_ids) > settings.search_max_document_ids
    ):
        raise HTTPException(422, detail="Too many document IDs")
    if request.rerank:
        raise HTTPException(503, detail="Reranking is not available yet")

    try:
        waiting = time.perf_counter()
        async with resources.models.lock:
            acquired = time.perf_counter()
            dense_vectors = await asyncio.to_thread(
                resources.models.dense.embed, [request.query], settings.embedding_batch_size
            )
            sparse_vector = await asyncio.to_thread(
                resources.models.sparse.query_embed, request.query
            )
        embedded = time.perf_counter()
        if len(dense_vectors) != 1:
            raise RuntimeError("Embedding model returned an unexpected result")
        points = await store.hybrid_search(
            tenant_id,
            resources.qdrant,
            settings.qdrant_collection,
            dense_vectors[0],
            sparse_vector.indices,
            sparse_vector.values,
            owner_id=request.owner_id,
            document_ids=request.document_ids,
            candidates=request.candidates,
            rrf_k=settings.rrf_k,
        )
        searched = time.perf_counter()
        document_ids = {UUID(str(point.payload["document_id"])) for point in points}
    except Exception as exc:
        raise HTTPException(503, detail="Search unavailable") from exc

    valid_documents: set[UUID] = set()
    if document_ids:
        filters = [
            Document.tenant_id == tenant_id,
            Document.status == "indexed",
            Document.id.in_(document_ids),
        ]
        if request.owner_id is not None:
            filters.append(Document.owner_id == request.owner_id)
        if request.document_ids is not None:
            filters.append(Document.id.in_(request.document_ids))
        async with resources.sessions() as session:
            valid_documents = set(
                (await session.scalars(select(Document.id).where(*filters))).all()
            )
    results = []
    try:
        for point in points:
            doc_id = UUID(str(point.payload["document_id"]))
            if doc_id not in valid_documents:
                continue
            if not math.isfinite(point.score):
                raise ValueError("Non-finite score")
            results.append(
                SearchHit(
                    chunk_id=point.id,
                    document_id=doc_id,
                    filename=point.payload["filename"],
                    locator=point.payload["locator"],
                    text=point.payload["text"],
                    score=point.score,
                    dense_rank=point.dense_rank,
                    sparse_rank=point.sparse_rank,
                )
            )
            if len(results) == request.top_k:
                break
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(503, detail="Search unavailable") from exc
    finished = time.perf_counter()
    return SearchResponse(
        results=results,
        rrf_k=settings.rrf_k,
        branch_limit=request.candidates,
        timings_ms={
            "capacity_wait": (acquired - waiting) * 1000,
            "embed": (embedded - acquired) * 1000,
            "search": (searched - embedded) * 1000,
            "validation": (finished - searched) * 1000,
            "rerank": 0.0,
            "total": (finished - started) * 1000,
        },
    )
