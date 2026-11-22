"""Contratos C01: sin Docker local en Skynet, limpieza y cancelación."""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from eval.phase1.runner import cancel_run, initial_status, write_status

from eval.phase1 import runner, skynet, stages


def test_docker_cmd_en_skynet_empieza_por_ssh() -> None:
    argv = skynet.docker_cmd("skynet-ts", "docker", "ps")
    assert argv[0] == "ssh"
    assert "skynet-ts" in argv
    assert argv[-2:] == ["docker", "ps"]


def test_docker_cmd_sin_host_es_ci_local() -> None:
    assert skynet.docker_cmd(None, "docker", "ps")[:2] == ["docker", "docker"]


def test_estatica_sin_docker_y_sin_red() -> None:
    argv = stages.static_command()
    texto = " ".join(argv)
    assert "docker" not in texto and "ssh" not in texto
    env = stages.static_env()
    assert env["DOCKER_HOST"] == "unix:///nonexistent"


def test_suite_fija_docker_prohibido_y_pasa_el_host() -> None:
    env = stages.suite_env("pg", "q", "secreto", "skynet-ts")
    assert env["DOCKER_HOST"] == "unix:///nonexistent"
    assert env["RAGMUR_TEST_SSH_HOST"] == "skynet-ts"
    assert "secreto" not in str({k: v for k, v in env.items() if k != "API_KEY_HMAC_SECRET"})
    sin_host = stages.suite_env("pg", "q", "secreto", None)
    assert "RAGMUR_TEST_SSH_HOST" not in sin_host


def test_etapa_estatica_usa_solo_su_orden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    llamadas: list[list[str]] = []

    def falso_run(*args: Any, **kwargs: Any) -> Any:
        llamadas.extend(arg for arg in args if isinstance(arg, list))
        acabado = Mock()
        acabado.returncode = 0
        return acabado

    monkeypatch.setattr(subprocess, "run", falso_run)
    resultado = stages.run_static(tmp_path)
    assert resultado["state"] == "passed"
    assert len(llamadas) == 1
    assert llamadas[0][0] == "bash"
    assert "docker" not in " ".join(llamadas[0])


