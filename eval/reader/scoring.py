"""Puntuación del lector: normalización, extracción y métricas, sin red ni modelos.

Todo este módulo es determinista y puro: la respuesta correcta sale del
dataset o de la construcción del caso, nunca del LLM (ver DECISIONS.md 3.34).
"""

from __future__ import annotations

import json
import random
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from eval.nli_run import wilson_interval

# Artículos que la normalización española elimina como tokens completos.
ARTICLES = frozenset({"el", "la", "los", "las", "un", "una", "unos", "unas", "lo"})

NO_CONSTA = "NO CONSTA"

Outcome = Literal["correct", "wrong", "abstained", "parse_error", "provider_error"]
CounterfactualOutcome = Literal["reads_context", "uses_memory", "both", "other"]


class ParseError(ValueError):
    """La salida del lector no trae un JSON válido con el esquema esperado."""


def normalize_es(text: str) -> str:
    """Normaliza español para comparar: minúsculas, sin tildes ni puntuación.

    Pasa a minúsculas, descompone Unicode (NFKD) y quita las marcas de
    combinación (tildes, diéresis, virgulilla de la eñe), elimina la
    puntuación (todo lo que no sea palabra ni espacio, incluido `_`),
    quita los artículos `el la los las un una unos unas lo`
    como tokens completos y colapsa los espacios. `\\w` conserva letras
    Unicode (`ł`, `ø`), que la clase ASCII anterior borraba.
    """
    lowered = text.lower()
    decomposed = unicodedata.normalize("NFKD", lowered)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    cleaned = re.sub(r"[^\w\s]|_", "", without_marks)
    return " ".join(token for token in cleaned.split() if token not in ARTICLES)


def contains_span(haystack_norm: str, needle_norm: str) -> bool:
    """Contención de tramo con límites de palabra sobre texto normalizado.

    Equivale a `f" {needle} " in f" {haystack} "` sobre texto ya normalizado:
    evita que `308` coincida en `3080` o que `10` coincida en `2010`.
    """
    if not needle_norm:
        return False
    if not haystack_norm:
        return False
    return f" {needle_norm} " in f" {haystack_norm} "


def answer_kind(text: str) -> str:
    """Clase del oro para el sustituto contrafactual: numérica, propia o común.

    `numeric` si el oro normalizado contiene un dígito; si no, `proper` si
    cada palabra del oro original empieza por mayúscula; si no, `common`.
    """
    normalized = normalize_es(text)
    if any(char.isdigit() for char in normalized):
        return "numeric"
    words = text.split()
    if words and all(word and word[0].isupper() for word in words):
        return "proper"
    return "common"


def golds_kind(golds: list[str] | tuple[str, ...]) -> str:
    """Clase representativa de una lista de oros: la del primer oro no vacío."""
    for gold in golds:
        if normalize_es(gold):
            return answer_kind(gold)
    return "common"


def exact_match(prediction: str, golds: list[str] | tuple[str, ...]) -> bool:
    """EM: igualdad normalizada con alguna respuesta del dataset."""
    normalized = normalize_es(prediction)
    return any(normalized == normalize_es(gold) for gold in golds if normalize_es(gold))


def contains_match(prediction: str, golds: list[str] | tuple[str, ...]) -> bool:
    """Métrica secundaria laxa: el oro cabe como tramo en la respuesta.

    Verdadera cuando la respuesta no es abstención, algún oro normalizado
    está contenido como tramo de palabra (`contains_span`) en la respuesta
    normalizada y la respuesta no es demasiado larga: como mucho
    `min(max_gold_tokens + 3, 2 * max_gold_tokens)` tokens, donde
    `max_gold_tokens` es el oro normalizado más largo. EM sigue primaria.
    """
    normalized = normalize_es(prediction)
    if not normalized:
        return False
    golds_norm = [normalize_es(gold) for gold in golds]
    golds_norm = [gold for gold in golds_norm if gold]
    if not golds_norm:
        return False
    max_gold_tokens = max(len(gold.split()) for gold in golds_norm)
    cap = min(max_gold_tokens + 3, 2 * max_gold_tokens)
    if len(normalized.split()) > cap:
        return False
    return any(contains_span(normalized, gold) for gold in golds_norm)


