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
