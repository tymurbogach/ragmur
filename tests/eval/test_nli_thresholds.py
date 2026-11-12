"""Comprueba que la comparación conserva la precedencia de contradicción."""

import pytest
from eval.nli_thresholds import summarize


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
