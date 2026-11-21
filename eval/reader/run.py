"""Ejecutor del lector: pasadas con/sin fragmentos y contrafactual, reanudable.

El contexto está fijado de antemano en la caché de recuperación
(`eval.reader.prepare`): este módulo no indexa, no recupera y no toca
Qdrant ni ningún modelo local. Lee la caché, envía cada caso al LLM con la
plantilla congelada y puntúa contra las respuestas humanas del dataset.

Pasadas (`--passes`, subconjunto de `with,without,counterfactual`):

- `with`: pregunta más los fragmentos de la caché.
- `without`: la misma pregunta sin contexto (control de contaminación).
- `counterfactual`: los mismos fragmentos con la respuesta sustituida por
  la de otra pregunta (lee frente a memoria).

Reanudación: cada llamada se anexa a `per_query/<run_id>/calls.jsonl` en
cuanto termina; repetir el comando omite los pares `(pase, caso)` ya
guardados salvo `provider_error`, que se reintenta (el resumen conserva solo
el último registro por par). `--max-calls` es obligatorio y acota las
llamadas nuevas de esta invocación (cuenta intentos del proveedor y el
reintento extra ante `retry_after`); si quedan pendientes, el resumen queda
marcado como parcial. Ante `LLMAuthError` (401/403) o `LLMQuotaExceeded`
(402) se detiene limpio: las llamadas en vuelo terminan, no se programa
ninguna más y el resumen queda marcado como abortado. `LLMRateLimited`
respeta `retry_after` una vez antes de rendirse en ese caso.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from eval.reader import scoring
from eval.reader.gitstate import is_dirty_tree
from eval.reader.reader import (
    NO_CONTEXT_PROMPT,
    READER_TEMPERATURE,
    WITH_CONTEXT_PROMPT,
    RenderedPrompt,
    call_reader,
    load_templates,
    prompt_path,
    prompt_sha256,
    render_with_context,
    render_without_context,
)
from eval.reader.scoring import (
    CounterfactualFragments,
    classify_counterfactual,
    classify_outcome,
    contains_match,
    exact_match,
    golds_kind,
    is_abstention,
    parse_reader_output,
    retrieval_hit,
    substitute_discard_reason,
    token_f1,
    valid_citations,
)
from eval.reader.xquad import (
    PARTITION_SEED,
    ReaderCase,
    list_cases,
    load_dataset,
)
from eval.run import hardware_info, read_commit
from ragmur.core.config import Settings, get_settings
from ragmur.core.logging import configure_logging
from ragmur.llm.provider import (
    Completion,
    LLMAuthError,
    LLMError,
    LLMQuotaExceeded,
    LLMRateLimited,
)

logger = logging.getLogger(__name__)

PASS_WITH = "with"
PASS_WITHOUT = "without"
PASS_COUNTERFACTUAL = "counterfactual"
VALID_PASSES = (PASS_WITH, PASS_WITHOUT, PASS_COUNTERFACTUAL)

DEFAULT_SEED = 20261121
DEFAULT_COUNTERFACTUAL_SIZE = 30
DEFAULT_CONCURRENCY = 1
# Espera máxima ante un `retry_after` del proveedor a nivel de ejecutor: se
# respeta su petición pero acotada para no bloquear el banco sin límite.
RATE_LIMIT_WAIT_CAP_SECONDS = 60.0
REVIEW_SAMPLE_SIZE = 30
FRAGMENT_EXCERPT_CHARS = 300

SCORED_OUTCOMES = ("correct", "wrong", "abstained", "parse_error")

CompleteFn = Callable[[RenderedPrompt], Awaitable[Completion]]


@dataclass(frozen=True, slots=True)
class CachedFragment:
    """Un fragmento de la caché: identificador citado y texto enviado."""

    chunk_id: str
    text: str


@dataclass(frozen=True, slots=True)
class CachedCase:
    """Un caso de la caché: pregunta más fragmentos ya recuperados."""

    case_id: str
    question: str
    fragments: tuple[CachedFragment, ...]


@dataclass(frozen=True, slots=True)
class Job:
    """Una llamada pendiente al lector, con todo lo necesario para puntuarla."""

    pass_name: str
    case_id: str
    question: str
    prompt: RenderedPrompt
    prompt_sha256: str
    golds: tuple[str, ...]
    gold_kind: str
    context_ids: frozenset[str]
    context_texts: dict[str, str]
    fragments_record: list[dict[str, str]]
    retrieval_hit: bool
    substitute: str | None


def parse_passes(raw: str) -> list[str]:
    """Valida `--passes`: subconjunto no vacío de pasadas conocidas, sin duplicados."""
    passes = [item.strip() for item in raw.split(",") if item.strip()]
    if not passes or any(item not in VALID_PASSES for item in passes):
        raise ValueError(f"Passes must be a subset of {','.join(VALID_PASSES)}")
    return list(dict.fromkeys(passes))


def build_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Define la interfaz de línea de órdenes del ejecutor del lector."""
    parser = argparse.ArgumentParser(description="Ejecuta el lector sobre la caché fijada")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--passes", type=str, default=",".join(VALID_PASSES))
    parser.add_argument(
        "--max-calls",
        type=int,
        required=True,
        help="Techo de llamadas LLM nuevas de esta invocación "
        "(cuenta intentos del proveedor y el reintento ante retry_after)",
    )
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--counterfactual-size", type=int, default=DEFAULT_COUNTERFACTUAL_SIZE)
    parser.add_argument("--results-dir", type=Path, default=Path("eval/results/reader"))
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--model-digest", type=str, default=None)
    parser.add_argument("--dataset-path", type=Path, default=None)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--llm-server-label", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def build_run_id(
    *, cache_key: str, seed: int, with_sha: str, without_sha: str, model_requested: str | None
) -> str:
    """Identidad de la ejecución: caché, semilla, plantillas y modelo.

    `p` son los 8 primeros hex del SHA-256 de la concatenación de ambos
    SHA de plantilla; `m` los 8 primeros del SHA-256 del modelo pedido.
    Cambiar un prompt o el modelo da otro `run_id` (otra muestra).
    """
    prompt_digest = hashlib.sha256((with_sha + without_sha).encode("utf-8")).hexdigest()[:8]
    model_digest = hashlib.sha256((model_requested or "").encode("utf-8")).hexdigest()[:8]
    return f"reader-{cache_key}-s{seed}-p{prompt_digest}-m{model_digest}"