def token_f1(prediction: str, golds: list[str] | tuple[str, ...]) -> float:
    """F1 de tokens (estilo SQuAD): máximo sobre las respuestas del dataset."""
    predicted_tokens = normalize_es(prediction).split()
    best = 0.0
    for gold in golds:
        gold_tokens = normalize_es(gold).split()
        if not predicted_tokens and not gold_tokens:
            return 1.0
        if not predicted_tokens or not gold_tokens:
            continue
        overlap = sum((Counter(predicted_tokens) & Counter(gold_tokens)).values())
        if overlap == 0:
            continue
        precision = overlap / len(predicted_tokens)
        recall = overlap / len(gold_tokens)
        best = max(best, 2 * precision * recall / (precision + recall))
    return best


def extract_json_object(text: str) -> dict[str, Any]:
    """Extrae el primer objeto JSON, tolerando vallas de código y basura.

    Quita los marcadores de valla (``` y ```json) y prueba cada `{` como
    inicio hasta que uno analice como objeto. Si ninguno lo hace, falla con
    `ParseError`: nunca se devuelve un error silencioso ni se cuenta como
    acierto.
    """
    cleaned = re.sub(r"```(?:json)?", "", text)
    position = cleaned.find("{")
    decoder = json.JSONDecoder()
    while position != -1:
        try:
            value, _ = decoder.raw_decode(cleaned[position:])
        except json.JSONDecodeError:
            position = cleaned.find("{", position + 1)
            continue
        if isinstance(value, dict):
            return value
        position = cleaned.find("{", position + 1)
    raise ParseError("No JSON object found in reader output")


@dataclass(frozen=True, slots=True)
class ParsedAnswer:
    """Respuesta analizada del lector: texto, citas declaradas y hallazgo."""

    answer: str
    citations: tuple[str, ...]
    found: bool


def _coerce_citations(raw: object) -> tuple[str, ...]:
    """Convierte la lista de citas a cadenas, descartando lo no convertible."""
    if not isinstance(raw, list):
        raise ParseError("Reader JSON field 'citations' must be a list of strings")
    coerced: list[str] = []
    for item in raw:
        if isinstance(item, str):
            if item.strip():
                coerced.append(item)
        elif isinstance(item, (int, float)) and not isinstance(item, bool):
            coerced.append(str(item))
        # Cualquier otro tipo (dict, list, None, bool) se descarta.
    return tuple(coerced)


