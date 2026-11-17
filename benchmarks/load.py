"""Arnés de carga y abuso en CPU local (fase F05c).

Reproduce de forma controlada el tráfico de la demo pública a través del
proxy y observa el comportamiento ante abuso, sin fijar ningún límite:
barrido de concurrencia con calentamiento, separación de 429 y 503,
recuperación tras saturación, ausencia de 500 y aislamiento por `owner_id`.

Fuente de consultas: solo el split dev de recuperación de
`eval/golden_set.yaml` (lectura). Cualquier identificador reservado
(split test, reserva NLI o borradores quemados `eut-*`/`euh2-*`) o
desconocido se rechaza antes de enviar la primera petición.

Uso típico contra la pila local::

    uv run python -m benchmarks.load --base-url http://127.0.0.1:18082 \\
        --profile search --levels 1,4,16,32 --requests 12 \\
        --output /tmp/f05c/summary.json --markdown benchmarks/load-cpu-2026-11-17.md

El arnés solo observa: nunca cambia límites, configuración ni código del
servicio. Si alguna ruta devuelve 500, el arnés lo registra y sale con
código 2; un 500 revela un posible defecto del servicio que esta fase no
debe corregir (ver informe F05c).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import platform
import resource
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml  # type: ignore[import-untyped]

logger = logging.getLogger("benchmarks.load")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GOLDEN = REPO_ROOT / "eval" / "golden_set.yaml"
NLI_TEST = REPO_ROOT / "eval" / "eu_nli_test.yaml"
RESERVED_PREFIXES = ("eut-", "euh2-")
EXIT_SERVER_ERROR = 2


class ReservedQueryError(ValueError):
    """Una consulta pedida no pertenece al split dev de recuperación."""


@dataclass(frozen=True)
class Query:
    """Consulta del split dev usable en carga."""

    id: str
    text: str


@dataclass
class Sample:
    """Resultado de una petición individual."""

    route: str
    status: int | None
    latency_ms: float
    retry_after: str | None = None
    capacity_wait_ms: float | None = None
    results: int | None = None
    error: str | None = None


@dataclass
class Settings:
    """Parámetros de ejecución del arnés (solo lectura del servicio)."""

    base_url: str
    profile: str
    levels: list[int] = field(default_factory=list)
    requests_per_level: int = 12
    warmup: int = 4
    top_k: int = 5
    candidates: int = 30
    rerank: bool = True
    owner_id: str = "ue-publico"
    alien_owner_id: str = "intruso-f05c"
    api_key: str | None = None
    cooldown_s: float = 0.0
    timeout_s: float = 180.0
    verify_chunks: int = 3


def percentile(sorted_values: list[float], pct: float) -> float | None:
    """Percentil por rango más cercano; `None` si no hay muestras."""
    if not sorted_values:
        return None
    if not 0 <= pct <= 100:
        raise ValueError("pct must be within [0, 100]")
    rank = max(1, -(-len(sorted_values) * pct // 100))
    return sorted_values[int(rank) - 1]


def _read_ids(path: Path, id_key: str = "id") -> tuple[set[str], set[str]]:
    """Separa identificadores dev y test de un YAML de consultas."""
    dev: set[str] = set()
    reserved: set[str] = set()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError:
        return dev, reserved
    if not isinstance(data, list):
        return dev, reserved
    for case in data:
        if not isinstance(case, dict):
            continue
        case_id = case.get(id_key)
        if not isinstance(case_id, str) or not case_id:
            continue
        if case.get("split") == "dev":
            dev.add(case_id)
        else:
            reserved.add(case_id)
    return dev, reserved


def load_dev_queries(golden_path: Path) -> tuple[list[Query], set[str]]:
    """Carga las consultas del split dev y los identificadores reservados.

    Solo lectura de `eval/`: el split dev de `golden_set.yaml` más la
    reserva de `eu_nli_test.yaml`. Todo lo demás (test, quemados) queda
    en el conjunto reservado que `resolve_workload` rechaza.
    """
    try:
        data = yaml.safe_load(golden_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ReservedQueryError(f"no se pudo leer {golden_path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ReservedQueryError(f"{golden_path} sin consultas")
    dev: list[Query] = []
    reserved: set[str] = set()
    for case in data:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str):
            continue
        if case.get("split") == "dev" and isinstance(case.get("query"), str):
            dev.append(Query(id=str(case["id"]), text=str(case["query"])))
        else:
            reserved.add(str(case["id"]))
    _, nli_reserved = _read_ids(NLI_TEST)
    reserved |= nli_reserved
    if not dev:
        raise ReservedQueryError(f"{golden_path} sin consultas en split dev")
    return dev, reserved


def resolve_workload(
    golden_path: Path, only_ids: list[str] | None
) -> tuple[list[Query], list[str]]:
    """Resuelve las consultas a ejecutar; rechaza reservas y desconocidos."""
    dev, reserved = load_dev_queries(golden_path)
    by_id = {query.id: query for query in dev}
    if not only_ids:
        return dev, sorted(query.id for query in dev)
    workload: list[Query] = []
    for wanted in only_ids:
        if wanted in reserved or wanted.startswith(RESERVED_PREFIXES):
            raise ReservedQueryError(f"consulta reservada rechazada: {wanted}")
        if wanted not in by_id:
            raise ReservedQueryError(f"consulta desconocida o fuera de dev: {wanted}")
        workload.append(by_id[wanted])
    return workload, list(only_ids)


def _codes(samples: list[Sample]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        key = str(sample.status) if sample.status is not None else "error"
        counts[key] = counts.get(key, 0) + 1
    return counts


def describe(samples: list[Sample]) -> dict[str, object]:
    """Agrega muestras en códigos, latencias y `capacity_wait` observado."""
    latencies = sorted(s.latency_ms for s in samples if s.status is not None)
    waits = sorted(s.capacity_wait_ms for s in samples if s.capacity_wait_ms is not None)
    retry_after = sum(1 for s in samples if s.retry_after is not None)
    limited = [s for s in samples if s.status in (429, 503)]
    limited_with_retry_after = sum(1 for s in limited if s.retry_after is not None)
    retry_after_values = sorted({s.retry_after for s in limited if s.retry_after is not None})[:10]
    return {
        "requests": len(samples),
        "codes": _codes(samples),
        "with_retry_after": retry_after,
        "limited_with_retry_after": limited_with_retry_after,
        "limited_retry_after_values": retry_after_values,
        "latency_ms": {
            "min": min(latencies) if latencies else None,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
            "max": max(latencies) if latencies else None,
        },
        "capacity_wait_ms": {
            "n": len(waits),
            "p50": percentile(waits, 50),
            "p95": percentile(waits, 95),
        },
    }


def hardware_info() -> dict[str, object]:
    """Describe el equipo local (CPU esperado en F05c, sin GPU)."""
    mem_mib: float | None = None
    cpu_model: str | None = None
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("model name") and cpu_model is None:
                cpu_model = line.split(":", 1)[1].strip()
    except OSError:
        cpu_model = None
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith("MemTotal:"):
                mem_mib = int(line.split()[1]) / 1024
                break
    except (OSError, ValueError, IndexError):
        mem_mib = None
    return {
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "cpu_count": os.cpu_count(),
        "mem_total_mib": round(mem_mib, 1) if mem_mib is not None else None,
        "device": "cpu",
        "gpu": None,
    }


def git_info() -> dict[str, object]:
    """Commit y limpieza del árbol (o desconocido fuera de Git)."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        ).stdout.strip()
        dirty = (
            subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                check=True,
                cwd=REPO_ROOT,
            ).stdout.strip()
            != ""
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.SubprocessError):
        return {"commit": "unknown", "dirty": "unknown"}


