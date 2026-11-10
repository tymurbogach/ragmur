"""Búsqueda HTTP con PostgreSQL y Qdrant aislados."""

import asyncio
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock
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


async def test_search_api_authorization_and_indexed_gate(
    isolated_qdrant: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
        monkeypatch.setenv("QDRANT_COLLECTION", "search_test")
        get_settings.cache_clear()
        dense = Mock()
        dense.dimension = 3
        dense.embed.side_effect = lambda texts, _: [[1.0, 0.0, 0.0] for _ in texts]
        sparse = Mock()
        sparse.metadata = {"model": "test"}
        sparse.embed.side_effect = lambda texts, _: [SparseVector([1], [1.0]) for _ in texts]
        sparse.query_embed.side_effect = lambda value: (
            SparseVector([], []) if value == "empty" else SparseVector([1], [1.0])
        )
        model = EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock())
        monkeypatch.setattr("ragmur.main.load_models", lambda _: model)
        from ragmur.main import create_app

        app = create_app()
        async with (
            app.router.lifespan_context(app),
            AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
        ):
            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                a = await create_tenant(session, "search-a")
                b = await create_tenant(session, "search-b")
                secret = get_settings().api_key_hmac_secret.get_secret_value()
                key_a = await issue_key(session, a.id, None, secret)
                key_b = await issue_key(session, b.id, None, secret)
            headers_a, headers_b = {"X-API-Key": key_a}, {"X-API-Key": key_b}
            empty = await client.post("/v1/search", headers=headers_a, json={"query": "test"})
            assert empty.status_code == 200 and empty.json()["results"] == []

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

            alice = await upload(headers_a, b"alice document", "alice")
            bob = await upload(headers_a, b"bob document", "bob")
            shared = await upload(headers_a, b"shared document", None)
            foreign = await upload(headers_b, b"foreign document", "alice")
            query = {"query": "test", "owner_id": "alice", "rerank": False}
            assert (await client.post("/v1/search", json=query)).status_code == 401
            response = await client.post("/v1/search", headers=headers_a, json=query)
            assert response.status_code == 200
            assert {UUID(hit["document_id"]) for hit in response.json()["results"]} == {alice}
            assert response.json()["results"][0]["score_type"] == "rrf"
            assert response.json()["results"][0]["dense_rank"] == 1
            assert response.json()["results"][0]["sparse_rank"] == 1
            assert all(value >= 0 for value in response.json()["timings_ms"].values())
            response = await client.post("/v1/search", headers=headers_a, json={"query": "test"})
            assert {UUID(hit["document_id"]) for hit in response.json()["results"]} == {
                alice,
                bob,
                shared,
            }
            response = await client.post("/v1/search", headers=headers_b, json=query)
            assert {UUID(hit["document_id"]) for hit in response.json()["results"]} == {foreign}
            response = await client.post(
                "/v1/search",
                headers=headers_a,
                json={"query": "test", "owner_id": "alice", "document_ids": [str(foreign)]},
            )
            assert response.status_code == 200 and response.json()["results"] == []
            response = await client.post(
                "/v1/search",
                headers=headers_a,
                json={"query": "test", "owner_id": "alice", "document_ids": [str(bob)]},
            )
            assert response.status_code == 200 and response.json()["results"] == []
            response = await client.post(
                "/v1/search", headers=headers_a, json={"query": "empty", "owner_id": "alice"}
            )
            assert (
                response.status_code == 200 and response.json()["results"][0]["sparse_rank"] is None
            )
            for invalid in (
                {"query": " ", "owner_id": "alice"},
                {"query": "test", "document_ids": []},
                {"query": "test", "top_k": 4, "candidates": 3},
                {"query": "test", "tenant_id": str(b.id)},
                {"query": "test", "owner_id": " "},
                {"query": "test", "candidates": 101},
            ):
                assert (
                    await client.post("/v1/search", headers=headers_a, json=invalid)
                ).status_code == 422
            assert (
                await client.post(
                    "/v1/search", headers=headers_a, json={"query": "test", "rerank": True}
                )
            ).status_code == 503
            async with factory() as session:
                await session.execute(
                    update(Document).where(Document.id == alice).values(status="failed")
                )
                await session.commit()
            response = await client.post("/v1/search", headers=headers_a, json=query)
            assert response.status_code == 200 and response.json()["results"] == []
            original_resources = app.state.resources
            unavailable = store.create_client("http://127.0.0.1:59998", 1)
            try:
                app.state.resources = replace(original_resources, qdrant=unavailable)
                response = await client.post("/v1/search", headers=headers_a, json=query)
                assert response.status_code == 503
                assert response.json()["detail"] == "Search unavailable"
            finally:
                app.state.resources = original_resources
                await unavailable.close()
            await engine.dispose()
            async with admin.connect() as connection:
                await connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
            response = await client.post("/v1/search", headers=headers_a, json=query)
            assert response.status_code == 503
            assert database not in response.text
    finally:
        await probe.close()
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)'))
        await admin.dispose()
