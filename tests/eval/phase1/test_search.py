"""Etapa search C04: seleccion congelada, metricas y detector de fugas.

Todo corre sin red ni GPU: la descarga y el calculo en la RTX 5080 los hace
la etapa ``search`` del runner sobre Skynet. Aqui se prueba lo mismo en
pequenyo: las metricas sobre rangos sinteticos y el detector con fugas
inyectadas, mas los contratos rapidos de la etapa.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from eval.phase1 import datasets, search_compute, search_data, stages


def _fila(
    row_id: str,
    src: str = "sqac",
    covered: bool = True,
    doc: int | None = 1,
    ans: int | None = 1,
    ms: float = 200.0,
) -> dict[str, Any]:
    """Una fila sintetica con el mismo rango en las cuatro etapas."""
    return {
        "id": row_id,
        "src": src,
        "covered": covered,
        "d_doc": doc,
        "d_ans": ans,
        "s_doc": doc,
        "s_ans": ans,
        "h_doc": doc,
        "h_ans": ans,
        "r_doc": doc,
        "r_ans": ans,
        "ms": ms,
    }


def _iso_limpio() -> dict[str, Any]:
    """Contadores de aislamiento sin fugas y con control positivo."""
    return {
        "tenant_results": 478320,
        "tenant_leaks": 0,
        "owner_results": 478320,
        "owner_leaks": 0,
        "cross_tenant_reads": search_data.EXPECTED_CASES,
        "cross_tenant_read_leaks": 0,
        "cross_owner_reads": search_data.EXPECTED_CASES,
        "cross_owner_read_leaks": 0,
        "control_read": 2,
    }


def test_seleccion_congelada_con_datos_reales() -> None:
    """5226 documentos y 15944 preguntas solo de practica."""
    from eval.reader import xquad

    xquad_path = datasets.download_allowed(datasets.SQAC_URL)  # solo verifica huella
    assert xquad_path.is_file()
    xquad_data = xquad.load_dataset(xquad.default_dataset_path())
    dev_ids = {case.case_id for case in xquad.list_cases(xquad_data, "dev")}
    sqac_data = json.loads(xquad_path.read_text(encoding="utf-8"))
    docs, cases, _ = search_data.build_selection(xquad_data, sqac_data, dev_ids)
    assert search_data.check_selection(docs, cases) == []
    assert len({case.id for case in cases}) == search_data.EXPECTED_CASES


def test_respuestas_sin_descarte_silencioso() -> None:
    """Un desplazamiento roto se reubica; lo ilocalizable se cuenta, no se tira."""
    assert search_data.resolve_answers("hola mundo", [(0, "hola")]) == [(0, 4, "hola")]
    assert search_data.resolve_answers("xx hola", [(0, "hola")]) == [(3, 7, "hola")]
    assert search_data.resolve_answers("hola", [(0, "adios")]) == []
    data = {"data": [{"title": "T", "paragraphs": [{"context": "sin respuesta", "qas": []}]}]}
    docs, cases, stats = search_data.build_selection(data, {"data": []}, set())
    assert len(docs) == 1 and cases == []
    assert stats["answers_missed"] == 0


def test_metricas_por_etapa_y_conjunto() -> None:
    """recall@1/5/10 de documento y fragmento, MRR y latencia por etapa y conjunto."""
    rows = [
        _fila("a1", "xquad", True, 1, 1, 100.0),
        _fila("a2", "xquad", True, 3, 12, 200.0),
        _fila("b1", "sqac", True, 6, 2, 300.0),
        _fila("b2", "sqac", True, None, None, 400.0),
        _fila("b3", "sqac", False, 2, None, 500.0),
    ]
    summary = search_data.aggregate(rows)
    assert summary["n_cases"] == 5
    assert summary["n_covered"] == 4
    assert summary["n_uncovered"] == 1
    assert summary["latency_ms"] == {"p50": 300.0, "p95": 500.0}
    for stage in search_data.STAGES_4:
        everything = summary["stages"][stage]["all"]
        assert everything["n"] == 5
        assert everything["doc"]["@1"] == pytest.approx(1 / 5, abs=1e-4)
        assert everything["doc"]["@5"] == pytest.approx(3 / 5, abs=1e-4)
        assert everything["doc"]["@10"] == pytest.approx(4 / 5, abs=1e-4)
        assert everything["doc_mrr10"] == pytest.approx((1 + 1 / 3 + 1 / 6 + 1 / 2) / 5, abs=1e-4)
        assert everything["ans"]["@1"] == pytest.approx(1 / 4, abs=1e-4)
        assert everything["ans"]["@10"] == pytest.approx(2 / 4, abs=1e-4)
        assert everything["ans_mrr10"] == pytest.approx((1 + 1 / 2) / 4, abs=1e-4)
    xquad = summary["stages"]["dense"]["xquad"]
    assert xquad["n"] == 2 and xquad["doc"]["@5"] == pytest.approx(1.0, abs=1e-4)
    sqac = summary["stages"]["dense"]["sqac"]
    assert sqac["n"] == 3 and sqac["doc"]["@5"] == pytest.approx(1 / 3, abs=1e-4)


def test_detector_caza_fuga_inyectada() -> None:
    """La autoprueba ve cada clase de fuga inventada y el control sano pasa."""
    assert search_data.injected_leak_check()
    assert search_data.check_isolation(_iso_limpio()) == []
    for key in (
        "tenant_leaks",
        "owner_leaks",
        "cross_tenant_read_leaks",
        "cross_owner_read_leaks",
    ):
        envenenado = _iso_limpio()
        envenenado[key] = 1
        assert any(key in fuga for fuga in search_data.check_isolation(envenenado)), key


def test_control_ciego_es_fallo_del_instrumento() -> None:
    """Si ni la lectura propia devuelve nada, el instrumento esta ciego."""
    ciego = _iso_limpio()
    ciego["control_read"] = 0
    assert any("ciego" in fuga for fuga in search_data.check_isolation(ciego))


def _carga_completa() -> tuple[list[str], dict[str, Any]]:
    """Una salida completa y limpia con los 15944 casos sinteticos."""
    ids = [f"sqac:q{i}" for i in range(search_data.EXPECTED_CASES)]
    rows = [_fila(row_id, "sqac", True, 1, 1) for row_id in ids]
    payload = {
        "device": "cuda",
        "meta": {"n_docs": search_data.EXPECTED_DOCS, "chunks": search_data.EXPECTED_CHUNKS},
        "iso": _iso_limpio(),
        "rows": rows,
    }
    return ids, payload


def test_fuga_real_es_fallo_duro() -> None:
    """Una fuga de verdad sale con 1 y deja registrado su caso."""
    ids, payload = _carga_completa()
    payload["iso"] = {**_iso_limpio(), "cross_owner_read_leaks": 3}
    estado, motivo, resumen = search_data.summarize(ids, payload, {})
    assert estado == "hard_failed"
    assert "cross_owner_read_leaks" in motivo
    assert resumen["iso"]["cross_owner_read_leaks"] == 3


def test_calculo_incompleto_o_distinto_es_duro() -> None:
    """Faltan filas, sobran documentos o el detector esta ciego: salida dura."""
    ids, payload = _carga_completa()
    estado, _, _ = search_data.summarize(ids, {**payload, "rows": payload["rows"][:-1]}, {})
    assert estado == "hard_failed"
    duplicadas = {"rows": payload["rows"][:-1] + payload["rows"][:1]}
    estado, _, _ = search_data.summarize(ids, {**payload, **duplicadas}, {})
    assert estado == "hard_failed"
    otros_docs = {"meta": {"n_docs": 10, "chunks": search_data.EXPECTED_CHUNKS}}
    estado, _, _ = search_data.summarize(ids, {**payload, **otros_docs}, {})
    assert estado == "hard_failed"


def test_calidad_se_publica_sin_umbral() -> None:
    """Cero aciertos tambien es passed: la nota la pone U01, no el instrumento."""
    ids = [f"sqac:q{i}" for i in range(search_data.EXPECTED_CASES)]
    rows = [_fila(row_id, "sqac", True, None, None) for row_id in ids]
    payload = {
        "device": "cuda",
        "meta": {"n_docs": search_data.EXPECTED_DOCS, "chunks": search_data.EXPECTED_CHUNKS},
        "iso": _iso_limpio(),
        "rows": rows,
    }
    estado, motivo, resumen = search_data.summarize(ids, payload, {})
    assert estado == "passed"
    assert resumen["metrics"]["stages"]["rerank"]["all"]["doc"]["@5"] == 0.0
    assert "doc@5 0.0%" in motivo


def test_reanudacion_conserva_puntuadas() -> None:
    """Las filas viejas se conservan y las nuevas se anyaden sin colision."""
    viejas = [_fila("a", "sqac"), _fila("b", "sqac")]
    nuevas = [_fila("c", "sqac"), _fila("d", "sqac")]
    unidas, choques = search_data.merge_rows(viejas, nuevas)
    assert choques == 0
    assert [row["id"] for row in unidas] == ["a", "b", "c", "d"]
    unidas, choques = search_data.merge_rows(viejas, [_fila("b", "sqac", ms=999.0)])
    assert choques == 1 and len(unidas) == 2


def test_calculo_sin_cargadores_de_conjuntos() -> None:
    """El calculo del contenedor no importa cargadores de datasets ni LLM."""
    root = Path(__file__).resolve().parents[3] / "eval" / "phase1"
    forbidden = (
        "eval.inferes",
        "eval.reader",
        "load_dataset",
        "snapshot_download",
        "datasets.download",
        "litellm",
        "openai",
    )
    for name in ("search_compute.py", "search_data.py"):
        source = (root / name).read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{name} menciona {marker}"


def test_etapa_search_sin_skynet_es_infra() -> None:
    """Sin host no hay GPU: la etapa queda como infraestructura, sin red."""
    resultado = stages.run_search(Path("/tmp/inexistente"), None, timeout=10.0)
    assert resultado["state"] == "infra_error"


def test_progreso_cada_500_y_reanudacion() -> None:
    """El avance se guarda cada 500 y la reanudacion viaja al contenedor."""
    assert search_data.PROGRESS_EVERY == 500
    from eval.phase1 import search as search_stage

    calls: list[tuple[str, ...]] = []

    def falso_remote(host: str | None, *args: str, **kwargs: Any) -> str:
        calls.append(args)
        if args[:2] == ("docker", "exec") and args[-2:] == ("cat", "/tmp/search-run.log"):
            return "2026-01-01 INFO search_compute: puntuadas 500 {'tenant_results': 1}\n"
        return ""

    import eval.phase1.skynet as skynet_mod

    real = skynet_mod.remote
    skynet_mod.remote = falso_remote
    try:
        assert search_stage.read_progress("h", "api") == 500
    finally:
        skynet_mod.remote = real
    assert any("cat" in call for call in calls)


def test_sellados_bloquean_la_preparacion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Con sellados, la preparacion falla cerrada antes de tocar la red."""
    from eval.phase1 import search as search_stage

    monkeypatch.setattr(datasets, "sealed_precheck", Mock(return_value=["sellado"]))
    with pytest.raises(datasets.SealedError):
        search_stage.prepare()


