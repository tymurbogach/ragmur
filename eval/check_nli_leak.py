"""Comprueba que los conjuntos NLI dev/test no comparten documentos.

Fase F01: el manifiesto queda congelado en 24 documentos (18 dev / 6 test)
y cada caso exige ``document_id`` igual a la clave del manifiesto, con
partición coincidente. Los borradores con etiquetas de IA ya ejecutados
como reserva (``eut-*`` y ``euh2-*``) están quemados y nunca son verdad:
reutilizar uno de sus identificadores en los conjuntos congelados falla.
En esta fase se prohíbe cualquier ``nli_run`` sobre test.

Fase F07: diagnóstico sintético EN+ES solo dev local. Manifiesto auto
separado con 35 documentos (26 dev / 9 test, ES 11/4 y EN 15/5) e IDs
``eua-*``. Solo dev genera casos; test queda reservado. Etiquetas
``gold: false`` y ``status: auto_rule_v1``, nunca ``weak`` como referencia.
Sin calibrar ni cerrar 1.8. Umbrales intactos 0.75/0.5/0.75.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import logging
import re
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
# Apertura única y legítima de la reserva (F03, 2026-11-18). Es el único
# resumen sobre test aceptado; cualquier otro reabre la reserva quemada.
BLESSED_TEST_OPENING = "nli-eu-test-2026-11-18.json"
BURNT_GLOBS = (
    "eval/eu_nli_test_ai_*.yaml",
    "eval/eu_nli_holdout2_ai_*.yaml",
    "eval/_archive_ai/eu_nli_test_ai_*.yaml",
    "eval/_archive_ai/eu_nli_holdout2_ai_*.yaml",
)

AUTO_EXPECTED_TOTAL = 35
AUTO_EXPECTED_DEV = 26
AUTO_EXPECTED_TEST = 9
AUTO_ID_PREFIX = "eua-"
AUTO_STATUS = "auto_rule_v1"
AUTO_VALID_RULES = (
    "supported_verbatim",
    "contradicted_negation",
    "contradicted_numeric",
    "contradicted_date",
    "contradicted_entity",
    "unsupported_crossdoc",
)

LEXICAL_JACCARD_THRESHOLD = 0.3

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
        if path.name == BLESSED_TEST_OPENING:
            continue
        errors.append(f"resultado reservado prohibido en esta fase: {path.name}")
    for path in sorted(results_dir.glob("*.json")):
        if path.name == BLESSED_TEST_OPENING:
            continue
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        marker = f'"dataset_sha256": "{test_sha256}"'.encode()
        if marker in payload:
            errors.append(f"{path.name} ejecutó el test congelado actual")
    return errors


def _normalize(text: str) -> str:
    """Normaliza espacios para comparar contención verbatim."""
    return re.sub(r"\s+", " ", text).strip()


def _word_set(text: str) -> set[str]:
    """Tokens alfanuméricos en minúsculas para la guarda léxica."""
    return set(re.findall(r"[a-záéíóúñü0-9]+", text.lower()))


def auto_manifest_map(entries: object) -> tuple[dict[str, dict[str, str]], list[str]]:
    """Valida el manifiesto auto y devuelve mapa a partición e idioma."""
    errors: list[str] = []
    if not isinstance(entries, list) or not entries:
        return {}, ["manifiesto auto vacío o con formato inválido"]
    mapping: dict[str, dict[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("entrada del manifiesto auto sin formato de diccionario")
            continue
        document_id = entry.get("document_id")
        split = entry.get("split")
        lang = entry.get("lang")
        if not isinstance(document_id, str) or not document_id:
            errors.append("entrada del manifiesto auto sin document_id")
            continue
        if not document_id.startswith(AUTO_ID_PREFIX):
            errors.append(f"manifiesto auto sin prefijo {AUTO_ID_PREFIX}: {document_id}")
        if document_id in mapping:
            errors.append(f"document_id duplicado en manifiesto auto: {document_id}")
            continue
        if split not in ("dev", "test"):
            errors.append(f"partición inválida en manifiesto auto para {document_id}: {split}")
            continue
        if lang not in ("es", "en"):
            errors.append(f"idioma inválido en manifiesto auto para {document_id}: {lang}")
            continue
        if document_id.startswith("eut-") or document_id.startswith("euh2-"):
            errors.append(f"manifiesto auto reutiliza reserva quemada: {document_id}")
            continue
        mapping[document_id] = {"split": str(split), "lang": str(lang)}
        sha = entry.get("sha256")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            errors.append(f"manifiesto auto sin sha256 válido para {document_id}")
        if not isinstance(entry.get("path"), str) or not entry.get("path"):
            errors.append(f"manifiesto auto sin ruta para {document_id}")
        if not isinstance(entry.get("source"), str) or not entry.get("source"):
            errors.append(f"manifiesto auto sin procedencia para {document_id}")
        if not isinstance(entry.get("license"), str) or not entry.get("license"):
            errors.append(f"manifiesto auto sin permiso para {document_id}")
    counts = Counter(info["split"] for info in mapping.values())
    if len(mapping) != AUTO_EXPECTED_TOTAL:
        errors.append(
            f"manifiesto auto con {len(mapping)} documentos, se esperan {AUTO_EXPECTED_TOTAL}"
        )
    if counts["dev"] != AUTO_EXPECTED_DEV or counts["test"] != AUTO_EXPECTED_TEST:
        errors.append(
            f"manifiesto auto dev/test {counts['dev']}/{counts['test']}, "
            f"se espera {AUTO_EXPECTED_DEV}/{AUTO_EXPECTED_TEST}"
        )
    lang_dev = Counter(info["lang"] for info in mapping.values() if info["split"] == "dev")
    if lang_dev["es"] != 11 or lang_dev["en"] != 15:
        errors.append(
            f"manifiesto auto dev es/en {lang_dev['es']}/{lang_dev['en']}, se espera 11/15"
        )
    lang_test = Counter(info["lang"] for info in mapping.values() if info["split"] == "test")
    if lang_test["es"] != 4 or lang_test["en"] != 5:
        errors.append(
            f"manifiesto auto test es/en {lang_test['es']}/{lang_test['en']}, se espera 4/5"
        )
    return mapping, errors


def auto_dataset_errors(
    name: str,
    data: object,
    manifest: dict[str, dict[str, str]],
    burnt_ids: set[str],
    seen_docs: dict[str, str],
) -> list[str]:
    """Valida un conjunto auto dev contra el manifiesto y reglas F07."""
    errors: list[str] = []
    if not isinstance(data, list) or not data:
        return [f"{name} auto debe ser una lista no vacía solo dev"]
    identifiers: set[str] = set()
    for case in data:
        if not isinstance(case, dict):
            errors.append(f"{name} auto tiene un caso sin formato de diccionario")
            continue
        case_id = case.get("id")
        document_id = case.get("document_id")
        split = case.get("split")
        if not isinstance(case_id, str) or not case_id or case_id in identifiers:
            errors.append(f"{name} auto tiene identificadores duplicados o vacíos")
            continue
        identifiers.add(case_id)
        if not case_id.startswith(AUTO_ID_PREFIX):
            errors.append(f"{name}/{case_id} auto sin prefijo {AUTO_ID_PREFIX}")
        if case_id in burnt_ids:
            errors.append(f"{name} auto reutiliza el identificador quemado {case_id}")
        if case_id.startswith("eut-") or case_id.startswith("euh2-"):
            errors.append(f"{name}/{case_id} auto reutiliza reserva quemada")
        if document_id not in manifest:
            errors.append(f"{name}/{case_id} auto usa document_id fuera del manifiesto")
            continue
        if split != manifest[str(document_id)]["split"]:
            errors.append(f"{name}/{case_id} auto declara split {split} distinto del manifiesto")
            continue
        if split != "dev":
            errors.append(f"{name}/{case_id} auto solo admite split dev en F07")
            continue
        if manifest[str(document_id)]["split"] != "dev":
            errors.append(f"{name}/{case_id} auto usa documento test en dev")
            continue
        if document_id in seen_docs and seen_docs[str(document_id)] != split:
            errors.append(f"documento auto {document_id} aparece en dev y en test")
        if isinstance(document_id, str):
            seen_docs.setdefault(document_id, str(split))
        premise = case.get("premise")
        locator = case.get("premise_locator")
        if not isinstance(premise, str) or not premise.strip():
            errors.append(f"{name}/{case_id} auto necesita una premisa no vacía")
            continue
        if len(premise) > 800:
            errors.append(f"{name}/{case_id} auto supera 800 caracteres de chunk")
        if not isinstance(locator, dict) or locator.get("type") != "offset":
            errors.append(f"{name}/{case_id} auto necesita localizador offset")
        if case.get("gold") is not False:
            errors.append(f"{name}/{case_id} auto exige gold:false")
        if case.get("status") != AUTO_STATUS:
            errors.append(f"{name}/{case_id} auto exige status {AUTO_STATUS}")
        rule = case.get("rule")
        if rule not in AUTO_VALID_RULES:
            errors.append(f"{name}/{case_id} auto tiene regla inválida")
        lang = case.get("lang")
        if lang != manifest[str(document_id)]["lang"]:
            errors.append(f"{name}/{case_id} auto idioma distinto del manifiesto")
        claims = case.get("claims")
        if not isinstance(claims, list) or not claims:
            errors.append(f"{name}/{case_id} auto necesita afirmaciones no vacías")
            continue
        for claim in claims:
            if not isinstance(claim, dict):
                errors.append(f"{name}/{case_id} auto tiene una etiqueta inválida")
                break
            if claim.get("label") == "weak":
                errors.append(f"{name}/{case_id} auto nunca usa weak como referencia")
                break
            if claim.get("label") not in VALID_LABELS:
                errors.append(f"{name}/{case_id} auto tiene una etiqueta inválida")
                break
            text = claim.get("text")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{name}/{case_id} auto tiene una afirmación vacía")
                break
            expected: str | None = None
            if isinstance(rule, str):
                if rule == "supported_verbatim":
                    expected = "supported"
                elif rule.startswith("contradicted_"):
                    expected = "contradicted"
                elif rule == "unsupported_crossdoc":
                    expected = "unsupported"
            if expected is not None and claim.get("label") != expected:
                errors.append(f"{name}/{case_id} auto regla {rule} exige {expected}")
                break
            norm_premise = _normalize(premise)
            norm_claim = _normalize(text)
            if expected == "supported" and norm_claim not in norm_premise:
                errors.append(f"{name}/{case_id} auto supported sin contención verbatim")
                break
            if expected == "unsupported":
                if norm_claim in norm_premise:
                    errors.append(f"{name}/{case_id} auto unsupported contenido en premisa")
                    break
                if set(re.findall(r"\d+", premise)) & set(re.findall(r"\d+", text)):
                    errors.append(f"{name}/{case_id} auto unsupported comparte dígitos")
                    break
                union = _word_set(premise) | _word_set(text)
                inter = _word_set(premise) & _word_set(text)
                jaccard = len(inter) / len(union) if union else 1.0
                if jaccard >= LEXICAL_JACCARD_THRESHOLD:
                    errors.append(f"{name}/{case_id} auto unsupported sin guarda léxica")
                    break
        if isinstance(rule, str) and rule.startswith("contradicted_"):
            source = case.get("source_sentence")
            if not isinstance(source, str) or not source.strip():
                errors.append(f"{name}/{case_id} auto contradicted sin frase origen")
            elif _normalize(str(source)) not in _normalize(premise):
                errors.append(f"{name}/{case_id} auto origen fuera de la premisa")
    return errors


def _contains_test_split(payload: object) -> bool:
    """Busca `split == "test"` en la estructura JSON sin depender del espaciado."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "split" and value == "test":
                return True
            if _contains_test_split(value):
                return True
        return False
    if isinstance(payload, list):
        return any(_contains_test_split(item) for item in payload)
    return False