def _extract_search(
    payload: object, latency_ms: float, status: int, headers: httpx.Headers
) -> Sample:
    capacity: float | None = None
    results: int | None = None
    if isinstance(payload, dict):
        timings = payload.get("timings_ms")
        if isinstance(timings, dict) and isinstance(timings.get("capacity_wait"), (int, float)):
            capacity = float(timings["capacity_wait"])
        if isinstance(payload.get("results"), list):
            results = len(payload["results"])
    return Sample(
        route="search",
        status=status,
        latency_ms=latency_ms,
        retry_after=headers.get("retry-after"),
        capacity_wait_ms=capacity,
        results=results,
    )


async def search_once(
    client: httpx.AsyncClient, settings: Settings, query: Query, owner_id: str | None
) -> tuple[Sample, list[str]]:
    """Una búsqueda; devuelve la muestra y hasta N `chunk_id` válidos."""
    body: dict[str, object] = {
        "query": query.text,
        "top_k": settings.top_k,
        "candidates": settings.candidates,
        "rerank": settings.rerank,
    }
    if owner_id is not None:
        body["owner_id"] = owner_id
    started = time.perf_counter()
    try:
        response = await client.post("/v1/search", json=body)
        latency = (time.perf_counter() - started) * 1000
        try:
            payload: object = response.json()
        except ValueError:
            payload = None
        sample = _extract_search(payload, latency, response.status_code, response.headers)
        chunk_ids: list[str] = []
        if response.status_code == 200 and isinstance(payload, dict):
            items = payload.get("results")
            if isinstance(items, list):
                for item in items[: settings.verify_chunks]:
                    if isinstance(item, dict) and isinstance(item.get("chunk_id"), str):
                        chunk_ids.append(str(item["chunk_id"]))
        return sample, chunk_ids
    except httpx.HTTPError as exc:
        latency = (time.perf_counter() - started) * 1000
        return Sample(route="search", status=None, latency_ms=latency, error=str(exc)), []