def test_interfaz_search_explica_su_plazo() -> None:
    """La etapa documenta su plazo largo de GPU en el valor por defecto."""
    assert stages.SEARCH_TIMEOUT_FALLBACK == 10800.0


def _sonda(iso: dict[str, int], control: bool = False) -> None:
    """Suma a ``iso`` lo que aporta un caso sondeado (30+30 resultados)."""
    iso["tenant_results"] += search_data.CANDIDATES
    iso["owner_results"] += search_data.CANDIDATES
    iso["cross_tenant_reads"] += 1
    iso["cross_owner_reads"] += 1
    if control:
        iso["control_read"] = 2


def test_resume_restaura_iso_en_copia() -> None:
    """El parcial devuelve filas e iso; tocarlo no corrompe el fichero."""
    parcial = {"rows": [_fila("a", "sqac")], "iso": {**_iso_limpio(), "cross_tenant_reads": 1}}
    filas, iso = search_compute.extract_resume(parcial)
    assert [row["id"] for row in filas] == ["a"]
    assert iso is not None and iso["cross_tenant_reads"] == 1
    assert iso is not parcial["iso"]
    iso["cross_tenant_reads"] = 999
    assert parcial["iso"]["cross_tenant_reads"] == 1  # type: ignore[index]


@pytest.mark.parametrize(
    "parcial",
    [
        {"rows": []},
        {"rows": [], "iso": None},
        {"rows": [], "iso": {"control_read": 1}},
    ],
)
def test_parcial_sin_iso_pide_resondeo(parcial: dict[str, Any]) -> None:
    """Sin iso no hay restauracion: hay que re-sondear, nunca partir de cero."""
    filas, iso = search_compute.extract_resume(parcial)
    assert filas == [] and iso is None
    roto = search_compute.extract_resume({"rows": [], "iso": {**_iso_limpio(), "control_read": -1}})
    assert roto[1] is None
    with pytest.raises(ValueError):
        search_compute.extract_resume({})


