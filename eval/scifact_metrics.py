"""Métricas de documentos para los fragmentos recuperados en SciFact.

Complementa a `eval/metrics.py`, que mide cobertura y orden sobre evidencias
localizadas del corpus propio. Los adaptadores externos (`eval/inferes.py`,
`eval/scifact_nli.py`) no emiten `document_id`, así que sus casos no valen
para la aceptación con anti-fuga por documento.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentMetrics:
    """Cobertura y orden de los documentos relevantes."""

    hit: float
    recall: float
    ndcg: float


def evaluate_documents(
    ranked_chunks: list[str], relevant: dict[str, int], *, limit: int = 10
) -> DocumentMetrics:
    """Corta los fragmentos antes de eliminar documentos repetidos."""
    if limit < 1 or not relevant or any(score < 1 for score in relevant.values()):
        raise ValueError("Expected a positive limit and relevance scores")
    documents = list(dict.fromkeys(ranked_chunks[:limit]))
    gains = [relevant.get(document, 0) for document in documents]
    ideal = sorted(relevant.values(), reverse=True)[:limit]
    dcg = sum((2**gain - 1) / math.log2(rank + 2) for rank, gain in enumerate(gains))
    idcg = sum((2**gain - 1) / math.log2(rank + 2) for rank, gain in enumerate(ideal))
    return DocumentMetrics(
        hit=float(any(gains)),
        recall=sum(gain > 0 for gain in gains) / len(relevant),
        ndcg=dcg / idcg,
    )


def classify_miss(
    candidates: list[str], ranked_chunks: list[str], relevant: dict[str, int], *, limit: int = 10
) -> str:
    """Indica en qué etapa desaparecen los documentos relevantes."""
    if evaluate_documents(ranked_chunks, relevant, limit=limit).hit:
        return "found"
    if not set(candidates) & set(relevant):
        return "missing_from_candidates"
    return "outside_top_10_after_reranking"
