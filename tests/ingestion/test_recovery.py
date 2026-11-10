"""Recuperación de documentos tras una parada inesperada."""

import os
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from ragmur.core.config import Settings, get_settings
from ragmur.db.models import Base, Document, Tenant
from ragmur.db.session import create_engine
from ragmur.ingestion.pipeline import IngestionCoordinator


async def test_recovery_marks_jobs_and_finishes_deletions(tmp_path: Path) -> None:
    settings = Settings(
        database_url=get_settings().database_url,
        api_key_hmac_secret="test-only",
        storage_dir=tmp_path,
        orphan_min_age_seconds=3600,
    )
    admin = create_engine(settings.database_url)
    schema = f"test_{uuid4().hex}"
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        settings.database_url, connect_args={"server_settings": {"search_path": schema}}
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id, pending_id, deleting_id = uuid4(), uuid4(), uuid4()
    pending_path, deleting_path = tmp_path / str(pending_id), tmp_path / str(deleting_id)
    pending_path.write_text("pending", encoding="utf-8")
    deleting_path.write_text("deleting", encoding="utf-8")
    orphan = tmp_path / str(uuid4())
    unrelated = tmp_path / "notes.txt"
    orphan.write_text("orphan", encoding="utf-8")
    unrelated.write_text("keep", encoding="utf-8")
    old = time.time() - 7200
    os.utime(orphan, (old, old))
    os.utime(unrelated, (old, old))
    try:
        async with factory() as session:
            session.add(Tenant(id=tenant_id, name="recovery-test"))
            await session.commit()
            for doc_id, path, status in (
                (pending_id, pending_path, "pending"),
                (deleting_id, deleting_path, "deleting"),
            ):
                session.add(
                    Document(
                        id=doc_id,
                        tenant_id=tenant_id,
                        filename="a.txt",
                        mime_type="text/plain",
                        content_sha256=str(doc_id),
                        storage_path=str(path),
                        status=status,
                    )
                )
            await session.commit()
        await IngestionCoordinator(factory, settings).reconcile()
        async with factory() as session:
            pending = await session.get(Document, pending_id)
            assert pending is not None and pending.status == "failed"
            assert await session.get(Document, deleting_id) is None
        assert pending_path.exists() and not deleting_path.exists()
        assert not orphan.exists() and unrelated.exists()
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


async def test_recovery_isolates_corrupt_rows(tmp_path: Path) -> None:
    """Una fila con ruta inválida no impide reconciliar el resto ni tumba el arranque."""
    settings = Settings(
        database_url=get_settings().database_url,
        api_key_hmac_secret="test-only",
        storage_dir=tmp_path,
        orphan_min_age_seconds=3600,
    )
    admin = create_engine(settings.database_url)
    schema = f"test_{uuid4().hex}"
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        settings.database_url, connect_args={"server_settings": {"search_path": schema}}
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        tenant_id, good_id, bad_id = uuid4(), uuid4(), uuid4()
        good_path = tmp_path / str(good_id)
        good_path.write_text("pending", encoding="utf-8")
        async with factory() as session:
            session.add(Tenant(id=tenant_id, name="recovery-isolation"))
            await session.commit()
            session.add(
                Document(
                    id=good_id,
                    tenant_id=tenant_id,
                    filename="a.txt",
                    mime_type="text/plain",
                    content_sha256=str(good_id),
                    storage_path=str(good_path),
                    status="pending",
                )
            )
            session.add(
                Document(
                    id=bad_id,
                    tenant_id=tenant_id,
                    filename="b.txt",
                    mime_type="text/plain",
                    content_sha256=str(bad_id),
                    storage_path="/etc/passwd",
                    status="deleting",
                )
            )
            await session.commit()
        await IngestionCoordinator(factory, settings).reconcile()
        async with factory() as session:
            good = await session.get(Document, good_id)
            assert good is not None and good.status == "failed"
            bad = await session.get(Document, bad_id)
            assert bad is not None and bad.status == "deleting"
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