async def verify_once(
    client: httpx.AsyncClient,
    settings: Settings,
    answer: str,
    chunk_ids: list[str],
    owner_id: str | None,
) -> Sample:
    """Una verificación sobre los fragmentos de la búsqueda previa."""
    body: dict[str, object] = {"answer": answer, "chunk_ids": chunk_ids}
    if owner_id is not None:
        body["owner_id"] = owner_id
    started = time.perf_counter()
    try:
        response = await client.post("/v1/verify", json=body)
        latency = (time.perf_counter() - started) * 1000
        return Sample(
            route="verify",
            status=response.status_code,
            latency_ms=latency,
            retry_after=response.headers.get("retry-after"),
        )
    except httpx.HTTPError as exc:
        latency = (time.perf_counter() - started) * 1000
        return Sample(route="verify", status=None, latency_ms=latency, error=str(exc))


async def iteration(
    client: httpx.AsyncClient, settings: Settings, query: Query, owner_id: str
) -> list[Sample]:
    """Una iteración del perfil: búsqueda, y verificación si toca."""
    sample, chunk_ids = await search_once(client, settings, query, owner_id)
    samples = [sample]
    if settings.profile == "mixed" and sample.status == 200 and chunk_ids:
        samples.append(await verify_once(client, settings, query.text, chunk_ids, owner_id))
    return samples


async def run_level(
    settings: Settings,
    workload: list[Query],
    concurrency: int,
    count: int,
    label: str,
) -> list[Sample]:
    """Ejecuta `count` iteraciones con el tope de concurrencia dado."""

    async def worker(
        client: httpx.AsyncClient, sem: asyncio.Semaphore, query: Query
    ) -> list[Sample]:
        async with sem:
            return await iteration(client, settings, query, settings.owner_id)

    queries = [workload[i % len(workload)] for i in range(count)]
    client_headers = {"X-API-Key": settings.api_key} if settings.api_key else None
    async with httpx.AsyncClient(
        base_url=settings.base_url, timeout=settings.timeout_s, headers=client_headers
    ) as client:
        sem = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(
            *(worker(client, sem, query) for query in queries),
            return_exceptions=False,
        )
    samples: list[Sample] = []
    for item in results:
        samples.extend(item)
    logger.info("%s concurrencia=%d peticiones=%d", label, concurrency, len(samples))
    return samples


