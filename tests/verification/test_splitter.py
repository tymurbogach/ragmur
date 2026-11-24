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


def test_split_claims_keeps_citations_with_their_sentence() -> None:
    assert split_claims(
        "El plazo es 48 horas. [1][2] El transporte va incluido. [3]", 10, 1000
    ) == [
        "El plazo es 48 horas. [1][2]",
        "El transporte va incluido. [3]",
    ]
    assert split_claims("Plazo de 48 horas [1, 2]. Transporte incluido.", 10, 1000) == [
        "Plazo de 48 horas [1, 2].",
        "Transporte incluido.",
    ]


def test_split_claims_citation_before_lowercase_does_not_split() -> None:
    assert split_claims("Dato A. [1] y más texto.", 10, 1000) == ["Dato A. [1] y más texto."]


def test_split_claims_abbreviations_do_not_split_but_sentence_ends_do() -> None:
    assert split_claims("La Sra. López y el Prof. Ruiz firmaron. Luego se fueron.", 10, 1000) == [
        "La Sra. López y el Prof. Ruiz firmaron.",
        "Luego se fueron.",
    ]
    assert split_claims("Llegó a las 5. Salió tarde.", 10, 1000) == [
        "Llegó a las 5.",
        "Salió tarde.",
    ]


def test_split_claims_list_markers_stay_with_their_item() -> None:
    assert split_claims("1) Abrir la puerta. 2) Cerrar la ventana.", 10, 1000) == [
        "1) Abrir la puerta.",
        "2) Cerrar la ventana.",
    ]
