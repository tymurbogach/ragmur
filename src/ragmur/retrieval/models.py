"""Carga y coordinación de los modelos de indexado."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from ragmur.core.config import Settings
from ragmur.retrieval.embedder import DenseEmbedder
from ragmur.retrieval.reranker import Reranker
from ragmur.retrieval.sparse import SparseEmbedder


async def run_inference[T](operation: Callable[..., T], *args: object) -> T:
    """Espera al hilo incluso si se cancela la petición que mantiene el bloqueo."""
    task = asyncio.create_task(asyncio.to_thread(operation, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not task.cancelled():
            task.exception()
        raise


@dataclass(slots=True)
class EmbeddingModels:
    """Modelos compartidos y bloqueo de inferencia."""

    dense: DenseEmbedder
    sparse: SparseEmbedder
    lock: asyncio.Lock
    reranker: Reranker | None = None


def load_models(settings: Settings) -> EmbeddingModels:
    """Carga ambas revisiones una vez en el arranque."""
    dense = DenseEmbedder(
        settings.embedding_model,
        settings.embedding_revision,
        settings.embedding_device,
        settings.model_cache_dir,
    )
    sparse = SparseEmbedder(
        settings.bm25_model,
        settings.bm25_revision,
        settings.model_cache_dir,
        settings.bm25_language,
        settings.bm25_disable_stemmer,
        settings.bm25_k,
        settings.bm25_b,
        settings.bm25_avg_len,
    )
    reranker = Reranker(
        settings.reranker_model,
        settings.reranker_revision,
        settings.embedding_device,
        settings.model_cache_dir,
    )
    return EmbeddingModels(dense=dense, sparse=sparse, lock=asyncio.Lock(), reranker=reranker)
