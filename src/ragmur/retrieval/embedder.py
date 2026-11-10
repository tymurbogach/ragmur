"""Embeddings densos BGE-M3 reutilizados entre peticiones."""

from pathlib import Path
from typing import Any, cast

from sentence_transformers import SentenceTransformer


class DenseEmbedder:
    """Carga una revisión concreta del modelo de embeddings."""

    def __init__(self, model_name: str, revision: str, device: str, cache_dir: Path) -> None:
        self.model = SentenceTransformer(
            model_name,
            revision=revision,
            device=device,
            cache_folder=str(cache_dir / "hub"),
            trust_remote_code=False,
        )
        dimension = self.model.get_embedding_dimension()
        if dimension != 1024:
            raise RuntimeError("The configured embedding model must produce 1024 dimensions")
        self.dimension: int = dimension

    def embed(self, texts: list[str], batch_size: int) -> list[list[float]]:
        """Calcula vectores densos normalizados en lotes."""
        if not texts:
            return []
        vectors = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return cast(list[list[float]], cast(Any, vectors).tolist())
