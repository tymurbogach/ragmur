"""Revisión humana ciega del holdout2: formulario, mapeo y utilitario."""

import copy
import hashlib
from pathlib import Path
from typing import Any, cast

import pytest
import yaml  # type: ignore[import-untyped]
from eval.holdout2_human_review import (
    JUICIOS_VALIDOS,
    comparar,
    validar,
    verificar_origen,
)

FORMULARIO = Path("eval/eu_nli_holdout2_human_review_form.yaml")
MAPEO = Path("eval/eu_nli_holdout2_human_review_mapping.yaml")
CURADO = Path("eval/_archive_ai/eu_nli_holdout2_ai_curated.yaml")
SHA_CONGELADO = "c4ae0d9339c488392e5c103dc0559a89c4379342bc698c0d4b40df94a7ea919e"


def cargar_formulario() -> dict[str, Any]:
    """Carga el formulario ciego real."""
    return cast("dict[str, Any]", yaml.safe_load(FORMULARIO.read_text(encoding="utf-8")))


def cargar_mapeo() -> dict[str, Any]:
    """Carga el mapeo privado real."""
    return cast("dict[str, Any]", yaml.safe_load(MAPEO.read_text(encoding="utf-8")))


def rellenar(formulario: dict[str, Any], juicio: str = "apoyada") -> dict[str, Any]:
    """Devuelve una copia del formulario con todos los juicios cubiertos."""
    copia = copy.deepcopy(formulario)
    for fragmento in copia["fragmentos"]:
        for afirmacion in fragmento["afirmaciones"]:
            afirmacion["juicio"] = juicio
    return copia


def construir_miniatura() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], bytes]:
    """Construye una miniatura sintética coherente con bytes y SHA."""
    curado: list[dict[str, Any]] = [
        {
            "id": "s1",
            "premise": "premisa uno",
            "claims": [{"text": "afirmación 1", "label": "supported"}],
        },
        {
            "id": "s2",
            "premise": "premisa uno",
            "claims": [{"text": "afirmación 2", "label": "supported"}],
        },
        {
            "id": "s3",
            "premise": "premisa dos",
            "claims": [{"text": "afirmación 3", "label": "unsupported"}],
        },
        {
            "id": "s4",
            "premise": "premisa dos",
            "claims": [{"text": "afirmación 4", "label": "contradicted"}],
        },
    ]
    curado_bytes = yaml.safe_dump(curado, allow_unicode=True, sort_keys=True).encode("utf-8")
    mapeo: dict[str, Any] = {
        "counts": {"fragmentos": 2, "items": 4},
        "source_sha256": hashlib.sha256(curado_bytes).hexdigest(),
        "fragmentos": [
            {
                "fragment_id": "H2-F01",
                "premise_sha256": hashlib.sha256(b"premisa uno").hexdigest(),
                "items": [
                    {
                        "item_id": "H2-F01-1",
                        "source_id": "s1",
                        "claim_sha256": hashlib.sha256("afirmación 1".encode()).hexdigest(),
                    },
                    {
                        "item_id": "H2-F01-2",
                        "source_id": "s2",
                        "claim_sha256": hashlib.sha256("afirmación 2".encode()).hexdigest(),
                    },
                ],
            },
            {
                "fragment_id": "H2-F02",
                "premise_sha256": hashlib.sha256(b"premisa dos").hexdigest(),
                "items": [
                    {
                        "item_id": "H2-F02-1",
                        "source_id": "s3",
                        "claim_sha256": hashlib.sha256("afirmación 3".encode()).hexdigest(),
                    },
                    {
                        "item_id": "H2-F02-2",
                        "source_id": "s4",
                        "claim_sha256": hashlib.sha256("afirmación 4".encode()).hexdigest(),
                    },
                ],
            },
        ],
    }
    formulario: dict[str, Any] = {
        "fragmentos": [
            {
                "fragment_id": "H2-F01",
                "premisa": "premisa uno",
                "afirmaciones": [
                    {
                        "item_id": "H2-F01-1",
                        "text": "afirmación 1",
                        "juicio": "apoyada",
                        "comentario": "",
                    },
                    {
                        "item_id": "H2-F01-2",
                        "text": "afirmación 2",
                        "juicio": "contradicha",
                        "comentario": "",
                    },
                ],
            },
            {
                "fragment_id": "H2-F02",
                "premisa": "premisa dos",
                "afirmaciones": [
                    {
                        "item_id": "H2-F02-1",
                        "text": "afirmación 3",
                        "juicio": "no dice",
                        "comentario": "",
                    },
                    {
                        "item_id": "H2-F02-2",
                        "text": "afirmación 4",
                        "juicio": "ambigua",
                        "comentario": "duda",
                    },
                ],
            },
        ],
    }
    return mapeo, formulario, curado, curado_bytes