def llm_api_base_host(api_base: str | None) -> str | None:
    """Anfitrión del `llm_api_base` sin credenciales ni ruta (solo registro)."""
    if not api_base:
        return None
    try:
        return urlparse(api_base).hostname
    except ValueError:
        return None


def resolve_llm_server(label: str | None, api_base: str | None) -> str | None:
    """Etiqueta del servidor LLM: flag explícita o anfitrión por defecto."""
    if label:
        return label
    return llm_api_base_host(api_base)


def read_cache_cases(path: Path) -> list[CachedCase]:
    """Lee los casos de la caché JSONL con un esquema mínimo validado."""
    if not path.is_file():
        raise ValueError(f"Cache file not found: {path}")
    cases: list[CachedCase] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record: Any = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"Malformed cache line {number} in {path}") from exc
            try:
                hits = record["hits"]
                fragments = tuple(
                    CachedFragment(chunk_id=str(item["chunk_id"]), text=str(item["text"]))
                    for item in hits
                )
                cases.append(
                    CachedCase(
                        case_id=str(record["case_id"]),
                        question=str(record["query"]),
                        fragments=fragments,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Malformed cache line {number} in {path}") from exc
    if not cases:
        raise ValueError(f"Cache file has no cases: {path}")
    return cases


def read_cache_meta(cache_path: Path) -> dict[str, Any]:
    """Lee el meta JSON hermano de la caché (condiciones de recuperación)."""
    if cache_path.suffix != ".jsonl":
        raise ValueError(f"Cache file must end in .jsonl: {cache_path}")
    meta_path = cache_path.parent / (cache_path.name[: -len(".jsonl")] + ".meta.json")
    if not meta_path.is_file():
        raise ValueError(f"Cache meta file not found: {meta_path}")
    try:
        meta: Any = json.loads(meta_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"Malformed cache meta file: {meta_path}") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"Malformed cache meta file: {meta_path}")
    return meta


def read_existing_records(path: Path) -> list[dict[str, Any]]:
    """Lee los registros ya guardados para reanudar sin repetir llamadas."""
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record: Any = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"Malformed calls line {number} in {path}") from exc
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("pass"), str)
                or not isinstance(record.get("case_id"), str)
            ):
                raise ValueError(f"Malformed calls line {number} in {path}")
            records.append(record)
    return records


def check_resume_compatible(
    records: list[dict[str, Any]],
    *,
    run_id: str,
    model_requested: str | None,
    with_sha: str,
    without_sha: str,
) -> None:
    """Rechaza reanudar si algún registro guardado no coincide con esta invocación."""
    allowed_shas = {with_sha, without_sha}
    for record in records:
        problems: list[str] = []
        if record.get("run_id") != run_id:
            problems.append(f"run_id {record.get('run_id')!r} != {run_id!r}")
        if record.get("model_requested") != model_requested:
            problems.append(f"model_requested {record.get('model_requested')!r} mismatch")
        sha = record.get("prompt_sha256")
        if not record.get("discarded") and sha not in allowed_shas:
            problems.append(f"prompt_sha256 {sha!r} mismatch")
        if problems:
            raise ValueError(
                f"Resume refused: stored record ({record.get('pass')}, "
                f"{record.get('case_id')}) mismatches this invocation: " + "; ".join(problems)
            )


