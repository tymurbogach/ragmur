"""Etapas C01: estática (puerta compartida) y suite completa en Skynet.

La etapa estática replica la primera llamada de la puerta compartida y nunca
invoca a Docker. La etapa suite levanta PostgreSQL y Qdrant desechables,
aplica migraciones, ejecuta los 382 tests y limpia siempre, en éxito, fallo
y cancelación.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from eval.phase1 import skynet
from eval.phase1.runner import REPO_ROOT, STAGE_TIMEOUTS, write_json

NLI_TIMEOUT_FALLBACK = 5400.0
SEARCH_TIMEOUT_FALLBACK = 10800.0

EXPECTED_PASSED_MIN = 376
EXPECTED_SKIPPED = 6

# Los 7 xfail estrictos de C02 (defectos conocidos D1-D7): aparecen como
# saltos en el XML de junit. Un xfail que pase de verdad falla por
# definición (estricto), así que estar en esta lista nunca oculta un arreglo.
KNOWN_XFAIL = frozenset(
    {
        "tests.known_defects.test_d1::test_d1_qdrant_request_filters_by_tenant",
        "tests.known_defects.test_d2::test_d2_docx_table_text_does_not_reject_body",
        "tests.known_defects.test_d3::test_d3_spanish_heading_style_detected",
        "tests.known_defects.test_d4::test_d4_hash_in_code_block_is_not_a_title",
        "tests.known_defects.test_d5::test_d5_chunks_start_at_word_boundaries",
        "tests.known_defects.test_d6::test_d6_sentence_splitter_abbreviations_citations_lists",
        "tests.known_defects.test_d7::test_d7_support_beats_single_contradiction",
    }
)
# Los 6 saltos registrados el 2026-11-22: dependen del entorno (modelos reales
# o proveedor vivo ausentes, caché de tokenizer opcional). Un salto fuera de
# esta lista es un cambio de comportamiento y falla; que falte uno porque el
# entorno lo permite (p. ej. la caché presente) no es un fallo.
KNOWN_SKIPPABLE = frozenset(
    {
        "tests.llm.test_provider_live::test_live_completion_returns_text_and_usage",
        "tests.verification.test_real_nli::test_real_nli_supports_contradicts_and_marks_unknown",
        "tests.verification.test_real_nli::test_real_nli_coreference_without_mitigation",
        "tests.verification.test_nli::test_long_hypothesis_with_cached_tokenizer",
        "tests.retrieval.test_benchmark_cpu::test_search_p95_with_real_cpu_models",
        "tests.retrieval.test_real_models::"
        "test_real_models_find_semantic_and_rare_terms_with_isolation",
    }
)


def static_command() -> list[str]:
    """Orden de la puerta compartida (llamada 1). Sin Docker por diseño."""
    return [
        "bash",
        "-c",
        "uv run ruff check . && uv run ruff format --check . && uv run mypy"
        " && uv run python -m eval.check_nli_leak",
    ]


def static_env() -> dict[str, str]:
    """Entorno de la etapa estática: Docker local prohibido."""
    env = dict(os.environ)
    env["DOCKER_HOST"] = "unix:///nonexistent"
    return env


def run_static(directory: Path, timeout: float = STAGE_TIMEOUTS["static"]) -> dict[str, Any]:
    """Ejecuta ruff, formato, mypy y el control anti-fuga NLI."""
    log_path = directory / "static.log"
    json_path = directory / "static.json"
    started = time.time()
    try:
        with log_path.open("wb") as handle:
            completed = subprocess.run(
                static_command(),
                cwd=REPO_ROOT,
                env=static_env(),
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        result: dict[str, Any] = {
            "state": "infra_error",
            "reason": f"plazo de etapa agotado ({timeout:g} s)",
            "log": str(log_path),
            "json": str(json_path),
        }
        write_json(json_path, result)
        return result
    except OSError as exc:
        result = {
            "state": "infra_error",
            "reason": f"no se pudo lanzar la etapa: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
        write_json(json_path, result)
        return result
    state = "passed" if completed.returncode == 0 else "hard_failed"
    result = {
        "state": state,
        "exit": completed.returncode,
        "elapsed_s": round(time.time() - started, 1),
        "log": str(log_path),
        "json": str(json_path),
    }
    write_json(json_path, result)
    return result


def ingest_command(out: Path) -> list[str]:
    """Orden de la etapa ingest: 100.000 documentos con semilla fija."""
    return [
        "uv",
        "run",
        "python",
        "-m",
        "eval.phase1.ingest",
        "--out",
        str(out),
    ]


def ingest_env() -> dict[str, str]:
    """Entorno de la etapa ingest: solo cómputo local, sin Docker."""
    env = dict(os.environ)
    env["DOCKER_HOST"] = "unix:///nonexistent"
    env["HF_HUB_OFFLINE"] = "1"
    return env


def map_ingest_summary(summary: dict[str, Any]) -> tuple[str, str]:
    """Traduce el resumen de ingest a estado: fallos reales son duros.

    Un fallo real (pérdida de texto, span o dueño erróneo, cuelgue o
    excepción no controlada) sale como ``hard_failed`` con su semilla.
    Medir el fallo no bloquea la etapa: el resumen queda escrito.
    """
    issues = summary.get("issues")
    if not isinstance(issues, list):
        return "infra_error", "resumen de ingest ilegible"
    if issues:
        seed = summary.get("seed")
        return "hard_failed", f"{len(issues)} fallos reales con semilla {seed}"
    return "passed", (
        f"{summary.get('docs', 0)} documentos, {summary.get('chunks', 0)} chunks sin fallos"
    )


def run_ingest(
    directory: Path,
    timeout: float = STAGE_TIMEOUTS["ingest"],
) -> dict[str, Any]:
    """Ejecuta la etapa ingest en el portátil y publica sus fallos reales."""
    log_path = directory / "ingest.log"
    json_path = directory / "ingest.json"
    out_dir = directory / "ingest"
    started = time.time()
    try:
        with log_path.open("wb") as handle:
            completed = subprocess.run(
                ingest_command(out_dir),
                cwd=REPO_ROOT,
                env=ingest_env(),
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        result: dict[str, Any] = {
            "state": "infra_error",
            "reason": f"plazo de etapa agotado ({timeout:g} s)",
            "log": str(log_path),
            "json": str(json_path),
        }
        write_json(json_path, result)
        return result
    except OSError as exc:
        result = {
            "state": "infra_error",
            "reason": f"no se pudo lanzar la etapa: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
        write_json(json_path, result)
        return result
    summary_path = out_dir / "summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "state": "infra_error",
            "reason": f"sin resumen de ingest: {exc}",
            "exit": completed.returncode,
            "log": str(log_path),
            "json": str(json_path),
        }
        write_json(json_path, result)
        return result
    if not isinstance(summary, dict):
        result = {
            "state": "infra_error",
            "reason": "resumen de ingest ilegible",
            "exit": completed.returncode,
            "log": str(log_path),
            "json": str(json_path),
        }
        write_json(json_path, result)
        return result
    state, reason = map_ingest_summary(summary)
    if completed.returncode not in (0, 1):
        state, reason = "infra_error", f"la etapa salió con {completed.returncode}"
    elif completed.returncode == 1 and state == "passed":
        state, reason = "infra_error", "salida 1 sin fallos en el resumen"
    elif completed.returncode == 0 and state != "passed":
        state, reason = "infra_error", "salida 0 con fallos en el resumen"
    result = {
        "state": state,
        "reason": reason,
        "exit": completed.returncode,
        "elapsed_s": round(time.time() - started, 1),
        "summary": summary,
        "log": str(log_path),
        "json": str(json_path),
    }
    write_json(json_path, result)
    return result


def _qdrant_ready(url: str, deadline: float) -> bool:
    """Espera al /healthz de Qdrant a través del túnel."""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=5) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(1.0)
    return False


def suite_env(pg_url: str, q_url: str, hmac_secret: str, host: str | None) -> dict[str, str]:
    """Entorno de la suite: servicios desechables y Docker local prohibido."""
    env = dict(os.environ)
    env["DOCKER_HOST"] = "unix:///nonexistent"
    env["HF_HUB_OFFLINE"] = "1"
    env["API_KEY_HMAC_SECRET"] = hmac_secret
    env["DATABASE_URL"] = pg_url
    env["QDRANT_URL"] = q_url
    if host:
        env["RAGMUR_TEST_SSH_HOST"] = host
    else:
        env.pop("RAGMUR_TEST_SSH_HOST", None)
    return env


def parse_junit(path: Path) -> dict[str, Any]:
    """Lee el resumen de pytest (pasados, fallos, errores, saltos e ids)."""
    root = ElementTree.parse(str(path)).getroot()
    suites = root.findall("testsuite") or ([root] if root.tag == "testsuite" else [])
    tests = failures = errors = skipped = 0
    skipped_ids: list[str] = []
    for suite in suites:
        tests += int(float(suite.get("tests", 0)))
        failures += int(float(suite.get("failures", 0)))
        errors += int(float(suite.get("errors", 0)))
        skipped += int(float(suite.get("skipped", 0)))
        for case in suite.iter("testcase"):
            if case.find("skipped") is not None:
                name = f"{case.get('classname', '')}::{case.get('name', '')}"
                skipped_ids.append(name)
    failed = failures + errors
    return {
        "tests": tests,
        "passed": tests - failed - skipped,
        "failed": failed,
        "skipped": skipped,
        "skipped_ids": sorted(skipped_ids),
    }


def _unknown_skips(skipped_ids: object) -> list[str]:
    """Saltos fuera de las listas registradas (formato con puntos o con barras)."""
    if not isinstance(skipped_ids, list):
        return ["<lista de saltos ilegible>"]
    known = KNOWN_SKIPPABLE | KNOWN_XFAIL
    unknown: list[str] = []
    for raw in skipped_ids:
        if not isinstance(raw, str):
            unknown.append(str(raw))
            continue
        if raw in known:
            continue
        normalized = raw.replace("/", ".")
        if normalized not in known and not any(
            normalized.endswith(item) or item.endswith(normalized) for item in known
        ):
            unknown.append(raw)
    return unknown


def suite_acceptance(counts: dict[str, Any]) -> tuple[str, str]:
    """Aplica el criterio C01: 0 fallos, al menos 376 pasados y sin saltos nuevos.

    Devuelve (estado, motivo). Es fallo duro, no de calidad: un desvío indica
    que el instrumento cambió, no que la calidad bajó.
    """
    failed = int(counts.get("failed", -1))
    passed = int(counts.get("passed", -1))
    if failed != 0:
        return "hard_failed", f"hay {failed} fallos"
    if passed < EXPECTED_PASSED_MIN:
        return "hard_failed", f"solo {passed} pasados, se esperan {EXPECTED_PASSED_MIN}"
    unknown = _unknown_skips(counts.get("skipped_ids"))
    if unknown:
        return "hard_failed", f"salto nuevo: {', '.join(unknown)}"
    skipped = int(counts.get("skipped", -1))
    return "passed", f"0 fallos, {passed} pasados y {skipped} saltos conocidos"


def run_suite(
    directory: Path,
    ssh_host: str | None,
    note_tunnels: Callable[[list[int]], None] | None = None,
    timeout: float = STAGE_TIMEOUTS["suite"],
) -> dict[str, Any]:
    """Ejecuta la suite completa contra servicios desechables y limpia siempre."""
    log_path = directory / "suite.log"
    json_path = directory / "suite.json"
    junit_path = directory / "suite-junit.xml"
    run_id = directory.name
    deadline = time.time() + timeout
    tunnels: list[Any] = []
    network = ""
    pg_name = ""
    q_name = ""
    password = secrets.token_hex(16)
    hmac_secret = secrets.token_hex(32)
    result: dict[str, Any] = {"state": "infra_error", "reason": "sin empezar"}
    try:
        network = skynet.create_network(ssh_host, run_id)
        pg_name = skynet.run_postgres(ssh_host, run_id, network, password)
        q_name = skynet.run_qdrant(ssh_host, run_id, network)
        pg_remote = skynet.remote_port(ssh_host, pg_name, 5432)
        q_remote = skynet.remote_port(ssh_host, q_name, 6333)
        if ssh_host is None:
            pg_local, q_local = pg_remote, q_remote
        else:
            pg_tunnel, pg_local = skynet.open_tunnel(ssh_host, pg_remote)
            tunnels.append(pg_tunnel)
            q_tunnel, q_local = skynet.open_tunnel(ssh_host, q_remote)
            tunnels.append(q_tunnel)
        if note_tunnels is not None:
            note_tunnels([int(p.pid) for p in tunnels if p.pid is not None])
        pg_url = f"postgresql+asyncpg://ragmur:{password}@127.0.0.1:{pg_local}/ragmur_test"
        q_url = f"http://127.0.0.1:{q_local}"
        skynet.wait_tcp(pg_local, deadline, "PostgreSQL desechable")
        if not _qdrant_ready(q_url, min(deadline, time.time() + 180.0)):
            raise skynet.SkynetError("Qdrant desechable no respondió a /health")
        env = suite_env(pg_url, q_url, hmac_secret, ssh_host)
        remaining = deadline - time.time()
        with log_path.open("ab") as handle:
            handle.write(f"run_id={run_id} ssh_host={ssh_host or 'local'}\n".encode())
            handle.flush()
            migration = subprocess.run(
                ["uv", "run", "alembic", "upgrade", "head"],
                cwd=REPO_ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=max(1.0, min(600.0, remaining)),
            )
            if migration.returncode != 0:
                raise skynet.SkynetError("la migración falló, ver suite.log")
            remaining = deadline - time.time()
            pytest_proc = subprocess.run(
                ["uv", "run", "pytest", "-q", f"--junitxml={junit_path}"],
                cwd=REPO_ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=handle,
                stderr=subprocess.STDOUT,
                timeout=max(1.0, remaining),
            )
        if not junit_path.exists():
            raise skynet.SkynetError(f"pytest salió con {pytest_proc.returncode} sin junit")
        counts = parse_junit(junit_path)
        state, reason = suite_acceptance(counts)
        result = {
            "state": state,
            "reason": reason,
            "exit": pytest_proc.returncode,
            "counts": counts,
            "elapsed_s": round(time.time() - (deadline - timeout), 1),
            "log": str(log_path),
            "json": str(json_path),
            "junit": str(junit_path),
        }
    except subprocess.TimeoutExpired:
        result = {
            "state": "infra_error",
            "reason": f"plazo de etapa agotado ({timeout:g} s)",
            "log": str(log_path),
            "json": str(json_path),
        }
    except (skynet.SkynetError, OSError, ElementTree.ParseError) as exc:
        result = {
            "state": "infra_error",
            "reason": f"infraestructura: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
    finally:
        for proc in tunnels:
            skynet.close_tunnel(proc)
        if q_name:
            skynet.stop_container(ssh_host, q_name)
        if pg_name:
            skynet.stop_container(ssh_host, pg_name)
        if network:
            skynet.remove_network(ssh_host, network)
    result.setdefault("log", str(log_path))
    result.setdefault("json", str(json_path))
    write_json(json_path, result)
    return result


__all__ = [
    "EXPECTED_PASSED_MIN",
    "EXPECTED_SKIPPED",
    "KNOWN_SKIPPABLE",
    "KNOWN_XFAIL",
    "NLI_TIMEOUT_FALLBACK",
    "ingest_command",
    "ingest_env",
    "map_ingest_summary",
    "parse_junit",
    "run_ingest",
    "run_nli",
    "run_search",
    "run_static",
    "run_suite",
    "static_command",
    "static_env",
    "suite_acceptance",
    "suite_env",
]


def run_search(
    directory: Path,
    ssh_host: str | None,
    timeout: float = SEARCH_TIMEOUT_FALLBACK,
) -> dict[str, Any]:
    """Ejecuta la etapa search C04: busqueda y aislamiento con miles de preguntas en GPU."""
    from eval.phase1 import search as search_stage

    return search_stage.run(directory, ssh_host, timeout)


def run_nli(
    directory: Path,
    ssh_host: str | None,
    timeout: float = NLI_TIMEOUT_FALLBACK,
) -> dict[str, Any]:
    """Ejecuta la etapa nli C03: verificador con miles de frases en GPU."""
    from eval.phase1 import nli as nli_stage

    return nli_stage.run(directory, ssh_host, timeout)
