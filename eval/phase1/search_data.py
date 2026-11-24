"""Seleccion congelada, metricas y fugas para la etapa search C04.

La etapa mide si el buscador encuentra el texto correcto entre miles de
documentos, y demuestra que no mezcla clientes (aislamiento). No usa ningun
LLM: solo los modelos de recuperacion del servicio (embeddings, BM25 y
reordenador, que en ingles se llama reranker).

Vocabulario usado aqui:

- ``recall@k``: fraccion de preguntas donde lo esperado aparece entre los k
  primeros resultados. Se mide a nivel de documento (el texto correcto) y a
  nivel de fragmento con respuesta (el trozo que contiene la respuesta).
- ``MRR@10`` (rango reciproco medio): media de 1/posicion del primer acierto
  entre los 10 primeros; 0 si no hay acierto. Premia que el acierto salga
  arriba, no solo que aparezca.
- ``cobertura@30``: fraccion donde el documento llega a los 30 candidatos que
  ve el reordenador. Si ni llega, el reordenador no puede rescatarlo.
- ``tenant``: espacio de una aplicacion cliente. ``owner_id``: subespacio de
  un usuario final dentro de ese tenant.

Seleccion congelada (no se cambia sin datos nuevos): parrafos XQuAD (240 de
practica dev mas reserva solo como ruido) y textos SQAC (4.986) suman 5.226
documentos; preguntas XQuAD dev (908) mas SQAC (15.036) suman 15.944 casos.
Ninguna pregunta se descarta en silencio: si su respuesta no cae en ningun
fragmento, se puntua igual y se cuenta como no cubierta.

Este modulo es puro: no importa cargadores de conjuntos ni el servicio, asi
que el calculo dentro del contenedor puede importarlo.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from typing import Any, Final, Literal

from eval.phase1.nli_data import wilson

EXPECTED_DOCS: Final[int] = 5226
EXPECTED_XQUAD_CASES: Final[int] = 908
EXPECTED_SQAC_CASES: Final[int] = 15036
EXPECTED_CASES: Final[int] = 15944
EXPECTED_CHUNKS: Final[int] = 11778
CHUNK_SIZE: Final[int] = 800
CHUNK_OVERLAP: Final[int] = 120
CANDIDATES: Final[int] = 30
RRF_K: Final[int] = 2
TOP_K: Final[int] = 10
PROGRESS_EVERY: Final[int] = 500
RECALL_AT: Final[tuple[int, ...]] = (1, 5, 10)
OWNERS: Final[tuple[str, str]] = ("alice", "bob")

Stage = Literal["dense", "sparse", "hybrid", "rerank"]
STAGES_4: Final[tuple[str, ...]] = ("dense", "sparse", "hybrid", "rerank")
SetName = Literal["all", "xquad", "sqac"]
SETS: Final[tuple[str, ...]] = ("all", "xquad", "sqac")


def normalize(text: str) -> str:
    """Normaliza saltos de linea igual que el troceador del servicio."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def owner_for(key: str) -> str:
    """Duenyo determinista de un documento, mitad y mitad."""
    return OWNERS[hashlib.sha256(key.encode()).digest()[0] % 2]


@dataclass(frozen=True, slots=True)
class Doc:
    """Un documento indexable: clave estable y texto."""

    key: str
    text: str

    def to_dict(self) -> dict[str, str]:
        """Convierte a JSON."""
        return {"key": self.key, "text": self.text}

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> Doc:
        """Reconstruye desde JSON."""
        return Doc(key=str(payload["key"]), text=str(payload["text"]))


