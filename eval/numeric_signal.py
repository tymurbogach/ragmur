"""Señal offline de revisión para diferencias numéricas.

Prototipo aislado en ``eval/``: no altera ``src/``, API, veredictos ni
umbrales. Solo biblioteca estándar. Nunca afirma contradicción; como
mucho marca ``needs_review=True`` cuando hay evidencia numérica
comparable y conservadora que justifica atención humana.

Criterio exacto (ver ``comparable_and_incompatible`` y
``numeric_review_signal``): cada mención con dígitos se modela como un
intervalo numérico. Solo se comparan menciones con la misma unidad
normalizada (o la misma granularidad de fecha). Los numerales en
palabras ("cinco", "un millar", "segundo") no se analizan y dan
``unknown``.

- Separadores: "300.000" / "300 000" con espacio fino se normalizan al
  mismo valor (miles, lectura española). Los decimales con coma
  ("20,2 %", "1,5") se interpretan como decimales. Un token con una
  sola coma seguida de exactamente tres cifras ("1,500") es ambiguo
  (miles ingleses frente a decimal español con ceros) y se descarta:
  sin contexto explícito no se afirma ninguna comparación sobre él y
  el resultado es ``unknown``. Varias comas ("1,500,000") sí fijan
  miles sin ambigüedad.
- Escalas ``millón/millones``, ``mil`` y ``billón/billones``
  (billón = 1e12, uso español) se pliegan al valor; la unidad
  restante debe coincidir.
- Cada mención se clasifica como ``exact`` | ``at_least`` |
  ``more_than`` | ``at_most`` | ``less_than`` | ``approx`` por
  marcadores previos ("más de" es estricto, "al menos" es inclusivo;
  "menos de" es estricto, "hasta"/"como máximo" son inclusivos;
  "aproximadamente", "casi", "unos" son aproximados). Ninguna mención
  ``approx`` genera aviso ni respaldo.
- Intervalos: ``exact`` es un punto; ``at_least``/``more_than`` son
  semirrectas inferior inclusiva/exclusiva; ``at_most``/``less_than``
  son semirrectas superior inclusiva/exclusiva. Una cota de la
  afirmación que incluye el intervalo de la premisa es compatible y no
  avisa (p. ej. premisa "hasta 10 euros" frente a "hasta 20 euros"):
  la segunda cota incluye la primera. Solo la disjunción clara de
  intervalos avisa (p. ej. "174 días" frente a "17 días", o un valor
  exacto fuera de una cota).
- Asociación número-entidad: el prototipo no resuelve correferencia
  ni atribuye cifras a entidades. Si la premisa contiene varios
  valores distintos con la misma unidad (p. ej. "10 alumnos de Madrid
  y 20 alumnos de Sevilla"), la coincidencia de cifra y unidad con la
  afirmación ("20 alumnos de Madrid") no verifica la asociación y da
  ``unknown``: mera coincidencia no implica respaldo. Solo un valor
  premise único e incluido en la afirmación da ``match``.
- Fechas: solo se comparan con la misma granularidad
  (año vs año, fecha completa vs fecha completa). Granularidad
  distinta da ``unknown``.

Límites: sin resolución de correferencia, sin equivalencias de
unidades (km vs m, EUR vs USD), sin numerales en palabras, sin
ordinales ("primero/segundo"), sin inferir semántica de
mínimos/subconjuntos más allá de la inclusión de intervalos.
``reason="match"`` indica solo coincidencia numérica, no que la entidad
o el significado coincidan. Las cifras distintas con la misma unidad
pueden referirse a magnitudes diferentes y generar un aviso no pertinente.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

BoundKind = Literal["exact", "at_least", "more_than", "at_most", "less_than", "approx"]

_NBSP = "\u00a0\u202f\u2009"
_WS_CLASS = r" \t\n\r\f\v" + _NBSP

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_SCALE_WORDS = {
    "millon": 1_000_000,
    "millones": 1_000_000,
    "millonés": 1_000_000,
    "mil": 1_000,
    "miles": 1_000,
    "billon": 1_000_000_000_000,
    "billones": 1_000_000_000_000,
}

_UNIT_SYNONYMS = {
    "eur": "eur",
    "euro": "eur",
    "euros": "eur",
    "€": "eur",
    "%": "percent",
    "porciento": "percent",
    "dia": "dia",
    "dias": "dia",
    "días": "dia",
    "día": "dia",
    "ano": "anio",
    "anos": "anio",
    "año": "anio",
    "años": "anio",
    "mes": "mes",
    "meses": "mes",
}

_HEDGE_MORE_THAN = (
    "más de",
    "mas de",
    "superior a",
    "por encima de",
    "supera",
    "superan",
)
_HEDGE_LESS_THAN = (
    "menos de",
    "inferior a",
    "por debajo de",
)
_HEDGE_AT_LEAST = (
    "al menos",
    "como mínimo",
    "mínimo de",
    "minimo de",
    "a partir de",
    "desde",
)
_HEDGE_AT_MOST = (
    "hasta",
    "hasta el",
    "hasta la",
    "como máximo",
    "máximo de",
    "maximo de",
    "como muy tarde",
    "a más tardar",
    "a mas tardar",
    "como máximo de",
    "máximo",
    "maximo",
)
_HEDGE_APPROX = (
    "aproximadamente",
    "aprox",
    "alrededor de",
    "cerca de",
    "unos",
    "unas",
    "casi",
    "en torno a",
)


@dataclass(frozen=True)
class Mention:
    """Mención numérica comparable o fecha."""

    value: float
    unit: str  # unidad normalizada o "date:Y" / "date:YM" / "date:YMD"
    bound: BoundKind
    raw: str
    extra_high: float | None = None  # extremo superior si es rango


@dataclass(frozen=True)
class SignalResult:
    """Resultado conservador de la señal."""

    needs_review: bool
    reason: str  # mismatch | bound_violation | range_disjoint | match | unknown
    detail: str


def _clean_spaces(text: str) -> str:
    for ch in _NBSP:
        text = text.replace(ch, " ")
    return text


def _normalize_number_token(token: str) -> float | None:
    """Interpreta un token con separadores españoles.

    Devuelve ``None`` si el token es ambiguo sin contexto explícito:
    una sola coma seguida de exactamente tres cifras ("1,500") puede
    ser miles ingleses o decimal español con ceros, así que no se
    afirma ninguna comparación sobre él.
    """
    t = token.strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if not t:
        return None
    # Miles con puntos y decimal con coma: 1.234,50 / 1.234.567,89.
    if re.fullmatch(r"\d{1,3}(\.\d{3})+,\d+", t):
        return float(t.replace(".", "").replace(",", "."))
    # Ambiguo: una sola coma con tres cifras ("1,500", "12,345").
    # Varias comas ("1,500,000") sí fijan miles sin ambigüedad.
    if re.fullmatch(r"\d{1,3},\d{3}", t):
        return None
    # Miles con puntos: 300.000 / 1.000.000 (lectura española).
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        return float(t.replace(".", ""))
    # Miles con comas inglesas: 1,500,000 (varias comas, sin ambigüedad).
    if re.fullmatch(r"\d{1,3}(,\d{3}){2,}", t):
        return float(t.replace(",", ""))
    # Decimal con coma española: 20,2 / 1,5 / 1234,567.
    if "," in t and "." not in t:
        parts = t.split(",")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 4 and parts[0].isdigit():
            try:
                return float(parts[0] + "." + parts[1])
            except ValueError:
                return None
        # Varias comas no agrupadas de tres: sin lectura segura.
        return None
    # Decimal con punto o entero.
    try:
        return float(t.replace(",", ""))
    except ValueError:
        return None


_NUMBER_RE = re.compile(
    r"\d{1,3}(?:\.\d{3})+,\d+|\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"|\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?"
)
_FULL_DATE_RE = re.compile(
    r"(\d{1,2})\s+de\s+([A-Za-záéíóúñ]+)\s+de\s+(\d{4})",
)
_YEAR_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
_YEAR_RANGE_RE = re.compile(r"\b(?:entre\s+(\d{4})\s+y\s+(\d{4})|de\s+(\d{4})\s+a\s+(\d{4}))\b")


def _classify_bound(prefix: str) -> BoundKind:
    p = " " + prefix.lower() + " "
    for h in _HEDGE_APPROX:
        if h in p:
            return "approx"
    if re.search(r"\bno\s+super(?:a|an)\s+(?:(?:el|la|los|las)\s+)?$", prefix.lower()):
        return "at_most"
    for h in _HEDGE_MORE_THAN:
        if h in p:
            return "more_than"
    for h in _HEDGE_LESS_THAN:
        if h in p:
            return "less_than"
    for h in _HEDGE_AT_LEAST:
        if h in p:
            return "at_least"
    for h in _HEDGE_AT_MOST:
        if h in p:
            return "at_most"
    return "exact"


def _normalize_unit(raw: str) -> str:
    r = raw.strip().lower().strip(".,;:()[]")
    if r in _UNIT_SYNONYMS:
        return _UNIT_SYNONYMS[r]
    # Quita tildes simples para días/años ya mapeados; resto literal.
    return r


def extract_mentions(text: str) -> list[Mention]:
    """Extrae menciones con dígitos, con unidad y cota locales."""
    cleaned = _clean_spaces(text)
    lowered = cleaned.lower()
    mentions: list[Mention] = []
    year_ranges = list(_YEAR_RANGE_RE.finditer(lowered))
    for match in year_ranges:
        start, end = (
            (match.group(1), match.group(2)) if match.group(1) else (match.group(3), match.group(4))
        )
        assert start is not None and end is not None
        year_lo, year_hi = sorted((int(start), int(end)))
        mentions.append(
            Mention(
                value=float(year_lo),
                unit="date:Y",
                bound="exact",
                raw=match.group(0),
                extra_high=float(year_hi),
            )
        )
    # Fechas completas primero para fijar granularidad día.
    for m in _FULL_DATE_RE.finditer(lowered):
        day, month_name, year = m.group(1), m.group(2), m.group(3)
        month = _MONTHS.get(month_name.lower(), 0)
        if month == 0:
            continue
        prefix = lowered[max(0, m.start() - 40) : m.start()]
        bound = _classify_bound(prefix)
        date_value = float(f"{int(year):04d}{month:02d}{int(day):02d}")
        mentions.append(
            Mention(
                value=date_value,
                unit="date:YMD",
                bound=bound,
                raw=m.group(0),
            )
        )
    # Números con posible unidad y escala.
    for m in _NUMBER_RE.finditer(cleaned):
        token = m.group(0)
        if any(span.start() <= m.start() and m.end() <= span.end() for span in year_ranges):
            continue
        # Evita doble conteo de fechas ya registradas.
        start = m.start()
        context = cleaned[max(0, start - 60) : start]
        if re.search(r"\d+\s+de\s+[A-Za-záéíóúñ]+\s+de\s*$", context):
            continue
        value = _normalize_number_token(token)
        if value is None:
            continue
        rest = cleaned[m.end() : m.end() + 40]
        rest_lower = rest.lower().lstrip(" \u00a0\u202f")
        unit = ""
        scale = 1.0
        percent = False
        if rest_lower.startswith("%"):
            unit = "percent"
            percent = True
        else:
            word = re.match(r"([A-Za-záéíóúñ€%²³]+)", rest_lower)
            word2 = ""
            if word:
                first = word.group(1)
                if first in _SCALE_WORDS:
                    scale = float(_SCALE_WORDS[first])
                    after = rest_lower[word.end() :].lstrip()
                    word_b = re.match(r"([A-Za-záéíóúñ€%²³]+)", after)
                    if word_b:
                        second = word_b.group(1)
                        if second == "%":
                            unit = "percent"
                        elif second in ("de", "del"):
                            after2 = after[word_b.end() :].lstrip()
                            word_c = re.match(r"([A-Za-záéíóúñ€%²³]+)", after2)
                            unit = _normalize_unit(word_c.group(1)) if word_c else ""
                        else:
                            unit = _normalize_unit(second)
                    word2 = first
                elif first in ("de", "del"):
                    unit = ""
                else:
                    unit = _normalize_unit(first)
            # "millones de euros": tras escala + "de" ya resuelto arriba.
            _ = word2
        # Años aislados: 4 dígitos en rango sin unidad -> fecha año.
        if (
            not unit
            and not percent
            and 1000 <= value <= 2100
            and re.fullmatch(r"\d{4}", token.replace(" ", ""))
        ):
            prefix = lowered[max(0, start - 40) : start]
            mentions.append(
                Mention(
                    value=value,
                    unit="date:Y",
                    bound=_classify_bound(prefix),
                    raw=token,
                )
            )
            continue
        if not unit:
            # Sin unidad no comparable de forma segura (evita falsos avisos).
            continue
        scaled = value * scale
        prefix = lowered[max(0, start - 40) : start]
        bound = _classify_bound(prefix)
        mentions.append(Mention(value=scaled, unit=unit, bound=bound, raw=token))
    # Rangos explicitos "entre X y Y" / "de X a Y".
    unit_pat = r"([A-Za-z\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1]+|%)"
    num_pat = r"(\d[\d \u00a0\u202f.,]*)"
    range_re = re.compile(
        r"(?:entre|de)\s+" + num_pat + r"\s+(?:y|a|-)\s+" + num_pat + r"\s*" + unit_pat
    )
    for rm in range_re.finditer(cleaned):
        if any(span.start() == rm.start() and span.end() <= rm.end() for span in year_ranges):
            continue
        lo = _normalize_number_token(rm.group(1))
        hi = _normalize_number_token(rm.group(2))
        if lo is None or hi is None:
            continue
        unit = _normalize_unit(rm.group(3)) if rm.group(3) else ""
        if not unit:
            continue
        if lo > hi:
            lo, hi = hi, lo
        prefix = lowered[max(0, rm.start() - 40) : rm.start()]
        mentions.append(
            Mention(
                value=lo,
                unit=unit,
                bound=_classify_bound(prefix),
                raw=rm.group(0),
                extra_high=hi,
            )
        )
    return mentions


def _same_unit(a: str, b: str) -> bool:
    return a == b and a != ""


# Intervalo (extremo, inclusivo): (-inf, False) y (+inf, False) abiertos.
_Interval = tuple[float, bool, float, bool]


def _interval(m: Mention) -> _Interval | None:
    """Modela la mención como intervalo; ``None`` si no comparable."""
    if m.bound == "approx":
        return None
    if m.extra_high is not None:
        if m.bound != "exact":
            # Rango acotado por hedges: sin lectura segura.
            return None
        return (m.value, True, m.extra_high, True)
    if m.bound == "exact":
        return (m.value, True, m.value, True)
    if m.bound == "at_least":
        return (m.value, True, math.inf, False)
    if m.bound == "more_than":
        return (m.value, False, math.inf, False)
    if m.bound == "at_most":
        return (-math.inf, False, m.value, True)
    # less_than
    return (-math.inf, False, m.value, False)


def _disjoint(a: _Interval, b: _Interval) -> bool:
    """True si los intervalos no comparten ningún punto."""
    a_lo, a_lo_inc, a_hi, a_hi_inc = a
    b_lo, b_lo_inc, b_hi, b_hi_inc = b
    if a_hi < b_lo or b_hi < a_lo:
        return True
    touch_high = a_hi == b_lo and math.isfinite(a_hi) and not (a_hi_inc and b_lo_inc)
    touch_low = b_hi == a_lo and math.isfinite(b_hi) and not (b_hi_inc and a_lo_inc)
    return touch_high or touch_low


def _covers(premise: _Interval, claim: _Interval) -> bool:
    """True si el intervalo de la premisa está incluido en el de la afirmación."""
    p_lo, p_lo_inc, p_hi, p_hi_inc = premise
    c_lo, c_lo_inc, c_hi, c_hi_inc = claim
    lo_ok = c_lo < p_lo or (c_lo == p_lo and (c_lo_inc or not p_lo_inc or not math.isfinite(c_lo)))
    hi_ok = c_hi > p_hi or (c_hi == p_hi and (c_hi_inc or not p_hi_inc or not math.isfinite(c_hi)))
    return lo_ok and hi_ok


def comparable_and_incompatible(premise: Mention, claim: Mention) -> bool:
    """True solo ante incompatibilidad numérica segura y comparable."""
    if not _same_unit(premise.unit, claim.unit):
        return False
    p_interval = _interval(premise)
    c_interval = _interval(claim)
    if p_interval is None or c_interval is None:
        return False
    return _disjoint(p_interval, c_interval)


def _compatible_match(premise: Mention, claim: Mention) -> bool:
    if not _same_unit(premise.unit, claim.unit):
        return False
    p_interval = _interval(premise)
    c_interval = _interval(claim)
    if p_interval is None or c_interval is None:
        return False
    return not _disjoint(p_interval, c_interval)


def numeric_review_signal(premise: str, claim: str) -> SignalResult:
    """Señal conservadora: nunca afirma contradicción.

    Se marca revisión cuando un número de la afirmación es disjunto de
    todos sus candidatos con la misma unidad. ``reason="match"`` indica
    al menos una coincidencia numérica única; no verifica las demás
    menciones, las entidades ni el significado. Con varios valores
    candidatos distintos no se atribuye la cifra a una entidad.
    ``"unknown"`` indica que no hay base numérica comparable.
    """
    premise_mentions = extract_mentions(premise)
    claim_mentions = extract_mentions(claim)
    if not premise_mentions or not claim_mentions:
        return SignalResult(False, "unknown", "sin menciones comparables con dígitos")
    any_comparable = False
    any_match = False
    for c in claim_mentions:
        if _interval(c) is None:
            continue
        candidates = [
            p for p in premise_mentions if _same_unit(p.unit, c.unit) and _interval(p) is not None
        ]
        if not candidates:
            continue
        any_comparable = True
        c_interval = _interval(c)
        assert c_interval is not None
        if all(comparable_and_incompatible(p, c) for p in candidates):
            bad = next(p for p in candidates if comparable_and_incompatible(p, c))
            bad_interval = _interval(bad)
            assert bad_interval is not None
            reason = (
                "mismatch"
                if bad.bound == "exact"
                and c.bound == "exact"
                and bad.extra_high is None
                and c.extra_high is None
                else "bound_violation"
                if bad.extra_high is None and c.extra_high is None
                else "range_disjoint"
            )
            return SignalResult(
                True,
                reason,
                f"valores numéricos diferentes en unidad {c.unit}: "
                f"afirmación {c.raw!r} ({c.bound}), premisa {bad.raw!r} "
                f"({bad.bound}); no se ha verificado si describen la misma magnitud",
            )
        # Solape con al menos un candidato: respaldo solo si el valor de
        # premisa es único (asociación determinable) y queda incluido.
        keys = {(p.value, p.extra_high) for p in candidates}
        if len(keys) == 1:
            only = _interval(candidates[0])
            assert only is not None
            if _covers(only, c_interval):
                any_match = True
    if any_comparable:
        if any_match:
            return SignalResult(
                False, "match", "coincidencia numérica; entidad y significado no verificados"
            )
        return SignalResult(
            False,
            "unknown",
            "dígitos sin equivalencia segura: la coincidencia de cifra y "
            "unidad no verifica la asociación número-entidad",
        )
    return SignalResult(False, "unknown", "sin unidad común entre dígitos")
