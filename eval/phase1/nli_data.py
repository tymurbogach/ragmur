"""Selección congelada, distractores, veredicto y métricas NLI (C03).

La cifra principal usa 4.602 pares de ``train.csv`` de InferES (temas 1-5,
premisa e hipótesis no vacías, en el orden del fichero, sin deduplicar) y la
principal filtra ``Anno_Type != "Automated"`` (3.124 pares). Las etiquetas se
traducen con ``LABELS``. Este módulo no importa cargadores de conjuntos: solo
trabaja sobre filas ya leídas, así que el cálculo en el contenedor puede
importarlo sin romper la regla de sitio de cálculo.

Distractores (algoritmo exacto del plan): ``P`` es la lista seleccionada en su
orden (incluye ``Automated``), ``n = len(P) = 4602``, ``id`` es la columna
``ID`` y ``t`` es ``Topic``.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Literal

LABELS: Final[dict[str, str]] = {
    "neutral": "unsupported",
    "ent": "supported",
    "cnt": "contradicted",
}
TOPICS: Final[frozenset[str]] = frozenset({"1", "2", "3", "4", "5"})

EXPECTED_TOTAL: Final[int] = 4602
EXPECTED_PRINCIPAL: Final[int] = 3124

EXPECTED_VECTORS: Final[dict[str, tuple[str, ...]]] = {
    "1968": ("2428", "5511", "4367", "2559"),
    "2148": ("4488", "793", "632", "93"),
}

Verdict = Literal["supported", "weak", "unsupported", "contradicted"]
VERDICTS: Final[tuple[str, ...]] = ("supported", "weak", "unsupported", "contradicted")

EXPECTED_CELLS: Final[dict[int, dict[str, tuple[int, int, int, int]]]] = {
    1: {
        "supported": (678, 188, 409, 68),
        "unsupported": (18, 25, 133, 50),
        "contradicted": (66, 74, 495, 920),
    },
    3: {
        "supported": (649, 185, 360, 149),
        "unsupported": (19, 30, 108, 69),
        "contradicted": (63, 90, 421, 981),
    },
    5: {
        "supported": (627, 193, 334, 189),
        "unsupported": (18, 31, 99, 78),
        "contradicted": (64, 88, 393, 1010),
    },
}
CELL_TOLERANCE: Final[int] = 5

FALSE_SUPPORT_MAX: Final[float] = 0.05
FALSE_SUPPORT_WILSON_MAX: Final[float] = 0.10
SUPPORT_RECALL_MIN: Final[float] = 0.50


@dataclass(frozen=True, slots=True)
class Pair:
    """Un par premisa-hipótesis con su etiqueta humana y su procedencia."""

    id: str
    premise: str
    hypothesis: str
    label: str
    topic: str
    anno: str


def select_pairs(rows: Iterable[Mapping[str, str]]) -> list[Pair]:
    """Aplica la selección congelada: temas 1-5, textos no vacíos, orden dado."""
    selected: list[Pair] = []
    for row in rows:
        topic = str(row.get("Topic", ""))
        if topic not in TOPICS:
            continue
        premise = str(row.get("Premise", ""))
        hypothesis = str(row.get("Hypothesis", ""))
        if not premise.strip() or not hypothesis.strip():
            continue
        raw_label = str(row.get("Label", ""))
        if raw_label not in LABELS:
            raise ValueError(f"etiqueta desconocida: {raw_label!r}")
        selected.append(
            Pair(
                id=str(row.get("ID", "")),
                premise=premise,
                hypothesis=hypothesis,
                label=LABELS[raw_label],
                topic=topic,
                anno=str(row.get("Anno_Type", "")),
            )
        )
    return selected


def principal_only(pairs: list[Pair]) -> list[Pair]:
    """Filtra la cifra principal: todo lo que no sea ``Automated``."""
    return [pair for pair in pairs if pair.anno != "Automated"]


def distractors(ordered: list[Pair], pair: Pair, texts: int = 5) -> list[Pair]:
    """Devuelve ``[p] + elegidos[:textos-1]`` con el algoritmo exacto del plan."""
    if texts < 1:
        raise ValueError("los textos deben ser al menos 1")
    total = len(ordered)
    index = int(hashlib.sha256(pair.id.encode()).hexdigest(), 16) % total
    chosen: list[Pair] = []
    while len(chosen) < 4:
        candidate = ordered[index % total]
        index += 37
        while candidate.topic == pair.topic or candidate.premise in [c.premise for c in chosen]:
            candidate = ordered[index % total]
            index += 1
        chosen.append(candidate)
    return [pair, *chosen[: texts - 1]]


def apply_verdict(
    entailment: float,
    contradiction: float,
    supported: float = 0.75,
    weak: float = 0.5,
    contradiction_threshold: float = 0.75,
    conflict_margin: float = 0.15,
) -> Verdict:
    """Aplica la regla de veredicto de ``/verify`` sobre dos máximos.

    La contradicción sobre su umbral gana, salvo que el apoyo supere su umbral
    y aventaje a la contradicción en el margen de conflicto. Es la misma
    precedencia que la ruta del servicio. El redondeo a nueve decimales evita
    que el ruido de coma flotante decida el empate exacto.
    """
    gap = round(entailment - contradiction, 9)
    support_wins = entailment >= supported and gap >= conflict_margin
    if contradiction >= contradiction_threshold and not support_wins:
        return "contradicted"
    if entailment >= supported:
        return "supported"
    if entailment >= weak:
        return "weak"
    return "unsupported"


def baseline_shape(hypothesis: str) -> Verdict:
    """Línea base trivial solo con la forma de la frase, sin su contenido.

    Usa el número de palabras de la hipótesis: corta, media o larga. Si las
    etiquetas humanas se pudieran adivinar por la longitud, esta línea base
    lo mostraría y la cifra principal quedaría bajo sospecha de fuga.
    """
    words = len(hypothesis.split())
    if words <= 6:
        return "supported"
    if words <= 12:
        return "unsupported"
    return "contradicted"


def wilson(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson al 95 % para una proporción."""
    if trials <= 0:
        return (0.0, 1.0)
    center = (successes + z * z / 2.0) / (trials + z * z)
    half = z * math.sqrt(successes * (trials - successes) / trials + z * z / 4.0) / (trials + z * z)
    return (max(0.0, center - half), min(1.0, center + half))


