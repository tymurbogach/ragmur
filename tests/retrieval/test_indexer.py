"""Indexación y compensación contra Qdrant real."""

import asyncio
from unittest.mock import Mock
from uuid import uuid4

import pytest

from ragmur.core.config import Settings, get_settings
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.ingestion.indexer import Indexer
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels
from ragmur.retrieval.sparse import SparseVector


async def test_indexer_removes_partial_batches_and_keeps_other_tenants(
    isolated_qdrant: str,
) -> None:
    client = store.create_client(isolated_qdrant, 5)
    try:
        for attempt in range(50):
            try:
                await store.ping(client)
                break
            except Exception:
                if attempt == 49:
                    raise
                await asyncio.sleep(0.1)
        settings = Settings(
            database_url=get_settings().database_url,
            api_key_hmac_secret="test",
            chunk_size=5,
            chunk_overlap=1,
            index_batch_size=1,
            qdrant_collection="index_test",
        )
        dense = Mock()
        dense.dimension = 3
        dense.embed.side_effect = [[[0.1, 0.2, 0.3]], ValueError("embedding failed")]
        sparse = Mock()
        sparse.metadata = {"model": "test"}
        sparse.embed.return_value = [SparseVector([1], [1.0])]
        models = EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock())
        indexer = Indexer(client, models, settings)
        tenant_a, tenant_b, document_id = uuid4(), uuid4(), uuid4()
        text = "a long document"
        source = ExtractionResult(
            [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
        )
        metadata = {
            "dense_model": settings.embedding_model,
            "dense_revision": settings.embedding_revision,
            "dense_dimension": 3,
            "sparse": sparse.metadata,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "normalization": "lf-v1",
        }
        await store.ensure_collection(tenant_b, client, settings.qdrant_collection, 3, metadata)
        other = store.VectorPoint(
            id=uuid4(),
            document_id=document_id,
            owner_id="bob",
            filename="a.txt",
            text="other",
            ordinal=0,
            start=0,
            end=5,
            locator={"type": "offset", "start": 0, "end": 5},
            dense=[0.1, 0.2, 0.3],
            sparse_indices=[1],
            sparse_values=[1.0],
        )
        await store.upsert_points(tenant_b, client, settings.qdrant_collection, [other])
        with pytest.raises(ValueError, match="embedding failed"):
            await indexer.index(tenant_a, document_id, "alice", "a.txt", source)
        assert (
            await store.count_document_points(
                tenant_a, client, settings.qdrant_collection, document_id
            )
            == 0
        )
        assert (
            await store.count_document_points(
                tenant_b, client, settings.qdrant_collection, document_id, "bob"
            )
            == 1
        )
        assert (
            await store.count_document_points(
                tenant_b, client, settings.qdrant_collection, document_id, "alice"
            )
            == 0
        )
    finally:
        await client.close()
