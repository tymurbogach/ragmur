"""Comprueba las validaciones del evaluador SciFact."""

from pathlib import Path

import pytest
from eval.scifact import load_dataset, write_results


def test_dataset_rejects_corrupted_corpus(tmp_path: Path) -> None:
    (tmp_path / "corpus.jsonl").write_text("corrupted")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_dataset(tmp_path, "test")


def test_dataset_rejects_unknown_partition(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported split"):
        load_dataset(tmp_path, "other")


def test_results_keep_per_query_details_separate(tmp_path: Path) -> None:
    write_results(tmp_path, "test", {"queries": 1}, [{"id": "1"}])
    assert len(list(tmp_path.glob("summary-scifact-test-*.json"))) == 1
    assert len(list((tmp_path / "per_query").glob("scifact-test-*.json"))) == 1


def test_partition_keeps_shared_relevant_documents_together() -> None:
    from eval.scifact import partition_queries

    labels = {"q1": {"a": 1}, "q2": {"a": 1, "b": 1}, "q3": {"b": 1}, "q4": {"c": 1}}
    partitions = partition_queries(labels)
    assert partitions["q1"] == partitions["q2"] == partitions["q3"]
    assert partitions == partition_queries(dict(reversed(list(labels.items()))))
