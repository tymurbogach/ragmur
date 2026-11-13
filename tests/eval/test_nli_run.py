"""Comprueba la incertidumbre de la tasa de respaldo falso."""

from pathlib import Path

import pytest
from eval.nli_run import validate_cases, wilson_interval


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
    dataset.write_text(
        "- id: case-1\n  document_id: doc-1\n  split: dev\n  premise: source\n"
        "  claims:\n  - text: claim\n    label: supported\n"
    )
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


def test_rejects_document_leak_between_splits() -> None:
    cases = [
        {
            "id": "first",
            "document_id": "same",
            "split": "dev",
            "premise": "source",
            "claims": [{"text": "claim", "label": "supported"}],
        },
        {
            "id": "second",
            "document_id": "same",
            "split": "test",
            "premise": "source",
            "claims": [{"text": "claim", "label": "unsupported"}],
        },
    ]
    with pytest.raises(ValueError, match="both evaluation splits"):
        validate_cases(cases, require_document_id=True)
    with pytest.raises(ValueError, match="both evaluation splits"):
        validate_cases(cases)


def test_strict_mode_rejects_missing_document_id() -> None:
    base = {
        "id": "first",
        "split": "dev",
        "premise": "source",
        "claims": [{"text": "claim", "label": "supported"}],
    }
    with pytest.raises(ValueError, match="document identifier"):
        validate_cases([{**base}], require_document_id=True)
    with pytest.raises(ValueError, match="document identifier"):
        validate_cases([{**base, "document_id": ""}], require_document_id=True)
    with pytest.raises(ValueError, match="document identifier"):
        validate_cases([{**base, "document_id": 123}], require_document_id=True)
    # El id del caso no sustituye al documento: sin document_id no hay
    # comprobación de fuga válida y el registro se rechaza en modo estricto.
    # Impacto: eval/nli_cases.yaml, eval/nli_public_cases.yaml y los YAML
    # generados por eval.inferes / eval.scifact_nli carecen de document_id
    # y solo son válidos en modo heredado, sin afirmar separación por documento.


def test_legacy_mode_accepts_missing_document_id_without_claiming_leak_check() -> None:
    base = {
        "id": "first",
        "split": "dev",
        "premise": "source",
        "claims": [{"text": "claim", "label": "supported"}],
    }
    assert validate_cases([{**base}]) == [{**base}]
    mixed = [
        {**base, "document_id": "doc-1"},
        {
            "id": "second",
            "split": "test",
            "premise": "source",
            "claims": [{"text": "claim", "label": "unsupported"}],
        },
    ]
    assert validate_cases(mixed) == mixed


def test_rejects_invalid_reference_label() -> None:
    cases = [
        {
            "id": "first",
            "document_id": "doc-1",
            "split": "dev",
            "premise": "source",
            "claims": [{"text": "claim", "label": "weak"}],
        }
    ]
    with pytest.raises(ValueError, match="reference label"):
        validate_cases(cases)


def test_reserved_run_does_not_overwrite_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sys

    from eval import nli_run

    output = tmp_path / "reserved.json"
    output.write_text("original")
    monkeypatch.setattr(sys, "argv", ["nli_run", "--split", "test", "--output", str(output)])
    with pytest.raises(ValueError, match="already exists"):
        nli_run.main()
    assert output.read_text() == "original"


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
        "- id: case-1\n  document_id: doc-1\n  split: dev\n  premise: confidential premise\n"
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
    assert rows[0]["split"] == "dev"
    assert rows[0]["verdict"] == "supported"
    assert "confidential" not in details.read_text()
    assert json.loads(summary.read_text())["counts"]["supported"] == 1
