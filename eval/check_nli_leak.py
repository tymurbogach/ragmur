"""Comprueba que los conjuntos NLI dev/test no comparten documentos.

Fase F01: el manifiesto queda congelado en 24 documentos (18 dev / 6 test)
y cada caso exige ``document_id`` igual a la clave del manifiesto, con
partición coincidente. Los borradores con etiquetas de IA ya ejecutados
como reserva (``eut-*`` y ``euh2-*``) están quemados y nunca son verdad:
reutilizar uno de sus identificadores en los conjuntos congelados falla.
En esta fase se prohíbe cualquier ``nli_run`` sobre test.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

EXPECTED_TOTAL = 24
EXPECTED_DEV = 18
EXPECTED_TEST = 6
PENDING_MARKER = "PENDING HUMAN REVIEW"
VALID_LABELS = ("supported", "contradicted", "unsupported")
BURNT_GLOBS = ("eval/eu_nli_test_ai_*.yaml", "eval/eu_nli_holdout2_ai_*.yaml")

logger = logging.getLogger(__name__)


def manifest_map(entries: object) -> tuple[dict[str, str], list[str]]:
    """Devuelve el mapa documento a partición y los errores del manifiesto."""
    errors: list[str] = []
    if not isinstance(entries, list) or not entries:
        return {}, ["manifiesto vacío o con formato inválido"]
    mapping: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("entrada del manifiesto sin formato de diccionario")
            continue
        document_id, split = entry.get("document_id"), entry.get("split")
        if not isinstance(document_id, str) or not document_id:
            errors.append("entrada del manifiesto sin document_id")
        elif document_id in mapping:
            errors.append(f"document_id duplicado en manifiesto: {document_id}")
        elif split not in ("dev", "test"):
            errors.append(f"partición inválida para {document_id}: {split}")
        else:
            mapping[document_id] = split
        if not isinstance(entry.get("sha256"), str) or not entry.get("sha256"):
            errors.append(f"manifiesto sin sha256 para {document_id}")
    counts = Counter(mapping.values())
    if len(mapping) != EXPECTED_TOTAL:
        errors.append(f"manifiesto con {len(mapping)} documentos, se esperan {EXPECTED_TOTAL}")
    if counts["dev"] != EXPECTED_DEV or counts["test"] != EXPECTED_TEST:
        errors.append(f"manifiesto dev/test {counts['dev']}/{counts['test']}, se espera 18/6")
    return mapping, errors


def collect_burnt_ids(patterns: tuple[str, ...] = BURNT_GLOBS) -> set[str]:
    """Recoge los identificadores de los borradores IA ya ejecutados."""
    burnt: set[str] = set()
    for pattern in patterns:
        for path in glob.glob(pattern):
            try:
                data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
            except OSError:
                continue
            if isinstance(data, list):
                for case in data:
                    if isinstance(case, dict) and isinstance(case.get("id"), str):
                        burnt.add(case["id"])
    return burnt


def dataset_errors(
    name: str,
    raw: str,
    data: object,
    manifest: dict[str, str],
    burnt_ids: set[str],
    seen_docs: dict[str, str],
) -> list[str]:
    """Valida un conjunto congelado contra el manifiesto y la reserva quemada."""
    errors: list[str] = []
    if isinstance(data, list) and not data and PENDING_MARKER in raw:
        logger.warning("%s pendiente de revisión humana: sin pares todavía", name)
        return errors
    if not isinstance(data, list) or not data:
        return [f"{name} debe ser una lista no vacía o marcar {PENDING_MARKER}"]
    identifiers: set[str] = set()
    for case in data:
        if not isinstance(case, dict):
            errors.append(f"{name} tiene un caso sin formato de diccionario")
            continue
        case_id = case.get("id")
        document_id = case.get("document_id")
        split = case.get("split")
        if not isinstance(case_id, str) or not case_id or case_id in identifiers:
            errors.append(f"{name} tiene identificadores duplicados o vacíos")
        else:
            identifiers.add(case_id)
        if isinstance(case_id, str) and case_id in burnt_ids:
            errors.append(f"{name} reutiliza el identificador quemado {case_id}")
        if document_id not in manifest:
            errors.append(f"{name}/{case_id} usa document_id fuera del manifiesto")
            continue
        if split != manifest[document_id]:
            errors.append(f"{name}/{case_id} declara split {split} distinto del manifiesto")
            continue
        if document_id in seen_docs and seen_docs[document_id] != split:
            errors.append(f"documento {document_id} aparece en dev y en test")
        seen_docs.setdefault(document_id, split)
        claims = case.get("claims")
        premise = case.get("premise")
        if not isinstance(premise, str) or not premise.strip():
            errors.append(f"{name}/{case_id} necesita una premisa no vacía")
        if not isinstance(claims, list) or not claims:
            errors.append(f"{name}/{case_id} necesita afirmaciones no vacías")
            continue
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("label") not in VALID_LABELS:
                errors.append(f"{name}/{case_id} tiene una etiqueta inválida")
                break
            if not isinstance(claim.get("text"), str) or not claim["text"].strip():
                errors.append(f"{name}/{case_id} tiene una afirmación vacía")
                break
    return errors


def test_execution_errors(results_dir: Path, test_sha256: str) -> list[str]:
    """Falla si algún resumen ejecutó el conjunto test congelado."""
    errors: list[str] = []
    if not results_dir.is_dir():
        return errors
    for path in sorted(results_dir.glob("nli-eu-test-*.json")):
        errors.append(f"resultado reservado prohibido en esta fase: {path.name}")
    for path in sorted(results_dir.glob("*.json")):
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        marker = f'"dataset_sha256": "{test_sha256}"'.encode()
        if marker in payload:
            errors.append(f"{path.name} ejecutó el test congelado actual")
    return errors


def run_checks(
    manifest_path: Path, dev_path: Path, test_path: Path, results_dir: Path
) -> list[str]:
    """Ejecuta todas las comprobaciones y devuelve los errores encontrados."""
    try:
        manifest_raw = manifest_path.read_bytes()
        dev_raw = dev_path.read_bytes()
        test_raw = test_path.read_bytes()
    except OSError as exc:
        return [f"no se pudo leer un conjunto congelado: {exc}"]
    manifest_data: Any = yaml.safe_load(manifest_raw.decode("utf-8"))
    manifest, errors = manifest_map(manifest_data)
    burnt_ids = collect_burnt_ids()
    logger.warning("identificadores quemados registrados: %d", len(burnt_ids))
    seen_docs: dict[str, str] = {}
    for name, raw in (
        (str(dev_path), dev_raw.decode("utf-8")),
        (str(test_path), test_raw.decode("utf-8")),
    ):
        data: Any = yaml.safe_load(raw)
        errors.extend(dataset_errors(name, raw, data, manifest, burnt_ids, seen_docs))
    test_sha256 = hashlib.sha256(test_raw).hexdigest()
    errors.extend(test_execution_errors(results_dir, test_sha256))
    return errors


def main() -> None:
    """Punto de entrada del script anti-fuga por documento."""
    parser = argparse.ArgumentParser(description="Comprueba la separación dev/test por documento")
    parser.add_argument("--manifest", type=Path, default=Path("eval/eu_manifest.yaml"))
    parser.add_argument("--dev", type=Path, default=Path("eval/eu_nli_dev.yaml"))
    parser.add_argument("--test", type=Path, default=Path("eval/eu_nli_test.yaml"))
    parser.add_argument("--results-dir", type=Path, default=Path("eval/results"))
    args = parser.parse_args()
    errors = run_checks(args.manifest, args.dev, args.test, args.results_dir)
    if errors:
        for error in errors:
            logger.error("%s", error)
        raise SystemExit(1)
    logging.warning("anti-fuga NLI en verde: dev/test separados por documento")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.WARNING)
    try:
        main()
    except Exception:
        logger.exception("fallo inesperado del control anti-fuga")
        sys.exit(2)
