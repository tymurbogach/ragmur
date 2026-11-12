"""Comprueba la selección y la separación de InferES."""

from pathlib import Path

import pytest
from eval.inferes import SAMPLE_PER_LABEL, load_rows, make_cases


def test_rejects_corrupted_source(tmp_path: Path) -> None:
    source = tmp_path / "train.csv"
    source.write_text("corrupted")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_rows(source, "train")


def test_balances_labels_and_rejects_shared_premises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(SAMPLE_PER_LABEL, "train", 1)
    monkeypatch.setitem(SAMPLE_PER_LABEL, "test", 1)

    def row(identifier: str, premise: str, label: str, topic: str) -> dict[str, str]:
        return {
            "ID": identifier,
            "Premise": premise,
            "Hypothesis": "Hypothesis",
            "Label": label,
            "Topic": topic,
            "Anno_Type": "Crowd",
        }

    train = [row("1", "a", "neutral", "1"), row("2", "b", "ent", "1"), row("3", "c", "cnt", "1")]
    test = [row("4", "d", "neutral", "6"), row("5", "e", "ent", "6"), row("6", "f", "cnt", "6")]
    cases = make_cases(train, test)
    assert len(cases) == 6
    assert {str(case["split"]) for case in cases} == {"dev", "test"}
    test[0]["Premise"] = "a"
    with pytest.raises(ValueError, match="premises overlap"):
        make_cases(train, test)
