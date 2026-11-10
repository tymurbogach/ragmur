"""Recuperación de puntos parciales desde un proceso nuevo."""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ragmur.core.config import get_settings
from ragmur.db.models import Base, Document, Tenant
from ragmur.retrieval import store


async def test_restart_cleans_interrupted_document_without_crossing_tenants(
    isolated_qdrant: str, tmp_path: Path
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
        tenant_a, tenant_b, document_id = uuid4(), uuid4(), uuid4()
        original_file = tmp_path / str(document_id)
        original_file.write_text("content", encoding="utf-8")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            session.add_all([Tenant(id=tenant_a, name="a"), Tenant(id=tenant_b, name="b")])
            await session.commit()
            session.add(
                Document(
                    id=document_id,
                    tenant_id=tenant_a,
                    owner_id="alice",
                    filename="doc.txt",
                    mime_type="text/plain",
                    content_sha256="a" * 64,
                    storage_path=str(original_file),
                    status="processing",
                )
            )
            await session.commit()
        collection = "restart_test"
        await store.ensure_collection(tenant_a, client, collection, 3, {"model": "test"})
        for tenant, owner in ((tenant_a, "alice"), (tenant_b, "bob")):
            point = store.VectorPoint(
                id=uuid4(),
                document_id=document_id,
                owner_id=owner,
                filename="doc.txt",
                text="content",
                ordinal=0,
                start=0,
                end=7,
                locator={"type": "offset", "start": 0, "end": 7},
                dense=[0.1, 0.2, 0.3],
                sparse_indices=[1],
                sparse_values=[1.0],
            )
            await store.upsert_points(tenant, client, collection, [point])
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": url,
                "API_KEY_HMAC_SECRET": "test",
                "QDRANT_URL": isolated_qdrant,
                "QDRANT_COLLECTION": collection,
                "STORAGE_DIR": str(tmp_path),
            }
        )
        program = """
import asyncio
from unittest.mock import Mock
from ragmur.core.config import get_settings
from ragmur.db.session import create_engine, create_session_factory
from ragmur.ingestion.indexer import Indexer
from ragmur.ingestion.pipeline import IngestionCoordinator
from ragmur.retrieval.store import create_client
async def main():
    settings = get_settings()
    engine = create_engine(settings.database_url)
    client = create_client(settings.qdrant_url, settings.health_timeout_seconds)
    try:
        coordinator = IngestionCoordinator(
            create_session_factory(engine), settings, Indexer(client, Mock(), settings)
        )
        await coordinator.reconcile()
    finally:
        await client.close()
        await engine.dispose()
asyncio.run(main())
"""
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            program,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        assert process.returncode == 0, stderr.decode()
        async with factory() as session:
            document = await session.get(Document, document_id)
            assert document is not None and document.status == "failed"
        assert original_file.exists()
        assert (
            await store.count_document_points(tenant_a, client, collection, document_id, "alice")
            == 0
        )
        assert (
            await store.count_document_points(tenant_b, client, collection, document_id, "bob") == 1
        )
        assert (
            await store.count_document_points(tenant_b, client, collection, document_id, "alice")
            == 0
        )
    finally:
        await client.close()
        await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        await admin.dispose()
