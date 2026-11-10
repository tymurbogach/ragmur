"""Fusión híbrida y corpus IDF con Qdrant real."""

import asyncio
from uuid import UUID, uuid4

from ragmur.retrieval import store


async def test_hybrid_filters_and_idf_corpus(isolated_qdrant: str) -> None:
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
        document_a, document_other = uuid4(), uuid4()
        collection = "hybrid_test"
        await store.ensure_collection(tenant_a, client, collection, 3, {"model": "test"})

        def point(document: UUID, owner: str | None, term: int) -> store.VectorPoint:
            return store.VectorPoint(
                id=uuid4(),
                document_id=document,
                owner_id=owner,
                filename="doc.txt",
                text="text",
                ordinal=0,
                start=0,
                end=4,
                locator={"type": "offset", "start": 0, "end": 4},
                dense=[1.0, 0.0, 0.0],
                sparse_indices=[term],
                sparse_values=[1.0],
            )

        await store.upsert_points(tenant_a, client, collection, [point(document_a, "alice", 1)])
        await store.upsert_points(tenant_a, client, collection, [point(document_other, "alice", 2)])

        async def search(
            tenant: UUID, owner: str | None, docs: list[UUID] | None = None
        ) -> list[store.HybridPoint]:
            return await store.hybrid_search(
                tenant,
                client,
                collection,
                [1.0, 0.0, 0.0],
                [1],
                [1.0],
                owner_id=owner,
                document_ids=docs,
                candidates=30,
                rrf_k=2,
            )

        before = await search(tenant_a, "alice")
        score_before = next(
            p.sparse_score for p in before if p.payload["document_id"] == str(document_a)
        )
        assert score_before is not None
        for _ in range(8):
            await store.upsert_points(tenant_a, client, collection, [point(uuid4(), "bob", 1)])
            await store.upsert_points(tenant_b, client, collection, [point(uuid4(), "bob", 1)])
        after = await search(tenant_a, "alice")
        assert {p.payload["owner_id"] for p in after} == {"alice"}
        score_after = next(
            p.sparse_score for p in after if p.payload["document_id"] == str(document_a)
        )
        assert score_after == score_before
        for branch in ("dense", "sparse"):
            branch_hits = await store.branch_search(
                tenant_a,
                client,
                collection,
                branch=branch,
                dense=[1.0, 0.0, 0.0],
                sparse_indices=[1],
                sparse_values=[1.0],
                owner_id="alice",
                document_ids=None,
                limit=30,
            )
            assert branch_hits and all(hit.payload["owner_id"] == "alice" for hit in branch_hits)
            foreign = await store.branch_search(
                tenant_b,
                client,
                collection,
                branch=branch,
                dense=[1.0, 0.0, 0.0],
                sparse_indices=[1],
                sparse_values=[1.0],
                owner_id="alice",
                document_ids=None,
                limit=30,
            )
            assert foreign == []
        filtered = await search(tenant_a, "alice", [document_a])
        assert len(filtered) == 1 and filtered[0].payload["document_id"] == str(document_a)
        assert filtered[0].sparse_score == score_before
        assert await search(tenant_a, "alice", [uuid4()]) == []
        assert await search(tenant_b, "alice") == []
        bob = await search(tenant_a, "bob")
        assert bob and all(p.payload["owner_id"] == "bob" for p in bob)
        all_owners = await search(tenant_a, None)
        assert {p.payload["owner_id"] for p in all_owners} == {"alice", "bob"}
    finally:
        await client.close()
