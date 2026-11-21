"""Ingesta del banco XQuAD-es en su tenant y colección propios.

Cada párrafo es un documento Ragmur (`document_key` de `xquad.py`) con UUID
derivado de su clave, de modo que reindexar no duplica ni renombra. Los
fragmentos (`chunks`, trozos en que se divide cada documento) llevan un UUID
derivado del documento y su ordinal: es el `chunk_id` estable que guarda la
caché, válido mientras no cambie la configuración de troceado. Un reindexado
con otro `chunk_size` regenera los identificadores, igual que en el servicio.

El troceado (`split_document` 800/120 de la configuración) y los pasos de
embedding y subida son los mismos que en `eval/run.py::index_corpus`, pero en
un indexador propio del banco: la colección es dedicada y los identificadores
son deterministas, así que compartir la función cambiaría su comportamiento.
"""

from __future__ import annotations

import asyncio
from uuid import NAMESPACE_DNS, UUID, uuid5

from ragmur.core.config import Settings
from ragmur.ingestion.chunker import split_document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.ingestion.indexer import Indexer
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels

READER_TENANT_UUID = uuid5(NAMESPACE_DNS, "ragmur.eval.reader.xquad-es")
DOCUMENT_NAMESPACE = "ragmur.eval.reader.doc:"
CHUNK_NAMESPACE = "ragmur.eval.reader.chunk:"
DEFAULT_COLLECTION_SUFFIX = "_eval_reader"
SOURCE_FILENAME = "xquad.es.json"


def reader_document_uuid(key: str) -> UUID:
    """Identidad estable del documento a partir de su `document_key`."""
    return uuid5(NAMESPACE_DNS, f"{DOCUMENT_NAMESPACE}{key}")


def reader_chunk_uuid(document_id: UUID, ordinal: int) -> UUID:
    """Identidad estable del fragmento a partir del documento y su ordinal."""
    return uuid5(NAMESPACE_DNS, f"{CHUNK_NAMESPACE}{document_id}:{ordinal}")


def reader_collection_name(settings: Settings, suffix: str = DEFAULT_COLLECTION_SUFFIX) -> str:
    """Colección de evaluación propia del banco, derivada de la configurada."""
    return f"{settings.qdrant_collection}{suffix}"


async def index_paragraphs(
    *,
    models: EmbeddingModels,
    settings: Settings,
    client: store.AsyncQdrantClient,
    collection: str,
    tenant_id: UUID,
    paragraphs: list[tuple[str, str]],
    owner_id: str | None = None,
    reuse_index: bool = False,
) -> dict[str, UUID]:
    """Trocea, embebe y publica cada párrafo como documento del tenant."""
    indexer = Indexer(client, models, settings)
    await store.ensure_collection(
        tenant_id, client, collection, models.dense.dimension, indexer.metadata()
    )
    if not reuse_index:
        await store.delete_tenant_points(tenant_id, client, collection)
    mapping: dict[str, UUID] = {}
    for key, context in paragraphs:
        document_id = reader_document_uuid(key)
        mapping[key] = document_id
        extraction = ExtractionResult(
            [Fragment(context, {"type": "offset", "start": 0, "end": len(context)})]
        )
        chunks = split_document(
            extraction,
            document_id,
            tenant_id,
            owner_id,
            size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        ).chunks
        if not chunks:
            raise RuntimeError(f"Paragraph {key} produced no chunks")
        if reuse_index:
            existing = await store.count_document_points(
                tenant_id, client, collection, document_id, owner_id
            )
            if existing == len(chunks):
                continue
            await store.delete_document_points(tenant_id, client, collection, document_id, owner_id)
        else:
            await store.delete_document_points(tenant_id, client, collection, document_id, owner_id)
        texts = [chunk.text for chunk in chunks]
        dense_vectors = await asyncio.to_thread(
            models.dense.embed, texts, settings.embedding_batch_size
        )
        sparse_vectors = await asyncio.to_thread(
            models.sparse.embed, texts, settings.embedding_batch_size
        )
        points = [
            store.VectorPoint(
                id=reader_chunk_uuid(document_id, chunk.ordinal),
                document_id=document_id,
                owner_id=owner_id,
                filename=SOURCE_FILENAME,
                text=chunk.text,
                ordinal=chunk.ordinal,
                start=chunk.start,
                end=chunk.end,
                locator=chunk.locator,
                dense=dense_vector,
                sparse_indices=sparse_vector.indices,
                sparse_values=sparse_vector.values,
            )
            for chunk, dense_vector, sparse_vector in zip(
                chunks, dense_vectors, sparse_vectors, strict=True
            )
        ]
        for start in range(0, len(points), settings.index_batch_size):
            await store.upsert_points(
                tenant_id, client, collection, points[start : start + settings.index_batch_size]
            )
    return mapping
