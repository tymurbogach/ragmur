"""Segmentación en frases sin modelo."""

import pytest

from ragmur.verification.splitter import split_claims


def test_split_claims_basic() -> None:
    assert split_claims("El plazo es 48 horas. El transporte va incluido.", 10, 1000) == [
        "El plazo es 48 horas.",
        "El transporte va incluido.",
    ]


def test_split_claims_rejects_blank_and_limits() -> None:
    with pytest.raises(ValueError):
        split_claims("   ", 10, 1000)
    with pytest.raises(ValueError):
        split_claims("Primera frase. Segunda frase.", 1, 1000)
    with pytest.raises(ValueError):
        split_claims("abc", 10, 2)
    with pytest.raises(ValueError):
        split_claims("", 10, 1000)


def test_split_claims_collapses_whitespace() -> None:
    assert split_claims("Primera  frase.\nSegunda   frase.", 10, 1000) == [
        "Primera frase.",
        "Segunda frase.",
    ]
