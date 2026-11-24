"""Segmentación de respuestas en frases, sin modelo de lenguaje.

Aproxima la descomposición en afirmaciones atómicas dividiendo por signos de
puntuación. Un punto no corta tras una abreviatura conocida ("Dr.", "Sra."),
tras el número de una lista ("1.") ni antes de una cita numérica ("[1]"), que
se queda con su frase. No resuelve correferencias: una referencia como
"este plazo" puede producir un falso `unsupported`. Esa limitación se evalúa
con la frase anterior antes de activar cualquier mitigación.
"""

import re

_OPENER = r"[\"'\u201c\u2018(\[¿¡A-ZÁÉÍÓÚÑ0-9]"
_SENTENCE_BOUNDARY = re.compile(rf"(?<=[.!?])\s+(?={_OPENER})")
_NEXT_SENTENCE = re.compile(rf"\s+(?={_OPENER})")
_CITATION = r"\[\d+(?:\s*[,\u2013-]\s*\d+)*\]"
_CITATIONS = re.compile(rf"{_CITATION}(?:[ \t]*{_CITATION})*")
_LAST_WORD = re.compile(r"(?:^|[\s(\"'\u201c\u2018¿¡])([^\W\d_]+)\.$")
_LIST_MARKER = re.compile(r"\d+[.)]")
_ABBREVIATIONS = frozenset(
    {
        "dr", "dra", "drs", "sr", "sra", "sres", "srta", "prof", "profa", "lic",
        "ing", "arq", "ud", "uds", "vd", "vds", "pág", "págs", "pag", "núm", "num",
        "art", "cap", "fig", "vol", "ej", "aprox", "tel", "avda", "cía", "cia",
        "dpto", "sta", "sto", "mr", "mrs", "ms", "st", "vs",
    }
)  # fmt: skip


def _is_abbreviation(segment: str) -> bool:
    """Indica si el segmento acaba en una abreviatura conocida seguida de punto."""
    match = _LAST_WORD.search(segment)
    return match is not None and match.group(1).lower() in _ABBREVIATIONS


def _split_sentences(text: str) -> list[str]:
    """Corta el texto por los límites de frase que superan las tres reglas."""
    sentences: list[str] = []
    start = 0
    for boundary in _SENTENCE_BOUNDARY.finditer(text):
        if boundary.start() < start:
            continue  # el límite cae dentro de una cita ya absorbida
        segment = text[start : boundary.start()]
        citation = _CITATIONS.match(text, boundary.end())
        if citation is not None:
            cut = citation.end()
            following = _NEXT_SENTENCE.match(text, cut)
            if following is None:
                continue
            sentences.append(text[start:cut])
            start = following.end()
        elif _is_abbreviation(segment) or _LIST_MARKER.fullmatch(segment.strip()):
            continue
        else:
            sentences.append(segment)
            start = boundary.end()
    sentences.append(text[start:])
    return sentences


def split_claims(text: str, max_claims: int, max_chars: int) -> list[str]:
    """Divide el texto en frases no vacías con límites explícitos."""
    if not text.strip():
        raise ValueError("Text must not be blank")
    if len(text) > max_chars:
        raise ValueError("Text exceeds the configured limit")
    parts = _split_sentences(text.strip())
    claims = [re.sub(r"\s+", " ", part).strip() for part in parts]
    claims = [claim for claim in claims if claim]
    if not claims:
        raise ValueError("Text must contain at least one claim")
    if len(claims) > max_claims:
        raise ValueError("Too many claims")
    return claims
