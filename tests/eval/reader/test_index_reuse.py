"""`--reuse-index` omite documentos ya indexados con el mismo conteo."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from eval.reader.index import index_paragraphs

from ragmur.core.config import get_settings
from ragmur.retrieval.sparse import SparseVector


def fake_models() -> Any:
    dense = Mock()
    dense.dimension = 3
    dense.embed.side_effect = lambda texts, batch: [[1.0, 0.0, 0.0] for _ in texts]
    sparse = Mock()
    sparse.metadata = {
        "language": "spanish",
        "disable_stemmer": False,
        "k": 1.2,
        "b": 0.75,
        "avg_len": 256.0,
    }
    sparse.embed.side_effect = lambda texts, batch: [SparseVector([1], [1.0]) for _ in texts]
    return SimpleNamespace(dense=dense, sparse=sparse)


async def test_reuse_index_skips_matching_point_count() -> None:
    settings = get_settings()
    client = Mock()
    paragraphs = [("k1", "short text one"), ("k2", "short text two")]
    # chunk counts: textos cortos -> 1 fragmento cada uno.
    with (
        patch("eval.reader.index.store.ensure_collection", new=AsyncMock()),
        patch(
            "eval.reader.index.store.count_document_points",
            new=AsyncMock(side_effect=[1, 0]),
        ) as count,
        patch("eval.reader.index.store.delete_document_points", new=AsyncMock()) as delete,
        patch("eval.reader.index.store.delete_tenant_points", new=AsyncMock()) as delete_tenant,
        patch("eval.reader.index.store.upsert_points", new=AsyncMock()) as upsert,
    ):
        mapping = await index_paragraphs(
            models=fake_models(),
            settings=settings,
            client=client,
            collection="col",
            tenant_id=uuid4(),
            paragraphs=paragraphs,
            reuse_index=True,
        )
    assert set(mapping) == {"k1", "k2"}
    assert count.await_count == 2
    # k1 coincide (1 punto) y se omite: solo k2 publica.
    assert upsert.await_count == 1
    delete_tenant.assert_not_awaited()
    # k2 no coincide y limpia sus puntos antes de reindexar.
    assert delete.await_count == 1


def test_index_uses_indexer_metadata() -> None:
    import inspect

    from eval.reader import index as index_module

    source = inspect.getsource(index_module.index_paragraphs)
    assert "Indexer(" in source and ".metadata()" in source