@dataclass(frozen=True, slots=True)
class Case:
    """Una pregunta con su documento esperado y sus respuestas localizadas."""

    id: str
    src: str
    question: str
    doc: str
    answers: tuple[tuple[int, int, str], ...]

    def to_dict(self) -> dict[str, Any]:
        """Convierte a JSON."""
        return {
            "id": self.id,
            "src": self.src,
            "q": self.question,
            "doc": self.doc,
            "ans": [[start, end, text] for start, end, text in self.answers],
        }

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> Case:
        """Reconstruye desde JSON."""
        answers = tuple((int(item[0]), int(item[1]), str(item[2])) for item in payload["ans"])
        return Case(
            id=str(payload["id"]),
            src=str(payload["src"]),
            question=str(payload["q"]),
            doc=str(payload["doc"]),
            answers=answers,
        )


def resolve_answers(context: str, answers: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """Localiza cada respuesta sobre el texto normalizado.

    Si el desplazamiento publicado no coincide, se busca el texto. Lo que no
    se encuentra se cuenta fuera: nunca se inventa un desplazamiento.
    """
    text = normalize(context)
    resolved: list[tuple[int, int, str]] = []
    missed = 0
    for start, answer in answers:
        if text[start : start + len(answer)] != answer:
            found = text.find(answer)
            if found < 0:
                missed += 1
                continue
            start = found
        resolved.append((start, start + len(answer), answer))
    return resolved


def build_selection(
    xquad_data: dict[str, Any], sqac_data: dict[str, Any], dev_ids: set[str]
) -> tuple[list[Doc], list[Case], dict[str, int]]:
    """Construye la seleccion congelada solo con datos de practica.

    XQuAD aporta todos sus parrafos (los de reserva solo como ruido) y sus
    preguntas dev; SQAC aporta todos sus textos y preguntas. Devuelve
    documentos, casos y contadores de respuestas no localizadas.
    """
    docs: list[Doc] = []
    cases: list[Case] = []
    stats = Counter({"xquad_docs": 0, "sqac_docs": 0, "answers_missed": 0, "cases_empty": 0})
    for article in xquad_data.get("data", []):
        title = article["title"]
        for index, paragraph in enumerate(article["paragraphs"]):
            key = f"xquad-es:{title}:{index}"
            docs.append(Doc(key=key, text=paragraph["context"]))
            stats["xquad_docs"] += 1
            for qa in paragraph["qas"]:
                if qa["id"] not in dev_ids:
                    continue
                raw = [(item["answer_start"], item["text"]) for item in qa["answers"]]
                resolved = resolve_answers(paragraph["context"], raw)
                stats["answers_missed"] += len(raw) - len(resolved)
                if not resolved:
                    stats["cases_empty"] += 1
                cases.append(
                    Case(
                        id=f"xquad:{qa['id']}",
                        src="xquad",
                        question=qa["question"],
                        doc=key,
                        answers=tuple(resolved),
                    )
                )
    number = 0
    for article in sqac_data.get("data", []):
        for paragraph in article["paragraphs"]:
            key = f"sqac:{number}"
            number += 1
            docs.append(Doc(key=key, text=paragraph["context"]))
            stats["sqac_docs"] += 1
            for qa in paragraph["qas"]:
                raw = [(item["answer_start"], item["text"]) for item in qa["answers"]]
                resolved = resolve_answers(paragraph["context"], raw)
                stats["answers_missed"] += len(raw) - len(resolved)
                if not resolved:
                    stats["cases_empty"] += 1
                cases.append(
                    Case(
                        id=f"sqac:{qa['id']}",
                        src="sqac",
                        question=qa["question"],
                        doc=key,
                        answers=tuple(resolved),
                    )
                )
    return docs, cases, dict(stats)


def check_selection(docs: list[Doc], cases: list[Case]) -> list[str]:
    """Comprueba las cifras congeladas de la seleccion."""
    errors: list[str] = []
    if len(docs) != EXPECTED_DOCS:
        errors.append(f"{len(docs)} documentos frente a {EXPECTED_DOCS}")
    by_src = Counter(case.src for case in cases)
    if by_src.get("xquad", 0) != EXPECTED_XQUAD_CASES:
        errors.append(f"xquad {by_src.get('xquad', 0)} frente a {EXPECTED_XQUAD_CASES}")
    if by_src.get("sqac", 0) != EXPECTED_SQAC_CASES:
        errors.append(f"sqac {by_src.get('sqac', 0)} frente a {EXPECTED_SQAC_CASES}")
    if len({case.id for case in cases}) != len(cases):
        errors.append("identificadores de caso duplicados")
    known = {doc.key for doc in docs}
    if any(case.doc not in known for case in cases):
        errors.append("caso que apunta a un documento ausente")
    return errors


def hit_at(rank: int | None, k: int) -> bool:
    """Dice si un rango cae dentro de los k primeros."""
    return rank is not None and rank <= k


def percentile(sorted_values: list[float], fraction: float) -> float:
    """Percentil por rango mas cercano sobre valores ya ordenados."""
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, int(fraction * len(sorted_values)))
    return sorted_values[index]