def test_formulario_agrupa_fragmentos_sin_pistas_ia() -> None:
    formulario = cargar_formulario()
    fragmentos = formulario["fragmentos"]
    assert len(fragmentos) == 93
    items = [a for f in fragmentos for a in f["afirmaciones"]]
    assert len(items) == 279
    assert len({a["item_id"] for a in items}) == 279
    assert len({f["fragment_id"] for f in fragmentos}) == 93
    for fragmento in fragmentos:
        assert set(fragmento) == {"fragment_id", "premisa", "afirmaciones"}
        assert len(fragmento["afirmaciones"]) == 3
        for afirmacion in fragmento["afirmaciones"]:
            assert set(afirmacion) == {"item_id", "text", "juicio", "comentario"}
            assert afirmacion["juicio"] is None
            assert afirmacion["comentario"] == ""
    crudo = FORMULARIO.read_text(encoding="utf-8")
    assert "euh2-" not in crudo
    for palabra in ("supported", "contradicted", "unsupported", "label", "score"):
        assert palabra not in crudo
    for clave in ("document_id", "evidence_quote", "gold", "phenomenon", "verdict"):
        assert clave not in crudo


def test_mapeo_traza_origen_sin_etiquetas() -> None:
    mapeo = cargar_mapeo()
    assert mapeo["source_file"] == str(CURADO)
    assert mapeo["source_sha256"] == SHA_CONGELADO
    assert hashlib.sha256(CURADO.read_bytes()).hexdigest() == SHA_CONGELADO
    assert mapeo["counts"] == {"fragmentos": 93, "items": 279}
    assert isinstance(mapeo["seed"], int)
    items = [it for f in mapeo["fragmentos"] for it in f["items"]]
    assert len(items) == 279
    assert len({it["item_id"] for it in items}) == 279
    assert len({it["source_id"] for it in items}) == 279
    crudo = MAPEO.read_text(encoding="utf-8")
    for palabra in ("supported", "contradicted", "unsupported"):
        assert palabra not in crudo


def test_validar_acepta_entrega_completa() -> None:
    assert validar(rellenar(cargar_formulario()), cargar_mapeo()) == []


def test_validar_detecta_formulario_incompleto() -> None:
    formulario = rellenar(cargar_formulario())
    formulario["fragmentos"][0]["afirmaciones"][0]["juicio"] = None
    errores = validar(formulario, cargar_mapeo())
    assert any("rellenar" in error for error in errores)


def test_validar_rechaza_vocabulario_fuera_de_lista() -> None:
    formulario = rellenar(cargar_formulario())
    formulario["fragmentos"][0]["afirmaciones"][0]["juicio"] = "supported"
    errores = validar(formulario, cargar_mapeo())
    assert any("no válido" in error for error in errores)


def test_validar_detecta_duplicados_y_desconocidos() -> None:
    formulario = rellenar(cargar_formulario())
    copia = copy.deepcopy(formulario["fragmentos"][0]["afirmaciones"][0])
    formulario["fragmentos"][1]["afirmaciones"].append(copia)
    errores = validar(formulario, cargar_mapeo())
    assert any("duplicado" in error for error in errores)

    formulario = rellenar(cargar_formulario())
    formulario["fragmentos"][0]["afirmaciones"][0]["item_id"] = "H2-F99-9"
    errores = validar(formulario, cargar_mapeo())
    assert any("desconocido" in error for error in errores)


def test_validar_detecta_textos_manipulados() -> None:
    formulario = rellenar(cargar_formulario())
    formulario["fragmentos"][0]["afirmaciones"][0]["text"] += " añadido"
    assert any("manipulado" in error for error in validar(formulario, cargar_mapeo()))
    formulario = rellenar(cargar_formulario())
    formulario["fragmentos"][0]["premisa"] += " añadido"
    assert any("manipulada" in error for error in validar(formulario, cargar_mapeo()))


