"""Tests unitarios del arnés de carga F05c. Sin red ni modelos."""

from pathlib import Path

import pytest
from load import (
    Query,
    ReservedQueryError,
    Sample,
    describe,
    percentile,
    render_markdown,
    resolve_workload,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = REPO_ROOT / "eval" / "golden_set.yaml"


def test_percentile_empty_returns_none() -> None:
    assert percentile([], 50) is None


def test_percentile_single_value() -> None:
    assert percentile([7.0], 50) == 7.0
    assert percentile([7.0], 95) == 7.0


def test_percentile_nearest_rank() -> None:
    values = [float(v) for v in (10, 20, 30, 40)]
    assert percentile(values, 50) == 20.0
    assert percentile(values, 95) == 40.0


def test_percentile_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        percentile([1.0], 101)


def test_workload_defaults_to_all_dev() -> None:
    workload, ids = resolve_workload(GOLDEN, None)
    assert {query.id for query in workload} == set(ids)
    assert len(workload) == 14
    assert "q001" in ids and "q014" in ids


def test_workload_accepts_dev_subset() -> None:
    workload, _ = resolve_workload(GOLDEN, ["q001", "q006"])
    assert [query.id for query in workload] == ["q001", "q006"]
    assert all(isinstance(query, Query) and query.text.strip() for query in workload)


def test_workload_rejects_test_split() -> None:
    with pytest.raises(ReservedQueryError):
        resolve_workload(GOLDEN, ["q015"])


def test_workload_rejects_unknown_id() -> None:
    with pytest.raises(ReservedQueryError):
        resolve_workload(GOLDEN, ["q999"])


def test_workload_rejects_burnt_prefixes() -> None:
    for burnt in ("eut-001", "euh2-014"):
        with pytest.raises(ReservedQueryError):
            resolve_workload(GOLDEN, [burnt])


def test_describe_separates_429_and_503() -> None:
    samples = [
        Sample(route="search", status=200, latency_ms=100.0, capacity_wait_ms=5.0),
        Sample(route="search", status=429, latency_ms=10.0, retry_after="60"),
        Sample(route="search", status=503, latency_ms=12.0, retry_after="5"),
        Sample(route="search", status=503, latency_ms=14.0),
    ]
    stats = describe(samples)
    assert stats["codes"] == {"200": 1, "429": 1, "503": 2}
    assert stats["with_retry_after"] == 2
    assert stats["limited_with_retry_after"] == 2
    assert stats["limited_retry_after_values"] == ["5", "60"]
    latency = stats["latency_ms"]
    assert isinstance(latency, dict)
    assert latency["p50"] == 12.0
    assert latency["p95"] == 100.0
    waits = stats["capacity_wait_ms"]
    assert isinstance(waits, dict)
    assert waits == {"n": 1, "p50": 5.0, "p95": 5.0}


def test_describe_empty() -> None:
    stats = describe([])
    assert stats["requests"] == 0
    assert stats["codes"] == {}
    latency = stats["latency_ms"]
    assert isinstance(latency, dict)
    assert latency["p50"] is None


def test_render_markdown_schema() -> None:
    level_samples = [Sample(route="search", status=200, latency_ms=50.0)]
    described = describe(level_samples)
    level = {"concurrency": 1, **described}
    summary = {
        "started_at": "2026-11-17T00:00:00+00:00",
        "git": {"commit": "abc", "dirty": False},
        "hardware": {"cpu_model": "CPU de prueba", "cpu_count": 4, "mem_total_mib": 1024.0},
        "software": {"python": "3.12.0", "httpx": "0.28.1"},
        "config": {
            "profile": "search",
            "base_url_host": "http://127.0.0.1:18082",
            "warmup": 1,
            "levels": [1],
            "requests_per_level": 1,
            "top_k": 5,
            "candidates": 30,
            "rerank": True,
            "owner_id": "ue-publico",
        },
        "query_source": {"count": 14, "golden_set": "eval/golden_set.yaml", "sha256": "0" * 64},
        "levels": [level],
        "recovery": described,
        "totals": {**described, "limited_with_retry_after": 0},
        "isolation": {
            "ok": True,
            "alien_search_status": 200,
            "alien_search_results": 0,
        },
        "saw_429": False,
        "saw_503": False,
        "saw_500": False,
    }
    text = render_markdown(summary)
    for section in (
        "## Hardware y software",
        "## Configuración",
        "## Resultados por concurrencia",
        "## Capacidad, recuperación y aislamiento",
        "## Límites",
    ):
        assert section in text
    assert "| 1 |" in text
