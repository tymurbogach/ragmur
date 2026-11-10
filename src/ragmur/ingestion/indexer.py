"""Indexado de fragmentos con compensación de fallos."""

import asyncio
from uuid import UUID

from ragmur.core.config import Settings
from ragmur.ingestion.chunker import split_document
from ragmur.ingestion.extractors.core import ExtractionResult
from ragmur.retrieval import store
from ragmur.retrieval.models import EmbeddingModels


class IncompleteCleanupError(RuntimeError):
    """Los puntos parciales requieren limpieza posterior."""


class Indexer:
    """Crea vectores por lotes y los guarda en el espacio autorizado."""

    def __init__(
        self, client: store.AsyncQdrantClient, models: EmbeddingModels, settings: Settings
    ) -> None:
        self.client = client
        self.models = models
        self.settings = settings
        self.initialization_lock = asyncio.Lock()

    def metadata(self) -> dict[str, object]:
        """Devuelve la configuración que debe compartir toda la colección."""
        settings = self.settings
        return {
            "dense_model": settings.embedding_model,
            "dense_revision": settings.embedding_revision,
            "dense_dimension": self.models.dense.dimension,
            "sparse": self.models.sparse.metadata,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "normalization": "lf-v1",
        }

    async def cleanup(self, tenant_id: UUID, document_id: UUID) -> None:
        """Elimina de forma idempotente los vectores de un documento."""
        collection = self.settings.qdrant_collection
        try:
            await store.delete_document_points(tenant_id, self.client, collection, document_id)
        except Exception as exc:
            raise IncompleteCleanupError("Could not remove old points") from exc

    async def index(
        self,
        tenant_id: UUID,
        document_id: UUID,
        owner_id: str | None,
        filename: str,
        extraction: ExtractionResult,
    ) -> int:
        """Indexa un documento y elimina puntos parciales si falla."""
        settings = self.settings
        chunks = split_document(
            extraction,
            document_id,
            tenant_id,
            owner_id,
            size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        ).chunks
        if not chunks:
            await self.cleanup(tenant_id, document_id)
            raise ValueError("The document has no extractable chunks")
        collection = settings.qdrant_collection
        async with self.initialization_lock:
            await store.ensure_collection(
                tenant_id, self.client, collection, self.models.dense.dimension, self.metadata()
            )
        await self.cleanup(tenant_id, document_id)
        try:
            for start in range(0, len(chunks), settings.index_batch_size):
                batch = chunks[start : start + settings.index_batch_size]
                texts = [chunk.text for chunk in batch]
                async with self.models.lock:
                    dense = await asyncio.to_thread(
                        self.models.dense.embed, texts, settings.embedding_batch_size
                    )
                    sparse = await asyncio.to_thread(
                        self.models.sparse.embed, texts, settings.embedding_batch_size
                    )
                if len(dense) != len(batch) or len(sparse) != len(batch):
                    raise RuntimeError("Embedding model returned an unexpected number of vectors")
                points = [
                    store.VectorPoint(
                        id=chunk.id,
                        document_id=document_id,
                        owner_id=owner_id,
                        filename=filename,
                        text=chunk.text,
                        ordinal=chunk.ordinal,
                        start=chunk.start,
                        end=chunk.end,
                        locator=chunk.locator,
                        dense=dense_vector,
                        sparse_indices=sparse_vector.indices,
                        sparse_values=sparse_vector.values,
                    )
                    for chunk, dense_vector, sparse_vector in zip(batch, dense, sparse, strict=True)
                ]
                await store.upsert_points(tenant_id, self.client, collection, points)
        except asyncio.CancelledError:
            raise
        except KeyboardInterrupt:
            raise
        except Exception:
            try:
                await self.cleanup(tenant_id, document_id)
            except Exception as exc:
                raise IncompleteCleanupError("Could not remove partial points") from exc
            raise
        return len(chunks)
