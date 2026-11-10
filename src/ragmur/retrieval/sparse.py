"""Embeddings léxicos BM25 con configuración explícita."""

import hashlib
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, cast

from fastembed import SparseTextEmbedding
from huggingface_hub import snapshot_download


@dataclass(frozen=True, slots=True)
class SparseVector:
    """Índices y pesos de un vector disperso."""

    indices: list[int]
    values: list[float]


class SparseEmbedder:
    """Carga BM25 con una revisión y una configuración reproducibles."""

    def __init__(
        self,
        model_name: str,
        revision: str,
        cache_dir: Path,
        language: str,
        disable_stemmer: bool,
        k: float,
        b: float,
        avg_len: float,
    ) -> None:
        model_path = snapshot_download(
            repo_id=model_name,
            revision=revision,
            cache_dir=str(cache_dir / "hub"),
        )
        self.model = SparseTextEmbedding(
            model_name=model_name,
            cache_dir=str(cache_dir),
            specific_model_path=model_path,
            language=language,
            disable_stemmer=disable_stemmer,
            k=k,
            b=b,
            avg_len=avg_len,
        )
        inner = cast(Any, self.model.model)
        words = "\n".join(sorted(inner.stopwords)).encode()
        self.metadata = {
            "model": model_name,
            "fastembed_version": version("fastembed"),
            "revision": revision,
            "language": language,
            "disable_stemmer": disable_stemmer,
            "stemmer": type(inner.stemmer).__name__ if inner.stemmer else None,
            "stopwords_sha256": hashlib.sha256(words).hexdigest(),
            "k": k,
            "b": b,
            "avg_len": avg_len,
            "token_max_length": inner.token_max_length,
        }

    def embed(self, texts: list[str], batch_size: int) -> list[SparseVector]:
        """Calcula pesos documentales BM25."""
        return [
            SparseVector(vector.indices.tolist(), vector.values.tolist())
            for vector in self.model.embed(texts, batch_size=batch_size)
        ]

    def query_embed(self, text: str) -> SparseVector:
        """Calcula los pesos de una consulta BM25."""
        vector = next(iter(self.model.query_embed(text)))
        return SparseVector(vector.indices.tolist(), vector.values.tolist())
