"""Alcance autorizado de `_checked_payload` y `retrieve_points` (Qdrant real)."""

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import pytest

from ragmur.retrieval import store

if TYPE_CHECKING:
    from qdrant_client import models as qdrant_models


def _scored(payload: dict[str, Any]) -> "qdrant_models.ScoredPoint":
    """Construye el mínimo que `_checked_payload` lee, sin importar Qdrant."""
    return cast("qdrant_models.ScoredPoint", SimpleNamespace(payload=payload))


def test_checked_payload_rejects_out_of_scope_point() -> None:
    tenant_id = uuid4()
    document_id = uuid4()
    base = {"tenant_id": str(tenant_id), "owner_id": "alice", "document_id": str(document_id)}

    assert store._checked_payload(_scored(dict(base)), tenant_id, "alice", [document_id]) == base

    with pytest.raises(RuntimeError, match="outside the authorized tenant"):
        store._checked_payload(
            _scored({**base, "tenant_id": str(uuid4())}), tenant_id, "alice", [document_id]
        )
    with pytest.raises(RuntimeError, match="outside the authorized owner"):
        store._checked_payload(
            _scored({**base, "owner_id": "bob"}), tenant_id, "alice", [document_id]
        )
    with pytest.raises(RuntimeError, match="outside the document filter"):
        store._checked_payload(
            _scored({**base, "document_id": str(uuid4())}), tenant_id, "alice", [document_id]
        )


async def test_retrieve_points_omits_out_of_scope_point(isolated_qdrant: str) -> None:
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
        tenant_a, tenant_b = uuid4(), uuid4()
        document_id = uuid4()
        collection = "scope_test"
        await store.ensure_collection(tenant_a, client, collection, 3, {"model": "test"})
        point_id = uuid4()
        await store.upsert_points(
            tenant_a,
            client,
            collection,
            [
                store.VectorPoint(
                    id=point_id,
                    document_id=document_id,
                    owner_id="alice",
                    filename="doc.txt",
                    text="text",
                    ordinal=0,
                    start=0,
                    end=4,
                    locator={"type": "offset", "start": 0, "end": 4},
                    dense=[1.0, 0.0, 0.0],
                    sparse_indices=[1],
                    sparse_values=[1.0],
                )
            ],
        )
        own = await store.retrieve_points(tenant_a, client, collection, [point_id], "alice")
        assert [point.id for point in own] == [point_id]
        assert await store.retrieve_points(tenant_b, client, collection, [point_id], "alice") == []
        assert await store.retrieve_points(tenant_a, client, collection, [point_id], "bob") == []
    finally:
        await client.close()
