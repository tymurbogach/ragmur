"""Comprueba la incertidumbre de la tasa de respaldo falso."""

from pathlib import Path

import pytest
from eval.nli_run import wilson_interval


def test_wilson_interval_for_no_observed_errors() -> None:
    interval = wilson_interval(0, 6)
    assert interval is not None
    assert interval[0] == pytest.approx(0)
    assert interval[1] == pytest.approx(0.3903, abs=0.0001)


def test_wilson_interval_handles_missing_and_invalid_samples() -> None:
    assert wilson_interval(0, 0) is None
    with pytest.raises(ValueError):
        wilson_interval(2, 1)


def test_public_cases_use_distinct_source_documents() -> None:
    import yaml  # type: ignore[import-untyped]

    cases = yaml.safe_load(Path("eval/nli_public_cases.yaml").read_text())
    assert len({case["id"] for case in cases}) == len(cases)
    assert {case["split"] for case in cases} == {"dev", "test"}
    for case in cases:
        source = Path("eval/corpus") / f"{case['id']}.txt"
        assert case["premise"] == source.read_text().strip()
        assert {claim["label"] for claim in case["claims"]} == {
            "supported",
            "contradicted",
            "unsupported",
        }


def test_empty_partition_fails_before_loading_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from eval import nli_run

    dataset = tmp_path / "cases.yaml"
    dataset.write_text("- split: dev\n")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nli_run",
            "--dataset",
            str(dataset),
            "--split",
            "test",
            "--output",
            str(tmp_path / "result.json"),
        ],
    )
    monkeypatch.setattr(nli_run, "load_verifier", lambda _: pytest.fail("Model must not load"))
    with pytest.raises(ValueError, match="split is empty"):
        nli_run.main()


def test_details_record_scores_without_private_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock

    from eval import nli_run

    dataset = tmp_path / "cases.yaml"
    dataset.write_text(
        "- id: case-1\n  split: dev\n  premise: confidential premise\n"
        "  claims:\n  - text: confidential claim\n    label: supported\n"
    )
    summary = tmp_path / "summary.json"
    details = tmp_path / "per_query" / "details.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "nli_run",
            "--dataset",
            str(dataset),
            "--split",
            "dev",
            "--output",
            str(summary),
            "--details",
            str(details),
        ],
    )
    monkeypatch.setattr(
        nli_run, "load_verifier", lambda _: SimpleNamespace(score_pairs=lambda *_: [(0.9, 0.01)])
    )
    monkeypatch.setattr(
        "eval.nli_run.subprocess.run", Mock(return_value=SimpleNamespace(stdout="a" * 40))
    )
    nli_run.main()
    rows = json.loads(details.read_text())
    assert rows[0]["case_id"] == "case-1"
    assert rows[0]["verdict"] == "supported"
    assert "confidential" not in details.read_text()
    assert json.loads(summary.read_text())["counts"]["supported"] == 1
