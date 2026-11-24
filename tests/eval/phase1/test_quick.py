"""Contratos del modo quick C06: rápido, local y sin Skynet ni LLM."""

from pathlib import Path
from typing import Any

from eval.phase1 import ingest, quick, runner


def test_quick_usa_diez_mil_documentos_y_semilla_fija() -> None:
    """El quick real procesa 10.000 documentos con la semilla de la etapa."""
    assert quick.QUICK_DOCS == 10_000
    assert quick.QUICK_SEED == ingest.SEED


def test_quick_env_prohibe_docker_y_fija_secretos_falsos() -> None:
    """Sin Docker local: todo lo que huela a Docker sale por la puerta."""
    env = quick.gate_env()
    assert env["DOCKER_HOST"] == "unix:///nonexistent"
    assert env["HF_HUB_OFFLINE"] == "1"
    assert "59999" in env["DATABASE_URL"] and "59998" in env["QDRANT_URL"]


def test_quick_no_conoce_skynet_ni_llm() -> None:
    """El quick es local: no importa Skynet, agentes ni LLM, ni los invoca."""
    text = Path(quick.__file__).read_text(encoding="utf-8")
    imports = [line for line in text.splitlines() if line.startswith(("import ", "from "))]
    for line in imports:
        lowered = line.lower()
        assert "skynet" not in lowered
        assert "opencode" not in lowered
        assert "litellm" not in lowered
        assert "llm" not in lowered
    assert "skynet." not in text
    assert "opencode run" not in text


def test_puerta_sin_servicios_ignora_lo_que_necesita_red() -> None:
    """La llamada 2 de la puerta es la de TASKS.md: ignora servicios."""
    cmd = " ".join(quick.gate_command())
    assert cmd.startswith("uv run pytest")
    for ignored in (
        "tests/retrieval",
        "tests/api/routes/test_health.py",
        "tests/api/test_rate_limit.py",
        "tests/test_auth.py",
        "tests/ingestion/test_recovery.py",
    ):
        assert ignored in cmd
    assert "docker" not in cmd and "ssh" not in cmd


def test_ingesta_rapida_real_con_pocos_documentos(tmp_path: Path) -> None:
    """El mismo código del quick, en pequeño: sin fallos en datos sanos."""
    result = quick.run_ingest_quick(tmp_path, ingest.SEED, 200, 2, 2)
    assert result["state"] == "passed"
    assert result["summary"]["docs"] == 200
    assert result["summary"]["issues"] == []


def test_defectos_conocidos_reproducen_cinco_y_pasan_d1_d7_d8(tmp_path: Path) -> None:
    """D2-D6 siguen en xfail estricto y D1+D7+D8 en verde (reparto real)."""
    result = quick.run_defects(tmp_path)
    assert result["state"] == "passed", result.get("reason")
    assert result["counts"]["failed"] == 0
    assert result["counts"]["skipped"] >= 5


def test_run_combina_las_cuatro_comprobaciones(tmp_path: Path, monkeypatch: Any) -> None:
    """El resumen junta estática, puerta, ingesta y defectos con precedencia 2,1,0."""

    def fake_static(directory: Path, timeout: float = 600.0) -> dict[str, Any]:
        return {"state": "passed"}

    def fake_gate(directory: Path, timeout: float = 600.0) -> dict[str, Any]:
        return {"state": "passed"}

    def fake_ingest(
        directory: Path,
        seed: int = 0,
        docs: int = 0,
        valid_each: int = 0,
        bad_each: int = 0,
        timeout: float = 0.0,
    ) -> dict[str, Any]:
        return {"state": "passed"}

    def fake_defects(directory: Path, timeout: float = 600.0) -> dict[str, Any]:
        return {"state": "infra_error", "reason": "corte de luz"}

    monkeypatch.setattr("eval.phase1.quick.stages.run_static", fake_static)
    monkeypatch.setattr("eval.phase1.quick.run_gate", fake_gate)
    monkeypatch.setattr("eval.phase1.quick.run_ingest_quick", fake_ingest)
    monkeypatch.setattr("eval.phase1.quick.run_defects", fake_defects)
    summary = quick.run(tmp_path)
    assert summary["mode"] == "quick"
    assert set(summary["checks"]) == {"static", "gate", "ingest", "defects"}
    assert summary["exit_code"] == runner.EXIT_INFRA
    assert (tmp_path / "quick.json").exists()
