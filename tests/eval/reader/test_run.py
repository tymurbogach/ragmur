"""Ejecutor del lector: presupuesto, reanudación, paradas y resumen, sin red."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from eval.reader.reader import (
    WITH_CONTEXT_PROMPT,
    RenderedPrompt,
    prompt_path,
    prompt_sha256,
)
from eval.reader.run import (
    build_run_id,
    parse_passes,
    read_cache_cases,
    run_bench,
)
from eval.reader.xquad import ReaderCase

from eval.reader import run as reader_run
from ragmur.core.config import Settings
from ragmur.llm.provider import Completion, LLMAuthError, LLMQuotaExceeded, LLMRateLimited

CACHE_KEY = "abc123abc123abcd"


def make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://lector:lector@127.0.0.1:5432/nada",
        api_key_hmac_secret="test-only-hmac-secret",
        llm_model="test-model",
    )


def write_cache(directory: Path) -> Path:
    """Caché mínima de dos casos con respuestas presentes en los fragmentos."""
    lines = [
        {
            "case_id": "c1",
            "query": "¿Color?",
            "hits": [
                {
                    "rank": 1,
                    "chunk_id": "frag-1",
                    "document_key": "d:0",
                    "text": "el logo era negro y amarillo",
                },
                {
                    "rank": 2,
                    "chunk_id": "frag-2",
                    "document_key": "d:1",
                    "text": "texto sin relación",
                },
            ],
            "latency_ms": 1.0,
        },
        {
            "case_id": "c2",
            "query": "¿Tamaño?",
            "hits": [
                {
                    "rank": 1,
                    "chunk_id": "frag-3",
                    "document_key": "d:0",
                    "text": "las familias medían cuatro miembros",
                }
            ],
            "latency_ms": 1.0,
        },
    ]
    jsonl = directory / f"retrieval-{CACHE_KEY}.jsonl"
    jsonl.write_text(
        "\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n",
        encoding="utf-8",
    )
    meta = {
        "cache_key": CACHE_KEY,
        "configuration": "hybrid_rerank",
        "candidates": 30,
        "top_k": 5,
        "chunk_size": 800,
        "chunk_overlap": 120,
        "dataset": {
            "url": "https://example/xquad.es.json",
            "sha256": "0" * 64,
            "license": "CC BY-SA 4.0",
            "path": "eval/.datasets/xquad/xquad.es.json",
        },
        "sample": {"split": "dev", "seed": 20261121, "sample_size": 2, "cases": 2},
    }
    (directory / f"retrieval-{CACHE_KEY}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return jsonl


def dataset_cases() -> list[ReaderCase]:
    return [
        ReaderCase(
            case_id="c1",
            article="Articulo",
            paragraph_index=0,
            question="¿Color?",
            answers=("negro y amarillo",),
            split="dev",
            document_key="xquad-es:Articulo:0",
        ),
        ReaderCase(
            case_id="c2",
            article="Articulo",
            paragraph_index=1,
            question="¿Tamaño?",
            answers=("cuatro miembros",),
            split="dev",
            document_key="xquad-es:Articulo:1",
        ),
    ]


def patch_dataset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader_run, "load_dataset", lambda path: {"ok": True})
    monkeypatch.setattr(reader_run, "list_cases", lambda data, split: dataset_cases())


def completion_for(text: str, attempts: int = 1) -> Completion:
    return Completion(
        text=text,
        model="fake-model",
        prompt_tokens=10,
        completion_tokens=5,
        latency_ms=2.0,
        attempts=attempts,
    )


def router_complete(
    text_by_marker: dict[str, str],
) -> Callable[[RenderedPrompt], Awaitable[Completion]]:
    async def complete(prompt: RenderedPrompt) -> Completion:
        for marker, text in text_by_marker.items():
            if marker in prompt.user:
                return completion_for(text)
        return completion_for('{"answer": "NO CONSTA", "citations": [], "found": false}')

    return complete


def run_kwargs(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "passes": ["with"],
        "max_calls": 10,
        "concurrency": 1,
        "seed": 20261121,
        "counterfactual_size": 30,
        "model_digest": None,
        "dataset_path": None,
        "allow_dirty": True,
    }
    base.update(overrides)
    return base


def test_parse_passes() -> None:
    assert parse_passes("with,without") == ["with", "without"]
    assert parse_passes("with,with") == ["with"]
    with pytest.raises(ValueError):
        parse_passes("with,otro")
    with pytest.raises(ValueError):
        parse_passes("")


def test_read_cache_cases_rejects_missing_and_malformed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not found"):
        read_cache_cases(tmp_path / "no.jsonl")
    bad = tmp_path / "retrieval-bad.jsonl"
    bad.write_text('{"case_id": "c1"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        read_cache_cases(bad)


async def test_max_calls_caps_and_marks_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    complete = router_complete(
        {
            "¿Color?": '{"answer": "negro y amarillo", "citations": ["frag-1"], "found": true}',
            "¿Tamaño?": '{"answer": "cuatro miembros", "citations": ["frag-3"], "found": true}',
        }
    )
    kwargs = run_kwargs(passes=["with", "without"], max_calls=2)
    summary_path, calls_path, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="cap-run",
        complete=complete,
        **kwargs,
    )
    assert summary_path.is_file() and calls_path.is_file()
    assert summary["partial"] is True and summary["calls"]["new_calls"] == 2
    assert len(read_cache_lines(calls_path)) == 2


async def test_resume_skips_done_cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    calls: list[str] = []
    base = router_complete({"¿Color?": '{"answer": "x", "citations": [], "found": true}'})

    async def counting(prompt: RenderedPrompt) -> Completion:
        calls.append(prompt.user)
        return await base(prompt)

    with_sha = prompt_sha256(prompt_path(WITH_CONTEXT_PROMPT))
    calls_path = tmp_path / "reader" / "per_query" / "resume-run" / "calls.jsonl"
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    calls_path.write_text(
        json.dumps(
            {
                "pass": "with",
                "case_id": "c1",
                "outcome": "correct",
                "run_id": "resume-run",
                "model_requested": "test-model",
                "prompt_sha256": with_sha,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    kwargs = run_kwargs(passes=["with"], max_calls=10)
    _, _, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="resume-run",
        complete=counting,
        **kwargs,
    )
    assert len(calls) == 1 and "¿Tamaño?" in calls[0]
    assert summary["partial"] is False


async def test_resume_retries_provider_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    with_sha = prompt_sha256(prompt_path(WITH_CONTEXT_PROMPT))
    calls_path = tmp_path / "reader" / "per_query" / "retry-provider" / "calls.jsonl"
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    calls_path.write_text(
        json.dumps(
            {
                "pass": "with",
                "case_id": "c1",
                "outcome": "provider_error",
                "run_id": "retry-provider",
                "model_requested": "test-model",
                "prompt_sha256": with_sha,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    complete = router_complete(
        {"¿Color?": '{"answer": "negro y amarillo", "citations": ["frag-1"], "found": true}'}
    )
    kwargs = run_kwargs(passes=["with"], max_calls=10)
    _, final_path, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="retry-provider",
        complete=complete,
        **kwargs,
    )
    lines = read_cache_lines(final_path)
    c1_lines = [line for line in lines if line["case_id"] == "c1"]
    assert len(c1_lines) == 2
    assert summary["metrics"]["with"]["provider_error"]["count"] == 0


async def test_resume_refuses_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    calls_path = tmp_path / "reader" / "per_query" / "mismatch-run" / "calls.jsonl"
    calls_path.parent.mkdir(parents=True, exist_ok=True)
    calls_path.write_text(
        json.dumps(
            {
                "pass": "with",
                "case_id": "c1",
                "outcome": "correct",
                "run_id": "other-run",
                "model_requested": "test-model",
                "prompt_sha256": "0" * 64,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    kwargs = run_kwargs(passes=["with"], max_calls=10)
    with pytest.raises(ValueError, match="Resume refused"):
        await run_bench(
            make_settings(),
            cache_path=cache,
            results_dir=tmp_path / "reader",
            run_id="mismatch-run",
            complete=router_complete({}),
            **kwargs,
        )


def test_run_id_changes_with_prompt_or_model() -> None:
    first = build_run_id(
        cache_key=CACHE_KEY,
        seed=20261121,
        with_sha="a" * 64,
        without_sha="b" * 64,
        model_requested="m1",
    )
    second = build_run_id(
        cache_key=CACHE_KEY,
        seed=20261121,
        with_sha="c" * 64,
        without_sha="b" * 64,
        model_requested="m1",
    )
    third = build_run_id(
        cache_key=CACHE_KEY,
        seed=20261121,
        with_sha="a" * 64,
        without_sha="b" * 64,
        model_requested="m2",
    )
    assert first != second and first != third
    assert first.startswith(f"reader-{CACHE_KEY}-s20261121-p") and "-m" in first


async def test_stops_cleanly_on_quota(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)

    async def failing(_prompt: RenderedPrompt) -> Completion:
        raise LLMQuotaExceeded("sin crédito")

    kwargs = run_kwargs(passes=["with"], max_calls=10)
    _, calls_path, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="quota-run",
        complete=failing,
        **kwargs,
    )
    assert summary["aborted"] is True and summary["abort_reason"] == "LLMQuotaExceeded"
    assert len(read_cache_lines(calls_path)) == 1


async def test_stops_cleanly_on_auth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)

    async def failing(_prompt: RenderedPrompt) -> Completion:
        raise LLMAuthError("clave mala")

    kwargs = run_kwargs(passes=["with"], max_calls=10)
    _, calls_path, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="auth-run",
        complete=failing,
        **kwargs,
    )
    assert summary["aborted"] is True and summary["abort_reason"] == "LLMAuthError"
    lines = read_cache_lines(calls_path)
    assert len(lines) == 1
    assert summary["calls"]["new_calls"] == 1


async def test_retry_after_is_honoured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    attempts = {"count": 0}

    async def flaky(_prompt: RenderedPrompt) -> Completion:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise LLMRateLimited("cuota", retry_after=0.5)
        return completion_for('{"answer": "negro", "citations": [], "found": true}')

    kwargs = run_kwargs(passes=["with"], max_calls=10)
    _, _, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="retry-run",
        complete=flaky,
        **kwargs,
    )
    sleep.assert_awaited_once_with(0.5)
    assert summary["aborted"] is False
    assert summary["metrics"]["with"]["n"] == 2
    assert summary["calls"]["new_retry_after_retries"] == 1


async def test_rate_limit_without_retry_after_is_provider_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)

    async def limited(_prompt: RenderedPrompt) -> Completion:
        raise LLMRateLimited("cuota")

    kwargs = run_kwargs(passes=["with"], max_calls=1)
    _, calls_path, _ = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="limited-run",
        complete=limited,
        **kwargs,
    )
    record = read_cache_lines(calls_path)[0]
    assert record["outcome"] == "provider_error"


async def test_attempts_count_toward_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)

    async def pricey(_prompt: RenderedPrompt) -> Completion:
        return completion_for('{"answer": "x", "citations": [], "found": true}', attempts=3)

    kwargs = run_kwargs(passes=["with"], max_calls=3)
    _, _, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="attempts-run",
        complete=pricey,
        **kwargs,
    )
    assert summary["calls"]["attempts_total"] == 6 or summary["calls"]["new_calls"] == 1
    assert summary["partial"] is True


async def test_dirty_tree_refuses_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    monkeypatch.setattr(reader_run, "is_dirty_tree", lambda: True)
    with pytest.raises(RuntimeError, match="dirty tree"):
        await run_bench(
            make_settings(),
            cache_path=cache,
            passes=["with"],
            max_calls=1,
            concurrency=1,
            seed=20261121,
            counterfactual_size=30,
            results_dir=tmp_path / "reader",
            run_id="dirty-run",
            model_digest=None,
            dataset_path=None,
            complete=router_complete({}),
            allow_dirty=False,
        )


async def test_summary_fields_and_review_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    complete = router_complete(
        {
            "¿Color?": '{"answer": "negro y amarillo", "citations": ["frag-1"], "found": true}',
            "¿Tamaño?": '{"answer": "cuatro miembros", "citations": ["frag-3"], "found": true}',
        }
    )
    kwargs = run_kwargs(passes=["with", "without", "counterfactual"], max_calls=20)
    kwargs["model_digest"] = "sha256:abc"
    summary_path, _, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="full-run",
        complete=complete,
        **kwargs,
    )
    for key in (
        "date",
        "run_id",
        "commit",
        "dirty",
        "smoke",
        "dataset",
        "partition",
        "split",
        "n_cases",
        "chunking",
        "candidates",
        "top_k",
        "configuration",
        "cache_key",
        "cache_commit",
        "cache_dirty",
        "model_requested",
        "model_returned",
        "model_digest",
        "llm_api_base_host",
        "llm_server",
        "temperature",
        "seed",
        "prompt_sha256",
        "hardware",
        "concurrency",
        "calls",
        "wall_seconds",
        "wall_seconds_cumulative",
        "metrics",
    ):
        assert key in summary, key
    assert summary["dataset"]["license"] == "CC BY-SA 4.0"
    assert summary["dataset"]["path"] == "eval/.datasets/xquad/xquad.es.json"
    assert set(summary["prompt_sha256"]) == {"with_context", "without_context"}
    assert summary["temperature"] == 0.0 and summary["model_requested"] == "test-model"
    assert summary["model_returned"] == ["fake-model"]
    assert summary["run_id"] == "full-run"
    metrics = summary["metrics"]
    assert metrics["with"]["em"]["rate"] == 1.0
    assert metrics["with"]["faithful_em"]["rate"] == 1.0
    assert "contains_match" in metrics["with"] and "wilson_95" in metrics["with"]["contains_match"]
    assert "contains_match" in metrics["without"]
    assert metrics["with"]["retrieval_hit"]["rate"] == 1.0
    assert "wilson_95" in metrics["with"]["em"]
    assert metrics["with"]["f1"]["mean"] == pytest.approx(1.0)
    assert metrics["delta"]["n_common"] == 2
    assert metrics["counterfactual"]["requested"] == 30
    assert metrics["counterfactual"]["shortfall"] >= 0
    check_review_sample(summary)
    assert summary_path.parent == tmp_path


async def test_parse_error_counts_and_provider_excluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)

    async def mixed(prompt: RenderedPrompt) -> Completion:
        if "¿Color?" in prompt.user:
            return completion_for("basura sin json")
        raise LLMRateLimited("cuota")

    kwargs = run_kwargs(passes=["with"], max_calls=10)
    _, _, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="denom-run",
        complete=mixed,
        **kwargs,
    )
    with_metrics = summary["metrics"]["with"]
    assert with_metrics["n"] == 1
    assert with_metrics["parse_error"]["successes"] == 1
    assert with_metrics["provider_error"]["count"] == 1
    assert with_metrics["em"]["successes"] == 0
    assert with_metrics["failure_attribution"]["reader_miss"] == 1


async def test_counterfactual_reads_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    # c1 recibe el sustituto ("cuatro miembros", respuesta de c2) y viceversa.
    complete = router_complete(
        {
            "¿Color?": '{"answer": "cuatro miembros", "citations": ["frag-1"], "found": true}',
            "¿Tamaño?": '{"answer": "negro y amarillo", "citations": ["frag-3"], "found": true}',
        }
    )
    kwargs = run_kwargs(passes=["counterfactual"], max_calls=20)
    _, _, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        results_dir=tmp_path / "reader",
        run_id="cf-run",
        complete=complete,
        **kwargs,
    )
    counterfactual = summary["metrics"]["counterfactual"]
    assert counterfactual["n"] == 2
    assert counterfactual["reads_context"]["rate"] == 1.0
    assert counterfactual["discarded"] == 0
    assert "by_with_em" in counterfactual


async def test_counterfactual_type_mismatch_discards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    numeric = [
        ReaderCase(
            case_id="c1",
            article="Solo",
            paragraph_index=0,
            question="¿Cuántos?",
            answers=("308",),
            split="dev",
            document_key="xquad-es:Solo:0",
        ),
        ReaderCase(
            case_id="c2",
            article="Solo",
            paragraph_index=1,
            question="¿Color?",
            answers=("rojo",),
            split="dev",
            document_key="xquad-es:Solo:1",
        ),
    ]
    monkeypatch.setattr(reader_run, "load_dataset", lambda path: {"ok": True})
    monkeypatch.setattr(reader_run, "list_cases", lambda data, split: numeric)
    lines = [
        {
            "case_id": "c1",
            "query": "¿Cuántos?",
            "hits": [
                {"rank": 1, "chunk_id": "f1", "document_key": "d:0", "text": "cedieron 308 puntos"}
            ],
            "latency_ms": 1.0,
        }
    ]
    jsonl = tmp_path / f"retrieval-{CACHE_KEY}.jsonl"
    jsonl.write_text(json.dumps(lines[0], ensure_ascii=False) + "\n", encoding="utf-8")
    (tmp_path / f"retrieval-{CACHE_KEY}.meta.json").write_text(
        json.dumps(
            {
                "cache_key": CACHE_KEY,
                "configuration": "hybrid_rerank",
                "candidates": 30,
                "top_k": 5,
                "chunk_size": 800,
                "chunk_overlap": 120,
                "dataset": {"url": "u", "sha256": "s", "license": "l"},
                "sample": {"split": "dev", "seed": 1, "sample_size": 1, "cases": 1},
            }
        ),
        encoding="utf-8",
    )
    calls = []

    async def counting(prompt: RenderedPrompt) -> Completion:
        calls.append(prompt)
        return completion_for('{"answer": "x", "citations": [], "found": true}')

    kwargs = run_kwargs(passes=["counterfactual"], max_calls=10)
    _, _, summary = await run_bench(
        make_settings(),
        cache_path=jsonl,
        results_dir=tmp_path / "reader",
        run_id="mismatch-cf",
        complete=counting,
        **kwargs,
    )
    assert calls == []
    assert summary["metrics"]["counterfactual"]["discarded"] == 1
    assert summary["metrics"]["counterfactual"]["discarded_reasons"] == {"type mismatch": 1}
    assert summary["calls"]["completed"] == 0


async def test_counterfactual_guard_discards_without_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cases = [
        ReaderCase(
            case_id="c1",
            article="Solo",
            paragraph_index=0,
            question="¿Color?",
            answers=("negro",),
            split="dev",
            document_key="xquad-es:Solo:0",
        ),
        ReaderCase(
            case_id="c2",
            article="Solo",
            paragraph_index=1,
            question="¿Otro?",
            answers=("rojo",),
            split="dev",
            document_key="xquad-es:Solo:1",
        ),
    ]
    monkeypatch.setattr(reader_run, "load_dataset", lambda path: {"ok": True})
    monkeypatch.setattr(reader_run, "list_cases", lambda data, split: cases)
    lines = [
        {
            "case_id": "c1",
            "query": "¿Color?",
            # El sustituto ("rojo") ya está en el fragmento: la guarda descarta.
            "hits": [
                {"rank": 1, "chunk_id": "f1", "document_key": "d:0", "text": "era negro y rojo"}
            ],
            "latency_ms": 1.0,
        }
    ]
    jsonl = tmp_path / f"retrieval-{CACHE_KEY}.jsonl"
    jsonl.write_text(json.dumps(lines[0], ensure_ascii=False) + "\n", encoding="utf-8")
    (tmp_path / f"retrieval-{CACHE_KEY}.meta.json").write_text(
        json.dumps(
            {
                "cache_key": CACHE_KEY,
                "configuration": "hybrid_rerank",
                "candidates": 30,
                "top_k": 5,
                "chunk_size": 800,
                "chunk_overlap": 120,
                "dataset": {"url": "u", "sha256": "s", "license": "l"},
                "sample": {"split": "dev", "seed": 1, "sample_size": 1, "cases": 1},
            }
        ),
        encoding="utf-8",
    )
    calls = []

    async def counting(prompt: RenderedPrompt) -> Completion:
        calls.append(prompt)
        return completion_for('{"answer": "x", "citations": [], "found": true}')

    kwargs = run_kwargs(passes=["counterfactual"], max_calls=10)
    _, _, summary = await run_bench(
        make_settings(),
        cache_path=jsonl,
        results_dir=tmp_path / "reader",
        run_id="guard-run",
        complete=counting,
        **kwargs,
    )
    assert calls == []
    assert summary["metrics"]["counterfactual"]["discarded"] == 1
    assert summary["calls"]["completed"] == 0


async def test_dry_run_builds_plan_without_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_dataset(monkeypatch)
    cache = write_cache(tmp_path)
    calls: list[RenderedPrompt] = []

    async def counting(prompt: RenderedPrompt) -> Completion:
        calls.append(prompt)
        raise AssertionError("dry run must not call the model")

    _, _, summary = await run_bench(
        make_settings(),
        cache_path=cache,
        passes=["with", "without", "counterfactual"],
        max_calls=10,
        concurrency=1,
        seed=20261121,
        counterfactual_size=30,
        results_dir=tmp_path / "reader",
        run_id="dry-run",
        model_digest=None,
        dataset_path=None,
        complete=counting,
        allow_dirty=True,
        dry_run=True,
    )
    assert calls == []
    assert summary["dry_run"] is True
    assert summary["plan"]["jobs_total"] > 0


def read_cache_lines(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def check_review_sample(summary: dict[str, Any]) -> None:
    """Comprueba la muestra de revisión fuera de la corrutina del test."""
    sample_path = Path(str(summary["review_sample"]["path"]))
    assert sample_path.is_file()
    text = sample_path.read_text(encoding="utf-8")
    assert "# Muestra de revisión" in text and "- Pregunta:" in text
    assert "Fragmento principal" in text
