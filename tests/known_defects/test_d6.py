"""D6: el divisor de frases respeta abreviaturas, citas y listas."""

import pytest

from ragmur.verification.splitter import split_claims


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="D6: divisor rompe Dr., aísla [1] y junta listas"
)
def test_d6_sentence_splitter_abbreviations_citations_lists() -> None:
    """Dr. no parte, [1] va con su frase y las listas no se mezclan."""
    claims = split_claims("El Dr. García llegó tarde. El informe quedó listo.", 10, 500)
    assert claims == ["El Dr. García llegó tarde.", "El informe quedó listo."], (
        f"D6: rompe Dr.: {claims}"
    )
    claims = split_claims("El plazo es 48 horas. [1] El transporte va incluido.", 10, 500)
    assert claims[0].endswith("[1]"), f"D6: aísla [1]: {claims}"
    claims = split_claims("1. Abrir la puerta. 2. Cerrar la ventana.", 10, 500)
    assert claims == ["1. Abrir la puerta.", "2. Cerrar la ventana."], f"D6: junta listas: {claims}"
