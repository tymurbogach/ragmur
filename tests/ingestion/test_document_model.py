"""Comprueba las restricciones de documentos en PostgreSQL."""

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from ragmur.core.config import get_settings
from ragmur.db.models import Document, Tenant
from ragmur.db.session import create_engine, create_session_factory


async def test_deduplication_includes_null_owner() -> None:
    engine = create_engine(get_settings().database_url)
    factory = create_session_factory(engine)
    tenant_id = uuid.uuid4()

    def document(owner: str | None) -> Document:
        return Document(
            tenant_id=tenant_id,
            owner_id=owner,
            filename="test.txt",
            mime_type="text/plain",
            content_sha256="a" * 64,
            storage_path=str(uuid.uuid4()),
            status="pending",
        )

    try:
        async with factory() as session:
            session.add(Tenant(id=tenant_id, name="document-test"))
            await session.commit()
            session.add(document(None))
            await session.commit()
            session.add(document(None))
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()
            session.add(document("owner-a"))
            session.add(document("owner-b"))
            await session.commit()
    finally:
        async with factory() as session:
            await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
            await session.commit()
        await engine.dispose()
