"""Métricas sobre evidencias localizadas, sin duplicar ganancias por solape.

Cubre la evaluación de recuperación del corpus propio. Para métricas a nivel
de documento sobre fragmentos de SciFact, ver `eval/scifact_metrics.py`.
"""

import math
import re
from dataclasses import dataclass
from uuid import UUID

Locator = dict[str, str | int | list[str]]


@dataclass(frozen=True, slots=True)
class Evidence:
    """Cita relevante esperada de un documento y localizador."""

    evidence_id: str
    document_id: UUID
    locator: Locator
    quote: str


@dataclass(frozen=True, slots=True)
class Hit:
    """Fragmento recuperado para comparar con evidencias."""

    document_id: UUID
    locator: Locator
    text: str


@dataclass(frozen=True, slots=True)
class QueryMetrics:
    """Resultados por consulta; las consultas negativas no tienen métricas positivas."""

    recall_candidates: float | None
    recall_at_10: float | None
    hit_rate_at_10: float | None
    reciprocal_rank_at_10: float | None
    ndcg_at_10: float | None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _locator_contains(actual: Locator, expected: Locator) -> bool:
    kind = expected.get("type")
    if kind != actual.get("type"):
        return False
    if kind in ("page", "offset"):
        actual_start, actual_end = actual.get("start"), actual.get("end")
        expected_start, expected_end = expected.get("start"), expected.get("end")
        return (
            isinstance(actual_start, int)
            and isinstance(actual_end, int)
            and isinstance(expected_start, int)
            and isinstance(expected_end, int)
            and actual_start <= expected_start
            and actual_end >= expected_end
        )
    if kind == "section":
        return actual.get("path") == expected.get("path") and actual.get("ordinal") == expected.get(
            "ordinal"
        )
    return False


def matched_evidence(hit: Hit, expected: list[Evidence]) -> set[str]:
    """Devuelve las evidencias cuyo texto y localizador contiene el fragmento."""
    text = _normalize(hit.text)
    return {
        evidence.evidence_id
        for evidence in expected
        if hit.document_id == evidence.document_id
        and _locator_contains(hit.locator, evidence.locator)
        and bool(_normalize(evidence.quote))
        and _normalize(evidence.quote) in text
    }


def evaluate_query(
    expected: list[Evidence], candidates: list[Hit], results: list[Hit]
) -> QueryMetrics:
    """Calcula cobertura de candidatos y métricas sobre los diez primeros resultados."""
    if not expected:
        return QueryMetrics(None, None, None, None, None)
    evidence_ids = [item.evidence_id for item in expected]
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("Evidence IDs must be unique within a query")
    if any(not _normalize(item.quote) for item in expected):
        raise ValueError("Evidence quotes must not be blank")
    candidate_matches: set[str] = set()
    for hit in candidates:
        candidate_matches.update(matched_evidence(hit, expected))
    matched: set[str] = set()
    dcg = 0.0
    first_rank: int | None = None
    for rank, hit in enumerate(results[:10], 1):
        found = matched_evidence(hit, expected)
        new = sorted(found - matched)
        matched.update(found)
        if new:
            dcg += 1.0 / math.log2(rank + 1)
            if first_rank is None:
                first_rank = rank
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(10, len(expected)) + 1))
    return QueryMetrics(
        recall_candidates=len(candidate_matches) / len(expected),
        recall_at_10=len(matched) / len(expected),
        hit_rate_at_10=float(first_rank is not None),
        reciprocal_rank_at_10=1.0 / first_rank if first_rank else 0.0,
        ndcg_at_10=dcg / ideal,
    )


@dataclass(frozen=True, slots=True)
class AggregateMetrics:
    """Promedios sobre positivas y número de consultas negativas."""

    positives: int
    negatives: int
    recall_candidates: float | None
    recall_at_10: float | None
    hit_rate_at_10: float | None
    mrr_at_10: float | None
    ndcg_at_10: float | None
    latency_p50_ms: float | None
    latency_p95_ms: float | None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("Latencies must be finite and non-negative")
    return sorted(values)[max(0, math.ceil(percentile * len(values)) - 1)]


def summarize(metrics: list[QueryMetrics], latencies_ms: list[float]) -> AggregateMetrics:
    """Promedia métricas positivas y calcula percentiles por rango más cercano."""
    if len(metrics) != len(latencies_ms):
        raise ValueError("Every query requires one latency")
    positives = [item for item in metrics if item.recall_at_10 is not None]

    def average(field: str) -> float | None:
        values = [getattr(item, field) for item in positives]
        if not values:
            return None
        if any(value is None for value in values):
            raise ValueError("Positive query has incomplete metrics")
        return sum(float(value) for value in values) / len(values)

    return AggregateMetrics(
        positives=len(positives),
        negatives=len(metrics) - len(positives),
        recall_candidates=average("recall_candidates"),
        recall_at_10=average("recall_at_10"),
        hit_rate_at_10=average("hit_rate_at_10"),
        mrr_at_10=average("reciprocal_rank_at_10"),
        ndcg_at_10=average("ndcg_at_10"),
        latency_p50_ms=_percentile(latencies_ms, 0.50),
        latency_p95_ms=_percentile(latencies_ms, 0.95),
    )


def compare_recall(
    left: dict[str, QueryMetrics], right: dict[str, QueryMetrics]
) -> tuple[int, int, int]:
    """Cuenta victorias, derrotas y empates de recall@10 en consultas positivas."""
    if left.keys() != right.keys():
        raise ValueError("Compared configurations must contain the same queries")
    wins = losses = ties = 0
    for query_id in left:
        first, second = left[query_id].recall_at_10, right[query_id].recall_at_10
        if first is None and second is None:
            continue
        if first is None or second is None:
            raise ValueError("Compared query labels do not match")
        if first > second:
            wins += 1
        elif first < second:
            losses += 1
        else:
            ties += 1
    return wins, losses, ties