def mrr_at_10(ranks: list[int | None]) -> float:
    """Rango reciproco medio con corte en 10."""
    if not ranks:
        return 0.0
    return sum(1.0 / rank for rank in ranks if rank is not None and rank <= 10) / len(ranks)


def recall(rows: list[dict[str, Any]], field: str, k: int) -> float:
    """Fraccion de filas con acierto en el campo hasta k."""
    if not rows:
        return 0.0
    return sum(1 for row in rows if hit_at(row.get(field), k)) / len(rows)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Resume metricas por etapa y conjunto, mas latencia.

    El documento se puntua sobre todos los casos; el fragmento con respuesta
    solo sobre los cubiertos (si la respuesta no cae en ningun fragmento, el
    caso no es recuperable a ese nivel y se cuenta aparte).
    """
    covered = [row for row in rows if row.get("covered")]
    latencies = sorted(float(row["ms"]) for row in rows)
    summary: dict[str, Any] = {
        "n_cases": len(rows),
        "n_covered": len(covered),
        "n_uncovered": len(rows) - len(covered),
        "latency_ms": {
            "p50": round(percentile(latencies, 0.5), 1),
            "p95": round(percentile(latencies, 0.95), 1),
        },
        "stages": {},
    }
    for stage in STAGES_4:
        doc_field = f"{stage[0]}_doc"
        ans_field = f"{stage[0]}_ans"
        per_set: dict[str, Any] = {}
        for name in SETS:
            subset = rows if name == "all" else [row for row in rows if row.get("src") == name]
            sub_covered = [row for row in subset if row.get("covered")]
            per_set[name] = {
                "n": len(subset),
                "doc": {f"@{k}": round(recall(subset, doc_field, k), 4) for k in RECALL_AT},
                "doc_mrr10": round(mrr_at_10([row.get(doc_field) for row in subset]), 4),
                "ans": {f"@{k}": round(recall(sub_covered, ans_field, k), 4) for k in RECALL_AT},
                "ans_mrr10": round(mrr_at_10([row.get(ans_field) for row in sub_covered]), 4),
            }
        summary["stages"][stage] = per_set
    hybrid_cover = recall(rows, "h_doc", CANDIDATES)
    summary["coverage30_doc"] = round(hybrid_cover, 4)
    summary["never_in_candidates"] = sum(1 for row in rows if row.get("h_doc") is None)
    depth = aggregate_depth(rows)
    if depth:
        summary["depth"] = depth
    return summary


def depth_keys(rows: list[dict[str, Any]]) -> list[int]:
    """Profundidades extra presentes en las filas (claves ``h<N>_doc``)."""
    found: set[int] = set()
    for row in rows:
        for key in row:
            if key.startswith("h") and key.endswith("_doc") and key[1:-4].isdigit():
                found.add(int(key[1:-4]))
    return sorted(found - {CANDIDATES})


def aggregate_depth(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Cobertura por profundidad de candidatos y efecto del reranker sobre la muestra.

    La cobertura cuenta, sobre todas las filas, cuantas tienen el documento en
    los N primeros candidatos hibridos. La muestra (filas marcadas ``sample``)
    reordena con cada profundidad y mide doc@5, ans@5 y la latencia del
    reranker, incluida la profundidad base de 30.
    """
    depths = depth_keys(rows)
    if not depths:
        return {}
    coverage = {str(CANDIDATES): round(recall(rows, "h_doc", CANDIDATES), 4)}
    for depth in depths:
        measured = [row for row in rows if f"h{depth}_doc" in row]
        coverage[str(depth)] = round(recall(measured, f"h{depth}_doc", depth), 4)
    sample = [row for row in rows if row.get("sample")]
    covered = [row for row in sample if row.get("covered")]
    base: dict[str, Any] = {
        "doc@5": round(recall(sample, "r_doc", 5), 4),
        "ans@5": round(recall(covered, "r_ans", 5), 4),
        "rerank_ms_p50": round(
            percentile(sorted(float(row["r30_ms"]) for row in sample if "r30_ms" in row), 0.5), 1
        ),
    }
    by_depth: dict[str, Any] = {str(CANDIDATES): base}
    for depth in depths:
        times = sorted(float(row[f"r{depth}_ms"]) for row in sample if f"r{depth}_ms" in row)
        by_depth[str(depth)] = {
            "doc@5": round(recall(sample, f"r{depth}_doc", 5), 4),
            "ans@5": round(recall(covered, f"r{depth}_ans", 5), 4),
            "rerank_ms_p50": round(percentile(times, 0.5), 1),
        }
    return {"coverage_doc": coverage, "sample_n": len(sample), "sample": by_depth}


