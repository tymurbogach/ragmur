"""Métricas y correspondencia de evidencias de recuperación."""

import math
from uuid import uuid4

import pytest
from eval.metrics import Evidence, Hit, Locator, evaluate_query


def test_recall_counts_distinct_evidence_and_ndcg_does_not_reward_overlap() -> None:
    document = uuid4()
    locator: Locator = {"type": "page", "start": 4, "end": 4}
    expected = [
        Evidence("a", document, locator, "plazo de entrega"),
        Evidence("b", document, locator, "transporte incluido"),
    ]
    both = Hit(document, locator, "El plazo de\n entrega está fijado y el transporte incluido.")
    repeated = Hit(document, locator, "transporte incluido")
    result = evaluate_query(expected, [both, repeated], [both, repeated])
    assert result.recall_candidates == result.recall_at_10 == 1.0
    assert result.hit_rate_at_10 == result.reciprocal_rank_at_10 == 1.0
    assert result.ndcg_at_10 == pytest.approx(1 / (1 + 1 / math.log2(3)))


def test_recall_differs_from_hit_rate_and_ignores_wrong_locations() -> None:
    document = uuid4()
    expected = [
        Evidence("a", document, {"type": "page", "start": 1, "end": 1}, "evidencia uno"),
        Evidence("b", document, {"type": "page", "start": 2, "end": 2}, "evidencia dos"),
    ]
    wrong_doc = Hit(uuid4(), {"type": "page", "start": 1, "end": 1}, "evidencia uno")
    wrong_page = Hit(document, {"type": "page", "start": 2, "end": 2}, "evidencia uno")
    correct = Hit(document, {"type": "page", "start": 1, "end": 1}, "evidencia uno")
    result = evaluate_query(
        expected, [wrong_doc, wrong_page, correct], [wrong_doc, wrong_page, correct]
    )
    assert result.recall_candidates == result.recall_at_10 == 0.5
    assert result.hit_rate_at_10 == 1.0
    assert result.reciprocal_rank_at_10 == pytest.approx(1 / 3)
    assert result.ndcg_at_10 == pytest.approx((1 / math.log2(4)) / (1 + 1 / math.log2(3)))


def test_negative_query_is_excluded_from_positive_metrics() -> None:
    result = evaluate_query([], [], [])
    assert result.recall_candidates is None and result.recall_at_10 is None
    assert result.hit_rate_at_10 is None and result.ndcg_at_10 is None
    assert result.reciprocal_rank_at_10 is None


def test_section_ordinal_and_offset_containment_are_required() -> None:
    document = uuid4()
    expected = [
        Evidence("a", document, {"type": "section", "path": ["Plazos"], "ordinal": 1}, "48 horas")
    ]
    wrong = Hit(document, {"type": "section", "path": ["Plazos"], "ordinal": 2}, "48 horas")
    assert evaluate_query(expected, [wrong], [wrong]).recall_at_10 == 0
    expected_offset = [
        Evidence("a", document, {"type": "offset", "start": 3, "end": 11}, "48 horas")
    ]
    partial = Hit(document, {"type": "offset", "start": 4, "end": 11}, "48 horas")
    assert evaluate_query(expected_offset, [partial], [partial]).recall_at_10 == 0


def test_duplicate_or_blank_evidence_is_rejected() -> None:
    document = uuid4()
    locator: Locator = {"type": "offset", "start": 0, "end": 1}
    with pytest.raises(ValueError):
        evaluate_query(
            [Evidence("a", document, locator, "x"), Evidence("a", document, locator, "y")], [], []
        )
    with pytest.raises(ValueError):
        evaluate_query([Evidence("a", document, locator, " ")], [], [])


def test_summary_excludes_negatives_and_compares_same_queries() -> None:
    from eval.metrics import compare_recall, summarize

    document = uuid4()
    locator: Locator = {"type": "offset", "start": 0, "end": 1}
    expected = [Evidence("a", document, locator, "x")]
    hit = Hit(document, locator, "x")
    success = evaluate_query(expected, [hit], [hit])
    miss = evaluate_query(expected, [], [])
    negative = evaluate_query([], [], [])
    summary = summarize([success, miss, negative], [1, 2, 100])
    assert summary.positives == 2 and summary.negatives == 1
    assert summary.recall_at_10 == 0.5 and summary.hit_rate_at_10 == 0.5
    assert summary.latency_p50_ms == 2 and summary.latency_p95_ms == 100
    assert compare_recall(
        {"a": success, "b": miss, "n": negative}, {"a": miss, "b": miss, "n": negative}
    ) == (1, 0, 1)
    with pytest.raises(ValueError):
        compare_recall({"a": success}, {"b": success})
    with pytest.raises(ValueError):
        summarize([success], [float("nan")])
