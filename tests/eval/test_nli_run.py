"""Comprueba la incertidumbre de la tasa de respaldo falso."""

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
    from pathlib import Path

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
