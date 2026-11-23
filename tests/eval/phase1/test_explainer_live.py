"""Explicador real con un paquete pequeño (C06).

Solo corre con ``RAGMUR_LIVE_EXPLAINER=1``: invoca de verdad a
``opencode run --agent critica`` y comprueba que ``explicacion.md`` sale
rotulada («no cambia la nota») sin tocar el resumen ni el código. Va por
separado del quick, que nunca llama al explicador.
"""

import os
from pathlib import Path
from typing import Any

import pytest

from eval.phase1 import delivery

LIVE = os.environ.get("RAGMUR_LIVE_EXPLAINER") == "1"

pytestmark = pytest.mark.skipif(not LIVE, reason="solo con RAGMUR_LIVE_EXPLAINER=1")


def _summary() -> dict[str, Any]:
    """Resumen con dos fallos sintéticos para el paquete pequeño."""
    return {
        "mode": "quick",
        "exit_code": 1,
        "checks": {
            "gate": {"state": "hard_failed", "reason": "2 fallos en la puerta"},
            "ingest": {
                "state": "passed",
                "reason": "sin fallos",
                "summary": {"issues": [{"kind": "span", "detail": "sintético 0"}]},
            },
        },
    }


def test_explicador_real_con_paquete_pequeno(tmp_path: Path) -> None:
    """El agente explica dos fallos y la nota queda intacta."""
    summary = _summary()
    package = delivery.build_package(summary)
    assert len(package["failures"]) == 2
    informe = delivery.write_informe(summary, package, tmp_path / "informe.md")
    before = informe.read_bytes()
    out = tmp_path / "explicacion.md"
    outcome = delivery.run_explainer(package, out, summary, timeout_s=240.0)
    assert outcome["state"] == "ok", outcome
    assert informe.read_bytes() == before
    assert summary["exit_code"] == 1
    text = out.read_text(encoding="utf-8")
    assert delivery.EXPLAINER_LABEL in text
