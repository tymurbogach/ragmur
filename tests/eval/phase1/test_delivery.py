"""Contratos de entrega C06: paquete público e informe inmunes al explicador."""

import json
from pathlib import Path
from typing import Any

from eval.phase1 import delivery


def _summary() -> dict[str, Any]:
    """Resumen quick con un fallo duro y 60 problemas sintéticos de ingesta."""
    return {
        "mode": "quick",
        "exit_code": 1,
        "seed": 20261122,
        "checks": {
            "static": {"state": "passed", "reason": "todo bien"},
            "gate": {"state": "hard_failed", "reason": "2 fallos en la puerta"},
            "ingest": {
                "state": "hard_failed",
                "reason": "60 fallos reales",
                "summary": {
                    "issues": [
                        {"kind": "text_loss", "detail": f"sintético {index}"} for index in range(60)
                    ]
                },
            },
            "defects": {"state": "passed", "reason": "D1-D7 y D8"},
        },
    }


def test_paquete_con_semilla_y_tope_cincuenta() -> None:
    """Misma semilla, mismo paquete; nunca más de 50 fallos."""
    first = delivery.build_package(_summary())
    second = delivery.build_package(_summary())
    assert first == second
    assert first["seed"] == delivery.PACKAGE_SEED
    assert len(first["failures"]) <= delivery.PACKAGE_MAX == 50


def test_paquete_sin_sellados_secretos_ni_datos_privados() -> None:
    """El paquete solo lleva motivos y detalles sintéticos."""
    package = delivery.build_package(_summary())
    assert delivery.check_package_clean(package) == []
    text = json.dumps(package, ensure_ascii=False)
    assert "plazo" not in text and "contrato" not in text


def test_escritura_falla_cerrada_ante_sellado(tmp_path: Path) -> None:
    """Un marcador sellado en un motivo impide publicar el paquete."""
    package = delivery.build_package(_summary())
    package["failures"].append(
        {"stage": "gate", "kind": "hard_failed", "detail": "ver test.csv sellado"}
    )
    try:
        delivery.write_package(package, tmp_path / "fallos-publicos.json")
    except ValueError as exc:
        assert "sellado" in str(exc)
    else:
        raise AssertionError("el paquete sellado se publicó")
    assert not (tmp_path / "fallos-publicos.json").exists()


def test_secretos_se_tachan_antes_de_publicar(tmp_path: Path) -> None:
    """Las claves con nombre sospechoso salen tachadas, no publicadas."""
    package = delivery.build_package(_summary())
    package["api_key_hmac_secret"] = "test-only-hmac-secret"
    path = delivery.write_package(package, tmp_path / "fallos-publicos.json")
    published = json.loads(path.read_text(encoding="utf-8"))
    assert published["api_key_hmac_secret"] == "<tachado>"
    assert delivery.check_package_clean(published) == []


def test_informe_en_espanol_sencillo_con_decision(tmp_path: Path) -> None:
    """El informe trae verde, rojo, no probado, conocidos y decisión."""
    summary = _summary()
    package = delivery.build_package(summary)
    path = delivery.write_informe(summary, package, tmp_path / "informe.md")
    text = path.read_text(encoding="utf-8")
    for section in (
        "Lo que está verde",
        "Lo que está rojo",
        "No probado",
        "Fallos ya conocidos",
        "Siguiente decisión",
    ):
        assert section in text
    assert "parar" in text  # código 1: hay que parar


def _freeze(path: Path) -> bytes:
    """Lee un fichero para comparar que no cambió."""
    return path.read_bytes()


def test_agente_caido_no_cambia_nada(tmp_path: Path) -> None:
    """Explicador caído: JSON, informe y código intactos; queda constancia."""
    summary = _summary()
    package = delivery.build_package(summary)
    informe = delivery.write_informe(summary, package, tmp_path / "informe.md")
    frozen = _freeze(informe)
    out = tmp_path / "explicacion.md"
    outcome = delivery.run_explainer(package, out, summary, timeout_s=30.0, explainer_cmd=["false"])
    assert outcome["state"] == "unavailable"
    assert _freeze(informe) == frozen
    assert summary["exit_code"] == 1
    text = out.read_text(encoding="utf-8")
    assert delivery.EXPLAINER_LABEL in text


def test_todo_aprobado_con_fallos_se_ignora(tmp_path: Path) -> None:
    """Un «todo aprobado» con fallos no toca JSON, informe ni código."""
    summary = _summary()
    package = delivery.build_package(summary)
    informe = delivery.write_informe(summary, package, tmp_path / "informe.md")
    frozen = _freeze(informe)
    out = tmp_path / "explicacion.md"
    outcome = delivery.run_explainer(
        package, out, summary, timeout_s=30.0, explainer_cmd=["echo", "Todo aprobado, sin fallos"]
    )
    assert outcome["state"] == "rejected"
    assert _freeze(informe) == frozen
    assert summary["exit_code"] == 1
    text = out.read_text(encoding="utf-8")
    assert delivery.EXPLAINER_LABEL in text
    assert "no cambia la nota" in text
