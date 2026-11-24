"""Verificación de afirmaciones contra fragmentos autorizados."""

import asyncio
from collections import Counter
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ragmur.api.deps import CurrentTenant, ResourcesDep
from ragmur.api.schemas import VerifyClaim, VerifyRequest, VerifyResponse, VerifySummary
from ragmur.core.config import get_settings
from ragmur.db.models import Document
from ragmur.retrieval import store
from ragmur.retrieval.models import run_inference
from ragmur.verification.splitter import split_claims

router = APIRouter(prefix="/v1", tags=["verify"])

Verdict = Literal["supported", "weak", "unsupported", "contradicted"]


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    request: VerifyRequest, tenant_id: CurrentTenant, resources: ResourcesDep
) -> VerifyResponse:
    """Puntúa cada frase contra los fragmentos autorizados y disponibles."""
    settings = get_settings()
    if len(request.answer) > settings.verify_max_answer_chars:
        raise HTTPException(422, detail="Answer too long")
    if len(set(request.chunk_ids)) > settings.verify_max_chunks:
        raise HTTPException(422, detail="Too many chunks")
    try:
        claims = await asyncio.to_thread(
            split_claims,
            request.answer,
            settings.verify_max_claims,
            settings.verify_max_answer_chars,
        )
    except ValueError as exc:
        raise HTTPException(422, detail="Invalid answer") from exc
    for claim in claims:
        try:
            await asyncio.to_thread(resources.verifier.check_hypothesis, claim)
        except ValueError as exc:
            raise HTTPException(422, detail="Claim too long") from exc
    unique_ids = list(dict.fromkeys(request.chunk_ids))
    try:
        points = await store.retrieve_points(
            tenant_id,
            resources.qdrant,
            settings.qdrant_collection,
            unique_ids,
            request.owner_id,
        )
        document_ids = {UUID(str(point.payload["document_id"])) for point in points}
    except Exception as exc:
        raise HTTPException(503, detail="Verification unavailable") from exc
    if not points:
        return _unsupported(claims, None)
    try:
        async with resources.sessions() as session:
            filters = [
                Document.tenant_id == tenant_id,
                Document.status == "indexed",
                Document.id.in_(document_ids),
            ]
            if request.owner_id is not None:
                filters.append(Document.owner_id == request.owner_id)
            valid = set((await session.scalars(select(Document.id).where(*filters))).all())
    except Exception as exc:
        raise HTTPException(503, detail="Verification unavailable") from exc
    available = [point for point in points if UUID(str(point.payload["document_id"])) in valid]
    if not available:
        return _unsupported(claims, None)
    if len(claims) * len(available) > settings.verify_max_pairs:
        raise HTTPException(422, detail="Too many claim-chunk pairs")
    premises = [str(point.payload["text"]) for point in available]
    pair_premises: list[str] = []
    pair_hypotheses: list[str] = []
    pair_index: list[tuple[int, int]] = []
    for claim_idx, claim in enumerate(claims):
        for chunk_idx, premise in enumerate(premises):
            pair_premises.append(premise)
            pair_hypotheses.append(claim)
            pair_index.append((claim_idx, chunk_idx))
    try:
        async with resources.models.lock:
            scores = await run_inference(
                resources.verifier.score_pairs,
                pair_premises,
                pair_hypotheses,
                settings.nli_batch_size,
            )
    except ValueError as exc:
        raise HTTPException(422, detail="Verification input exceeds model limits") from exc
    except Exception as exc:
        raise HTTPException(503, detail="Verification unavailable") from exc
    max_ent = [0.0] * len(claims)
    max_contra = [0.0] * len(claims)
    best_ent: list[UUID | None] = [None] * len(claims)
    best_contra: list[UUID | None] = [None] * len(claims)
    for (claim_idx, chunk_idx), (ent, contra) in zip(pair_index, scores, strict=True):
        if ent > max_ent[claim_idx]:
            max_ent[claim_idx] = ent
            best_ent[claim_idx] = available[chunk_idx].id
        if contra > max_contra[claim_idx]:
            max_contra[claim_idx] = contra
            best_contra[claim_idx] = available[chunk_idx].id
    results: list[VerifyClaim] = []
    for idx, claim in enumerate(claims):
        ent, contra = max_ent[idx], max_contra[idx]
        # D7: el apoyo que supera su umbral y aventaja a la contradicción en el
        # margen gana a una contradicción aislada (DECISIONS.md §3.36). El redondeo
        # evita que el ruido de coma flotante decida el empate exacto.
        support_wins = (
            ent >= settings.verify_supported_threshold
            and round(ent - contra, 9) >= settings.verify_conflict_margin
        )
        if contra >= settings.verify_contradiction_threshold and not support_wins:
            verdict: Verdict = "contradicted"
            score = contra
            best = best_contra[idx]
        elif ent >= settings.verify_supported_threshold:
            verdict = "supported"
            score = ent
            best = best_ent[idx]
        elif ent >= settings.verify_weak_threshold:
            verdict = "weak"
            score = ent
            best = best_ent[idx]
        else:
            verdict = "unsupported"
            score = ent
            best = None
        results.append(VerifyClaim(text=claim, verdict=verdict, score=score, best_chunk_id=best))
    counts = Counter(claim.verdict for claim in results)
    return VerifyResponse(
        claims=results,
        summary=VerifySummary(
            supported=counts.get("supported", 0),
            weak=counts.get("weak", 0),
            unsupported=counts.get("unsupported", 0),
            contradicted=counts.get("contradicted", 0),
        ),
    )


def _unsupported(claims: list[str], best: UUID | None) -> VerifyResponse:
    """Devuelve todas las frases como no respaldadas sin evidencia válida."""
    results = [
        VerifyClaim(text=claim, verdict="unsupported", score=0.0, best_chunk_id=best)
        for claim in claims
    ]
    return VerifyResponse(
        claims=results,
        summary=VerifySummary(supported=0, weak=0, unsupported=len(results), contradicted=0),
    )
