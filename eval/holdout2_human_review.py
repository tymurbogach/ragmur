"""Validación ciega y comparación agregada de la revisión humana (holdout2).

El formulario solo contiene fragmentos y afirmaciones con identificadores
opacos y juicios vacíos. Este módulo valida la entrega sin leer etiquetas IA
y, solo con los 279 juicios completos y válidos, calcula una comparación
agregada sin exponer predicciones por caso.

Antes de comparar, `comparar` exige los bytes del curado y verifica que su
SHA-256 coincida con `source_sha256` del mapeo y que el mapeo sea biyectivo
sobre los casos del dataset (cada `source_id` con los hashes reales de su
premisa y su única afirmación). Alcance: detecta alteraciones independientes
del mapeo o del dataset; no ofrece garantías frente a una modificación
coordinada de mapeo y formulario a la vez.
"""

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

JUICIOS_VALIDOS = ("apoyada", "contradicha", "no dice", "ambigua")

JUICIO_A_REFERENCIA = {
    "apoyada": "supported",
    "contradicha": "contradicted",
    "no dice": "unsupported",
}

CLAVES_INTERNAS_PROHIBIDAS = (
    "document_id",
    "locator",
    "ordinal",
    "span",
    "source",
    "chunking",
    "status",
    "human_review",
    "gold",
    "phenomenon",
    "note",
    "evidence_quote",
    "label",
    "score",
    "prediction",
    "verdict",
)


