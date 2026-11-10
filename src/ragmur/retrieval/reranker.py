"""Reordenación local por relevancia de consulta y fragmento."""

from pathlib import Path
from typing import Any, cast

from sentence_transformers import CrossEncoder
from torch.nn import Identity


class Reranker:
    """Carga una revisión concreta del modelo de reordenación."""

    def __init__(self, model_name: str, revision: str, device: str, cache_dir: Path) -> None:
        self.model = CrossEncoder(
            model_name,
            revision=revision,
            device=device,
            cache_folder=str(cache_dir / "hub"),
            trust_remote_code=False,
            activation_fn=Identity(),
        )

    def score(self, query: str, texts: list[str], batch_size: int) -> list[float]:
        """Puntúa pares por lotes y devuelve valores sin normalizar."""
        if not texts:
            return []
        pairs = [(query, text) for text in texts]
        scores = self.model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            apply_softmax=False,
        )
        return cast(list[float], cast(Any, scores).tolist())
