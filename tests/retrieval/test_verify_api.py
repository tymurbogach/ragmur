"""Verificación HTTP con aislamiento y umbrales."""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ragmur.auth.service import create_tenant, issue_key
from ragmur.core.config import get_settings
from ragmur.db.models import Base, Document
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels
from ragmur.retrieval.sparse import SparseVector


async def _wait_search(
    client: AsyncClient, headers: dict[str, str], payload: dict[str, Any]
) -> list[dict[str, Any]]:
    for _ in range(50):
        response = await client.post("/v1/search", headers=headers, json=payload)
        assert response.status_code == 200
        body: Any = response.json()
        results: list[dict[str, Any]] = body["results"]
        if results:
            return results
        await asyncio.sleep(0.1)
    raise AssertionError("search did not index in time")


async def test_verify_verdicts_and_isolation(
    isolated_qdrant: str, tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    original = make_url(get_settings().database_url)
    database = "test_" + uuid4().hex
    admin = create_async_engine(original, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database}"'))
    url = original.set(database=database).render_as_string(hide_password=False)
    engine = create_async_engine(url)
    probe = store.create_client(isolated_qdrant, 5)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        for attempt in range(50):
            try:
                await store.ping(probe)
                break
            except Exception:
                if attempt == 49:
                    raise
                await asyncio.sleep(0.1)
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("QDRANT_URL", isolated_qdrant)
        monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
        monkeypatch.setenv("QDRANT_COLLECTION", "verify_test")
        get_settings.cache_clear()
        dense = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        dense.dimension = 3
        dense.embed.side_effect = lambda texts, _: [[1.0, 0.0, 0.0] for _ in texts]
        sparse = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        sparse.metadata = {"model": "test"}
        sparse.embed.side_effect = lambda texts, _: [SparseVector([1], [1.0]) for _ in texts]
        sparse.query_embed.side_effect = lambda value: SparseVector([1], [1.0])
        reranker = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        reranker.score.side_effect = lambda _q, texts, _b: [float(i) for i in range(len(texts))]
        models = EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock(), reranker=reranker)
        verifier = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        verifier.check_hypothesis.return_value = None
        verifier.score_pairs.side_effect = lambda premises, hyps, _b: [(0.9, 0.1)] * len(hyps)
        monkeypatch.setattr("ragmur.main.load_models", lambda _: models)
        monkeypatch.setattr("ragmur.main.load_verifier", lambda _: verifier)
        from ragmur.main import create_app

        app = create_app()
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                tenant_a = await create_tenant(session, "verify-a")
                tenant_b = await create_tenant(session, "verify-b")
                secret = get_settings().api_key_hmac_secret.get_secret_value()
                key_a = await issue_key(session, tenant_a.id, None, secret)
                key_b = await issue_key(session, tenant_b.id, None, secret)
            headers_a, headers_b = {"X-API-Key": key_a}, {"X-API-Key": key_b}
            assert (await client.post("/v1/verify", json={})).status_code == 401

            async def upload(headers: dict[str, str], content: bytes, owner: str | None) -> UUID:
                data = {} if owner is None else {"owner_id": owner}
                response = await client.post(
                    "/v1/documents",
                    headers=headers,
                    files={"file": ("doc.txt", content, "text/plain")},
                    data=data,
                )
                assert response.status_code == 202
                return UUID(response.json()["document_id"])

            alice = await upload(headers_a, b"El plazo de entrega es 48 horas.", "alice")
            await upload(headers_a, b"Documento de otro usuario.", "bob")
            foreign_doc = await upload(headers_b, b"Documento ajeno.", "alice")
            hits = await _wait_search(
                client, headers_a, {"query": "plazo", "owner_id": "alice", "rerank": False}
            )
            assert {UUID(hit["document_id"]) for hit in hits} == {alice}
            chunk_id = UUID(hits[0]["chunk_id"])
            foreign_hits = await _wait_search(
                client, headers_b, {"query": "ajeno", "owner_id": "alice", "rerank": False}
            )
            foreign_chunk = UUID(foreign_hits[0]["chunk_id"])

            async def verify(headers: dict[str, str], payload: dict[str, Any]) -> tuple[int, Any]:
                response = await client.post("/v1/verify", headers=headers, json=payload)
                body: Any = response.json()
                return response.status_code, body

            status, body = await verify(
                headers_a, {"answer": "El plazo es 48 horas.", "chunk_ids": [str(chunk_id)]}
            )
            assert status == 200 and body["claims"][0]["verdict"] == "supported"
            assert body["claims"][0]["score"] == 0.9
            assert UUID(body["claims"][0]["best_chunk_id"]) == chunk_id
            assert body["summary"] == {
                "supported": 1,
                "weak": 0,
                "unsupported": 0,
                "contradicted": 0,
            }
            verifier.score_pairs.side_effect = lambda p, h, _b: [(0.9, 0.8)] * len(h)
            status, body = await verify(
                headers_a, {"answer": "El plazo es 48 horas.", "chunk_ids": [str(chunk_id)]}
            )
            assert body["claims"][0]["verdict"] == "contradicted"
            assert body["claims"][0]["score"] == 0.8
            verifier.score_pairs.side_effect = lambda p, h, _b: [(0.6, 0.1)] * len(h)
            status, body = await verify(
                headers_a, {"answer": "El plazo es 48 horas.", "chunk_ids": [str(chunk_id)]}
            )
            assert body["claims"][0]["verdict"] == "weak"
            verifier.score_pairs.side_effect = lambda p, h, _b: [(0.2, 0.1)] * len(h)
            status, body = await verify(
                headers_a, {"answer": "El plazo es 48 horas.", "chunk_ids": [str(chunk_id)]}
            )
            assert body["claims"][0]["verdict"] == "unsupported"
            assert body["claims"][0]["score"] == 0.2
            assert body["claims"][0]["best_chunk_id"] is None
            verifier.score_pairs.side_effect = lambda p, h, _b: [(0.9, 0.1)] * len(h)
            status, body = await verify(
                headers_a,
                {"answer": "Texto ajeno.", "chunk_ids": [str(foreign_chunk)], "owner_id": "alice"},
            )
            assert status == 200
            assert body["claims"][0]["verdict"] == "unsupported"
            assert body["claims"][0]["score"] == 0.0
            status, body = await verify(
                headers_a,
                {
                    "answer": "El plazo es 48 horas.",
                    "chunk_ids": [str(chunk_id), str(foreign_chunk)],
                    "owner_id": "alice",
                },
            )
            assert status == 200 and body["claims"][0]["verdict"] == "supported"
            async with factory() as session:
                await session.execute(
                    update(Document).where(Document.id == alice).values(status="failed")
                )
                await session.commit()
            status, body = await verify(
                headers_a,
                {
                    "answer": "El plazo es 48 horas.",
                    "chunk_ids": [str(chunk_id)],
                    "owner_id": "alice",
                },
            )
            assert body["claims"][0]["verdict"] == "unsupported"
            many_ids = [str(uuid4()) for _ in range(21)]
            for invalid in (
                {"answer": " ", "chunk_ids": [str(chunk_id)]},
                {"answer": "texto", "chunk_ids": []},
                {"answer": "texto", "chunk_ids": many_ids},
                {"answer": "texto", "chunk_ids": [str(chunk_id)], "owner_id": " "},
                {"answer": "texto", "chunk_ids": [str(chunk_id)], "tenant_id": str(tenant_a.id)},
            ):
                assert (
                    await client.post("/v1/verify", headers=headers_a, json=invalid)
                ).status_code in (
                    401,
                    422,
                )
            assert (await client.post("/v1/verify", headers=headers_a, json={})).status_code == 422
            _ = foreign_doc
            await engine.dispose()
            async with admin.connect() as connection:
                await connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
    finally:
        await probe.close()
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        await admin.dispose()
