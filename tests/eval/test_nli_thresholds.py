"""Comprueba que la comparación conserva la precedencia de contradicción."""

import pytest
from eval.nli_thresholds import select_support_threshold, summarize


def test_counts_supported_and_false_support() -> None:
    rows = [
        {"expected": "supported", "entailment": 0.9, "contradiction": 0.1},
        {"expected": "contradicted", "entailment": 0.9, "contradiction": 0.1},
        {"expected": "contradicted", "entailment": 0.9, "contradiction": 0.9},
        {"expected": "unsupported", "entailment": 0.2, "contradiction": 0.1},
    ]
    assert summarize(rows, 0.75, 0.75) == {
        "true_supported": 1,
        "false_supported": 1,
        "expected_supported": 1,
        "expected_not_supported": 3,
    }
    assert summarize(rows, 0.95, 0.75)["false_supported"] == 0


def test_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        summarize([], 0.75, 0.75)
    with pytest.raises(ValueError):
        summarize(
            [{"expected": "supported", "entailment": float("nan"), "contradiction": 0}], 0.75, 0.75
        )


def test_selects_lowest_false_support_with_minimum_recall() -> None:
    rows = [
        {"split": "dev", "expected": "supported", "entailment": score, "contradiction": 0.1}
        for score in (0.99, 0.94, 0.85, 0.7)
    ] + [
        {"split": "dev", "expected": "unsupported", "entailment": score, "contradiction": 0.1}
        for score in (0.92, 0.8, 0.2)
    ]
    result = select_support_threshold(rows, [0.75, 0.9, 0.95], 0.75, 0.5)
    assert result["selected"]["supported_threshold"] == 0.9
    assert result["selected"]["supported_recall"] == 0.5
    assert result["selected"]["false_support_rate"] == 1 / 3
    assert result["candidates"][2]["eligible"] is False


def test_fails_when_no_threshold_preserves_recall() -> None:
    rows = [
        {"split": "dev", "expected": "supported", "entailment": 0.6, "contradiction": 0.1},
        {"split": "dev", "expected": "unsupported", "entailment": 0.3, "contradiction": 0.1},
    ]
    with pytest.raises(ValueError, match="No threshold"):
        select_support_threshold(rows, [0.75], 0.75, 0.5)
    with pytest.raises(ValueError, match="must exceed"):
        select_support_threshold(rows, [0.5], 0.75, 0.5)
    with pytest.raises(ValueError, match="development"):
        select_support_threshold([{**rows[0], "split": "test"}, rows[1]], [0.5], 0.75, 0.1)
