"""Reindexación aislada con PostgreSQL y Qdrant reales."""

import asyncio
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ragmur.core.config import Settings, get_settings
from ragmur.db.models import Base, Document, Tenant
from ragmur.ingestion.indexer import Indexer
from ragmur.ingestion.maintenance import reindex
from ragmur.ingestion.pipeline import IngestionCoordinator
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels
from ragmur.retrieval.sparse import SparseVector


async def test_reindex_scopes_and_new_configuration(
    isolated_qdrant: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = make_url(get_settings().database_url)
    database = "test_" + uuid4().hex
    admin = create_async_engine(original, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{database}"'))
    url = original.set(database=database).render_as_string(hide_password=False)
    engine = create_async_engine(url)
    client = store.create_client(isolated_qdrant, 5)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        for attempt in range(50):
            try:
                await store.ping(client)
                break
            except Exception:
                if attempt == 49:
                    raise
                await asyncio.sleep(0.1)
        settings = Settings(
            database_url=url,
            api_key_hmac_secret="test",
            storage_dir=tmp_path,
            qdrant_url=isolated_qdrant,
            qdrant_collection="maintenance_test",
            chunk_size=100,
            chunk_overlap=10,
        )
        dense = Mock()
        dense.dimension = 3
        dense.embed.side_effect = lambda texts, _: [[0.1, 0.2, 0.3] for _ in texts]
        sparse = Mock()
        sparse.metadata = {"model": "test"}
        sparse.embed.side_effect = lambda texts, _: [SparseVector([1], [1.0]) for _ in texts]
        models = EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock())
        monkeypatch.setattr("ragmur.ingestion.maintenance.load_models", lambda _: models)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        coordinator = IngestionCoordinator(factory, settings, Indexer(client, models, settings))
        tenants, docs = [uuid4(), uuid4()], [uuid4(), uuid4()]
        async with factory() as session:
            session.add_all([Tenant(id=tenants[0], name="a"), Tenant(id=tenants[1], name="b")])
            await session.commit()
            for index, document_id in enumerate(docs):
                path = tmp_path / str(document_id)
                path.write_text("A short document", encoding="utf-8")
                session.add(
                    Document(
                        id=document_id,
                        tenant_id=tenants[index],
                        owner_id="alice",
                        filename="a.txt",
                        mime_type="text/plain",
                        content_sha256=str(document_id),
                        storage_path=str(path),
                        status="pending",
                    )
                )
            await session.commit()
        for tenant, document_id in zip(tenants, docs, strict=True):
            assert coordinator.reserve(document_id)
            await coordinator.run(tenant, document_id)
        before_a = await store.list_document_point_ids(
            tenants[0], client, settings.qdrant_collection, docs[0], "alice"
        )
        before_b = await store.list_document_point_ids(
            tenants[1], client, settings.qdrant_collection, docs[1], "alice"
        )
        assert before_a and before_b
        assert await reindex(settings, document_id=docs[0], tenant_id=None) == (1, 0, 0)
        after_a = await store.list_document_point_ids(
            tenants[0], client, settings.qdrant_collection, docs[0], "alice"
        )
        after_b = await store.list_document_point_ids(
            tenants[1], client, settings.qdrant_collection, docs[1], "alice"
        )
        assert after_a and after_a.isdisjoint(before_a)
        assert after_b == before_b
        assert await reindex(settings, document_id=None, tenant_id=tenants[1]) == (1, 0, 0)
        tenant_b_reindexed = await store.list_document_point_ids(
            tenants[1], client, settings.qdrant_collection, docs[1], "alice"
        )
        assert tenant_b_reindexed and tenant_b_reindexed.isdisjoint(after_b)
        assert (
            await store.list_document_point_ids(
                tenants[0], client, settings.qdrant_collection, docs[0], "alice"
            )
            == after_a
        )
        settings.chunk_size = 80
        with pytest.raises(RuntimeError, match="metadata"):
            await reindex(settings, document_id=docs[0], tenant_id=None)
        assert (
            await store.list_document_point_ids(
                tenants[0], client, settings.qdrant_collection, docs[0], "alice"
            )
            == after_a
        )
        from ragmur.ingestion import maintenance

        original_delete = store.delete_tenant_points

        async def interrupted(*args: object, **kwargs: object) -> None:
            raise RuntimeError("interrupted")

        monkeypatch.setattr(maintenance, "delete_tenant_points", interrupted)
        with pytest.raises(RuntimeError, match="interrupted"):
            await reindex(settings, document_id=None, tenant_id=None)
        async with factory() as session:
            for document_id in docs:
                document = await session.get(Document, document_id)
                assert document is not None and document.status == "failed"
        monkeypatch.setattr(maintenance, "delete_tenant_points", original_delete)
        original_metadata = store.set_reindex_metadata
        monkeypatch.setattr(maintenance, "set_reindex_metadata", interrupted)
        with pytest.raises(RuntimeError, match="interrupted"):
            await reindex(settings, document_id=None, tenant_id=None)
        async with factory() as session:
            for document_id in docs:
                document = await session.get(Document, document_id)
                assert document is not None and document.status == "failed"
        for tenant, document_id in zip(tenants, docs, strict=True):
            assert await store.count_document_points(
                tenant, client, settings.qdrant_collection, document_id
            ) == 0
        monkeypatch.setattr(maintenance, "set_reindex_metadata", original_metadata)
        original_run = IngestionCoordinator.run
        calls = 0

        async def interrupted_run(
            coordinator: IngestionCoordinator, tenant_id: UUID, document_id: UUID
        ) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("interrupted during rebuild")
            await original_run(coordinator, tenant_id, document_id)

        monkeypatch.setattr(IngestionCoordinator, "run", interrupted_run)
        with pytest.raises(RuntimeError, match="interrupted during rebuild"):
            await reindex(settings, document_id=None, tenant_id=None)
        async with factory() as session:
            rows = [await session.get(Document, doc_id) for doc_id in docs]
            assert all(row is not None for row in rows)
            statuses = [row.status for row in rows if row is not None]
            assert sorted(statuses) == ["indexed", "pending"]
        monkeypatch.setattr(IngestionCoordinator, "run", original_run)
        assert await reindex(settings, document_id=None, tenant_id=None) == (2, 0, 0)
        assert (
            await store.count_document_points(
                tenants[0], client, settings.qdrant_collection, docs[0], "alice"
            )
            > 0
        )
        assert (
            await store.count_document_points(
                tenants[0], client, settings.qdrant_collection, docs[0], "bob"
            )
            == 0
        )
        assert (
            await store.count_document_points(
                tenants[1], client, settings.qdrant_collection, docs[1], "alice"
            )
            > 0
        )
        assert (
            await store.count_document_points(
                tenants[1], client, settings.qdrant_collection, docs[0], "alice"
            )
            == 0
        )
    finally:
        await client.close()
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        await admin.dispose()


async def test_reindex_refuses_running_instance(tmp_path: Path) -> None:
    from ragmur.ingestion.storage import acquire_instance_lock

    settings = Settings(
        database_url=get_settings().database_url,
        api_key_hmac_secret="test",
        storage_dir=tmp_path,
    )
    with acquire_instance_lock(tmp_path), pytest.raises(ValueError, match="Stop the API"):
        await reindex(settings, document_id=uuid4(), tenant_id=None)


async def test_reindex_counts_unsupported_separately(
    isolated_qdrant: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un escaneado (sin texto) cuenta como unsupported, no como failed."""
    original = make_url(get_settings().database_url)
    database = "test_" + uuid4().hex
    admin = create_async_engine(original, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'CREATE DATABASE "{database}"'))
    url = original.set(database=database).render_as_string(hide_password=False)
    engine = create_async_engine(url)
    client = store.create_client(isolated_qdrant, 5)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        for attempt in range(50):
            try:
                await store.ping(client)
                break
            except Exception:
                if attempt == 49:
                    raise
                await asyncio.sleep(0.1)
        settings = Settings(
            database_url=url,
            api_key_hmac_secret="test",
            storage_dir=tmp_path,
            qdrant_url=isolated_qdrant,
            qdrant_collection="maintenance_unsupported_test",
            chunk_size=100,
            chunk_overlap=10,
        )
        dense = Mock()
        dense.dimension = 3
        dense.embed.side_effect = lambda texts, _: [[0.1, 0.2, 0.3] for _ in texts]
        sparse = Mock()
        sparse.metadata = {"model": "test"}
        sparse.embed.side_effect = lambda texts, _: [SparseVector([1], [1.0]) for _ in texts]
        models = EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock())
        monkeypatch.setattr("ragmur.ingestion.maintenance.load_models", lambda _: models)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant, ok_id, empty_id = uuid4(), uuid4(), uuid4()
        ok_path = tmp_path / str(ok_id)
        empty_path = tmp_path / str(empty_id)
        ok_path.write_text("A short document", encoding="utf-8")
        empty_path.write_text("   ", encoding="utf-8")
        async with factory() as session:
            session.add(Tenant(id=tenant, name="u"))
            await session.commit()
            for document_id, path in ((ok_id, ok_path), (empty_id, empty_path)):
                session.add(
                    Document(
                        id=document_id,
                        tenant_id=tenant,
                        owner_id=None,
                        filename="a.txt",
                        mime_type="text/plain",
                        content_sha256=str(document_id),
                        storage_path=str(path),
                        status="pending",
                    )
                )
            await session.commit()
        assert await reindex(settings, document_id=None, tenant_id=tenant) == (1, 0, 1)
    finally:
        await client.close()
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        await admin.dispose()