def confusion(rows: list[dict[str, str]], key: str) -> dict[str, Counter[str]]:
    """Cuenta veredictos por etiqueta humana para una clave de veredicto."""
    matrix: dict[str, Counter[str]] = {
        "supported": Counter(),
        "unsupported": Counter(),
        "contradicted": Counter(),
    }
    for row in rows:
        human = row["y"]
        if human in matrix:
            matrix[human][str(row[key])] += 1
    return matrix


def quality_refs(matrix: dict[str, Counter[str]]) -> dict[str, float]:
    """Referencias diagnósticas sobre la matriz de 1 texto (cifra principal)."""
    n_sup = sum(matrix["supported"].values())
    n_uns = sum(matrix["unsupported"].values())
    n_con = sum(matrix["contradicted"].values())
    false_support_n = matrix["contradicted"]["supported"] + matrix["unsupported"]["supported"]
    false_support_d = n_con + n_uns
    false_support = false_support_n / false_support_d if false_support_d else 0.0
    _, wilson_hi = wilson(false_support_n, false_support_d)
    recall_support = matrix["supported"]["supported"] / n_sup if n_sup else 0.0
    return {
        "false_support": false_support,
        "false_support_wilson_hi": wilson_hi,
        "recall_support": recall_support,
    }


def quality_errors(refs: dict[str, float]) -> list[str]:
    """Traduce las referencias a una lista de incumplimientos (vacía si cumple)."""
    errors: list[str] = []
    if refs["false_support"] > FALSE_SUPPORT_MAX:
        errors.append(f"respaldo falso {refs['false_support']:.3f} supera {FALSE_SUPPORT_MAX:.2f}")
    if refs["false_support_wilson_hi"] > FALSE_SUPPORT_WILSON_MAX:
        errors.append(
            f"Wilson superior {refs['false_support_wilson_hi']:.3f} supera "
            f"{FALSE_SUPPORT_WILSON_MAX:.2f}"
        )
    if refs["recall_support"] < SUPPORT_RECALL_MIN:
        errors.append(f"recall de apoyo {refs['recall_support']:.3f} bajo {SUPPORT_RECALL_MIN:.2f}")
    return errors


def cell_mismatches(
    matrix: dict[str, Counter[str]],
    key: int,
    tolerance: int = CELL_TOLERANCE,
) -> list[str]:
    """Compara cada celda con la esperada (±``tolerance`` casos)."""
    expected = EXPECTED_CELLS[key]
    mismatches: list[str] = []
    for human in ("supported", "unsupported", "contradicted"):
        for verdict, want in zip(VERDICTS, expected[human], strict=True):
            got = matrix[human][verdict]
            if abs(got - want) > tolerance:
                mismatches.append(
                    f"{key} textos {human}/{verdict}: {got} frente a {want} ±{tolerance}"
                )
    return mismatches


__all__ = [
    "CELL_TOLERANCE",
    "EXPECTED_CELLS",
    "EXPECTED_PRINCIPAL",
    "EXPECTED_TOTAL",
    "EXPECTED_VECTORS",
    "FALSE_SUPPORT_MAX",
    "FALSE_SUPPORT_WILSON_MAX",
    "LABELS",
    "SUPPORT_RECALL_MIN",
    "TOPICS",
    "VERDICTS",
    "Pair",
    "Verdict",
    "apply_verdict",
    "baseline_shape",
    "cell_mismatches",
    "confusion",
    "distractors",
    "principal_only",
    "quality_errors",
    "quality_refs",
    "select_pairs",
    "wilson",
]
