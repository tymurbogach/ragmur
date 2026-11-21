"""Recuperación del banco sin modelos ni Qdrant reales."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest
from eval.reader.retrieve import retrieve_case
from eval.reader.xquad import ReaderCase

from ragmur.core.config import get_settings


def make_case() -> ReaderCase:
    return ReaderCase(
        case_id="qa-1",
        article="Tesla",
        paragraph_index=0,
        question="Who was Tesla?",
        answers=("an inventor",),
        split="dev",
        document_key="xquad-es:Tesla:0",
    )


def make_models(scores: list[float] | None = None, *, no_reranker: bool = False) -> Any:
    if scores is None:
        scores = [3.0, 1.0, 2.0]
    dense = Mock()
    dense.embed.return_value = [[1.0, 0.0]]
    sparse = Mock()
    sparse.query_embed.return_value = SimpleNamespace(indices=[1], values=[1.0])
    reranker = None if no_reranker else Mock()
    if reranker is not None:
        reranker.score.return_value = scores
    return SimpleNamespace(dense=dense, sparse=sparse, reranker=reranker)


def make_points(n: int, doc_id: UUID) -> Any:
    points = []
    for index in range(n):
        points.append(
            SimpleNamespace(
                id=uuid4(),
                payload={
                    "text": f"text-{index}",
                    "document_id": str(doc_id),
                },
            )
        )
    return points


async def test_orders_by_score_and_cuts_to_top_k() -> None:
    settings = get_settings()
    doc_id = uuid4()
    models = make_models([1.0, 3.0, 2.0])
    points = make_points(3, doc_id)
    document_keys = {str(doc_id): "xquad-es:Tesla:0"}
    with patch(
        "eval.reader.retrieve.store.hybrid_search",
        new=AsyncMock(return_value=points),
    ):
        result = await retrieve_case(
            case=make_case(),
            models=models,
            settings=settings,
            client=Mock(),
            collection="col",
            tenant_id=uuid4(),
            document_keys=document_keys,
            candidates=3,
            top_k=2,
        )
    assert [hit.text for hit in result.hits] == ["text-1", "text-2"]
    assert [hit.rerank_score for hit in result.hits] == [3.0, 2.0]
    assert [hit.rank for hit in result.hits] == [1, 2]


async def test_requires_reranker() -> None:
    settings = get_settings()
    doc_id = uuid4()
    models = make_models(no_reranker=True)
    points = make_points(1, doc_id)
    with (
        patch(
            "eval.reader.retrieve.store.hybrid_search",
            new=AsyncMock(return_value=points),
        ),
        pytest.raises(RuntimeError, match="Reranker"),
    ):
        await retrieve_case(
            case=make_case(),
            models=models,
            settings=settings,
            client=Mock(),
            collection="col",
            tenant_id=uuid4(),
            document_keys={str(doc_id): "xquad-es:Tesla:0"},
        )


async def test_rejects_point_outside_corpus() -> None:
    settings = get_settings()
    doc_id = uuid4()
    other = uuid4()
    models = make_models([1.0])
    points = make_points(1, other)
    with (
        patch(
            "eval.reader.retrieve.store.hybrid_search",
            new=AsyncMock(return_value=points),
        ),
        pytest.raises(RuntimeError, match="outside"),
    ):
        await retrieve_case(
            case=make_case(),
            models=models,
            settings=settings,
            client=Mock(),
            collection="col",
            tenant_id=uuid4(),
            document_keys={str(doc_id): "xquad-es:Tesla:0"},
        )
