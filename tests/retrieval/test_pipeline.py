"""Consistencia de ingesta e indexado con PostgreSQL y Qdrant reales."""

import asyncio
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ragmur.core.config import Settings, get_settings
from ragmur.db.models import Base, Document, Tenant
from ragmur.db.session import create_engine
from ragmur.ingestion.indexer import Indexer
from ragmur.ingestion.pipeline import IngestionCoordinator
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels
from ragmur.retrieval.sparse import SparseVector


async def test_ingest_and_recover_partial_points(isolated_qdrant: str, tmp_path: Path) -> None:
    settings = Settings(
        database_url=get_settings().database_url,
        api_key_hmac_secret="test",
        storage_dir=tmp_path,
        chunk_size=100,
        chunk_overlap=10,
        qdrant_collection="pipeline_test",
    )
    admin = create_engine(settings.database_url)
    schema = f"test_{uuid4().hex}"
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        settings.database_url, connect_args={"server_settings": {"search_path": schema}}
    )
    client = store.create_client(isolated_qdrant, 5)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        for attempt in range(50):
            try:
                await store.ping(client)
                break
            except Exception:
                if attempt == 49:
                    raise
                await asyncio.sleep(0.1)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        dense = Mock()
        dense.dimension = 3
        dense.embed.side_effect = lambda texts, _: [[0.1, 0.2, 0.3] for _ in texts]
        sparse = Mock()
        sparse.metadata = {"model": "test"}
        sparse.embed.side_effect = lambda texts, _: [SparseVector([1], [1.0]) for _ in texts]
        indexer = Indexer(
            client, EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock()), settings
        )
        coordinator = IngestionCoordinator(factory, settings, indexer)
        tenant_a, tenant_b, doc_id = uuid4(), uuid4(), uuid4()
        path = tmp_path / str(doc_id)
        path.write_text("A small document", encoding="utf-8")
        async with factory() as session:
            session.add_all([Tenant(id=tenant_a, name="a"), Tenant(id=tenant_b, name="b")])
            await session.commit()
            session.add(
                Document(
                    id=doc_id,
                    tenant_id=tenant_a,
                    owner_id="alice",
                    filename="doc.txt",
                    mime_type="text/plain",
                    content_sha256="a" * 64,
                    storage_path=str(path),
                    status="pending",
                )
            )
            await session.commit()
        assert coordinator.reserve(doc_id)
        await coordinator.run(tenant_a, doc_id)
        async with factory() as session:
            doc = await session.get(Document, doc_id)
            assert doc is not None and doc.status == "indexed" and doc.chunk_count == 1
            doc.status = "processing"
            await session.commit()
        assert (
            await store.count_document_points(
                tenant_a, client, settings.qdrant_collection, doc_id, "alice"
            )
            == 1
        )
        assert (
            await store.count_document_points(
                tenant_a, client, settings.qdrant_collection, doc_id, "bob"
            )
            == 0
        )
        assert (
            await store.count_document_points(tenant_b, client, settings.qdrant_collection, doc_id)
            == 0
        )
        await coordinator.reconcile()
        async with factory() as session:
            doc = await session.get(Document, doc_id)
            assert doc is not None and doc.status == "failed"
        assert (
            await store.count_document_points(tenant_a, client, settings.qdrant_collection, doc_id)
            == 0
        )
        assert path.exists()
    finally:
        await client.close()
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
