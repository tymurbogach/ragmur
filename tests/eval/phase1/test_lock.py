"""Cerrojo de una ejecución: latido, vida del PID y toma ante muerte."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from eval.phase1.runner import (
    LockedError,
    acquire_lock,
    heartbeat_age,
    lock_is_dead,
    read_lock,
    refresh_lock,
    release_lock,
    write_lock,
)

from eval.phase1 import runner, skynet


@pytest.fixture
def aislamiento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Redirige el cerrojo y los estados a un directorio temporal."""
    runs = tmp_path / "per_query"
    runs.mkdir()
    monkeypatch.setattr(runner, "RUNS_DIR", runs)
    monkeypatch.setattr(runner, "LOCK_FILE", runs / ".lock")
    limpieza = Mock(return_value={})
    monkeypatch.setattr(skynet, "cleanup_run", limpieza)
    return limpieza


def _cerrojo(pid: int, latido: str) -> dict[str, Any]:
    return {"run_id": "vieja", "pid": pid, "heartbeat": latido}


def test_segunda_ejecucion_viva_no_toma_el_cerrojo(aislamiento: Mock) -> None:
    write_lock("primera", os.getpid())
    with pytest.raises(LockedError):
        acquire_lock("segunda", os.getpid(), None)
    assert read_lock()["run_id"] == "primera"


def test_muerte_es_pid_inexistente_y_latido_viejo(aislamiento: Mock) -> None:
    assert lock_is_dead(_cerrojo(2**30, "2000-01-01T00:00:00+00:00"))
    assert not lock_is_dead(_cerrojo(2**30, runner.utcnow()))
    assert not lock_is_dead(_cerrojo(os.getpid(), "2000-01-01T00:00:00+00:00"))


def test_toma_tras_muerte_y_retira_restos(aislamiento: Mock) -> None:
    write_lock("vieja", 2**30)
    anterior = read_lock()
    anterior["heartbeat"] = "2000-01-01T00:00:00+00:00"
    runner.write_json(runner.LOCK_FILE, anterior)
    tomada = acquire_lock("nueva", os.getpid(), None)
    assert tomada is not None and tomada["run_id"] == "vieja"
    assert read_lock()["run_id"] == "nueva"
    aislamiento.assert_called_once()


def test_latido_sin_fecha_es_infinito() -> None:
    assert heartbeat_age({}) == float("inf")
    assert heartbeat_age({"heartbeat": "no-fecha"}) == float("inf")


def test_refresco_y_suelta_solo_lo_propio(aislamiento: Mock) -> None:
    write_lock("mia", os.getpid())
    refresh_lock("otra", 999999999)
    assert read_lock()["run_id"] == "mia"
    release_lock("otra")
    assert read_lock()["run_id"] == "mia"
    release_lock("mia")
    assert read_lock() == {}


def test_adquiere_sin_cerrojo_previo(aislamiento: Mock) -> None:
    assert acquire_lock("primera", os.getpid(), None) is None
    assert read_lock()["run_id"] == "primera"