def test_resume_mitad_cubre_todas_las_sondas() -> None:
    """Caida a mitad (~8000): al reanudar, las sondas cubren los 15944."""
    total = search_data.EXPECTED_CASES
    corte = 8000
    iso = search_compute.zero_iso()
    for posicion in range(total):
        _sonda(iso, control=posicion == 0)
        if posicion + 1 == corte:
            parcial_iso = dict(iso)
    assert parcial_iso["cross_tenant_reads"] == corte
    assert search_data.check_isolation(parcial_iso) != []
    _filas, restaurado = search_compute.extract_resume(
        {"rows": [_fila(f"sqac:q{i}", "sqac") for i in range(corte)], "iso": parcial_iso}
    )
    assert restaurado == parcial_iso
    assert restaurado is not None
    for _posicion in range(corte, total):
        _sonda(restaurado, control=False)
    assert restaurado["cross_tenant_reads"] == total
    assert restaurado["cross_owner_reads"] == total
    assert restaurado["control_read"] >= 1
    assert search_data.check_isolation(restaurado) == []


def test_resume_vacio_borde_no_pierde_iso() -> None:
    """Sin nada pendiente, el iso restaurado ya cubre todo y pasa."""
    total = search_data.EXPECTED_CASES
    filas = [_fila(f"sqac:q{i}", "sqac") for i in range(total)]
    unidas, choques = search_data.merge_rows(filas, [])
    assert choques == 0 and len(unidas) == total
    parcial = {"rows": filas, "iso": _iso_limpio()}
    _, restaurado = search_compute.extract_resume(parcial)
    assert restaurado == _iso_limpio()
    assert search_data.check_isolation(dict(restaurado or {})) == []