def sha256_texto(texto: str) -> str:
    """Calcula el SHA-256 de un texto en UTF-8."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def sha256_bytes(datos: bytes) -> str:
    """Calcula el SHA-256 de unos bytes."""
    return hashlib.sha256(datos).hexdigest()


def cargar_yaml(ruta: Path) -> Any:
    """Carga un fichero YAML como objeto de Python."""
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def validar(
    formulario: dict[str, Any],
    mapeo: dict[str, Any],
) -> list[str]:
    """Valida una entrega sin leer etiquetas IA. Devuelve la lista de errores."""
    errores: list[str] = []
    if not isinstance(formulario, dict) or not isinstance(formulario.get("fragmentos"), list):
        return ["El formulario debe ser un mapeo con la clave `fragmentos`"]
    if not isinstance(mapeo, dict) or not isinstance(mapeo.get("fragmentos"), list):
        return ["El mapeo debe ser un mapeo con la clave `fragmentos`"]
    fragmentos_form: list[Any] = formulario["fragmentos"]
    fragmentos_map: list[Any] = mapeo["fragmentos"]
    esperados = mapeo.get("counts", {})
    n_fragmentos = esperados.get("fragmentos") if isinstance(esperados, dict) else None
    n_items = esperados.get("items") if isinstance(esperados, dict) else None

    referencia: dict[str, str] = {}
    for entrada in fragmentos_map:
        if not isinstance(entrada, dict):
            errores.append("Entrada de mapeo no válida")
            continue
        fid = entrada.get("fragment_id")
        items = entrada.get("items")
        if not isinstance(fid, str) or not isinstance(items, list):
            errores.append("Entrada de mapeo sin `fragment_id` o sin `items`")
            continue
        for item in items:
            if not isinstance(item, dict):
                errores.append(f"Ítem de mapeo no válido en {fid}")
                continue
            iid = item.get("item_id")
            if not isinstance(iid, str) or iid in referencia:
                errores.append(f"Ítem de mapeo duplicado o sin id en {fid}")
                continue
            referencia[iid] = fid

    vistos: set[str] = set()
    juicios_pendientes = 0
    for entrada in fragmentos_form:
        if not isinstance(entrada, dict):
            errores.append("Fragmento del formulario no válido")
            continue
        fid = entrada.get("fragment_id")
        premisa = entrada.get("premisa")
        afirmaciones = entrada.get("afirmaciones")
        if (
            not isinstance(fid, str)
            or not isinstance(premisa, str)
            or not isinstance(afirmaciones, list)
        ):
            errores.append("Fragmento sin `fragment_id`, `premisa` o `afirmaciones`")
            continue
        for clave in entrada:
            if clave in CLAVES_INTERNAS_PROHIBIDAS:
                errores.append(f"Clave interna prohibida en el formulario: {clave}")
        mapa_frag = next(
            (m for m in fragmentos_map if isinstance(m, dict) and m.get("fragment_id") == fid),
            None,
        )
        if mapa_frag is None:
            errores.append(f"Fragmento desconocido: {fid}")
            continue
        if sha256_texto(premisa) != str(mapa_frag.get("premise_sha256")):
            errores.append(f"Premisa manipulada o distinta en {fid}")
        for afirmacion in afirmaciones:
            if not isinstance(afirmacion, dict):
                errores.append(f"Afirmación no válida en {fid}")
                continue
            iid = afirmacion.get("item_id")
            texto = afirmacion.get("text")
            juicio = afirmacion.get("juicio")
            comentario = afirmacion.get("comentario")
            if not isinstance(iid, str):
                errores.append(f"Afirmación sin `item_id` en {fid}")
                continue
            if iid in vistos:
                errores.append(f"Ítem duplicado: {iid}")
                continue
            vistos.add(iid)
            if referencia.get(iid) != fid:
                errores.append(f"Ítem desconocido o fuera de su fragmento: {iid}")
                continue
            for clave in afirmacion:
                if clave in CLAVES_INTERNAS_PROHIBIDAS:
                    errores.append(f"Clave interna prohibida en el formulario: {clave}")
            if not isinstance(texto, str) or sha256_texto(texto) != str(
                next(
                    (
                        it.get("claim_sha256")
                        for it in mapa_frag.get("items", [])
                        if isinstance(it, dict) and it.get("item_id") == iid
                    ),
                    "",
                )
            ):
                errores.append(f"Texto manipulado o distinto en {iid}")
            if juicio is None:
                juicios_pendientes += 1
            elif juicio not in JUICIOS_VALIDOS:
                errores.append(f"Juicio no válido en {iid}: {juicio!r}")
            if not isinstance(comentario, str):
                errores.append(f"Comentario no válido en {iid}")

    if isinstance(n_fragmentos, int) and len(fragmentos_form) != n_fragmentos:
        errores.append(f"Se esperaban {n_fragmentos} fragmentos y hay {len(fragmentos_form)}")
    if isinstance(n_items, int) and len(vistos) != n_items:
        errores.append(f"Se esperaban {n_items} ítems y hay {len(vistos)}")
    faltan = set(referencia) - vistos
    sobran = vistos - set(referencia)
    if faltan:
        errores.append(f"Faltan {len(faltan)} ítems del mapeo")
    if sobran:
        errores.append(f"Sobran {len(sobran)} ítems ajenos al mapeo")
    if juicios_pendientes:
        errores.append(f"Faltan {juicios_pendientes} juicios por rellenar")
    return errores


def verificar_origen(
    mapeo: dict[str, Any],
    curado: list[dict[str, Any]],
    curado_bytes: bytes | None,
) -> None:
    """Verifica que el mapeo describe fielmente al dataset curado.

    Comprueba el SHA-256 de los bytes del curado frente a `source_sha256`
    del mapeo, la biyección entre `source_id` del mapeo e `id` del dataset,
    y que cada `source_id` corresponde a los hashes reales de su premisa
    y de su única afirmación. Falla con `ValueError` si cambia el mapeo
    o el dataset.
    """
    if not isinstance(mapeo, dict) or not isinstance(mapeo.get("fragmentos"), list):
        raise ValueError("Mapeo no válido para verificar el origen")
    fuente_sha = mapeo.get("source_sha256")
    if not isinstance(fuente_sha, str) or len(fuente_sha) != 64:
        raise ValueError("Mapeo sin `source_sha256` válido: mapeo alterado o incompleto")
    try:
        int(fuente_sha, 16)
    except ValueError as exc:
        raise ValueError("Mapeo sin `source_sha256` válido: mapeo alterado o incompleto") from exc
    if curado_bytes is None:
        raise ValueError(
            "Sin bytes del curado: no se puede verificar `source_sha256`; "
            "mapeo o dataset sin comprobar"
        )
    if sha256_bytes(curado_bytes) != fuente_sha:
        raise ValueError(
            "Dataset curado alterado: su SHA-256 no coincide con `source_sha256` del mapeo"
        )
    if not isinstance(curado, list):
        raise ValueError("Dataset curado no válido")
    premisa_por_fuente: dict[str, str] = {}
    texto_por_fuente: dict[str, str] = {}
    for registro in curado:
        if not isinstance(registro, dict):
            raise ValueError("Registro curado no válido: mapeo o dataset alterado")
        fuente = registro.get("id")
        premisa = registro.get("premise")
        claims = registro.get("claims")
        if not isinstance(fuente, str) or not isinstance(premisa, str):
            raise ValueError("Registro curado sin `id` o sin `premise`: mapeo o dataset alterado")
        if not isinstance(claims, list) or len(claims) != 1 or not isinstance(claims[0], dict):
            raise ValueError(
                f"Registro curado sin una única afirmación en {fuente}: mapeo o dataset alterado"
            )
        texto = claims[0].get("text")
        if not isinstance(texto, str):
            raise ValueError(
                f"Registro curado sin texto de afirmación en {fuente}: mapeo o dataset alterado"
            )
        if fuente in premisa_por_fuente:
            raise ValueError(f"ID duplicado en dataset curado: {fuente}")
        premisa_por_fuente[fuente] = premisa
        texto_por_fuente[fuente] = texto
    hash_afirmacion: dict[str, str] = {}
    hash_premisa_por_fragmento: dict[str, str] = {}
    fuentes_por_fragmento: dict[str, list[str]] = {}
    for entrada in mapeo["fragmentos"]:
        if not isinstance(entrada, dict):
            raise ValueError("Entrada de mapeo no válida: mapeo alterado")
        fid = entrada.get("fragment_id")
        items = entrada.get("items")
        premisa_sha = entrada.get("premise_sha256")
        if (
            not isinstance(fid, str)
            or not isinstance(items, list)
            or not isinstance(premisa_sha, str)
        ):
            raise ValueError("Entrada de mapeo sin `fragment_id` o sin hashes: mapeo alterado")
        if fid in hash_premisa_por_fragmento:
            raise ValueError(f"Fragmento duplicado en mapeo: {fid}")
        hash_premisa_por_fragmento[fid] = premisa_sha
        fuentes_por_fragmento[fid] = []
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Ítem de mapeo no válido en {fid}: mapeo alterado")
            fuente = item.get("source_id")
            reclamo_sha = item.get("claim_sha256")
            if not isinstance(fuente, str) or not isinstance(reclamo_sha, str):
                raise ValueError(f"Ítem de mapeo sin `source_id` en {fid}: mapeo alterado")
            if fuente in hash_afirmacion:
                raise ValueError(f"`source_id` duplicado o reasignado en mapeo: {fuente}")
            hash_afirmacion[fuente] = reclamo_sha
            fuentes_por_fragmento[fid].append(fuente)
    ids_curado = set(premisa_por_fuente)
    ids_mapeo = set(hash_afirmacion)
    if ids_curado != ids_mapeo:
        faltan = sorted(ids_curado - ids_mapeo)
        sobran = sorted(ids_mapeo - ids_curado)
        if faltan:
            raise ValueError(
                f"El mapeo no cubre {len(faltan)} casos del dataset "
                f"(p. ej. {faltan[0]}): mapeo o dataset alterado"
            )
        raise ValueError(
            f"El mapeo contiene {len(sobran)} `source_id` ajenos al dataset "
            f"(p. ej. {sobran[0]}): mapeo o dataset alterado"
        )
    for fid, fuentes in fuentes_por_fragmento.items():
        premisas = {premisa_por_fuente[fuente] for fuente in fuentes}
        if len(premisas) != 1:
            raise ValueError(
                f"Fragmento {fid} agrupa casos con premisas distintas "
                "en el dataset: mapeo o dataset alterado"
            )
        premisa = next(iter(premisas))
        if sha256_texto(premisa) != hash_premisa_por_fragmento[fid]:
            raise ValueError(
                f"Premisa del dataset no coincide con el mapeo en {fid}: mapeo o dataset alterado"
            )
        for fuente in fuentes:
            if sha256_texto(texto_por_fuente[fuente]) != hash_afirmacion[fuente]:
                raise ValueError(
                    f"Afirmación del dataset no coincide con el mapeo en {fuente}: "
                    "mapeo o dataset alterado"
                )


def comparar(
    formulario: dict[str, Any],
    mapeo: dict[str, Any],
    curado: list[dict[str, Any]],
    curado_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Compara la entrega validada con las etiquetas IA. Solo agregados.

    Exige la validación completa previa, verifica que el mapeo describe
    fielmente al dataset curado y nunca devuelve detalle por caso.

    Alcance de la verificación: detecta alteraciones independientes del
    mapeo o del dataset (bytes distintos de `source_sha256`, `source_id`
    reasignados o duplicados, textos que ya no coinciden con sus hashes).
    No protege frente a una modificación coordinada de mapeo y formulario
    a la vez: si ambos se reescriben de forma coherente, los hashes del
    formulario siguen pasando y el agregado puede ser incorrecto.
    """
    errores = validar(formulario, mapeo)
    if errores:
        raise ValueError("Entrega no válida: " + "; ".join(errores[:5]))
    verificar_origen(mapeo, curado, curado_bytes)
    referencia_ia: dict[str, str] = {}
    for registro in curado:
        if not isinstance(registro, dict):
            raise ValueError("Registro curado no válido")
        claims = registro.get("claims")
        if not isinstance(claims, list) or len(claims) != 1:
            raise ValueError("Registro curado sin una única afirmación")
        etiqueta = claims[0].get("label")
        if etiqueta not in ("supported", "contradicted", "unsupported"):
            raise ValueError("Etiqueta IA no válida")
        referencia_ia[str(registro.get("id"))] = str(etiqueta)
    item_a_fuente: dict[str, str] = {}
    for entrada in mapeo["fragmentos"]:
        for item in entrada["items"]:
            item_a_fuente[str(item["item_id"])] = str(item["source_id"])
    distribucion: dict[str, int] = {juicio: 0 for juicio in JUICIOS_VALIDOS}
    matriz: dict[str, dict[str, int]] = {
        juicio: {"supported": 0, "contradicted": 0, "unsupported": 0} for juicio in JUICIOS_VALIDOS
    }
    ambiguas = 0
    comparables = 0
    coincidencias = 0
    for fragmento in formulario["fragmentos"]:
        for afirmacion in fragmento["afirmaciones"]:
            juicio = str(afirmacion["juicio"])
            distribucion[juicio] += 1
            fuente = item_a_fuente[str(afirmacion["item_id"])]
            etiqueta_ia = referencia_ia[fuente]
            if juicio == "ambigua":
                ambiguas += 1
                continue
            comparables += 1
            matriz[juicio][etiqueta_ia] += 1
            if JUICIO_A_REFERENCIA[juicio] == etiqueta_ia:
                coincidencias += 1
    return {
        "total": sum(distribucion.values()),
        "distribucion_humana": distribucion,
        "ambiguas": ambiguas,
        "comparables": comparables,
        "coincidencias": coincidencias,
        "tasa_coincidencia": (coincidencias / comparables) if comparables else 0.0,
        "matriz_humana_vs_ia": matriz,
        "nota": (
            "Una sola revisión humana; no equivale a dos revisores "
            "ni declara gold, aceptación o cierre. Verificación previa: "
            "SHA-256 del curado igual a `source_sha256` del mapeo y cada "
            "`source_id` corresponde a los hashes reales de su premisa y "
            "su única afirmación. No protege frente a una modificación "
            "coordinada de mapeo y formulario a la vez."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del utilitario offline."""
    parser = argparse.ArgumentParser(description="Revisión humana ciega del holdout2")
    sub = parser.add_subparsers(dest="orden", required=True)
    validador = sub.add_parser("validar", help="Valida la entrega sin leer etiquetas IA")
    validador.add_argument("--formulario", type=Path, required=True)
    validador.add_argument("--mapeo", type=Path, required=True)
    comparador = sub.add_parser("comparar", help="Comparación agregada tras validar 279 juicios")
    comparador.add_argument("--formulario", type=Path, required=True)
    comparador.add_argument("--mapeo", type=Path, required=True)
    comparador.add_argument("--curado", type=Path, required=True)
    comparador.add_argument("--salida", type=Path, required=False)
    args = parser.parse_args(argv)
    formulario = cargar_yaml(args.formulario)
    mapeo = cargar_yaml(args.mapeo)
    errores = validar(formulario, mapeo)
    if args.orden == "validar":
        if errores:
            for error in errores:
                logging.warning("Entrega no válida: %s", error)
            return 1
        logging.warning("Entrega válida: juicios completos y textos intactos")
        return 0
    if errores:
        for error in errores:
            logging.warning("Entrega no válida: %s", error)
        return 1
    curado = cargar_yaml(args.curado)
    try:
        curado_bytes = args.curado.read_bytes()
    except OSError as exc:
        logging.warning("No se puede leer el curado: %s", exc)
        return 1
    try:
        resumen = comparar(formulario, mapeo, curado, curado_bytes)
    except ValueError as exc:
        logging.warning("Comparación imposible: %s", exc)
        return 1
    contenido = json.dumps(resumen, ensure_ascii=False, indent=2, sort_keys=True)
    if args.salida is not None:
        args.salida.write_text(contenido + "\n", encoding="utf-8")
        logging.warning("Resumen agregado en %s", args.salida)
    else:
        sys.stdout.write(contenido + "\n")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    raise SystemExit(main())
