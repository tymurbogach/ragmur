"""Comprueba las métricas por documento de SciFact."""

import pytest
from eval.scifact_metrics import evaluate_documents


def test_cut_precedes_document_deduplication() -> None:
    result = evaluate_documents(["a", "a", "b"], {"b": 1}, limit=2)
    assert result.hit == 0
    assert result.recall == 0
    assert result.ndcg == 0


def test_multiple_relevant_documents_and_deduplication() -> None:
    result = evaluate_documents(["a", "a", "b"], {"a": 1, "b": 1})
    assert result.hit == 1
    assert result.recall == 1
    assert result.ndcg == pytest.approx(1)


def test_invalid_relevance() -> None:
    with pytest.raises(ValueError):
        evaluate_documents([], {})


def test_classifies_retrieval_and_reranking_misses() -> None:
    from eval.scifact_metrics import classify_miss

    assert classify_miss(["x"], ["x"], {"a": 1}) == "missing_from_candidates"
    assert (
        classify_miss(["a", "x"], ["x", "a"], {"a": 1}, limit=1) == "outside_top_10_after_reranking"
    )
    assert classify_miss(["a"], ["a"], {"a": 1}) == "found"
