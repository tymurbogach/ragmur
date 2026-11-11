"""Verificación de citas con inferencia de lenguaje natural.

Clasifica pares (premisa, hipótesis) como entailment, neutral o contradiction.
La ejecución es local y reutiliza el modelo entre peticiones. Los umbrales se
calibran en desarrollo y se evalúan con datos reservados; este módulo solo
puntúa, no decide veredictos.
"""

from pathlib import Path
from typing import Literal

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from ragmur.core.config import Settings


def _find_label(id2label: dict[int, str], names: tuple[str, ...]) -> int:
    """Localiza un índice de etiqueta sin suponer su orden."""
    normalized = {index: label.lower() for index, label in id2label.items()}
    for index, label in normalized.items():
        if any(name in label for name in names):
            return index
    raise RuntimeError(f"NLI label not found: {names}")


class NliVerifier:
    """Cross-encoder NLI cargado una vez y reutilizado entre peticiones."""

    def __init__(
        self,
        model_name: str,
        revision: str,
        device: str,
        cache_dir: Path,
        max_windows: int = 2000,
    ) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            cache_dir=str(cache_dir / "hub"),
            trust_remote_code=False,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            revision=revision,
            cache_dir=str(cache_dir / "hub"),
            trust_remote_code=False,
        )
        self.model.to(device)
        self.model.eval()
        self.device = device
        raw_labels: dict[int, str] = dict(self.model.config.id2label)
        self.entailment_index = _find_label(raw_labels, ("entail",))
        self.contradiction_index = _find_label(raw_labels, ("contradict", "contra"))
        _find_label(raw_labels, ("neutral",))
        position_embeddings = getattr(self.model.config, "max_position_embeddings", 512)
        self.max_length = min(int(position_embeddings), 512)
        self.max_windows = max_windows

    def check_hypothesis(self, hypothesis: str) -> None:
        """Rechaza hipótesis que no caben con los tokens especiales."""
        if not hypothesis.strip():
            raise ValueError("Hypothesis must not be blank")
        tokens = self.tokenizer(hypothesis, add_special_tokens=False)["input_ids"]
        special = self.tokenizer.num_special_tokens_to_add(pair=True)
        if len(tokens) + special >= self.max_length:
            raise ValueError("Hypothesis exceeds the model context")

    def score_pairs(
        self, premises: list[str], hypotheses: list[str], batch_size: int
    ) -> list[tuple[float, float]]:
        """Puntúa pares por lotes y devuelve máximos por par original.

        Cada par puede generar varias ventanas sobre la premisa; se conserva el
        máximo de entailment y de contradiction por separado. La hipótesis nunca
        se trunca: si no cabe, se rechaza en lugar de puntuar solo una parte.
        """
        if len(premises) != len(hypotheses):
            raise ValueError("Premises and hypotheses must align")
        if not premises:
            return []
        for hypothesis in hypotheses:
            self.check_hypothesis(hypothesis)
        special = self.tokenizer.num_special_tokens_to_add(pair=True)
        budgets = [
            self.max_length
            - special
            - len(self.tokenizer(h, add_special_tokens=False)["input_ids"])
            for h in hypotheses
        ]
        stride = min(50, min(budgets) - 1)
        windows = 0
        for premise, budget in zip(premises, budgets, strict=True):
            length = len(self.tokenizer(premise, add_special_tokens=False)["input_ids"])
            windows += 1 + max(0, (length - budget + budget - stride - 1) // (budget - stride))
            if windows > self.max_windows:
                raise ValueError("Too many verification windows")
        encoding = self.tokenizer(
            premises,
            hypotheses,
            truncation="only_first",
            max_length=self.max_length,
            stride=stride,
            return_overflowing_tokens=True,
            padding=True,
            return_tensors="pt",
        )
        mapping: list[int] = encoding["overflow_to_sample_mapping"].tolist()
        input_ids = encoding["input_ids"]
        attention_mask = encoding["attention_mask"]
        window_ents: list[float] = []
        window_contras: list[float] = []
        with torch.no_grad():
            for start in range(0, len(input_ids), batch_size):
                batch_ids = input_ids[start : start + batch_size].to(self.device)
                batch_mask = attention_mask[start : start + batch_size].to(self.device)
                logits = self.model(input_ids=batch_ids, attention_mask=batch_mask).logits
                probs = torch.softmax(logits, dim=-1).cpu().tolist()
                for row in probs:
                    window_ents.append(float(row[self.entailment_index]))
                    window_contras.append(float(row[self.contradiction_index]))
        best: dict[int, list[float]] = {}
        for sample, ent, contra in zip(mapping, window_ents, window_contras, strict=True):
            current = best.get(sample)
            if current is None:
                best[sample] = [ent, contra]
            else:
                current[0] = max(current[0], ent)
                current[1] = max(current[1], contra)
        return [(best[index][0], best[index][1]) for index in range(len(premises))]

    def verifier_type(self) -> Literal["nli"]:
        """Identifica el verificador en tiempos y respuestas."""
        return "nli"


def load_verifier(settings: Settings) -> NliVerifier:
    """Carga el modelo NLI una vez al arrancar."""
    return NliVerifier(
        settings.nli_model,
        settings.nli_revision,
        settings.embedding_device,
        settings.model_cache_dir,
        settings.verify_max_windows,
    )
