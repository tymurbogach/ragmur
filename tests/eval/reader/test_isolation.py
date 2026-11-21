"""Aislamiento del tenant lector con Qdrant real y modelos simulados.

Ingesta tres párrafos en el tenant propio del banco (`owner_id` nulo),
copias idénticas en un tenant señuelo y copias en el mismo tenant con otros
`owner_id`. Ninguna búsqueda devuelve puntos del otro lado, en ambos
sentidos, y el filtro por `owner_id` se comporta como documenta `store.py`:
con `owner_id` solo su espacio, sin él todo el tenant por diseño
(`owner_id=None` ve todo el tenant).
"""

import asyncio
from unittest.mock import Mock
from uuid import UUID, uuid4

from eval.reader.index import READER_TENANT_UUID, index_paragraphs

from ragmur.core.config import get_settings
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels
from ragmur.retrieval.sparse import SparseVector

PARAGRAPHS = [
    "Nikola Tesla was an inventor born in Smiljan.",
    "Marie Curie won two Nobel prizes for her research.",
    "Ada Lovelace wrote the first algorithm for a machine.",
]
COLLECTION = "reader_isolation_test"
DECOY_OWNER = "decoy-owner"
DECOY_OWNER_B = "decoy-owner-b"


def fake_models() -> EmbeddingModels:
    """Embedders deterministas sin descargar ningún modelo."""
    dense = Mock()
    dense.dimension = 3
    dense.embed.side_effect = lambda texts, batch_size: [[1.0, 0.0, 0.0] for _ in texts]
    sparse = Mock()
    sparse.metadata = {"model": "test"}
    sparse.embed.side_effect = lambda texts, batch_size: [SparseVector([1], [1.0]) for _ in texts]
    return EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock())


async def wait_for_qdrant(client: store.AsyncQdrantClient) -> None:
    for attempt in range(50):
        try:
            await store.ping(client)
            return
        except Exception:
            if attempt == 49:
                raise
            await asyncio.sleep(0.1)


async def test_reader_tenant_isolation(isolated_qdrant: str) -> None:
    settings = get_settings()
    client = store.create_client(isolated_qdrant, 5)
    try:
        await wait_for_qdrant(client)
        models = fake_models()
        decoy_tenant = uuid4()
        reader_keys = [f"test:{index}" for index in range(len(PARAGRAPHS))]
        await index_paragraphs(
            models=models,
            settings=settings,
            client=client,
            collection=COLLECTION,
            tenant_id=READER_TENANT_UUID,
            paragraphs=list(zip(reader_keys, PARAGRAPHS, strict=True)),
        )
        await index_paragraphs(
            models=models,
            settings=settings,
            client=client,
            collection=COLLECTION,
            tenant_id=decoy_tenant,
            paragraphs=[(f"decoy:{index}", text) for index, text in enumerate(PARAGRAPHS)],
        )
        await index_paragraphs(
            models=models,
            settings=settings,
            client=client,
            collection=COLLECTION,
            tenant_id=READER_TENANT_UUID,
            paragraphs=[(f"owned:{index}", text) for index, text in enumerate(PARAGRAPHS)],
            owner_id=DECOY_OWNER,
            reuse_index=True,
        )
        await index_paragraphs(
            models=models,
            settings=settings,
            client=client,
            collection=COLLECTION,
            tenant_id=READER_TENANT_UUID,
            paragraphs=[(f"owned-b:{index}", text) for index, text in enumerate(PARAGRAPHS)],
            owner_id=DECOY_OWNER_B,
            reuse_index=True,
        )

        async def search(tenant: UUID, owner: str | None) -> list[store.HybridPoint]:
            return await store.hybrid_search(
                tenant,
                client,
                COLLECTION,
                [1.0, 0.0, 0.0],
                [1],
                [1.0],
                owner_id=owner,
                document_ids=None,
                candidates=30,
                rrf_k=2,
            )

        reader_wide = await search(READER_TENANT_UUID, None)
        assert reader_wide
        assert {point.payload["tenant_id"] for point in reader_wide} == {str(READER_TENANT_UUID)}
        assert {point.payload["owner_id"] for point in reader_wide} == {
            None,
            DECOY_OWNER,
            DECOY_OWNER_B,
        }

        decoy_hits = await search(decoy_tenant, None)
        assert decoy_hits
        assert {point.payload["tenant_id"] for point in decoy_hits} == {str(decoy_tenant)}

        owned = await search(READER_TENANT_UUID, DECOY_OWNER)
        assert owned
        assert {point.payload["owner_id"] for point in owned} == {DECOY_OWNER}

        owned_b = await search(READER_TENANT_UUID, DECOY_OWNER_B)
        assert owned_b
        assert {point.payload["owner_id"] for point in owned_b} == {DECOY_OWNER_B}

        for branch in ("dense", "sparse"):
            if branch == "dense":
                foreign = await store.branch_search(
                    decoy_tenant,
                    client,
                    COLLECTION,
                    branch="dense",
                    dense=[1.0, 0.0, 0.0],
                    sparse_indices=[],
                    sparse_values=[],
                    owner_id=None,
                    document_ids=None,
                    limit=30,
                )
            else:
                foreign = await store.branch_search(
                    decoy_tenant,
                    client,
                    COLLECTION,
                    branch="sparse",
                    dense=[],
                    sparse_indices=[1],
                    sparse_values=[1.0],
                    owner_id=None,
                    document_ids=None,
                    limit=30,
                )
            assert {point.payload["tenant_id"] for point in foreign} == {str(decoy_tenant)}
    finally:
        await store.delete_tenant_points(READER_TENANT_UUID, client, COLLECTION)
        await store.delete_tenant_points(decoy_tenant, client, COLLECTION)
        await client.close()