async def drive(
    settings: Settings, workload: list[Query], query_ids: list[str]
) -> dict[str, object]:
    """Calentamiento, barrido, recuperación y aislamiento. Solo observa."""
    started_at = datetime.now(UTC).isoformat()
    begun = time.perf_counter()
    levels: list[dict[str, object]] = []
    all_samples: list[Sample] = []

    if settings.warmup > 0:
        await run_level(settings, workload, 1, min(settings.warmup, len(workload)), "warmup")
    for concurrency in settings.levels:
        samples = await run_level(
            settings, workload, concurrency, settings.requests_per_level, "sweep"
        )
        all_samples.extend(samples)
        entry: dict[str, object] = {"concurrency": concurrency}
        entry.update(describe(samples))
        by_route = {
            route: describe([s for s in samples if s.route == route])
            for route in ("search", "verify")
            if any(s.route == route for s in samples)
        }
        if settings.profile == "mixed" and "verify" not in by_route:
            by_route["verify"] = {
                "requests": 0,
                "codes": {},
                "with_retry_after": 0,
                "limited_with_retry_after": 0,
                "latency_ms": {"min": None, "p50": None, "p95": None, "max": None},
                "capacity_wait_ms": {"n": 0, "p50": None, "p95": None},
                "note": "sin muestras: la API no expone timings en /v1/verify",
            }
        entry["by_route"] = by_route
        levels.append(entry)

    recovery = await run_level(settings, workload, 1, 5, "recovery")
    all_samples.extend(recovery)

    if settings.cooldown_s > 0:
        logger.info("pausa de %.0f s antes de recuperación y aislamiento", settings.cooldown_s)
        await asyncio.sleep(settings.cooldown_s)
        cooldown_recovery = await run_level(settings, workload, 1, 5, "post-cooldown")
        post: dict[str, object] = {"concurrency": 1, "cooldown_s": settings.cooldown_s}
        post.update(describe(cooldown_recovery))
        levels.append(post)
        all_samples.extend(cooldown_recovery)

    isolation_headers = {"X-API-Key": settings.api_key} if settings.api_key else None
    async with httpx.AsyncClient(
        base_url=settings.base_url, timeout=settings.timeout_s, headers=isolation_headers
    ) as client:
        alien_search, _ = await search_once(client, settings, workload[0], settings.alien_owner_id)
        alien_verify = Sample(route="verify", status=None, latency_ms=0.0)
        if settings.profile == "mixed":
            probe, chunk_ids = await search_once(client, settings, workload[0], settings.owner_id)
            if probe.status == 200 and chunk_ids:
                alien_verify = await verify_once(
                    client, settings, workload[0].text, chunk_ids, settings.alien_owner_id
                )
    isolation = {
        "alien_owner_id": settings.alien_owner_id,
        "alien_search_status": alien_search.status,
        "alien_search_results": alien_search.results,
        "alien_verify_status": alien_verify.status,
        "ok": alien_search.status == 200
        and (alien_search.results == 0)
        and (alien_verify.status in (None, 200)),
    }
    all_samples.extend([alien_search, alien_verify])

    codes = _codes(all_samples)
    summary: dict[str, object] = {
        "tool": "benchmarks/load.py",
        "phase": "F05c",
        "started_at": started_at,
        "duration_s": round(time.perf_counter() - begun, 2),
        "git": git_info(),
        "hardware": hardware_info(),
        "software": {
            "python": platform.python_version(),
            "httpx": httpx.__version__,
        },
        "config": {
            "base_url_host": settings.base_url.split("@")[-1],
            "profile": settings.profile,
            "warmup": settings.warmup,
            "cooldown_s": settings.cooldown_s,
            "levels": settings.levels,
            "requests_per_level": settings.requests_per_level,
            "top_k": settings.top_k,
            "candidates": settings.candidates,
            "rerank": settings.rerank,
            "owner_id": settings.owner_id,
            "timeout_s": settings.timeout_s,
        },
        "query_source": {
            "golden_set": str(DEFAULT_GOLDEN.relative_to(REPO_ROOT)),
            "split": "dev",
            "sha256": _sha256(DEFAULT_GOLDEN),
            "count": len(workload),
            "ids": query_ids,
        },
        "levels": levels,
        "recovery": describe(recovery),
        "isolation": isolation,
        "totals": describe(all_samples),
        "saw_429": codes.get("429", 0) > 0,
        "saw_503": codes.get("503", 0) > 0,
        "saw_500": codes.get("500", 0) > 0,
        "client_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "notes": [
            "429 = cuota o límite por IP (proxy o app); 503 = capacidad de "
            "inferencia o dependencia caída. La app no devuelve 500 en "
            "condiciones normales: search.py y verify.py convierten los "
            "fallos internos en 503.",
            "/v1/verify no expone timings_ms: capacity_wait por ruta solo "
            "se observa en search; verify registra latencia de cliente.",
            "Latencia en CPU no vale como cifra pública (diseño §10, F05d).",
        ],
    }
    return summary


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_markdown(summary: dict[str, object]) -> str:
    """Resumen legible con hardware, configuración y resultados."""

    def row(level: dict[str, object]) -> str:
        latency = level["latency_ms"]
        assert isinstance(latency, dict)
        codes = level["codes"]
        assert isinstance(codes, dict)
        order = ["200", "429", "503", "500", "error"]
        code_cells = "/".join(f"{c}={codes.get(c, 0)}" for c in order if c in codes)
        return (
            f"| {level['concurrency']} | {level['requests']} | {code_cells} | "
            f"{level['with_retry_after']} | {latency['p50']} | {latency['p95']} |"
        )

    config = summary["config"]
    assert isinstance(config, dict)
    hardware = summary["hardware"]
    assert isinstance(hardware, dict)
    git = summary["git"]
    assert isinstance(git, dict)
    source = summary["query_source"]
    assert isinstance(source, dict)
    software = summary["software"]
    assert isinstance(software, dict)
    totals = summary["totals"]
    assert isinstance(totals, dict)
    isolation = summary["isolation"]
    assert isinstance(isolation, dict)
    levels = summary["levels"]
    assert isinstance(levels, list)
    lines = [
        "# Resumen de carga y abuso en CPU local (F05c)",
        "",
        "Fecha: "
        + str(summary["started_at"])
        + ". Esta prueba mide comportamiento ante abuso, no calidad.",
        "",
        "## Hardware y software",
        "",
        f"- CPU: {hardware['cpu_model']} ({hardware['cpu_count']} núcleos)",
        f"- RAM: {hardware['mem_total_mib']} MiB; dispositivo de inferencia: cpu",
        f"- Commit: {git['commit']} (árbol sucio: {git['dirty']})",
        f"- Python {software['python']}, httpx {software['httpx']}",
        "",
        "## Configuración (sin cambios de límites)",
        "",
        f"- Perfil: {config['profile']}; base: {config['base_url_host']} (vía proxy)",
        f"- Calentamiento: {config['warmup']}; niveles: {config['levels']} "
        f"x {config['requests_per_level']} peticiones",
        f"- Búsqueda: top_k={config['top_k']}, candidates={config['candidates']}, "
        f"rerank={config['rerank']}; owner_id={config['owner_id']}",
        f"- Consultas: {source['count']} del split dev de {source['golden_set']} "
        f"(sha256 `{str(source['sha256'])[:16]}…`); reserva rechazada por el arnés",
        "",
        "## Resultados por concurrencia",
        "",
        "| Concurrencia | Peticiones | Códigos | Retry-After | p50 (ms) | p95 (ms) |",
        "|---|---|---|---|---|---|",
    ]
    for level in levels:
        assert isinstance(level, dict)
        lines.append(row(level))
    lines += [
        "",
        "## Capacidad, recuperación y aislamiento",
        "",
        f"- 429 observados: {summary['saw_429']}; 503 observados: {summary['saw_503']}; "
        f"500 observados: {summary['saw_500']} (esperado: ninguno).",
        f"- Respuestas 429/503 con `Retry-After` (totales): "
        f"{totals['limited_with_retry_after']}. "
        "Nginx añade `Retry-After: 60` también en 200 (ruido conocido, diseño §7).",
        f"- Recuperación tras saturación: {summary['recovery']}.",
        f"- Aislamiento intacto: {isolation['ok']} "
        f"(búsqueda ajena: {isolation['alien_search_status']} con "
        f"{isolation['alien_search_results']} resultados).",
        "",
        "## Límites",
        "",
        "- Muestra pequeña (split dev); latencia en CPU, sin valor público.",
        "- El arnés no fija límites: F05d los decide con datos de GPU.",
    ]
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define la interfaz de línea de órdenes del arnés."""
    parser = argparse.ArgumentParser(
        description="Arnés de carga F05c: barrido de concurrencia sin cambiar límites."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:18082")
    parser.add_argument("--profile", choices=("search", "mixed"), default="search")
    parser.add_argument(
        "--levels",
        default="1,4,16,32",
        help="concurrencias separadas por comas, p. ej. 1,4,16,32",
    )
    parser.add_argument("--requests", type=int, default=12, dest="requests_per_level")
    parser.add_argument("--warmup", type=int, default=4)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=30)
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--owner-id", default="ue-publico")
    parser.add_argument("--alien-owner-id", default="intruso-f05c")
    parser.add_argument(
        "--api-key",
        default=None,
        help="clave X-API-Key (solo para la API interna; el proxy la inyecta)",
    )
    parser.add_argument("--golden-set", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--query-ids", default="", help="ids dev separados por comas")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument(
        "--cooldown",
        type=float,
        default=0.0,
        help="pausa en segundos antes de las sondas de recuperación y "
        "aislamiento (renueva la cuota por clave sin tocar límites)",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--markdown", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada: resuelve carga, ejecuta y escribe el resumen."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        only = [part.strip() for part in args.query_ids.split(",") if part.strip()] or None
        workload, query_ids = resolve_workload(args.golden_set, only)
    except ReservedQueryError as exc:
        logger.error("carga rechazada: %s", exc)
        return 1
    try:
        levels = [int(part) for part in args.levels.split(",") if part.strip()]
    except ValueError:
        logger.error("niveles inválidos: %s", args.levels)
        return 1
    if not levels or any(level < 1 for level in levels):
        logger.error("niveles inválidos: %s", args.levels)
        return 1
    settings = Settings(
        base_url=args.base_url.rstrip("/"),
        profile=args.profile,
        levels=levels,
        requests_per_level=args.requests_per_level,
        warmup=args.warmup,
        top_k=args.top_k,
        candidates=args.candidates,
        rerank=not args.no_rerank,
        owner_id=args.owner_id,
        alien_owner_id=args.alien_owner_id,
        api_key=args.api_key,
        timeout_s=args.timeout,
        cooldown_s=args.cooldown,
    )
    try:
        summary = asyncio.run(drive(settings, workload, query_ids))
    except httpx.HTTPError as exc:
        logger.error("sin conexión con %s: %s", settings.base_url, exc)
        return 1
    payload = json.dumps(summary, indent=2, default=str)
    if args.output is not None:
        args.output.write_text(payload + "\n", encoding="utf-8")
        logger.info("resumen JSON en %s", args.output)
    else:
        sys.stdout.write(payload + "\n")
    if args.markdown is not None:
        args.markdown.write_text(render_markdown(summary), encoding="utf-8")
        logger.info("resumen Markdown en %s", args.markdown)
    if summary["saw_500"]:
        logger.error("se observaron 500: posible defecto del servicio (no corregido en F05c)")
        return EXIT_SERVER_ERROR
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
