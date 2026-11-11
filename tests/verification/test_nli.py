"""Verificador NLI con etiquetas leídas de la configuración."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import torch

from ragmur.verification.nli import NliVerifier


def _verifier(monkeypatch: pytest.MonkeyPatch) -> NliVerifier:
    encoding = {
        "input_ids": torch.tensor([[1, 2, 3]]),
        "attention_mask": torch.tensor([[1, 1, 1]]),
        "overflow_to_sample_mapping": torch.tensor([0]),
    }

    def fake_tokenize(*args: object, **kwargs: object) -> dict[str, object]:
        if kwargs.get("add_special_tokens") is False:
            text = args[0]
            assert isinstance(text, str)
            return {"input_ids": [1] * min(len(text.split()), 10)}
        return encoding  # type: ignore[return-value]

    tokenizer = Mock()
    tokenizer.model_max_length = 512
    tokenizer.num_special_tokens_to_add.return_value = 3
    tokenizer.side_effect = fake_tokenize
    model = Mock()
    model.config = SimpleNamespace(
        id2label={0: "contradiction", 1: "entailment", 2: "neutral"},
        max_position_embeddings=512,
    )
    model.return_value = SimpleNamespace(logits=torch.tensor([[0.1, 2.0, 0.1]]))
    monkeypatch.setattr(
        "ragmur.verification.nli.AutoTokenizer.from_pretrained", Mock(return_value=tokenizer)
    )
    monkeypatch.setattr(
        "ragmur.verification.nli.AutoModelForSequenceClassification.from_pretrained",
        Mock(return_value=model),
    )
    verifier = NliVerifier("model", "rev", "cpu", Path("/tmp"))
    verifier.tokenizer = tokenizer
    verifier.model = model
    return verifier


def test_nli_reads_labels_and_scores_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = _verifier(monkeypatch)
    assert verifier.entailment_index == 1 and verifier.contradiction_index == 0
    scores = verifier.score_pairs(["premisa larga"], ["hipótesis"], batch_size=8)
    assert len(scores) == 1
    ent, contra = scores[0]
    assert ent > contra


def test_nli_rejects_blank_and_long_hypothesis(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = _verifier(monkeypatch)
    with pytest.raises(ValueError):
        verifier.check_hypothesis("   ")

    def fake_tokenize(*args: object, **kwargs: object) -> dict[str, object]:
        if kwargs.get("add_special_tokens") is False:
            return {"input_ids": [1] * 600}
        return {
            "input_ids": torch.tensor([[1, 2, 3]]),
            "attention_mask": torch.tensor([[1, 1, 1]]),
            "overflow_to_sample_mapping": torch.tensor([0]),
        }

    verifier.tokenizer.side_effect = fake_tokenize
    with pytest.raises(ValueError):
        verifier.check_hypothesis("hipótesis demasiado larga " * 100)
    with pytest.raises(ValueError):
        verifier.score_pairs(["a", "b"], ["solo una"], batch_size=8)
    assert verifier.score_pairs([], [], batch_size=8) == []


def test_nli_limits_windows_before_model_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    verifier = _verifier(monkeypatch)
    verifier.max_windows = 1
    verifier.max_length = 5
    verifier.tokenizer.side_effect = lambda text, **kwargs: (
        {"input_ids": list(range(10))} if text == "premise" else {"input_ids": [1]}
    )
    with pytest.raises(ValueError, match="Too many verification windows"):
        verifier.score_pairs(["premise"], ["claim"], 8)
    verifier.model.assert_not_called()


def test_long_hypothesis_with_cached_tokenizer(monkeypatch: pytest.MonkeyPatch) -> None:
    from transformers import AutoTokenizer

    path = Path("models/huggingface/hub/models--MoritzLaurer--mDeBERTa-v3-base-xnli-")
    path = (
        path.with_name(path.name + "multilingual-nli-2mil7")
        / "snapshots"
        / ("b5113eb38ab63efdd7f280f8c144ea8b13f978ce")
    )
    if not path.is_dir():
        pytest.skip("Requires the cached NLI tokenizer")
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    verifier = _verifier(monkeypatch)
    verifier.tokenizer = tokenizer
    verifier.model = Mock(
        side_effect=lambda input_ids, attention_mask: SimpleNamespace(
            logits=torch.zeros((len(input_ids), 3))
        )
    )
    hypothesis = "palabra " * 230
    assert len(verifier.tokenizer(hypothesis, add_special_tokens=False)["input_ids"]) == 460
    assert len(verifier.score_pairs(["texto de evidencia " * 100], [hypothesis], 8)) == 1
