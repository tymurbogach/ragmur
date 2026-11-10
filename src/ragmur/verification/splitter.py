"""Segmentación de respuestas en frases, sin modelo de lenguaje.

Aproxima la descomposición en afirmaciones atómicas dividiendo por signos de
puntuación. No resuelve abreviaturas ni correferencias: una referencia como
"este plazo" puede producir un falso `unsupported`. Esa limitación se evalúa
con la frase anterior antes de activar cualquier mitigación.
"""

import re

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[\"'\u201c\u2018\(\[¿¡A-ZÁÉÍÓÚÑ0-9])")


def split_claims(text: str, max_claims: int, max_chars: int) -> list[str]:
    """Divide el texto en frases no vacías con límites explícitos."""
    if not text.strip():
        raise ValueError("Text must not be blank")
    if len(text) > max_chars:
        raise ValueError("Text exceeds the configured limit")
    parts = _SENTENCE_BOUNDARY.split(text.strip())
    claims = [re.sub(r"\s+", " ", part).strip() for part in parts]
    claims = [claim for claim in claims if claim]
    if not claims:
        raise ValueError("Text must contain at least one claim")
    if len(claims) > max_claims:
        raise ValueError("Too many claims")
    return claims
