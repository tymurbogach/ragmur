"""Reindexación de originales con la API detenida."""

import asyncio
from contextlib import AsyncExitStack
from uuid import UUID

from sqlalchemy import select, update

from ragmur.core.config import Settings
from ragmur.db.models import Document, Tenant
from ragmur.db.session import acquire_database_lock, create_engine, create_session_factory
from ragmur.ingestion.indexer import Indexer
from ragmur.ingestion.pipeline import IngestionCoordinator
from ragmur.ingestion.storage import acquire_instance_lock
from ragmur.retrieval.models import load_models
from ragmur.retrieval.store import (
    create_client,
    delete_tenant_points,
    ensure_collection,
    ping,
    set_reindex_metadata,
)


async def reindex(
    settings: Settings, *, document_id: UUID | None, tenant_id: UUID | None
) -> tuple[int, int]:
    """Reindexa un documento, un tenant o todo el corpus con la API detenida."""
    async with AsyncExitStack() as stack:
        try:
            lock = await asyncio.to_thread(acquire_instance_lock, settings.storage_dir)
        except BlockingIOError as exc:
            raise ValueError("Stop the API before reindexing") from exc
        stack.callback(lock.close)
        engine = create_engine(settings.database_url)
        stack.push_async_callback(engine.dispose)
        try:
            db_lock = await acquire_database_lock(engine)
        except RuntimeError as exc:
            raise ValueError("Stop the API before reindexing") from exc
        stack.push_async_callback(db_lock.close)
        sessions = create_session_factory(engine)
        async with sessions() as session:
            query = select(Document.id, Document.tenant_id, Document.status).order_by(
                Document.created_at, Document.id
            )
            if document_id is not None:
                query = query.where(Document.id == document_id)
            if tenant_id is not None:
                query = query.where(Document.tenant_id == tenant_id)
            documents = (await session.execute(query)).all()
        if not documents and (document_id is not None or tenant_id is not None):
            raise ValueError("No documents found for the requested scope")
        if not documents:
            return (0, 0)
        client = create_client(settings.qdrant_url, settings.health_timeout_seconds)
        stack.push_async_callback(client.close)
        await ping(client)
        models = await asyncio.to_thread(load_models, settings)
        indexer = Indexer(client, models, settings)
        coordinator = IngestionCoordinator(sessions, settings, indexer)
        if document_id is None and tenant_id is None:
            if any(document.status == "deleting" for document in documents):
                raise ValueError("Complete pending deletions before reindexing the corpus")
            async with sessions() as session:
                tenant_ids = (await session.scalars(select(Tenant.id))).all()
                await session.execute(
                    update(Document).values(status="pending", error=None, chunk_count=None)
                )
                await session.commit()
            for space in tenant_ids:
                await delete_tenant_points(space, client, settings.qdrant_collection)
            await set_reindex_metadata(
                tenant_ids[0],
                client,
                settings.qdrant_collection,
                models.dense.dimension,
                indexer.metadata(),
            )
        else:
            await ensure_collection(
                documents[0].tenant_id,
                client,
                settings.qdrant_collection,
                models.dense.dimension,
                indexer.metadata(),
            )
        indexed = 0
        failed = 0
        for doc_id, doc_tenant, _ in documents:
            async with sessions() as session:
                document = await session.get(Document, doc_id)
                if document is None or document.status == "deleting":
                    failed += 1
                    continue
                document.status = "pending"
                document.error = None
                document.chunk_count = None
                await session.commit()
            await indexer.cleanup(doc_tenant, doc_id)
            if not coordinator.reserve(doc_id):
                raise RuntimeError("Could not reserve maintenance capacity")
            await coordinator.run(doc_tenant, doc_id)
            async with sessions() as session:
                document = await session.get(Document, doc_id)
                if document is not None and document.status == "indexed":
                    indexed += 1
                else:
                    failed += 1
        return indexed, failed