def test_suite_en_skynet_no_toca_docker_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Con host, ni un argv empieza por ``docker``: todo sale por ``ssh``."""
    vistos: list[list[str]] = []

    def falso_remote(host: str | None, *args: str, **kwargs: Any) -> str:
        vistos.append(skynet.docker_cmd(host, *args))
        if args[:2] == ("docker", "port"):
            return "127.0.0.1:32768"
        return ""

    monkeypatch.setattr(skynet, "remote", falso_remote)
    monkeypatch.setattr(skynet, "wait_tcp", Mock(return_value=None))
    monkeypatch.setattr(stages, "_qdrant_ready", Mock(return_value=True))

    tunel = Mock()
    tunel.pid = 123456789
    monkeypatch.setattr(skynet, "open_tunnel", Mock(return_value=(tunel, 18080)))
    for nombre in ("close_tunnel", "stop_container", "remove_network"):
        monkeypatch.setattr(skynet, nombre, Mock())

    junit = tmp_path / "suite-junit.xml"
    junit.write_text(
        '<testsuite tests="2" failures="0" errors="0" skipped="0"></testsuite>',
        encoding="utf-8",
    )

    def falso_run(*args: Any, **kwargs: Any) -> Any:
        argv = args[0]
        assert isinstance(argv, list)
        assert argv[0] in ("uv", "bash")
        env = kwargs.get("env", {})
        assert env.get("DOCKER_HOST") == "unix:///nonexistent"
        acabado = Mock()
        acabado.returncode = 0
        return acabado

    monkeypatch.setattr(subprocess, "run", falso_run)
    monkeypatch.setattr(
        stages,
        "parse_junit",
        Mock(
            return_value={"tests": 382, "passed": 376, "failed": 0, "skipped": 6, "skipped_ids": []}
        ),
    )
    resultado = stages.run_suite(tmp_path, "skynet-ts", None, timeout=120.0)
    assert resultado["state"] == "passed"
    assert vistos, "la etapa suite debe hablar con Skynet"
    assert all(argv[0] == "ssh" for argv in vistos)


def test_parse_junit_y_criterio() -> None:
    conocidos = [
        "tests.llm.test_provider_live::test_live_completion_returns_text_and_usage",
        "tests.verification.test_nli::test_long_hypothesis_with_cached_tokenizer",
    ]
    base = {"failed": 0, "passed": 398, "skipped": 2, "skipped_ids": conocidos}
    assert stages.suite_acceptance(base)[0] == "passed"
    con_fallos = {"failed": 1, "passed": 400, "skipped": 5, "skipped_ids": []}
    assert stages.suite_acceptance(con_fallos)[0] == "hard_failed"
    pocos = {"failed": 0, "passed": 100, "skipped": 5, "skipped_ids": []}
    assert stages.suite_acceptance(pocos)[0] == "hard_failed"
    nuevo = {
        "failed": 0,
        "passed": 376,
        "skipped": 3,
        "skipped_ids": [*conocidos, "tests.otro::test_x"],
    }
    estado, motivo = stages.suite_acceptance(nuevo)
    assert estado == "hard_failed" and "salto nuevo" in motivo
    sin_ids = {"failed": 0, "passed": 376, "skipped": 6}
    estado_ids, motivo_ids = stages.suite_acceptance(sin_ids)
    assert estado_ids == "hard_failed" and "ilegible" in motivo_ids


def test_cancel_deja_estado_y_suelta_cerrojo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = tmp_path / "per_query"
    runs.mkdir()
    monkeypatch.setattr(runner, "RUNS_DIR", runs)
    monkeypatch.setattr(runner, "LOCK_FILE", runs / ".lock")
    monkeypatch.setattr(skynet, "cleanup_run", Mock(return_value={}))
    monkeypatch.setattr(
        skynet, "list_resources", Mock(return_value={"containers": [], "networks": []})
    )
    estado = initial_status("cancela1", ["static", "suite"], "abc", [], "skynet-ts")
    estado["pid"] = 2**30  # muerto: no se mata a nadie real
    estado["stages"]["static"]["state"] = "running"
    write_status(estado)
    runner.write_lock("cancela1", 2**30)
    # Envejecer el latido no importa para cancelar: cancel actúa siempre.
    desenlace = cancel_run("cancela1")
    assert desenlace["containers_left"] == []
    assert desenlace["networks_left"] == []
    assert desenlace["tunnels_left"] == []
    final = runner.read_status("cancela1")
    assert final["status"] == "cancelled"
    assert final["stages"]["static"]["state"] == "incomplete"
    assert runner.read_lock() == {}
    assert desenlace["worker_was_alive"] is False


def test_provision_solo_nombres_del_prefijo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Los recursos creados llevan el prefijo y la etiqueta de la ejecución."""
    creados: list[str] = []

    def falso_remote(host: str | None, *args: str, **kwargs: Any) -> str:
        if args[:2] == ("docker", "run"):
            nombre = args[args.index("--name") + 1]
            creados.append(nombre)
            assert nombre.startswith("ragmur-p1-miid-")
            etiqueta = args[args.index("--label") + 1]
            assert etiqueta == "ragmur.p1.run=miid"
            return "id-falso"
        if args[:2] == ("docker", "network") and args[2] == "create":
            assert args[-1] == "ragmur-p1-miid-net"
            return "red-falsa"
        return ""

    monkeypatch.setattr(skynet, "remote", falso_remote)
    red = skynet.create_network("skynet-ts", "miid")
    pg = skynet.run_postgres("skynet-ts", "miid", red, "clave")
    q = skynet.run_qdrant("skynet-ts", "miid", red)
    assert red == "ragmur-p1-miid-net"
    assert (pg, q) == ("ragmur-p1-miid-pg", "ragmur-p1-miid-q")
    assert "ragmur_deploy" not in " ".join(creados)