def test_iso_a_cero_con_filas_nunca_pasa() -> None:
    """Filas completas con iso a cero es fallo duro, nunca un completo silencioso."""
    _, payload = _carga_completa()
    estado, motivo, _ = search_data.summarize(
        [f"sqac:q{i}" for i in range(search_data.EXPECTED_CASES)],
        {**payload, "iso": search_compute.zero_iso()},
        {},
    )
    assert estado == "hard_failed"
    assert "sondas incompletas" in motivo or "ciego" in motivo


def test_salida_lleva_iso_para_el_parcial(tmp_path: Path) -> None:
    """Lo escrito por el calculo trae filas e iso para reanudar."""
    ajustes = SimpleNamespace(
        resolved_device="cpu",
        embedding_model="denso",
        embedding_revision="r1",
        bm25_model="bm25",
        bm25_revision="r1",
        reranker_model="reordenador",
        reranker_revision="r1",
        rrf_k=search_data.RRF_K,
    )
    destino = tmp_path / "salida.json"
    search_compute.write_out(destino, ajustes, [], 0, 0.0, 0.0, _iso_limpio(), [_fila("a", "sqac")])
    filas, iso = search_compute.extract_resume(json.loads(destino.read_text(encoding="utf-8")))
    assert [row["id"] for row in filas] == ["a"]
    assert iso == _iso_limpio()