def auto_test_execution_errors(results_dir: Path, auto_shas: set[str]) -> list[str]:
    """Falla si algún resumen ejecutó auto en test o mezcla auto con test."""
    errors: list[str] = []
    if not results_dir.is_dir():
        return errors
    for path in sorted(results_dir.glob("*auto*test*.json")):
        errors.append(f"resultado auto en test prohibido en F07: {path.name}")
    for path in sorted(results_dir.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "auto" not in text.lower() and path.name.find("auto") < 0:
            continue
        try:
            payload: object = json.loads(text)
        except ValueError:
            continue
        if not _contains_test_split(payload):
            continue
        for sha in auto_shas:
            if sha in text:
                errors.append(f"{path.name} ejecutó auto en split test")
                break
    return errors


def run_auto_checks(
    auto_manifest_path: Path,
    auto_dev_es_path: Path,
    auto_dev_en_path: Path,
    results_dir: Path,
) -> list[str]:
    """Valida manifiesto auto, datasets auto dev y ausencia de test auto."""
    try:
        auto_manifest_raw = auto_manifest_path.read_bytes()
        auto_es_raw = auto_dev_es_path.read_bytes()
        auto_en_raw = auto_dev_en_path.read_bytes()
    except OSError as exc:
        return [f"no se pudo leer un conjunto auto: {exc}"]
    auto_manifest_data: Any = yaml.safe_load(auto_manifest_raw.decode("utf-8"))
    auto_manifest, errors = auto_manifest_map(auto_manifest_data)
    burnt_ids = collect_burnt_ids()
    seen_docs: dict[str, str] = {}
    for name, raw in (
        (str(auto_dev_es_path), auto_es_raw.decode("utf-8")),
        (str(auto_dev_en_path), auto_en_raw.decode("utf-8")),
    ):
        data: Any = yaml.safe_load(raw)
        errors.extend(auto_dataset_errors(name, data, auto_manifest, burnt_ids, seen_docs))
    auto_shas = {
        hashlib.sha256(auto_es_raw).hexdigest(),
        hashlib.sha256(auto_en_raw).hexdigest(),
    }
    errors.extend(auto_test_execution_errors(results_dir, auto_shas))
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
    parser.add_argument("--auto-manifest", type=Path, default=Path("eval/eu_auto_manifest.yaml"))
    parser.add_argument("--auto-dev-es", type=Path, default=Path("eval/eu_nli_dev_auto_es.yaml"))
    parser.add_argument("--auto-dev-en", type=Path, default=Path("eval/eu_nli_dev_auto_en.yaml"))
    args = parser.parse_args()
    errors = run_checks(args.manifest, args.dev, args.test, args.results_dir)
    errors.extend(
        run_auto_checks(args.auto_manifest, args.auto_dev_es, args.auto_dev_en, args.results_dir)
    )
    # El manifiesto auto no reutiliza documentos del congelado: espacios distintos.
    try:
        frozen_data: Any = yaml.safe_load(args.manifest.read_bytes().decode("utf-8"))
        auto_data: Any = yaml.safe_load(args.auto_manifest.read_bytes().decode("utf-8"))
        frozen_ids = (
            {str(e.get("document_id")) for e in frozen_data if isinstance(e, dict)}
            if isinstance(frozen_data, list)
            else set()
        )
        auto_ids = (
            {str(e.get("document_id")) for e in auto_data if isinstance(e, dict)}
            if isinstance(auto_data, list)
            else set()
        )
        if frozen_ids & auto_ids:
            errors.append("manifiesto auto reutiliza document_id del congelado")
    except OSError as exc:
        errors.append(f"no se pudo comparar manifiestos: {exc}")
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
