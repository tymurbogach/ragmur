"""Prueba opcional con inferencia real; no sustituye la evaluación del corpus."""

import asyncio
import os
from uuid import UUID, uuid4

import pytest

from ragmur.core.config import Settings, get_settings
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.ingestion.indexer import Indexer
from ragmur.retrieval import store
from ragmur.retrieval.models import load_models


@pytest.mark.skipif(os.environ.get("RAGMUR_REAL_MODEL_TESTS") != "1", reason="Requires real models")
async def test_real_models_find_semantic_and_rare_terms_with_isolation(
    isolated_qdrant: str,
) -> None:
    settings = Settings(
        database_url=get_settings().database_url,
        api_key_hmac_secret="test",
        qdrant_url=isolated_qdrant,
        qdrant_collection="real_model_test",
    )
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
        models = await asyncio.to_thread(load_models, settings)
        assert models.reranker is not None
        scores = await asyncio.to_thread(
            models.reranker.score,
            "plazo de entrega",
            ["El plazo de entrega es de 48 horas.", "Las montañas tienen árboles."],
            2,
        )
        assert len(scores) == 2 and scores[0] > scores[1]
        one_score = await asyncio.to_thread(
            models.reranker.score, "plazo", ["El plazo es de 48 horas."], 2
        )
        assert len(one_score) == 1
        indexer = Indexer(client, models, settings)
        tenant_a, tenant_b = uuid4(), uuid4()
        semantic_id, rare_id = uuid4(), uuid4()
        docs = [
            (
                tenant_a,
                "alice",
                semantic_id,
                "Las condiciones de entrega indican un plazo de cuarenta y ocho horas.",
            ),
            (
                tenant_a,
                "alice",
                rare_id,
                "Las montañas y los bosques son zonas naturales con árboles y animales. " * 9
                + " ZXQ794K",
            ),
            (
                tenant_a,
                "alice",
                uuid4(),
                "El código de registro del producto indica su número de referencia "
                "y permite verificar su autenticidad.",
            ),
            (
                tenant_a,
                "alice",
                uuid4(),
                "La referencia del producto está registrada en el catálogo de identificadores.",
            ),
            (
                tenant_a,
                "alice",
                uuid4(),
                "Se consulta el registro de códigos de producto de la base de datos.",
            ),
            (tenant_a, "bob", uuid4(), "ZXQ794K privado de otro usuario"),
            (tenant_b, "alice", uuid4(), "ZXQ794K privado de otro tenant"),
        ]
        for tenant, owner, doc_id, text in docs:
            source = ExtractionResult(
                [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
            )
            assert await indexer.index(tenant, doc_id, owner, "test.txt", source) > 0

        async def query(tenant: UUID, owner: str, value: str) -> list[store.HybridPoint]:
            dense = await asyncio.to_thread(models.dense.embed, [value], 8)
            sparse = await asyncio.to_thread(models.sparse.query_embed, value)
            return await store.hybrid_search(
                tenant,
                client,
                settings.qdrant_collection,
                dense[0],
                sparse.indices,
                sparse.values,
                owner_id=owner,
                document_ids=None,
                candidates=30,
                rrf_k=2,
            )

        semantic = await query(tenant_a, "alice", "duración del suministro")
        hit = next(hit for hit in semantic if hit.payload["document_id"] == str(semantic_id))
        assert hit.dense_rank is not None and hit.sparse_rank is None
        rare = await query(tenant_a, "alice", "ZXQ794K")
        hit = next(hit for hit in rare if hit.payload["document_id"] == str(rare_id))
        assert hit.sparse_rank == 1 and hit.dense_rank is not None and hit.dense_rank > 1
        assert all(
            hit.payload["owner_id"] == "alice" and hit.payload["tenant_id"] == str(tenant_a)
            for hit in rare
        )
        bob = await query(tenant_a, "bob", "ZXQ794K")
        assert bob and all(hit.payload["owner_id"] == "bob" for hit in bob)
        foreign = await query(tenant_b, "alice", "ZXQ794K")
        assert foreign and all(hit.payload["tenant_id"] == str(tenant_b) for hit in foreign)
    finally:
        await client.close()
