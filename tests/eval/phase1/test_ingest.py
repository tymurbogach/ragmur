"""Etapa ingest C02: detectores con fallos inyectados y contratos rápidos.

El barrido completo (100.000 documentos, 8.000 ficheros) lo ejecuta la etapa
``ingest`` del runner en el portátil. Aquí se prueba lo mismo en pequeño: los
detectores cazan cada fallo inyectado y el resumen es reproducible.
"""

import json
import random
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from eval.phase1 import ingest, stages


def _chunks(text: str, size: int = 120, overlap: int = 30) -> tuple[list[Any], Any, Any]:
    """Trocea un texto con el troceador real del servicio."""
    from ragmur.ingestion.chunker import split_document
    from ragmur.ingestion.extractors.core import ExtractionResult, Fragment

    tenant_id, document_id = uuid4(), uuid4()
    extraction = ExtractionResult(
        [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
    )
    chunks = split_document(
        extraction, document_id, tenant_id, "alice", size=size, overlap=overlap
    ).chunks
    return chunks, tenant_id, document_id


def _text(words: int = 120) -> str:
    """Texto sintético con la semilla fija de la etapa."""
    rng = random.Random(ingest.SEED)
    return " ".join(rng.choice(ingest.WORDS) for _ in range(words))


def test_texto_sano_pasa_los_tres_detectores() -> None:
    """Sin fallos no hay problemas: el instrumento no inventa fallos."""
    text = _text()
    chunks, tenant_id, document_id = _chunks(text)
    assert ingest.check_text_preserved(text, chunks) == []
    assert ingest.check_spans(text, chunks) == []
    assert ingest.check_owners(chunks, tenant_id, "alice", document_id) == []


def test_detector_caza_perdida_de_texto_inyectada() -> None:
    """Si falta una letra, la reconstrucción por spans no coincide."""
    text = _text()
    chunks, _, _ = _chunks(text)
    assert ingest.check_text_preserved(text, chunks) == []
    assert ingest.check_text_preserved(text, chunks[1:]) != []
    assert ingest.check_text_preserved(text[:-1] + "X", chunks) != []


def test_detector_caza_span_erroneo_inyectado() -> None:
    """Si un span se desplaza, el texto ya no coincide con su rango."""
    text = _text()
    chunks, _, _ = _chunks(text)
    assert ingest.check_spans(text, chunks) == []
    moved = SimpleNamespace(text=chunks[0].text, start=chunks[0].start + 1, end=chunks[0].end + 1)
    assert ingest.check_spans(text, [moved, *chunks[1:]]) != []
    broken = SimpleNamespace(text="zzz", start=0, end=3)
    assert ingest.check_spans(text, [broken, *chunks[1:]]) != []


def test_detector_caza_dueno_erroneo_inyectado() -> None:
    """Si cambia el dueño, el tenant o el documento, el detector lo marca."""
    tenant, document = uuid4(), uuid4()
    good = [SimpleNamespace(tenant_id=tenant, owner_id="alice", document_id=document)]
    assert ingest.check_owners(good, tenant, "alice", document) == []
    assert ingest.check_owners(good, tenant, "bob", document) != []
    assert ingest.check_owners(good, uuid4(), "alice", document) != []
    assert ingest.check_owners(good, tenant, "alice", uuid4()) != []


def test_detector_caza_cuelgue_inyectado() -> None:
    """Una función que duerme supera el plazo y se registra como cuelgue."""

    def cuelgue() -> str:
        time.sleep(2.0)
        return "tarde"

    status, _ = ingest.run_with_timeout(cuelgue, 0.05)
    assert status == "hang"
    status, _ = ingest.run_with_timeout(lambda: "pronto", 5.0)
    assert status == "ok"


def test_detector_caza_excepcion_no_controlada() -> None:
    """Una excepción rara se publica como fallo, no se deja escapar."""

    def roto() -> str:
        raise RuntimeError("fallo raro")

    assert ingest.classify_outcome(*ingest.run_with_timeout(roto, 5.0))[0] == "crashed"
    assert ingest.classify_outcome("raised", ValueError("x")) == ("crashed", "ValueError: x")
    from ragmur.ingestion.extractors.core import ExtractionError, UnsupportedDocumentError

    assert ingest.classify_outcome("raised", ExtractionError("y"))[0] == "invalid"
    assert ingest.classify_outcome("raised", UnsupportedDocumentError("z"))[0] == "invalid"
    assert ingest.classify_outcome("hang", "lento")[0] == "hang"
    assert ingest.classify_outcome("ok", "texto")[0] == "ok"


@pytest.mark.parametrize("kind", ["txt", "md", "docx", "pdf"])
def test_ficheros_validos_se_extraen_y_rotos_se_rechazan(tmp_path: Path, kind: str) -> None:
    """Cada formato: lo válido se lee y lo roto no cuelga ni revienta."""
    rng = random.Random(ingest.SEED)
    for index in range(3):
        path = tmp_path / f"valid-{index}"
        ingest.write_valid_file(kind, path, rng)
        assert ingest.classify_extraction(kind, path, 30.0)[0] == "ok"
    for index in range(3):
        path = tmp_path / f"bad-{index}.bin"
        ingest.write_bad_file(kind, path, rng, index % 3)
        assert ingest.classify_extraction(kind, path, 30.0)[0] in ("ok", "invalid")


def test_barrido_pequeno_sin_fallos_y_reproducible(tmp_path: Path) -> None:
    """El resumen con semilla fija es idéntico entre ejecuciones."""
    first = ingest.run_stage(ingest.SEED, 30, 2, 2, tmp_path / "a", 30.0)
    second = ingest.run_stage(ingest.SEED, 30, 2, 2, tmp_path / "b", 30.0)
    assert first["issues"] == [] and first["issue_count"] == 0
    for key in ("seed", "docs", "chunks", "extraction", "issues", "issue_count"):
        assert first[key] == second[key]
    assert (tmp_path / "a" / "summary.json").exists()
    assert (
        json.loads((tmp_path / "a" / "summary.json").read_text(encoding="utf-8"))["seed"]
        == ingest.SEED
    )


def test_fallo_real_se_publica_como_duro_con_semilla() -> None:
    """El resumen con problemas sale hard_failed y conserva la semilla."""
    state, reason = stages.map_ingest_summary({"issues": [], "seed": 7, "docs": 1, "chunks": 2})
    assert (state, "7" in reason) == ("passed", False)
    state, reason = stages.map_ingest_summary({"issues": [{"kind": "hang"}], "seed": 7})
    assert state == "hard_failed" and "7" in reason
    assert stages.map_ingest_summary({})[0] == "infra_error"
    assert stages.map_ingest_summary({"issues": "roto"})[0] == "infra_error"


def test_ingest_sin_docker_y_sin_red() -> None:
    """La etapa corre en el portátil: ni Docker local ni SSH en la orden."""
    argv = stages.ingest_command(Path("/tmp/salida"))
    assert argv[:2] == ["uv", "run"]
    assert "docker" not in " ".join(argv) and "ssh" not in argv
    env = stages.ingest_env()
    assert env["DOCKER_HOST"] == "unix:///nonexistent"
    assert env["HF_HUB_OFFLINE"] == "1"


def test_etapa_ingest_usa_solo_su_orden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """La etapa escribe su resumen y traduce fallos reales a salida dura."""
    from unittest.mock import Mock

    llamadas: list[list[str]] = []

    def falso_run(*args: Any, **kwargs: Any) -> Any:
        llamadas.extend(arg for arg in args if isinstance(arg, list))
        (tmp_path / "ingest").mkdir(exist_ok=True)
        (tmp_path / "ingest" / "summary.json").write_text(
            json.dumps({"seed": ingest.SEED, "docs": 1, "chunks": 2, "issues": []}),
            encoding="utf-8",
        )
        acabado = Mock()
        acabado.returncode = 0
        return acabado

    monkeypatch.setattr(subprocess, "run", falso_run)
    resultado = stages.run_ingest(tmp_path)
    assert resultado["state"] == "passed"
    assert len(llamadas) == 1 and llamadas[0][:4] == ["uv", "run", "python", "-m"]

    def falso_fallo(*args: Any, **kwargs: Any) -> Any:
        (tmp_path / "ingest" / "summary.json").write_text(
            json.dumps({"seed": ingest.SEED, "issues": [{"kind": "crashed"}]}),
            encoding="utf-8",
        )
        acabado = Mock()
        acabado.returncode = 1
        return acabado

    monkeypatch.setattr(subprocess, "run", falso_fallo)
    resultado = stages.run_ingest(tmp_path)
    assert resultado["state"] == "hard_failed" and str(ingest.SEED) in resultado["reason"]


def test_interfaz_ingest_explica_sus_opciones() -> None:
    """La etapa documenta semilla, volúmenes y plazo en su ayuda."""
    parser = ingest.build_parser()
    assert parser.parse_args(["--out", "x"]).seed == ingest.SEED
    assert parser.parse_args(["--out", "x"]).docs == ingest.DOCS