def last_records_by_key(records: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Último registro por par (pase, caso): la reanudación solo conserva este."""
    last: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        last[(str(record.get("pass")), str(record.get("case_id")))] = record
    return last


def append_record(path: Path, record: dict[str, Any]) -> None:
    """Anexa un registro al JSONL sin tocar las líneas ya escritas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


async def call_with_rate_limit(
    prompt: RenderedPrompt, complete: CompleteFn, retry_counter: list[int]
) -> Completion:
    """Llama al lector respetando `retry_after` una vez antes de rendirse.

    El proveedor ya reintenta por su cuenta con espera acotada; si aun así
    devuelve `LLMRateLimited` con `retry_after`, el ejecutor espera lo pedido
    (acotado) y repite la llamada una sola vez. Sin `retry_after` no hay nada
    que respetar y el error se propaga tal cual.
    """
    try:
        return await complete(prompt)
    except LLMRateLimited as exc:
        if exc.retry_after is None:
            raise
        wait = min(exc.retry_after, RATE_LIMIT_WAIT_CAP_SECONDS)
        if wait > 0:
            logger.warning("límite del proveedor, esperando %.1f s", wait)
            await asyncio.sleep(wait)
        retry_counter.append(1)
        return await complete(prompt)


def build_jobs(
    cases: list[CachedCase],
    golds: dict[str, ReaderCase],
    articles: dict[str, list[ReaderCase]],
    templates: tuple[RenderedPrompt, RenderedPrompt],
    passes: list[str],
    counterfactual_size: int,
    seed: int,
    with_sha: str,
    without_sha: str,
    run_id: str,
    model_requested: str | None,
) -> tuple[list[Job], list[dict[str, Any]], dict[str, Any]]:
    """Prepara las llamadas: ordenadas por pase y por orden de la caché.

    Devuelve los trabajos que requieren al LLM, los registros inmediatos
    (contrafactuales descartados por la guarda, que no consumen llamadas) y
    las estadísticas de selección contrafactual (pedidos, elegibles,
    construidos, descartes por motivo y faltantes).
    """
    with_template, without_template = templates
    jobs: list[Job] = []
    immediate: list[dict[str, Any]] = []
    cf_stats: dict[str, Any] = {
        "requested": 0,
        "eligible": 0,
        "built": 0,
        "discarded": 0,
        "discarded_reasons": {},
        "shortfall": 0,
    }
    for pass_name in passes:
        if pass_name in (PASS_WITH, PASS_WITHOUT):
            for case in cases:
                gold = golds[case.case_id]
                context_texts = {item.chunk_id: item.text for item in case.fragments}
                hit = retrieval_hit([item.text for item in case.fragments], list(gold.answers))
                if pass_name == PASS_WITH:
                    prompt = render_with_context(
                        with_template,
                        case.question,
                        [(item.chunk_id, item.text) for item in case.fragments],
                    )
                    sha = with_sha
                else:
                    prompt = render_without_context(without_template, case.question)
                    sha = without_sha
                jobs.append(
                    Job(
                        pass_name=pass_name,
                        case_id=case.case_id,
                        question=case.question,
                        prompt=prompt,
                        prompt_sha256=sha,
                        golds=tuple(gold.answers),
                        gold_kind=golds_kind(list(gold.answers)),
                        context_ids=frozenset(context_texts),
                        context_texts=context_texts,
                        fragments_record=[
                            {"chunk_id": item.chunk_id, "text": item.text}
                            for item in case.fragments
                        ],
                        retrieval_hit=hit,
                        substitute=None,
                    )
                )
        else:
            cf_stats["requested"] = max(0, counterfactual_size)
            eligible = [
                case
                for case in cases
                if retrieval_hit(
                    [item.text for item in case.fragments],
                    list(golds[case.case_id].answers),
                )
            ]
            order = list(eligible)
            random.Random(seed).shuffle(order)
            cf_stats["eligible"] = len(order)
            built = 0
            # Respuestas de otros artículos del mismo split (la reserva nunca
            # se carga: `dataset_cases` solo trae el split pedido).
            by_article_answers: dict[str, list[str]] = {}
            for article, article_cases in articles.items():
                by_article_answers[article] = [
                    answer for rc in article_cases for answer in rc.answers
                ]
            for case in order:
                if built >= cf_stats["requested"]:
                    break
                gold = golds[case.case_id]
                siblings = [
                    other
                    for other in articles.get(gold.article, [])
                    if other.case_id != case.case_id
                ]
                sibling_answers = [answer for sib in siblings for answer in sib.answers]
                rng = random.Random(f"{seed}:{case.case_id}")
                substitute = scoring.choose_substitute(list(gold.answers), sibling_answers, rng)
                if substitute is None:
                    other_answers: list[str] = []
                    for article, answers in by_article_answers.items():
                        if article == gold.article:
                            continue
                        other_answers.extend(answers)
                    substitute = scoring.choose_substitute(list(gold.answers), other_answers, rng)
                if substitute is None:
                    reason = substitute_discard_reason(
                        list(gold.answers), sibling_answers + other_answers
                    )
                    immediate.append(
                        discarded_record(
                            case.case_id,
                            case.question,
                            reason,
                            run_id=run_id,
                            model_requested=model_requested,
                            prompt_sha256=with_sha,
                            gold_kind=golds_kind(list(gold.answers)),
                            substitute=None,
                        )
                    )
                    continue
                built_frag: CounterfactualFragments = scoring.build_counterfactual_fragments(
                    [item.text for item in case.fragments],
                    list(gold.answers),
                    substitute,
                )
                if built_frag.discarded:
                    immediate.append(
                        discarded_record(
                            case.case_id,
                            case.question,
                            built_frag.reason,
                            run_id=run_id,
                            model_requested=model_requested,
                            prompt_sha256=with_sha,
                            gold_kind=golds_kind(list(gold.answers)),
                            substitute=substitute,
                        )
                    )
                    continue
                replaced = [
                    (item.chunk_id, text)
                    for item, text in zip(case.fragments, built_frag.fragments, strict=True)
                ]
                prompt = render_with_context(with_template, case.question, replaced)
                context_texts = dict(
                    zip(
                        [item.chunk_id for item in case.fragments],
                        built_frag.fragments,
                        strict=True,
                    )
                )
                jobs.append(
                    Job(
                        pass_name=pass_name,
                        case_id=case.case_id,
                        question=case.question,
                        prompt=prompt,
                        prompt_sha256=with_sha,
                        golds=tuple(gold.answers),
                        gold_kind=golds_kind(list(gold.answers)),
                        context_ids=frozenset(context_texts),
                        context_texts=context_texts,
                        fragments_record=[
                            {"chunk_id": chunk_id, "text": text} for chunk_id, text in replaced
                        ],
                        retrieval_hit=True,
                        substitute=substitute,
                    )
                )
                built += 1
            cf_stats["built"] = built
            discarded = len(immediate)
            cf_stats["discarded"] = discarded
            reasons: dict[str, int] = {}
            for record in immediate:
                reason = str(record.get("guard_reason"))
                reasons[reason] = reasons.get(reason, 0) + 1
            cf_stats["discarded_reasons"] = reasons
            cf_stats["shortfall"] = max(0, cf_stats["requested"] - built)
    return jobs, immediate, cf_stats


def discarded_record(
    case_id: str,
    question: str,
    reason: str,
    *,
    run_id: str,
    model_requested: str | None,
    prompt_sha256: str,
    gold_kind: str,
    substitute: str | None = None,
) -> dict[str, Any]:
    """Registro sin llamada: la guarda contrafactual descartó el caso."""
    return {
        "pass": PASS_COUNTERFACTUAL,
        "case_id": case_id,
        "question": question,
        "discarded": True,
        "guard_reason": reason,
        "outcome": None,
        "run_id": run_id,
        "model_requested": model_requested,
        "prompt_sha256": prompt_sha256,
        "gold_kind": gold_kind,
        "substitute": substitute,
    }


def provider_error_record(
    job: Job, error: str, model_requested: str | None, run_id: str
) -> dict[str, Any]:
    """Registro de una llamada fallida a nivel de proveedor, sin puntuación."""
    return {
        "pass": job.pass_name,
        "case_id": job.case_id,
        "question": job.question,
        "discarded": False,
        "run_id": run_id,
        "model_requested": model_requested,
        "model_returned": None,
        "prompt_sha256": job.prompt_sha256,
        "fragments": job.fragments_record,
        "answer": None,
        "citations": [],
        "found": None,
        "parse_ok": False,
        "parse_error": None,
        "provider_error": error,
        "outcome": "provider_error",
        "em": False,
        "faithful_em": False,
        "contains_match": False,
        "f1": 0.0,
        "retrieval_hit": job.retrieval_hit,
        "valid_citations": [],
        "abstained": False,
        "substitute": job.substitute,
        "gold_kind": job.gold_kind,
        "counterfactual_outcome": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "latency_ms": None,
        "attempts": None,
    }


def score_record(
    job: Job, completion: Completion, model_requested: str | None, run_id: str
) -> dict[str, Any]:
    """Puntúa una llamada completada contra las respuestas del dataset."""
    base: dict[str, Any] = {
        "pass": job.pass_name,
        "case_id": job.case_id,
        "question": job.question,
        "discarded": False,
        "run_id": run_id,
        "model_requested": model_requested,
        "model_returned": completion.model,
        "prompt_sha256": job.prompt_sha256,
        "fragments": job.fragments_record,
        "provider_error": None,
        "substitute": job.substitute,
        "gold_kind": job.gold_kind,
        "prompt_tokens": completion.prompt_tokens,
        "completion_tokens": completion.completion_tokens,
        "latency_ms": completion.latency_ms,
        "attempts": completion.attempts,
    }
    try:
        parsed = parse_reader_output(completion.text)
    except scoring.ParseError as exc:
        return base | {
            "answer": None,
            "citations": [],
            "found": None,
            "parse_ok": False,
            "parse_error": str(exc),
            "outcome": "parse_error",
            "em": False,
            "faithful_em": False,
            "contains_match": False,
            "f1": 0.0,
            "retrieval_hit": job.retrieval_hit,
            "valid_citations": [],
            "abstained": False,
            "counterfactual_outcome": None,
        }
    abstained = is_abstention(parsed.answer, parsed.found)
    em = exact_match(parsed.answer, list(job.golds)) and not abstained
    lax = contains_match(parsed.answer, list(job.golds)) and not abstained
    valid = valid_citations(
        list(parsed.citations), set(job.context_ids), dict(job.context_texts), list(job.golds)
    )
    counterfactual_outcome = (
        classify_counterfactual(parsed.answer, list(job.golds), job.substitute)
        if job.pass_name == PASS_COUNTERFACTUAL and job.substitute is not None
        else None
    )
    return base | {
        "answer": parsed.answer,
        "citations": list(parsed.citations),
        "found": parsed.found,
        "parse_ok": True,
        "parse_error": None,
        "outcome": classify_outcome(em=em, abstained=abstained),
        "em": em,
        "faithful_em": em and bool(valid),
        "contains_match": lax,
        "f1": token_f1(parsed.answer, list(job.golds)),
        "retrieval_hit": job.retrieval_hit,
        "valid_citations": valid,
        "abstained": abstained,
        "counterfactual_outcome": counterfactual_outcome,
    }


async def execute_jobs(
    jobs: list[Job],
    *,
    model_requested: str | None,
    run_id: str,
    concurrency: int,
    complete: CompleteFn,
    on_record: Callable[[dict[str, Any]], None],
    retry_counter: list[int],
) -> tuple[list[dict[str, Any]], str | None]:
    """Ejecuta los trabajos con concurrencia acotada y parada limpia.

    Ante `LLMAuthError` o `LLMQuotaExceeded` no se programa nada más: las
    llamadas en vuelo terminan y el motivo queda registrado para marcar el
    resumen como abortado.
    """
    semaphore = asyncio.Semaphore(concurrency)
    abort_reason: str | None = None

    async def run_one(job: Job) -> dict[str, Any] | None:
        nonlocal abort_reason
        async with semaphore:
            if abort_reason is not None:
                return None
            try:
                completion = await call_with_rate_limit(job.prompt, complete, retry_counter)
            except (LLMAuthError, LLMQuotaExceeded) as exc:
                abort_reason = type(exc).__name__
                record = provider_error_record(job, abort_reason, model_requested, run_id)
            except LLMError as exc:
                record = provider_error_record(job, type(exc).__name__, model_requested, run_id)
            else:
                record = score_record(job, completion, model_requested, run_id)
            on_record(record)
            return record

    results = await asyncio.gather(*(run_one(job) for job in jobs))
    return [record for record in results if record is not None], abort_reason


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega los registros (último por par) con Wilson al 95 %.

    Denominadores: todo caso del pase con registro analizado o con error de
    análisis (`parse_error` cuenta como no acierto y como fallo del lector si
    hubo acierto de recuperación). Los errores de proveedor se excluyen y se
    informan aparte como recuento.
    """

    def deduped() -> dict[tuple[str, str], dict[str, Any]]:
        return last_records_by_key(records)

    def scored(pass_name: str, last: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            record
            for (passe, _), record in last.items()
            if passe == pass_name
            and not record.get("discarded")
            and record.get("outcome") in SCORED_OUTCOMES
        ]

    def provider_errors(pass_name: str, last: dict[tuple[str, str], dict[str, Any]]) -> int:
        return sum(
            1
            for (passe, _), record in last.items()
            if passe == pass_name
            and not record.get("discarded")
            and record.get("outcome") == "provider_error"
        )

    last = deduped()
    with_scored = scored(PASS_WITH, last)
    without_scored = scored(PASS_WITHOUT, last)
    correct_with = sum(1 for record in with_scored if record["outcome"] == "correct")
    faithful = sum(1 for record in with_scored if record.get("faithful_em"))
    lax_with = sum(1 for record in with_scored if record.get("contains_match"))
    abstained = sum(1 for record in with_scored if record["outcome"] == "abstained")
    retrieval_hits = sum(1 for record in with_scored if record.get("retrieval_hit"))
    failures_no_hit = sum(
        1
        for record in with_scored
        if record["outcome"] != "correct" and not record.get("retrieval_hit")
    )
    failures_with_hit = sum(
        1
        for record in with_scored
        if record["outcome"] != "correct" and record.get("retrieval_hit")
    )
    f1_values = [float(record.get("f1") or 0.0) for record in with_scored]
    correct_without = sum(1 for record in without_scored if record["outcome"] == "correct")
    lax_without = sum(1 for record in without_scored if record.get("contains_match"))
    contaminated = sorted(
        record["case_id"] for record in without_scored if record["outcome"] == "correct"
    )
    with_em = {str(record["case_id"]): (record["outcome"] == "correct") for record in with_scored}
    without_em = {
        str(record["case_id"]): (record["outcome"] == "correct") for record in without_scored
    }
    common = sorted(set(with_em) & set(without_em))
    delta = (
        sum(1 for case_id in common if with_em[case_id]) / len(common)
        - sum(1 for case_id in common if without_em[case_id]) / len(common)
        if common
        else 0.0
    )
    counterfactual = [
        record
        for (passe, _), record in last.items()
        if passe == PASS_COUNTERFACTUAL
        and not record.get("discarded")
        and record.get("outcome") in SCORED_OUTCOMES
    ]
    reads = sum(1 for r in counterfactual if r.get("counterfactual_outcome") == "reads_context")
    memory = sum(1 for r in counterfactual if r.get("counterfactual_outcome") == "uses_memory")
    both = sum(1 for r in counterfactual if r.get("counterfactual_outcome") == "both")
    other_cf = sum(1 for r in counterfactual if r.get("counterfactual_outcome") == "other")
    discarded = sum(1 for item in records if item.get("discarded"))
    discarded_reasons: dict[str, int] = {}
    for record in records:
        if record.get("discarded"):
            reason = str(record.get("guard_reason"))
            discarded_reasons[reason] = discarded_reasons.get(reason, 0) + 1
    by_with_em: dict[str, dict[str, int]] = {
        "with_correct": {"reads_context": 0, "uses_memory": 0, "both": 0, "other": 0, "n": 0},
        "with_not_correct": {"reads_context": 0, "uses_memory": 0, "both": 0, "other": 0, "n": 0},
    }
    for record in counterfactual:
        key = "with_correct" if with_em.get(str(record["case_id"]), False) else "with_not_correct"
        outcome = str(record.get("counterfactual_outcome") or "other")
        if outcome not in ("reads_context", "uses_memory", "both", "other"):
            outcome = "other"
        by_with_em[key][outcome] += 1
        by_with_em[key]["n"] += 1
    return {
        "with": {
            "n": len(with_scored),
            "em": scoring.proportion(correct_with, len(with_scored)),
            "faithful_em": scoring.proportion(faithful, len(with_scored)),
            "contains_match": scoring.proportion(lax_with, len(with_scored)),
            "abstention": scoring.proportion(abstained, len(with_scored)),
            "parse_error": scoring.proportion(
                sum(1 for r in with_scored if r.get("outcome") == "parse_error"),
                len(with_scored),
            ),
            "provider_error": {"count": provider_errors(PASS_WITH, last)},
            "retrieval_hit": scoring.proportion(retrieval_hits, len(with_scored)),
            "f1": {
                "mean": (sum(f1_values) / len(f1_values)) if f1_values else None,
                "n": len(f1_values),
            },
            "failure_attribution": {
                "retrieval_miss": failures_no_hit,
                "reader_miss": failures_with_hit,
            },
        },
        "without": {
            "n": len(without_scored),
            "em": scoring.proportion(correct_without, len(without_scored)),
            "contains_match": scoring.proportion(lax_without, len(without_scored)),
            "provider_error": {"count": provider_errors(PASS_WITHOUT, last)},
            "contaminated": len(contaminated),
            "contaminated_case_ids": contaminated,
        },
        "delta": {"em_with_minus_without": delta, "n_common": len(common)},
        "counterfactual": {
            "n": len(counterfactual),
            "reads_context": scoring.proportion(reads, len(counterfactual)),
            "uses_memory": scoring.proportion(memory, len(counterfactual)),
            "both": scoring.proportion(both, len(counterfactual)),
            "other": scoring.proportion(other_cf, len(counterfactual)),
            "provider_error": {"count": provider_errors(PASS_COUNTERFACTUAL, last)},
            "discarded": discarded,
            "discarded_reasons": discarded_reasons,
            "by_with_em": by_with_em,
        },
    }


def write_review_sample(
    path: Path,
    records: list[dict[str, Any]],
    golds: dict[str, ReaderCase],
    seed: int,
    run_id: str,
) -> int:
    """Muestra humana de 30 casos con fragmentos: pregunta, oro y respuesta."""
    last = last_records_by_key(records)
    with_records = [
        record
        for (passe, _), record in last.items()
        if passe == PASS_WITH
        and not record.get("discarded")
        and record.get("outcome") in SCORED_OUTCOMES
    ]
    rng = random.Random(seed)
    sample = rng.sample(with_records, min(REVIEW_SAMPLE_SIZE, len(with_records)))
    lines = [
        f"# Muestra de revisión ({run_id})",
        "",
        f"{len(sample)} casos con fragmentos elegidos al azar con semilla {seed}.",
        "Cifras aparte: esto es lectura humana, no aceptación.",
        "",
    ]
    for record in sorted(sample, key=lambda item: str(item["case_id"])):
        case_id = str(record["case_id"])
        gold = golds.get(case_id)
        expected = ", ".join(f'"{answer}"' for answer in gold.answers) if gold else "?"
        fragments = {item["chunk_id"]: item["text"] for item in record.get("fragments", [])}
        ordered_ids = [str(item["chunk_id"]) for item in record.get("fragments", [])]
        cited = [str(item) for item in record.get("valid_citations", [])]
        lines.append(f"## Caso {case_id}")
        lines.append("")
        lines.append(f"- Pregunta: {record.get('question')}")
        lines.append(f"- Respuestas esperadas: {expected}")
        lines.append(f"- Respuesta del modelo: {record.get('answer')}")
        lines.append(f"- Resultado: {record.get('outcome')}")
        lines.append(f"- Citas válidas: {', '.join(cited) if cited else 'ninguna'}")
        if ordered_ids:
            top_id = ordered_ids[0]
            excerpt = fragments.get(top_id, "")[:FRAGMENT_EXCERPT_CHARS]
            lines.append(f"- Fragmento principal {top_id}: «{excerpt}»")
        for chunk_id in cited[:2]:
            if ordered_ids and chunk_id == ordered_ids[0]:
                continue
            excerpt = fragments.get(chunk_id, "")[:FRAGMENT_EXCERPT_CHARS]
            lines.append(f"- Fragmento citado {chunk_id}: «{excerpt}»")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return len(sample)


def plan_dry_run(
    jobs: list[Job], immediate: list[dict[str, Any]], cf_stats: dict[str, Any]
) -> dict[str, Any]:
    """Resume el plan sin llamar al modelo: trabajos por pase y descartes."""
    by_pass: dict[str, int] = {}
    for job in jobs:
        by_pass[job.pass_name] = by_pass.get(job.pass_name, 0) + 1
    reasons: dict[str, int] = {}
    for record in immediate:
        reason = str(record.get("guard_reason"))
        reasons[reason] = reasons.get(reason, 0) + 1
    plan = {
        "jobs_total": len(jobs),
        "jobs_by_pass": by_pass,
        "discarded_total": len(immediate),
        "discarded_reasons": reasons,
        "counterfactual": dict(cf_stats),
    }
    logger.info(
        "plan en seco: %d trabajos %s, %d descartes %s",
        len(jobs),
        by_pass,
        len(immediate),
        reasons,
    )
    return plan


def previous_cumulative_wall(results_dir: Path, run_id: str) -> float:
    """Pared acumulada de reanudaciones previas con el mismo `run_id`."""
    parent = results_dir.parent
    if not parent.is_dir():
        return 0.0
    best = 0.0
    for path in sorted(parent.glob("reader-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict) or payload.get("run_id") != run_id:
            continue
        candidate = payload.get("wall_seconds_cumulative", payload.get("wall_seconds", 0.0))
        try:
            best = max(best, float(candidate or 0.0))
        except (TypeError, ValueError):
            continue
    return best


async def run_bench(
    settings: Settings,
    *,
    cache_path: Path,
    passes: list[str],
    max_calls: int,
    concurrency: int,
    seed: int,
    counterfactual_size: int,
    results_dir: Path,
    run_id: str | None,
    model_digest: str | None,
    dataset_path: Path | None,
    complete: CompleteFn,
    allow_dirty: bool = False,
    llm_server_label: str | None = None,
    dry_run: bool = False,
) -> tuple[Path, Path, dict[str, Any]]:
    """Orquesta lectura de caché, ejecución, resumen y muestra de revisión."""
    if max_calls < 1:
        raise ValueError("--max-calls must be at least 1")
    if concurrency < 1:
        raise ValueError("--concurrency must be at least 1")
    dirty = is_dirty_tree()
    if dirty and not allow_dirty:
        raise RuntimeError(
            "Refusing to run with a dirty tree (src/eval); "
            "commit the changes or retry with --allow-dirty"
        )
    cases = read_cache_cases(cache_path)
    meta = read_cache_meta(cache_path)
    sample_meta = meta.get("sample", {})
    split = str(sample_meta.get("split", "dev"))
    dataset_meta = meta.get("dataset", {})
    meta_dataset_path = dataset_meta.get("path")
    if dataset_path is not None:
        target = dataset_path
    elif isinstance(meta_dataset_path, str) and meta_dataset_path:
        target = Path(meta_dataset_path)
    else:
        target = Path("eval/.datasets/xquad/xquad.es.json")
    data = load_dataset(target)
    dataset_cases = list_cases(data, split)
    golds = {case.case_id: case for case in dataset_cases}
    missing = [case.case_id for case in cases if case.case_id not in golds]
    if missing:
        raise ValueError(f"Cache cases missing from the {split} dataset: {missing[:5]}")
    articles: dict[str, list[ReaderCase]] = {}
    for case in dataset_cases:
        articles.setdefault(case.article, []).append(case)
    with_template, without_template = load_templates()
    with_sha = prompt_sha256(prompt_path(WITH_CONTEXT_PROMPT))
    without_sha = prompt_sha256(prompt_path(NO_CONTEXT_PROMPT))
    model_requested = settings.llm_model
    cache_key = str(meta.get("cache_key", "unknown"))
    resolved_run_id = run_id or build_run_id(
        cache_key=cache_key,
        seed=seed,
        with_sha=with_sha,
        without_sha=without_sha,
        model_requested=model_requested,
    )
    jobs, immediate, cf_stats = build_jobs(
        cases,
        golds,
        articles,
        (with_template, without_template),
        passes,
        counterfactual_size,
        seed,
        with_sha,
        without_sha,
        resolved_run_id,
        model_requested,
    )
    calls_path = results_dir / "per_query" / resolved_run_id / "calls.jsonl"
    existing = read_existing_records(calls_path)
    check_resume_compatible(
        existing,
        run_id=resolved_run_id,
        model_requested=model_requested,
        with_sha=with_sha,
        without_sha=without_sha,
    )
    if dry_run:
        plan = plan_dry_run(jobs, immediate, cf_stats)
        summary_stub: dict[str, Any] = {
            "run_id": resolved_run_id,
            "dry_run": True,
            "plan": plan,
        }
        return calls_path, calls_path, summary_stub
    last = last_records_by_key(existing)
    done = {
        key
        for key, record in last.items()
        if record.get("discarded") or record.get("outcome") != "provider_error"
    }
    fresh_immediate = [r for r in immediate if (r["pass"], r["case_id"]) not in done]
    for record in fresh_immediate:
        append_record(calls_path, record)
    pending = [job for job in jobs if (job.pass_name, job.case_id) not in done]
    retry_counter: list[int] = []
    invocation_counts: list[int] = []

    async def counting_complete(prompt: RenderedPrompt) -> Completion:
        invocation_counts.append(1)
        return await complete(prompt)

    executed_all: list[dict[str, Any]] = []
    remaining = list(pending)
    tries_used = 0
    abort_reason: str | None = None
    started = time.perf_counter()
    while remaining and tries_used < max_calls and abort_reason is None:
        batch_size = min(concurrency, max_calls - tries_used, len(remaining))
        batch = remaining[:batch_size]
        remaining = remaining[batch_size:]
        batch_before = len(invocation_counts)
        executed, abort_reason = await execute_jobs(
            batch,
            model_requested=model_requested,
            run_id=resolved_run_id,
            concurrency=concurrency,
            complete=counting_complete,
            on_record=lambda record: append_record(calls_path, record),
            retry_counter=retry_counter,
        )
        executed_all.extend(executed)
        invocations = len(invocation_counts) - batch_before
        attempts = sum(
            int(record.get("attempts") or 0) for record in executed if record.get("attempts")
        )
        # Cada trabajo cuesta al menos sus invocaciones; los intentos internos
        # del proveedor (`attempts`) suman lo que exceda de una por invocación.
        # El reintento extra ante `retry_after` ya cuenta en invocaciones.
        batch_tries = max(invocations, attempts)
        if batch_tries < 1:
            batch_tries = len(executed)
        tries_used += batch_tries
        if abort_reason is not None:
            break
    skipped_by_abort = len(pending) - len(executed_all) - len(remaining)
    wall_seconds = time.perf_counter() - started
    cumulative_wall = previous_cumulative_wall(results_dir, resolved_run_id) + wall_seconds
    all_records = existing + fresh_immediate + executed_all
    left_over = len(remaining)
    summary_calls = {
        "max_calls": max_calls,
        "new_calls": len(executed_all) + len(fresh_immediate),
        "new_tries": len(invocation_counts),
        "new_retry_after_retries": len(retry_counter),
        "completed": sum(
            1 for record in last_records_by_key(all_records).values() if not record.get("discarded")
        ),
        "cumulative_records": len(all_records),
        "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in all_records),
        "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in all_records),
        "attempts_total": sum(
            int(r.get("attempts") or 0) for r in all_records if r.get("attempts")
        ),
    }
    metrics = summarize_records(all_records)
    if PASS_COUNTERFACTUAL in passes:
        metrics["counterfactual"]["requested"] = cf_stats["requested"]
        metrics["counterfactual"]["eligible"] = cf_stats["eligible"]
        metrics["counterfactual"]["built"] = cf_stats["built"]
        metrics["counterfactual"]["shortfall"] = cf_stats["shortfall"]
    smoke = bool(allow_dirty)
    summary = {
        "date": datetime.now(UTC).isoformat(),
        "run_id": resolved_run_id,
        "commit": read_commit(),
        "dirty": dirty,
        "smoke": smoke,
        "dataset": {
            "url": dataset_meta.get("url"),
            "sha256": dataset_meta.get("sha256"),
            "license": dataset_meta.get("license"),
            "path": str(target),
        },
        "partition": {"seed": PARTITION_SEED, "split": split},
        "split": split,
        "n_cases": len(cases),
        "chunking": {
            "chunk_size": meta.get("chunk_size"),
            "chunk_overlap": meta.get("chunk_overlap"),
        },
        "candidates": meta.get("candidates"),
        "top_k": meta.get("top_k"),
        "configuration": meta.get("configuration"),
        "cache_key": cache_key,
        "cache_commit": meta.get("commit"),
        "cache_dirty": meta.get("dirty"),
        "model_requested": model_requested,
        "model_returned": sorted(
            {str(r["model_returned"]) for r in all_records if r.get("model_returned")}
        ),
        "model_digest": model_digest,
        "llm_api_base_host": llm_api_base_host(settings.llm_api_base),
        "llm_server": resolve_llm_server(llm_server_label, settings.llm_api_base),
        "temperature": READER_TEMPERATURE,
        "seed": seed,
        "prompt_sha256": {
            "with_context": with_sha,
            "without_context": without_sha,
        },
        "hardware": hardware_info(settings),
        "concurrency": concurrency,
        "passes": passes,
        "counterfactual_size": counterfactual_size,
        "calls": summary_calls,
        "wall_seconds": wall_seconds,
        "wall_seconds_cumulative": cumulative_wall,
        "partial": bool(left_over > 0 or skipped_by_abort > 0),
        "pending": left_over + skipped_by_abort,
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
        "metrics": metrics,
    }
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S%fZ")
    suffix = "-smoke" if smoke else ""
    summary_path = results_dir.parent / f"reader-{timestamp}-{split}{suffix}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    sample_path = calls_path.parent / "review_sample.md"
    summary["review_sample"] = {
        "path": str(sample_path),
        "cases": write_review_sample(sample_path, all_records, golds, seed, resolved_run_id),
    }
    # La muestra se cuenta en el resumen pero se escribe aparte: el resumen
    # versionado no incluye los volcados por consulta.
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(
        "banco del lector completado",
        extra={"summary": str(summary_path), "run_id": resolved_run_id},
    )
    return summary_path, calls_path, summary


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada sin `print`: el resultado va al log y al resumen."""
    args = build_arguments(argv)
    try:
        passes = parse_passes(args.passes)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    settings = get_settings()
    configure_logging(settings.log_level)

    async def default_complete(prompt: RenderedPrompt) -> Completion:
        return await call_reader(prompt, settings=settings, seed=args.seed)

    digest = args.model_digest or os.environ.get("LLM_MODEL_DIGEST")
    asyncio.run(
        run_bench(
            settings,
            cache_path=args.cache,
            passes=passes,
            max_calls=args.max_calls,
            concurrency=args.concurrency,
            seed=args.seed,
            counterfactual_size=args.counterfactual_size,
            results_dir=args.results_dir,
            run_id=args.run_id,
            model_digest=digest,
            dataset_path=args.dataset_path,
            complete=default_complete,
            allow_dirty=args.allow_dirty,
            llm_server_label=args.llm_server_label,
            dry_run=args.dry_run,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