def check_isolation(iso: dict[str, Any]) -> list[str]:
    """Traduce los contadores de aislamiento a una lista de fugas.

    Vacia si el instrumento esta sano: cero fugas, control positivo que ve
    datos y todas las sondas ejecutadas. Una lista no vacia describe fugas
    reales (salida 1) o un control ciego (instrumento roto).
    """
    leaks: list[str] = []
    for key in ("tenant_leaks", "owner_leaks", "cross_tenant_read_leaks", "cross_owner_read_leaks"):
        value = int(iso.get(key, -1))
        if value > 0:
            leaks.append(f"{key}: {value}")
        elif value < 0:
            leaks.append(f"{key}: sin contar")
    if int(iso.get("control_read", 0)) < 1:
        leaks.append("control ciego: la lectura propia no devolvio nada")
    for key in ("cross_tenant_reads", "cross_owner_reads"):
        if int(iso.get(key, -1)) < EXPECTED_CASES:
            leaks.append(f"{key}: sondas incompletas ({iso.get(key)})")
    return leaks


def injected_leak_check() -> bool:
    """Autoprueba del detector: una fuga inventada debe cazarla.

    Si el detector no ve ni la fuga inyectada, el instrumento esta ciego y
    medir con el seria peor que no medir.
    """
    clean: dict[str, Any] = {
        "tenant_leaks": 0,
        "owner_leaks": 0,
        "cross_tenant_read_leaks": 0,
        "cross_owner_read_leaks": 0,
        "control_read": 2,
        "cross_tenant_reads": EXPECTED_CASES,
        "cross_owner_reads": EXPECTED_CASES,
    }
    if check_isolation(dict(clean)):
        return False
    for key in ("tenant_leaks", "owner_leaks", "cross_tenant_read_leaks", "cross_owner_read_leaks"):
        poisoned = dict(clean)
        poisoned[key] = 1
        found = check_isolation(poisoned)
        if not any(key in leak for leak in found):
            return False
    return True