def test_reanudacion_envia_iso(monkeypatch: pytest.MonkeyPatch) -> None:
    """El envio al contenedor lleva filas e iso; sin iso viaja nulo."""
    from eval.phase1 import search as search_stage

    capturado: dict[str, bytes] = {}

    def falso_run(cmd: list[str], **kwargs: Any) -> Any:
        capturado["entrada"] = kwargs["input"]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", falso_run)
    search_stage.send_resume("h", "api", [{"id": "a"}], {"control_read": 2})
    envio = json.loads(capturado["entrada"].decode("utf-8"))
    assert envio == {"rows": [{"id": "a"}], "iso": {"control_read": 2}}
    search_stage.send_resume("h", "api", [{"id": "a"}])
    envio = json.loads(capturado["entrada"].decode("utf-8"))
    assert envio == {"rows": [{"id": "a"}], "iso": None}


def test_avance_guarda_iso_en_el_portatil(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El parcial del portatil guarda filas e iso para el mismo run_id."""
    from eval.phase1 import search as search_stage

    parcial = {"rows": [_fila("a", "sqac")], "iso": _iso_limpio()}
    texto = json.dumps(parcial, ensure_ascii=False)
    llamadas = iter([False, True])

    monkeypatch.setattr(search_stage, "compute_done", lambda host, api: next(llamadas))
    monkeypatch.setattr(search_stage, "container_alive", lambda host, api: True)
    monkeypatch.setattr(search_stage, "read_progress", lambda host, api: 500)
    monkeypatch.setattr(search_stage, "collect_text", lambda host, api, path: texto)
    monkeypatch.setattr("time.sleep", lambda segundos: None)
    resultado = search_stage.wait_compute("h", "api", tmp_path, 9999999999.0, lambda mensaje: None)
    assert resultado == parcial
    guardado = json.loads((tmp_path / "search-partial.json").read_text(encoding="utf-8"))
    assert guardado == parcial


def test_aggregate_sin_profundidades_no_añade_seccion() -> None:
    filas = [{"id": "a", "src": "sqac", "covered": True, "ms": 1.0, "h_doc": 1, "r_doc": 1}]
    assert search_data.aggregate_depth(filas) == {}
    assert "depth" not in search_data.aggregate(filas)


def test_aggregate_depth_mide_cobertura_y_muestra() -> None:
    """La cobertura usa todas las filas; el reranker solo la muestra marcada."""
    filas: list[dict[str, Any]] = [
        {
            "id": "a",
            "src": "sqac",
            "covered": True,
            "ms": 1.0,
            "h_doc": None,
            "h50_doc": 40,
            "r_doc": None,
            "r_ans": None,
            "sample": True,
            "r30_ms": 200.0,
            "r50_doc": 2,
            "r50_ans": 3,
            "r50_ms": 330.0,
        },
        {
            "id": "b",
            "src": "sqac",
            "covered": True,
            "ms": 1.0,
            "h_doc": 3,
            "h50_doc": 3,
            "r_doc": 1,
            "r_ans": 1,
        },
    ]
    depth = search_data.aggregate_depth(filas)
    assert depth["coverage_doc"] == {"30": 0.5, "50": 1.0}
    assert depth["sample_n"] == 1
    assert depth["sample"]["30"] == {"doc@5": 0.0, "ans@5": 0.0, "rerank_ms_p50": 200.0}
    assert depth["sample"]["50"] == {"doc@5": 1.0, "ans@5": 1.0, "rerank_ms_p50": 330.0}


def test_parse_depths_valida_los_limites() -> None:
    from eval.phase1.search_compute import parse_depths

    assert parse_depths("", 100) == []
    assert parse_depths("50, 100,50", 100) == [50, 100]
    for malo in ("30", "101", "10"):
        with pytest.raises(ValueError):
            parse_depths(malo, 100)


def test_depth_arguments_desde_el_entorno(monkeypatch: pytest.MonkeyPatch) -> None:
    from eval.phase1 import search

    monkeypatch.delenv("RAGMUR_SEARCH_DEPTHS", raising=False)
    assert search.depth_arguments() == []
    monkeypatch.setenv("RAGMUR_SEARCH_DEPTHS", "50,100")
    assert search.depth_arguments() == ["--depths", "50,100", "--rerank-every", "10"]
    monkeypatch.setenv("RAGMUR_SEARCH_RERANK_EVERY", "5")
    assert search.depth_arguments()[-1] == "5"
