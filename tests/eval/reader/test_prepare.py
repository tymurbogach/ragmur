"""Reanudación y guardas de `prepare_bank` con dependencias simuladas."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from eval.reader.cache import append_results, build_cache_key, cache_file_paths
from eval.reader.prepare import is_dirty_tree, prepare_bank
from eval.reader.retrieve import RetrievalResult
from eval.reader.xquad import ReaderCase

from ragmur.core.config import get_settings


def fake_case(case_id: str) -> ReaderCase:
    return ReaderCase(
        case_id=case_id,
        article="Tesla",
        paragraph_index=0,
        question=f"question {case_id}",
        answers=("answer",),
        split="dev",
        document_key="xquad-es:Tesla:0",
    )


def fake_result(case_id: str) -> RetrievalResult:
    from eval.reader.retrieve import ReaderHit

    return RetrievalResult(
        case_id=case_id,
        query=f"question {case_id}",
        hits=(
            ReaderHit(
                rank=1,
                chunk_id=uuid4(),
                document_key="xquad-es:Tesla:0",
                text="some text",
                rerank_score=1.0,
            ),
        ),
        latency_ms=5.0,
    )


def mock_common(tmp_path: Path, cases: list[ReaderCase]) -> tuple[Any, list[Any]]:
    settings = get_settings()
    doc_id = uuid4()
    mapping = {"xquad-es:Tesla:0": doc_id}
    models = SimpleNamespace(
        dense=Mock(),
        sparse=SimpleNamespace(metadata={"language": "spanish"}),
    )
    client = SimpleNamespace(close=AsyncMock())
    patches = [
        patch("eval.reader.prepare.is_dirty_tree", return_value=False),
        patch("eval.reader.prepare.download_dataset", return_value=tmp_path / "x.json"),
        patch("eval.reader.prepare.load_dataset", return_value={"data": []}),
        patch("eval.reader.prepare.check_article_count", return_value=None),
        patch(
            "eval.reader.prepare.iter_paragraphs",
            return_value=[("xquad-es:Tesla:0", "some context")],
        ),
        patch("eval.reader.prepare.list_cases", return_value=cases),
        patch("eval.reader.prepare.sample_cases", return_value=cases),
        patch("eval.reader.prepare.load_models", return_value=models),
        patch("eval.reader.prepare.read_commit", return_value="abc123"),
        patch("eval.reader.prepare.dataset_sha256", return_value="0" * 64),
        patch("eval.reader.prepare.hardware_info", return_value={"cpu": "test"}),
        patch("eval.reader.prepare.index_paragraphs", new=AsyncMock(return_value=mapping)),
        patch("ragmur.retrieval.store.create_client", return_value=client),
        patch("ragmur.retrieval.store.ping", new=AsyncMock(return_value=None)),
    ]
    return settings, patches


async def test_resume_does_not_repeat_cached_cases(tmp_path: Path) -> None:
    cases = [fake_case("qa-1"), fake_case("qa-2")]
    settings, patches = mock_common(tmp_path, cases)
    for entered in patches:
        entered.start()
    try:
        # Prepara la caché con el primer caso ya guardado.
        from eval.reader.cache import sparse_metadata_hash

        key = build_cache_key(
            dataset_sha256="0" * 64,
            commit="abc123",
            dirty=False,
            configuration="hybrid_rerank",
            candidates=30,
            top_k=5,
            rrf_k=settings.rrf_k,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            dense_model=settings.embedding_model,
            dense_revision=settings.embedding_revision,
            sparse_model=settings.bm25_model,
            sparse_revision=settings.bm25_revision,
            sparse_metadata_hash=sparse_metadata_hash({"language": "spanish"}),
            reranker_model=settings.reranker_model,
            reranker_revision=settings.reranker_revision,
            seed=20261121,
            sample_size=2,
            split="dev",
        )
        jsonl_path, _ = cache_file_paths(tmp_path, key)
        append_results(jsonl_path, [fake_result("qa-1")])
        with patch(
            "eval.reader.prepare.retrieve_case",
            new=AsyncMock(side_effect=lambda **kwargs: fake_result(kwargs["case"].case_id)),
        ) as retrieve:
            out = await prepare_bank(
                settings,
                split="dev",
                sample_size=2,
                seed=20261121,
                candidates=30,
                top_k=5,
                collection_suffix="_eval_reader",
                results_dir=tmp_path,
                dataset_path=tmp_path / "x.json",
                reuse_index=True,
                allow_dirty=True,
            )
        assert out == jsonl_path
        assert retrieve.await_count == 1
        called_ids = [call.kwargs["case"].case_id for call in retrieve.await_args_list]
        assert called_ids == ["qa-2"]
    finally:
        for entered in reversed(patches):
            entered.stop()


async def test_dirty_tree_refuses_without_flag(tmp_path: Path) -> None:
    settings = get_settings()
    with (
        patch("eval.reader.prepare.is_dirty_tree", return_value=True),
        pytest.raises(RuntimeError, match="allow-dirty"),
    ):
        await prepare_bank(
            settings,
            split="dev",
            sample_size=1,
            seed=1,
            candidates=30,
            top_k=5,
            collection_suffix="_eval_reader",
            results_dir=tmp_path,
            dataset_path=tmp_path / "x.json",
            reuse_index=True,
            allow_dirty=False,
        )


async def test_empty_collection_suffix_is_rejected(tmp_path: Path) -> None:
    settings = get_settings()
    with (
        patch("eval.reader.prepare.is_dirty_tree", return_value=True),
        pytest.raises(ValueError, match="collection-suffix"),
    ):
        await prepare_bank(
            settings,
            split="dev",
            sample_size=1,
            seed=1,
            candidates=30,
            top_k=5,
            collection_suffix="",
            results_dir=tmp_path,
            dataset_path=tmp_path / "x.json",
            reuse_index=True,
            allow_dirty=True,
        )


async def test_meta_preserves_created_at(tmp_path: Path) -> None:
    cases = [fake_case("qa-1")]
    settings, patches = mock_common(tmp_path, cases)
    for entered in patches:
        entered.start()
    try:
        with patch(
            "eval.reader.prepare.retrieve_case",
            new=AsyncMock(side_effect=lambda **kwargs: fake_result(kwargs["case"].case_id)),
        ):
            await prepare_bank(
                settings,
                split="dev",
                sample_size=1,
                seed=20261121,
                candidates=30,
                top_k=5,
                collection_suffix="_eval_reader",
                results_dir=tmp_path,
                dataset_path=tmp_path / "x.json",
                reuse_index=True,
                allow_dirty=True,
            )
        from eval.reader.cache import sparse_metadata_hash

        key = build_cache_key(
            dataset_sha256="0" * 64,
            commit="abc123",
            dirty=False,
            configuration="hybrid_rerank",
            candidates=30,
            top_k=5,
            rrf_k=settings.rrf_k,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            dense_model=settings.embedding_model,
            dense_revision=settings.embedding_revision,
            sparse_model=settings.bm25_model,
            sparse_revision=settings.bm25_revision,
            sparse_metadata_hash=sparse_metadata_hash({"language": "spanish"}),
            reranker_model=settings.reranker_model,
            reranker_revision=settings.reranker_revision,
            seed=20261121,
            sample_size=1,
            split="dev",
        )
        _, meta_path = cache_file_paths(tmp_path, key)
        first = json.loads(meta_path.read_text(encoding="utf-8"))
        assert "created_at" in first and "updated_at" in first
        assert first["dirty"] is False
        assert first["rrf_k"] == settings.rrf_k
        assert "sparse_metadata_hash" in first
        assert first["hardware"] == {"cpu": "test"}
        with patch(
            "eval.reader.prepare.retrieve_case",
            new=AsyncMock(side_effect=AssertionError("must not retrieve again")),
        ):
            await prepare_bank(
                settings,
                split="dev",
                sample_size=1,
                seed=20261121,
                candidates=30,
                top_k=5,
                collection_suffix="_eval_reader",
                results_dir=tmp_path,
                dataset_path=tmp_path / "x.json",
                reuse_index=True,
                allow_dirty=True,
            )
        second = json.loads(meta_path.read_text(encoding="utf-8"))
        assert second["created_at"] == first["created_at"]
    finally:
        for entered in reversed(patches):
            entered.stop()


def test_is_dirty_tree_ignores_results_and_datasets(tmp_path: Path) -> None:
    # Solo verifica el filtrado: un estado con esas rutas no cuenta como sucio.
    from eval.reader import prepare as prepare_module

    with patch("subprocess.run") as run:
        run.return_value = Mock(
            stdout=" M eval/results/reader/per_query/x.jsonl\n"
            "?? eval/.datasets/xquad/xquad.es.json\n"
        )
        assert prepare_module.is_dirty_tree() is False
        run.return_value = Mock(stdout=" M eval/reader/cache.py\n")
        assert prepare_module.is_dirty_tree() is True
    assert isinstance(is_dirty_tree(), bool)