def merge_rows(
    old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], int]:
    """Une filas de una reanudacion: conserva las puntuadas y anyade las nuevas.

    Devuelve las filas unidas y cuantas colisionaban (el calculo salta los
    identificadores ya puntuados, asi que colisionar indica un instrumento
    roto).
    """
    merged: dict[str, dict[str, Any]] = {str(row["id"]): row for row in old_rows}
    overlap = 0
    for row in new_rows:
        if str(row["id"]) in merged:
            overlap += 1
        merged[str(row["id"])] = row
    return list(merged.values()), overlap


def summarize(
    case_ids: list[str], payload: dict[str, Any], prepared_stats: dict[str, int]
) -> tuple[str, str, dict[str, Any]]:
    """Compara el calculo con lo congelado y publica cifras sin umbral.

    Duro (salida 1): calculo incompleto, cifras distintas de las congeladas,
    detector ciego o fuga real. La calidad de busqueda nunca falla aqui: se
    publica tal cual y el umbral lo fija U01.
    """
    meta = payload.get("meta")
    rows = payload.get("rows")
    iso = payload.get("iso")
    if not isinstance(meta, dict) or not isinstance(rows, list) or not isinstance(iso, dict):
        return "hard_failed", "salida del calculo ilegible", {}
    if len(rows) != EXPECTED_CASES:
        return "hard_failed", f"{len(rows)} casos puntuados frente a {EXPECTED_CASES}", {}
    if len({str(row.get("id")) for row in rows}) != EXPECTED_CASES:
        return "hard_failed", "identificadores duplicados o ausentes en las filas", {}
    if set(case_ids) != {str(row.get("id")) for row in rows}:
        return "hard_failed", "las filas no cubren la seleccion preparada", {}
    if int(meta.get("n_docs", -1)) != EXPECTED_DOCS:
        return "hard_failed", f"documentos {meta.get('n_docs')} frente a {EXPECTED_DOCS}", {}
    if int(meta.get("chunks", -1)) != EXPECTED_CHUNKS:
        return "hard_failed", f"fragmentos {meta.get('chunks')} frente a {EXPECTED_CHUNKS}", {}
    if not injected_leak_check():
        return "hard_failed", "el detector no caza la fuga inyectada", {}
    leaks = check_isolation(iso)
    if leaks:
        return "hard_failed", "fuga real: " + "; ".join(leaks[:4]), {"iso": iso}
    metrics = aggregate(rows)
    summary: dict[str, Any] = {
        "device": payload.get("device"),
        "gpu": payload.get("gpu"),
        "models": payload.get("models"),
        "config": {
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "candidates": CANDIDATES,
            "rrf_k": RRF_K,
            "top_k": TOP_K,
        },
        "corpus": {
            "docs": meta.get("n_docs"),
            "chunks": meta.get("chunks"),
            "index_s": meta.get("index_s"),
            "search_s": meta.get("search_s"),
            "answers_missed": prepared_stats.get("answers_missed"),
            "cases_empty": prepared_stats.get("cases_empty"),
        },
        "iso": iso,
        "metrics": metrics,
    }
    rerank = metrics["stages"]["rerank"]["all"]["doc"]["@5"]
    return "passed", f"{len(rows)} casos, rerank doc@5 {rerank:.1%}", summary


__all__ = [
    "CANDIDATES",
    "CHUNK_OVERLAP",
    "CHUNK_SIZE",
    "EXPECTED_CASES",
    "EXPECTED_CHUNKS",
    "EXPECTED_DOCS",
    "EXPECTED_SQAC_CASES",
    "EXPECTED_XQUAD_CASES",
    "OWNERS",
    "PROGRESS_EVERY",
    "RECALL_AT",
    "RRF_K",
    "SETS",
    "STAGES_4",
    "TOP_K",
    "Case",
    "Doc",
    "aggregate",
    "aggregate_depth",
    "build_selection",
    "check_isolation",
    "check_selection",
    "hit_at",
    "injected_leak_check",
    "merge_rows",
    "mrr_at_10",
    "normalize",
    "owner_for",
    "percentile",
    "recall",
    "resolve_answers",
    "summarize",
    "wilson",
]