def test_comparar_exige_entrega_completa() -> None:
    curado = yaml.safe_load(CURADO.read_text(encoding="utf-8"))
    curado_bytes = CURADO.read_bytes()
    with pytest.raises(ValueError, match="no válida"):
        comparar(cargar_formulario(), cargar_mapeo(), curado, curado_bytes)


def test_comparar_exige_bytes_del_curado() -> None:
    mapeo, formulario, curado, _ = construir_miniatura()
    with pytest.raises(ValueError, match="Sin bytes del curado"):
        comparar(formulario, mapeo, curado, None)


def test_comparar_solo_devuelve_agregados() -> None:
    """Compara una miniatura sintética: agregados correctos y sin detalle."""
    mapeo, formulario, curado, curado_bytes = construir_miniatura()
    assert validar(formulario, mapeo) == []
    resumen = comparar(formulario, mapeo, curado, curado_bytes)
    assert resumen["total"] == 4
    assert resumen["ambiguas"] == 1
    assert resumen["comparables"] == 3
    assert resumen["coincidencias"] == 2
    assert resumen["tasa_coincidencia"] == pytest.approx(2 / 3)
    texto = yaml.safe_dump(resumen, allow_unicode=True)
    assert "H2-F" not in texto and "s1" not in texto
    assert set(resumen) == {
        "total",
        "distribucion_humana",
        "ambiguas",
        "comparables",
        "coincidencias",
        "tasa_coincidencia",
        "matriz_humana_vs_ia",
        "nota",
    }
    assert "coordinada" in resumen["nota"]


def test_comparar_detecta_sha_distinto() -> None:
    mapeo, formulario, curado, _ = construir_miniatura()
    with pytest.raises(ValueError, match="SHA-256 no coincide"):
        comparar(formulario, mapeo, curado, b"bytes ajenos al curado")


def test_comparar_detecta_dataset_manipulado() -> None:
    """Un texto del dataset que ya no coincide con su hash invalida el agregado."""
    mapeo, formulario, curado, curado_bytes = construir_miniatura()
    curado[0]["claims"][0]["text"] = "afirmación manipulada"
    with pytest.raises(ValueError, match="mapeo o dataset alterado"):
        comparar(formulario, mapeo, curado, curado_bytes)


def test_comparar_detecta_source_ids_reordenados() -> None:
    """Reasignar `source_id` entre fragmentos rompe la correspondencia con el dataset."""
    mapeo, formulario, curado, curado_bytes = construir_miniatura()
    mapeo["fragmentos"][0]["items"][1]["source_id"] = "s3"
    mapeo["fragmentos"][1]["items"][0]["source_id"] = "s2"
    assert validar(formulario, mapeo) == []
    with pytest.raises(ValueError, match="mapeo o dataset alterado"):
        comparar(formulario, mapeo, curado, curado_bytes)


def test_comparar_detecta_source_ids_duplicados() -> None:
    mapeo, formulario, curado, curado_bytes = construir_miniatura()
    mapeo["fragmentos"][1]["items"][1]["source_id"] = "s1"
    with pytest.raises(ValueError, match="duplicado o reasignado"):
        verificar_origen(mapeo, curado, curado_bytes)
    with pytest.raises(ValueError, match=r"duplicado o reasignado|cubre|ajenos"):
        comparar(formulario, mapeo, curado, curado_bytes)


def test_comparar_verifica_origen_real() -> None:
    """El mapeo real es biyectivo sobre el dataset real y el agregado no detalla casos."""
    mapeo = cargar_mapeo()
    curado = yaml.safe_load(CURADO.read_text(encoding="utf-8"))
    curado_bytes = CURADO.read_bytes()
    verificar_origen(mapeo, curado, curado_bytes)
    resumen = comparar(rellenar(cargar_formulario()), mapeo, curado, curado_bytes)
    assert resumen["total"] == 279
    assert resumen["comparables"] == 279
    assert resumen["ambiguas"] == 0
    texto = yaml.safe_dump(resumen, allow_unicode=True)
    assert "H2-F" not in texto and "euh2-" not in texto


def test_vocabulario_revisor() -> None:
    assert set(JUICIOS_VALIDOS) == {"apoyada", "contradicha", "no dice", "ambigua"}
