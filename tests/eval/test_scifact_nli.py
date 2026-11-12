"""Comprueba la selección de fragmentos con evidencia anotada."""

import pytest
from eval.scifact_nli import evidence_chunk


def test_evidence_chunk_contains_annotated_sentences() -> None:
    result = evidence_chunk(["First sentence.", "Second sentence."], [0, 1])
    assert result == "First sentence.\nSecond sentence."


def test_evidence_spanning_larger_than_chunk_is_skipped() -> None:
    assert evidence_chunk(["a" * 750, "b" * 200], [0, 1]) is None


def test_invalid_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="indices"):
        evidence_chunk(["Sentence"], [1])
    with pytest.raises(ValueError, match="indices"):
        evidence_chunk(["Sentence"], [])
