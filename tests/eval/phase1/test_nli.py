"""Etapa nli C03: cargador cerrado, selección, métricas y paridad con /verify.

Todo corre sin red ni GPU: la descarga real y el cálculo en la RTX 5080 los
hace la etapa ``nli`` del runner sobre Skynet.
"""

import asyncio
import hashlib
import json
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from eval.phase1.nli_data import Pair

from eval.phase1 import datasets, nli_data, stages


def _pair(pair_id: str, topic: str, premise: str, anno: str = "Generate") -> Pair:
    """Construye un par sintético con etiqueta válida."""
    return Pair(
        id=pair_id,
        premise=premise,
        hypothesis=f"hipótesis {pair_id}",
        label="supported",
        topic=topic,
        anno=anno,
    )


def test_cargador_rechaza_sellados_y_otras_urls_sin_red(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nada fuera de la lista cerrada provoca ni una petición de red."""

    def _prohibido(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("el cargador no debe tocar la red para rechazar")

    monkeypatch.setattr(urllib.request, "urlopen", _prohibido)
    with pytest.raises(ValueError, match="lista cerrada"):
        datasets.download_allowed("https://example.com/train.csv")
    with pytest.raises(ValueError, match="lista cerrada"):
        datasets.download_allowed(
            "https://huggingface.co/datasets/venelin/inferes/resolve/otro/train.csv"
        )
    with pytest.raises(ValueError, match="lista cerrada"):
        datasets.download_allowed(
            "https://huggingface.co/datasets/venelin/inferes/resolve/"
            "c371a1915e6902b40182b2ae83c5ec7fe5e6cbd2/test.csv"
        )
    with pytest.raises(ValueError, match="lista cerrada"):
        datasets.allowed_target(
            "https://huggingface.co/datasets/PlanTL-GOB-ES/SQAC/resolve/x/dev.json"
        )


def test_descarga_atomica_y_con_huella(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """La descarga verifica la huella y no deja el temporal con el nombre final."""
    payload = b"ID,Premise\n1,hola\n"
    digest = hashlib.sha256(payload).hexdigest()
    url = "https://huggingface.test/only/train.csv"
    monkeypatch.setitem(datasets.ALLOWED, url, ("solo/train.csv", digest))
    monkeypatch.setattr(datasets, "DATASETS_DIR", tmp_path)

    class _Respuesta:
        def __enter__(self) -> "_Respuesta":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return payload

    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Respuesta())
    target = datasets.download_allowed(url)
    assert target.read_bytes() == payload
    assert not target.with_name(target.name + ".tmp").exists()

    def _red(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("con el fichero presente no debe haber red")

    monkeypatch.setattr(urllib.request, "urlopen", _red)
    assert datasets.download_allowed(url) == target


def test_sellados_y_reserva_fallan_sin_red(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """dev.json, test.json, test.csv o una pregunta reserva son fallo cerrado."""
    data = tmp_path / "data"
    prepared = tmp_path / "prepared"
    (data / "inferes").mkdir(parents=True)
    (data / "inferes" / "train.csv").write_text("ID\n1\n", encoding="utf-8")
    assert datasets.sealed_precheck(data, prepared, set()) == []
    (data / "sqac").mkdir()
    (data / "sqac" / "dev.json").write_text("{}", encoding="utf-8")
    errors = datasets.sealed_precheck(data, prepared, set())
    assert any("dev.json" in error for error in errors)
    (data / "sqac" / "dev.json").unlink()
    (data / "x").mkdir()
    (data / "x" / "test.csv").write_text("a", encoding="utf-8")
    assert datasets.sealed_precheck(data, prepared, set()), "test.csv debe fallar"
    (data / "x" / "test.csv").unlink()
    prepared.mkdir()
    (prepared / "nli.json").write_text(json.dumps([{"id": "q-reserva-1"}]), encoding="utf-8")
    errors = datasets.sealed_precheck(data, prepared, {"q-reserva-1"})
    assert any("reserva" in error for error in errors)
    reserva_real = next(iter(datasets.load_reserve_ids()))
    (prepared / "nli.json").write_text(json.dumps([{"id": reserva_real}]), encoding="utf-8")
    monkeypatch.setattr(datasets, "DATASETS_DIR", data)
    monkeypatch.setattr(datasets, "PREPARED_DIR", prepared)
    with pytest.raises(datasets.SealedError):
        datasets.assert_no_sealed()


def test_vectores_de_distractores_con_datos_reales() -> None:
    """1968 y 2148 eligen sus 4 distractores con el algoritmo exacto."""
    fixture = Path(__file__).parent / "fixtures" / "inferes_vectors.json"
    rows = json.loads(fixture.read_text(encoding="utf-8"))["rows"]
    assert len(rows) == nli_data.EXPECTED_TOTAL
    ordered = [
        Pair(id=r[0], premise=r[2], hypothesis="h", label="supported", topic=r[1], anno="Generate")
        for r in rows
    ]
    by_id = {pair.id: pair for pair in ordered}
    for wanted_id, wanted in nli_data.EXPECTED_VECTORS.items():
        got = tuple(extra.id for extra in nli_data.distractors(ordered, by_id[wanted_id], 5)[1:])
        assert got == wanted, f"vector {wanted_id}"
        single = nli_data.distractors(ordered, by_id[wanted_id], 1)
        assert [pair.id for pair in single] == [wanted_id]


def test_seleccion_congelada() -> None:
    """Temas 1-5, textos no vacíos, orden del fichero y etiquetas traducidas."""
    rows = [
        {
            "ID": "1",
            "Premise": "p",
            "Hypothesis": "h",
            "Label": "ent",
            "Topic": "1",
            "Anno_Type": "Generate",
        },
        {
            "ID": "2",
            "Premise": "  ",
            "Hypothesis": "h",
            "Label": "ent",
            "Topic": "1",
            "Anno_Type": "Generate",
        },
        {
            "ID": "3",
            "Premise": "p",
            "Hypothesis": "h",
            "Label": "cnt",
            "Topic": "6",
            "Anno_Type": "Generate",
        },
        {
            "ID": "4",
            "Premise": "p",
            "Hypothesis": "h",
            "Label": "neutral",
            "Topic": "5",
            "Anno_Type": "Automated",
        },
    ]
    selected = nli_data.select_pairs(rows)
    assert [pair.id for pair in selected] == ["1", "4"]
    assert [pair.label for pair in selected] == ["supported", "unsupported"]
    assert [pair.id for pair in nli_data.principal_only(selected)] == ["1"]
    with pytest.raises(ValueError, match="etiqueta desconocida"):
        nli_data.select_pairs([{**rows[0], "Label": "otra"}])
    with pytest.raises(ValueError):
        nli_data.distractors(selected, selected[0], 0)


def test_veredicto_precedencia_y_wilson() -> None:
    """La contradicción sobre umbral gana; Wilson acota la proporción."""
    assert nli_data.apply_verdict(0.9, 0.8) == "contradicted"
    assert nli_data.apply_verdict(0.9, 0.1) == "supported"
    assert nli_data.apply_verdict(0.6, 0.1) == "weak"
    assert nli_data.apply_verdict(0.1, 0.1) == "unsupported"
    low, high = nli_data.wilson(0, 0)
    assert (low, high) == (0.0, 1.0)
    low, high = nli_data.wilson(70, 1000)
    assert low < 0.07 < high and high - low < 0.05


def test_metricas_y_celdas() -> None:
    """Matrices, referencias y comparación ±5 sobre datos sintéticos."""
    rows: list[dict[str, str]] = []
    for human, cells in nli_data.EXPECTED_CELLS[1].items():
        for verdict, count in zip(nli_data.VERDICTS, cells, strict=True):
            rows.extend([{"y": human, "v": verdict}] * count)
    matrix = nli_data.confusion(rows, "v")
    assert matrix["supported"]["supported"] == 678
    assert nli_data.cell_mismatches(matrix, 1) == []
    refs = nli_data.quality_refs(matrix)
    assert refs["recall_support"] == pytest.approx(678 / 1343)
    assert refs["false_support"] == pytest.approx(84 / 1781)
    assert nli_data.quality_errors({**refs, "false_support": 0.0, "recall_support": 1.0}) == []
    assert nli_data.quality_errors({**refs, "false_support": 0.06}), "detecta el respaldo falso"
    desviada = dict(matrix)
    desviada["supported"] = matrix["supported"] + Counter({"supported": 100})
    fallo = nli_data.cell_mismatches(desviada, 1)
    assert len(fallo) == 1 and "1 textos supported/supported" in fallo[0]


def test_calculo_sin_cargadores_de_conjuntos() -> None:
    """El cálculo del contenedor no importa cargadores de datasets."""
    root = Path(__file__).resolve().parents[3] / "eval" / "phase1"
    forbidden = (
        "eval.inferes",
        "eval.reader",
        "load_dataset",
        "snapshot_download",
        "git clone",
        "datasets.download",
    )
    for name in ("nli_compute.py", "nli_data.py"):
        source = (root / name).read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{name} menciona {marker}"


def test_etapa_nli_sin_skynet_es_infra(tmp_path: Path) -> None:
    """Sin host no hay GPU: la etapa queda como infraestructura, sin red."""
    result = stages.run_nli(tmp_path, None, timeout=10.0)
    assert result["state"] == "infra_error"
    assert (tmp_path / "nli.json").is_file()


def test_paridad_con_la_ruta_verify(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """La regla de veredicto coincide con /verify llamando a la ruta."""
    from ragmur.api.routes import verify as verify_module
    from ragmur.api.routes.verify import router  # noqa: F401  (la ruta existe)
    from ragmur.api.schemas import VerifyRequest
    from ragmur.core.config import get_settings
    from ragmur.retrieval import store

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:x@127.0.0.1:59999/x")
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:59998")
    monkeypatch.setenv("API_KEY_HMAC_SECRET", "test-only-hmac-secret")
    get_settings.cache_clear()

    tenant_id, document_id, chunk_id = uuid4(), uuid4(), uuid4()

    class _Sesion:
        def __init__(self, valid: set[object]) -> None:
            self._valid = valid

        async def __aenter__(self) -> "_Sesion":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def scalars(self, *args: object, **kwargs: object) -> Mock:
            consultas = Mock()
            consultas.all.return_value = list(self._valid)
            return consultas

    points = [
        store.StoredPoint(
            id=chunk_id,
            payload={"document_id": str(document_id), "text": "El plazo es 48 horas."},
        )
    ]

    async def _puntos(*args: object, **kwargs: object) -> Any:
        return points

    monkeypatch.setattr(store, "retrieve_points", _puntos)

    async def _llamar(ent: float, contra: float) -> str:
        verificador = Mock()
        verificador.check_hypothesis.return_value = None
        verificador.score_pairs.side_effect = lambda ps, hs, b: [(ent, contra)] * len(hs)
        recursos = Mock()
        recursos.verifier = verificador
        recursos.models.lock = asyncio.Lock()
        recursos.sessions.return_value = _Sesion({document_id})
        respuesta = await verify_module.verify(
            VerifyRequest(answer="El plazo es 48 horas.", chunk_ids=[chunk_id]),
            tenant_id,
            recursos,
        )
        assert len(respuesta.claims) == 1
        return respuesta.claims[0].verdict

    for ent, contra in [(0.9, 0.8), (0.9, 0.1), (0.6, 0.1), (0.1, 0.1)]:
        esperado = nli_data.apply_verdict(ent, contra)
        assert asyncio.run(_llamar(ent, contra)) == esperado
    get_settings.cache_clear()
