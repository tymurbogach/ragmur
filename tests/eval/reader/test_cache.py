"""Clave de caché y reanudación del JSONL sin modelos."""

from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from eval.reader.cache import (
    append_results,
    build_cache_key,
    cache_file_paths,
    read_cached_case_ids,
    record_to_result,
    result_to_record,
    sparse_metadata_hash,
)
from eval.reader.retrieve import ReaderHit, RetrievalResult

BASE_KEY: dict[str, Any] = {
    "dataset_sha256": "0" * 64,
    "commit": "abc123",
    "dirty": False,
    "configuration": "hybrid_rerank",
    "candidates": 30,
    "top_k": 5,
    "rrf_k": 2,
    "chunk_size": 800,
    "chunk_overlap": 120,
    "dense_model": "dense",
    "dense_revision": "rev1",
    "sparse_model": "sparse",
    "sparse_revision": "rev2",
    "sparse_metadata_hash": "0" * 64,
    "reranker_model": "reranker",
    "reranker_revision": "rev3",
    "seed": 20261121,
    "sample_size": 100,
    "split": "dev",
}

ALTERNATES: dict[str, Any] = {
    "dataset_sha256": "1" * 64,
    "commit": "def456",
    "dirty": True,
    "configuration": "hybrid",
    "candidates": 20,
    "top_k": 3,
    "rrf_k": 7,
    "chunk_size": 400,
    "chunk_overlap": 60,
    "dense_model": "other-dense",
    "dense_revision": "revX",
    "sparse_model": "other-sparse",
    "sparse_revision": "revY",
    "sparse_metadata_hash": "1" * 64,
    "reranker_model": "other-reranker",
    "reranker_revision": "revZ",
    "seed": 1,
    "sample_size": 5,
    "split": "reserve",
}


def sample_result(case_id: str) -> RetrievalResult:
    return RetrievalResult(
        case_id=case_id,
        query=f"question {case_id}",
        hits=(
            ReaderHit(
                rank=1,
                chunk_id=uuid4(),
                document_key="xquad-es:Tesla:0",
                text="Nikola Tesla was an inventor.",
                rerank_score=2.5,
            ),
        ),
        latency_ms=12.5,
    )


def test_cache_key_is_stable_hex() -> None:
    first = build_cache_key(**BASE_KEY)
    assert first == build_cache_key(**BASE_KEY)
    assert len(first) == 16 and all(char in "0123456789abcdef" for char in first)


def test_resume_skips_done_cases(tmp_path: Path) -> None:
    jsonl_path, _ = cache_file_paths(tmp_path, "deadbeef01234567")
    assert read_cached_case_ids(jsonl_path) == set()
    append_results(jsonl_path, [sample_result("qa-1"), sample_result("qa-2")])
    assert read_cached_case_ids(jsonl_path) == {"qa-1", "qa-2"}
    append_results(jsonl_path, [sample_result("qa-3")])
    assert read_cached_case_ids(jsonl_path) == {"qa-1", "qa-2", "qa-3"}


def test_record_round_trip() -> None:
    result = sample_result("qa-1")
    assert record_to_result(result_to_record(result)) == result


def test_cache_paths_share_the_key(tmp_path: Path) -> None:
    jsonl_path, meta_path = cache_file_paths(tmp_path, "deadbeef01234567")
    assert jsonl_path.name == "retrieval-deadbeef01234567.jsonl"
    assert meta_path.name == "retrieval-deadbeef01234567.meta.json"
    assert jsonl_path.parent == meta_path.parent == tmp_path / "per_query"


@pytest.mark.parametrize("field", sorted(BASE_KEY))
def test_each_field_affects_the_key(field: str) -> None:
    mutated = dict(BASE_KEY)
    mutated[field] = ALTERNATES[field]
    assert build_cache_key(**mutated) != build_cache_key(**BASE_KEY)


def test_sparse_metadata_hash_covers_bm25_settings() -> None:
    base = {
        "language": "spanish",
        "disable_stemmer": False,
        "k": 1.2,
        "b": 0.75,
        "avg_len": 256.0,
    }
    assert sparse_metadata_hash(base) == sparse_metadata_hash(dict(base))
    for field, other in [
        ("language", "english"),
        ("disable_stemmer", True),
        ("k", 2.0),
        ("b", 0.5),
        ("avg_len", 100.0),
    ]:
        mutated = dict(base)
        mutated[field] = other
        assert sparse_metadata_hash(mutated) != sparse_metadata_hash(base)


def test_truncated_last_line_is_ignored_and_rewritten(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    jsonl_path, _ = cache_file_paths(tmp_path, "deadbeef01234567")
    append_results(jsonl_path, [sample_result("qa-1")])
    with jsonl_path.open("a", encoding="utf-8") as stream:
        stream.write('{"case_id": "qa-2", "query": "trunc')
    with caplog.at_level(logging.WARNING):
        assert read_cached_case_ids(jsonl_path) == {"qa-1"}
    assert any("truncated" in record.message for record in caplog.records)
    # Reescrito sin la línea truncada: la siguiente lectura es estable.
    assert read_cached_case_ids(jsonl_path) == {"qa-1"}
    append_results(jsonl_path, [sample_result("qa-2")])
    assert read_cached_case_ids(jsonl_path) == {"qa-1", "qa-2"}


def test_middle_malformed_line_raises(tmp_path: Path) -> None:
    jsonl_path, _ = cache_file_paths(tmp_path, "deadbeef01234567")
    append_results(jsonl_path, [sample_result("qa-1")])
    with jsonl_path.open("a", encoding="utf-8") as stream:
        stream.write("not json\n")
        stream.write('{"case_id": "qa-3", "query": "x", "hits": [], "latency_ms": 1}\n')
    with pytest.raises(ValueError, match="Malformed cache line"):
        read_cached_case_ids(jsonl_path)