def _coerce_found(raw: object) -> bool:
    """Acepta booleanos y las cadenas `true`/`false` (cualquier caja)."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    raise ParseError("Reader JSON field 'found' must be a boolean")


def parse_reader_output(text: str) -> ParsedAnswer:
    """Analiza la salida del lector al esquema `answer/citations/found`."""
    parsed = extract_json_object(text)
    try:
        answer = parsed["answer"]
        citations = parsed["citations"]
        found = parsed["found"]
    except KeyError as exc:
        raise ParseError(f"Missing key in reader JSON: {exc}") from exc
    if not isinstance(answer, str):
        raise ParseError("Reader JSON field 'answer' must be a string")
    return ParsedAnswer(
        answer=answer, citations=_coerce_citations(citations), found=_coerce_found(found)
    )


def is_abstention(answer: str, found: bool) -> bool:
    """Abstención: `found` falso o respuesta `NO CONSTA` en cualquier forma."""
    if not found:
        return True
    return answer.strip().upper() == NO_CONSTA or normalize_es(answer) == "no consta"


def valid_citations(
    citations: list[str] | tuple[str, ...],
    context_ids: set[str],
    context_texts: dict[str, str],
    golds: list[str] | tuple[str, ...],
) -> list[str]:
    """Citas válidas: `chunk_id` enviado cuyo fragmento contiene una respuesta.

    El `chunk_id` debe estar en el contexto enviado y el texto normalizado
    del fragmento debe contener alguna respuesta normalizada como tramo de
    palabra (`contains_span`).
    """
    golds_normalized = [normalize_es(gold) for gold in golds]
    golds_normalized = [gold for gold in golds_normalized if gold]
    valid: list[str] = []
    for citation in citations:
        if citation not in context_ids or citation in valid:
            continue
        fragment = normalize_es(context_texts.get(citation, ""))
        if any(contains_span(fragment, gold) for gold in golds_normalized):
            valid.append(citation)
    return valid


def retrieval_hit(
    fragments: list[str] | tuple[str, ...], golds: list[str] | tuple[str, ...]
) -> bool:
    """Acierto de recuperación: alguna respuesta está en los fragmentos."""
    golds_normalized = [gold for gold in (normalize_es(gold) for gold in golds) if gold]
    normalized_fragments = [normalize_es(fragment) for fragment in fragments]
    return any(
        contains_span(fragment, gold)
        for gold in golds_normalized
        for fragment in normalized_fragments
    )


def classify_outcome(*, em: bool, abstained: bool) -> Outcome:
    """Clasifica el caso: acierto, fallo o abstención (errores, aparte)."""
    if abstained:
        return "abstained"
    return "correct" if em else "wrong"


# Sustitución contrafactual: cada letra admite sus variantes con tilde para
# localizar la respuesta original en el texto sin normalizar (insensible a
# mayúsculas y tildes). `re.IGNORECASE` cubre las mayúsculas.
_ACCENT_VARIANTS = {
    "a": "aáàäâ",
    "e": "eéèëê",
    "i": "iíìïî",
    "n": "nñ",
    "o": "oóòöô",
    "u": "uúùüû",
}


def _base_letter(char: str) -> str:
    """Letra base sin tilde para construir la clase de equivalencia."""
    decomposed = unicodedata.normalize("NFKD", char.casefold())
    return decomposed[0] if decomposed else char


def _pattern_char(char: str) -> str:
    """Clase de equivalencia de un carácter para la búsqueda insensible."""
    if char.isdigit() or char.isspace():
        return re.escape(char)
    if char.isalnum():
        base = _base_letter(char)
        if base in _ACCENT_VARIANTS:
            return f"[{_ACCENT_VARIANTS[base]}]"
        return re.escape(char)
    # Puntuación del original: se busca literal (los límites los pone el
    # llamante con `(?<!\\w)` / `(?!\\w)`).
    return re.escape(char)


def substitute_answers(text: str, replacements: list[tuple[str, str]]) -> str:
    """Sustituye cada respuesta por el sustituto, insensible a caja y tildes.

    La coincidencia más larga va primero para no partir respuestas que
    contienen a otras. Los límites `(?<!\\w)` y `(?!\\w)` exigen palabra
    completa sobre el texto original: `308` no toca `3080` ni `10` a `2010`.
    El sustituto se inserta literal (sin interpretar escapes de la regex).
    """
    for original, substitute in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        if not original.strip():
            continue
        pattern = "".join(_pattern_char(char) for char in original)
        bounded = rf"(?<!\w){pattern}(?!\w)"
        text = _replace_literal(text, bounded, substitute)
    return text


def _replace_literal(text: str, pattern: str, substitute: str) -> str:
    """Sustituye por el literal sin interpretar escapes de la sustitución regex."""

    def replace(_match: re.Match[str]) -> str:
        return substitute

    return re.sub(pattern, replace, text, flags=re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CounterfactualFragments:
    """Fragmentos contrafactuales y resultado de la guarda."""

    fragments: tuple[str, ...]
    discarded: bool
    reason: str


def build_counterfactual_fragments(
    fragments: list[str] | tuple[str, ...],
    golds: list[str] | tuple[str, ...],
    substitute: str,
) -> CounterfactualFragments:
    """Reemplaza las respuestas por el sustituto y aplica la guarda.

    La guarda descarta el caso (sin llamar al modelo) si el sustituto ya
    estaba en los fragmentos originales o si el original normalizado sigue
    apareciendo tras la sustitución. La contención es siempre de tramo
    (`contains_span`): `308` no cuenta en `3080`. El motivo queda registrado.
    """
    originals = {normalize_es(gold) for gold in golds}
    originals.discard("")
    normalized_substitute = normalize_es(substitute)
    if not normalized_substitute:
        return CounterfactualFragments(tuple(fragments), True, "empty substitute")
    if normalized_substitute in originals:
        return CounterfactualFragments(tuple(fragments), True, "substitute equals original")
    normalized_originals = [normalize_es(fragment) for fragment in fragments]
    if any(contains_span(fragment, normalized_substitute) for fragment in normalized_originals):
        return CounterfactualFragments(tuple(fragments), True, "substitute already present")
    replacements = [(gold, substitute) for gold in golds if gold.strip()]
    replaced = tuple(substitute_answers(fragment, replacements) for fragment in fragments)
    normalized_replaced = [normalize_es(fragment) for fragment in replaced]
    if any(
        contains_span(fragment, original)
        for original in originals
        for fragment in normalized_replaced
    ):
        return CounterfactualFragments(tuple(fragments), True, "original remains")
    return CounterfactualFragments(replaced, False, "ok")


def choose_substitute(
    golds: list[str] | tuple[str, ...],
    candidates: list[str] | tuple[str, ...],
    rng: random.Random,
) -> str | None:
    """Elige el sustituto: respuesta de otra pregunta, distinta al normalizar.

    Solo valen candidatas de la misma clase (`answer_kind`): numérica,
    propia o común. `candidates` trae las respuestas de las demás preguntas;
    se eliminan duplicados y las iguales al original normalizado. Sin
    candidata válida devuelve `None` (el caso se descarta; si hay candidatas
    de otra clase, el motivo es `type mismatch`).
    """
    own = {normalize_es(gold) for gold in golds}
    targets = {answer_kind(gold) for gold in golds if normalize_es(gold)}
    pool = [
        candidate
        for candidate in dict.fromkeys(candidates)
        if candidate.strip()
        and normalize_es(candidate) not in own
        and answer_kind(candidate) in targets
    ]
    if not pool:
        return None
    return rng.choice(sorted(pool))


def substitute_discard_reason(
    golds: list[str] | tuple[str, ...],
    candidates: list[str] | tuple[str, ...],
) -> str:
    """Motivo de descarte cuando no hay sustituto: clase u oferta.

    `type mismatch` si hay candidatas distintas al normalizar pero ninguna de
    la misma clase; `no substitute` si no hay ninguna candidata distinta.
    """
    own = {normalize_es(gold) for gold in golds}
    distinct = [
        candidate
        for candidate in dict.fromkeys(candidates)
        if candidate.strip() and normalize_es(candidate) not in own
    ]
    if not distinct:
        return "no substitute"
    return "type mismatch"


def classify_counterfactual(
    prediction: str, golds: list[str] | tuple[str, ...], substitute: str
) -> CounterfactualOutcome:
    """El lector lee (sustituto), tira de memoria (original), ambos u otro.

    Sobre respuestas normalizadas: `reads_context` si el sustituto está
    contenido como tramo y el original no, con tope de longitud laxo (el de
    `contains_match` calculado sobre el sustituto); `uses_memory` si el
    original está contenido y el sustituto no (sin tope); `both` si ambos
    están contenidos; `other` en el resto (incluido un sustituto contenido
    pero demasiado verborreico).
    """
    normalized = normalize_es(prediction)
    originals = [normalize_es(gold) for gold in golds]
    originals = [gold for gold in originals if gold]
    normalized_substitute = normalize_es(substitute)
    original_contained = any(contains_span(normalized, gold) for gold in originals)
    substitute_contained = bool(normalized_substitute) and contains_span(
        normalized, normalized_substitute
    )
    if substitute_contained and original_contained:
        return "both"
    if original_contained:
        return "uses_memory"
    if substitute_contained:
        sub_tokens = len(normalized_substitute.split())
        cap = min(sub_tokens + 3, 2 * sub_tokens) if sub_tokens else 0
        if len(normalized.split()) <= cap:
            return "reads_context"
        return "other"
    return "other"


def proportion(successes: int, total: int) -> dict[str, Any]:
    """Tasa con intervalo de Wilson al 95 % (reutilizado de `eval.nli_run`)."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Invalid counts")
    rate = successes / total if total else 0.0
    interval = wilson_interval(successes, total)
    return {
        "successes": successes,
        "total": total,
        "rate": rate,
        "wilson_95": list(interval) if interval is not None else None,
    }
