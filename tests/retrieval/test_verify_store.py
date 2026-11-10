"""Recuperación por identificadores para verificación."""

import asyncio
from uuid import uuid4

from ragmur.retrieval import store


async def test_retrieve_points_ignores_foreign_ids(isolated_qdrant: str) -> None:
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
        document = uuid4()
        collection = "test_verify_chunks"
        await store.ensure_collection(tenant_a, client, collection, 3, {"model": "test"})

        def point(owner: str | None) -> store.VectorPoint:
            return store.VectorPoint(
                id=uuid4(),
                document_id=document,
                owner_id=owner,
                filename="test.txt",
                text="evidencia",
                ordinal=0,
                start=0,
                end=8,
                locator={"type": "offset", "start": 0, "end": 8},
                dense=[0.1, 0.2, 0.3],
                sparse_indices=[1],
                sparse_values=[1.0],
            )

        alice = point("alice")
        bob = point("bob")
        await store.upsert_points(tenant_a, client, collection, [alice])
        await store.upsert_points(tenant_a, client, collection, [bob])
        assert await store.retrieve_points(tenant_a, client, "missing", [alice.id], None) == []
        assert await store.retrieve_points(tenant_a, client, collection, [], None) == []
        own = await store.retrieve_points(tenant_a, client, collection, [alice.id, bob.id], "alice")
        assert [item.id for item in own] == [alice.id]
        foreign = await store.retrieve_points(
            tenant_b, client, collection, [alice.id, bob.id], None
        )
        assert foreign == []
        both = await store.retrieve_points(
            tenant_a, client, collection, [alice.id, bob.id, uuid4()], None
        )
        assert {item.id for item in both} == {alice.id, bob.id}
    finally:
        await client.close()
