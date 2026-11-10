"""Prueba la colección y el aislamiento contra Qdrant en Docker."""

import asyncio
from uuid import UUID, uuid4

import pytest

from ragmur.retrieval import store


async def test_store_isolates_tenants_and_owners(isolated_qdrant: str) -> None:
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
        tenant_a, tenant_b, document_id = uuid4(), uuid4(), uuid4()
        collection = "test_chunks"
        await store.ensure_collection(tenant_a, client, collection, 3, {"model": "test"})
        await store.ensure_collection(tenant_b, client, collection, 3, {"model": "test"})
        with pytest.raises(RuntimeError, match="metadata"):
            await store.ensure_collection(tenant_a, client, collection, 3, {"model": "different"})
        shared_id = uuid4()

        def point(identifier: UUID, owner: str | None) -> store.VectorPoint:
            return store.VectorPoint(
                id=identifier,
                document_id=document_id,
                owner_id=owner,
                filename="test.txt",
                text="hello",
                ordinal=0,
                start=0,
                end=5,
                locator={"type": "offset", "start": 0, "end": 5},
                dense=[0.1, 0.2, 0.3],
                sparse_indices=[1],
                sparse_values=[1.0],
            )

        await store.upsert_points(tenant_a, client, collection, [point(shared_id, "alice")])
        await store.upsert_points(tenant_a, client, collection, [point(uuid4(), "bob")])
        await store.upsert_points(tenant_b, client, collection, [point(uuid4(), "alice")])
        assert (
            await store.count_document_points(tenant_a, client, collection, document_id, "alice")
            == 1
        )
        assert (
            await store.count_document_points(tenant_a, client, collection, document_id, "bob") == 1
        )
        assert (
            await store.count_document_points(tenant_b, client, collection, document_id, "bob") == 0
        )
        with pytest.raises(RuntimeError):
            await store.upsert_points(tenant_b, client, collection, [point(shared_id, "alice")])
        with pytest.raises(RuntimeError):
            await store.upsert_points(tenant_a, client, collection, [point(shared_id, "bob")])
        assert await store.count_document_points(tenant_a, client, collection, document_id) == 2
        assert await store.count_document_points(tenant_b, client, collection, document_id) == 1
        shared_point = point(uuid4(), None)
        await store.upsert_points(tenant_a, client, collection, [shared_point])
        await store.upsert_points(tenant_a, client, collection, [shared_point])
        assert await store.count_document_points(tenant_a, client, collection, document_id) == 3
        await store.delete_document_points(tenant_a, client, collection, document_id, "bob")
        assert (
            await store.count_document_points(tenant_a, client, collection, document_id, "bob") == 0
        )
        assert (
            await store.count_document_points(tenant_a, client, collection, document_id, "alice")
            == 1
        )
        await store.delete_document_points(tenant_a, client, collection, document_id)
        assert await store.count_document_points(tenant_a, client, collection, document_id) == 0
        assert await store.count_document_points(tenant_b, client, collection, document_id) == 1
    finally:
        await client.close()
