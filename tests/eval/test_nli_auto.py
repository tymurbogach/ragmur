"""Diagnóstico sintético F07 solo dev local, sin inferencia real."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import yaml  # type: ignore[import-untyped]
from eval.check_nli_leak import (
    LEXICAL_JACCARD_THRESHOLD,
    auto_dataset_errors,
    auto_manifest_map,
    auto_test_execution_errors,
    collect_burnt_ids,
    run_auto_checks,
)
from eval.nli_run import validate_cases

from ragmur.ingestion.chunker import split_document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment
from ragmur.verification.splitter import split_claims

AUTO_MANIFEST = Path("eval/eu_auto_manifest.yaml")
AUTO_ES = Path("eval/eu_nli_dev_auto_es.yaml")
AUTO_EN = Path("eval/eu_nli_dev_auto_en.yaml")
FROZEN_MANIFEST = Path("eval/eu_manifest.yaml")
FROZEN_TEST = Path("eval/eu_nli_test.yaml")


def _load_manifest() -> list[Any]:
    data: Any = yaml.safe_load(AUTO_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def _load_cases(path: Path) -> list[Any]:
    data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def test_auto_manifest_freeze() -> None:
    entries = _load_manifest()
    manifest, errors = auto_manifest_map(entries)
    assert not errors
    assert len(manifest) == 35
    dev = sum(1 for info in manifest.values() if info["split"] == "dev")
    test = sum(1 for info in manifest.values() if info["split"] == "test")
    assert (dev, test) == (26, 9)
    es_dev = sum(1 for i in manifest.values() if i["split"] == "dev" and i["lang"] == "es")
    en_dev = sum(1 for i in manifest.values() if i["split"] == "dev" and i["lang"] == "en")
    assert (es_dev, en_dev) == (11, 15)
    assert all(key.startswith("eua-") for key in manifest)
    assert not any(key.startswith("eut-") or key.startswith("euh2-") for key in manifest)
    for entry in entries:
        assert isinstance(entry, dict)
        sha = entry.get("sha256")
        assert isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)
        for field in ("path", "source", "license"):
            value = entry.get(field)
            assert isinstance(value, str) and value.strip()


def test_auto_manifest_no_overlap_frozen() -> None:
    frozen = yaml.safe_load(FROZEN_MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(frozen, list)
    frozen_ids = {str(e.get("document_id")) for e in frozen if isinstance(e, dict)}
    assert len(frozen_ids) == 24
    auto_ids = {str(e.get("document_id")) for e in _load_manifest() if isinstance(e, dict)}
    assert not (frozen_ids & auto_ids)


def test_auto_datasets_counts_and_labels() -> None:
    for path in (AUTO_ES, AUTO_EN):
        cases = _load_cases(path)
        assert len(cases) == 300
        labels = [str(c["claims"][0]["label"]) for c in cases if isinstance(c, dict)]
        assert labels.count("supported") == 100
        assert labels.count("contradicted") == 100
        assert labels.count("unsupported") == 100
        assert all(str(c.get("split")) == "dev" for c in cases)
        assert all(c.get("gold") is False for c in cases)
        assert all(c.get("status") == "auto_rule_v1" for c in cases)
        assert all(str(c.get("id", "")).startswith("eua-") for c in cases)
        assert len({str(c.get("id")) for c in cases}) == 300
        validate_cases(cases, require_document_id=True)


def test_auto_datasets_never_weak() -> None:
    for path in (AUTO_ES, AUTO_EN):
        for case in _load_cases(path):
            assert isinstance(case, dict)
            claims = case.get("claims")
            assert isinstance(claims, list)
            for claim in claims:
                assert isinstance(claim, dict)
                assert claim.get("label") in ("supported", "contradicted", "unsupported")
                assert claim.get("label") != "weak"


def test_auto_datasets_rules_match_labels() -> None:
    for path in (AUTO_ES, AUTO_EN):
        for case in _load_cases(path):
            assert isinstance(case, dict)
            rule = str(case.get("rule"))
            label = str(case["claims"][0]["label"]) if isinstance(case.get("claims"), list) else ""
            if rule == "supported_verbatim":
                assert label == "supported"
            elif rule.startswith("contradicted_"):
                assert label == "contradicted"
            elif rule == "unsupported_crossdoc":
                assert label == "unsupported"
            else:
                raise AssertionError(f"regla inválida {rule}")
            if rule.startswith("contradicted_"):
                source = case.get("source_sentence")
                assert isinstance(source, str) and source.strip()


def test_auto_supported_containment_sample() -> None:
    for path in (AUTO_ES, AUTO_EN):
        cases = _load_cases(path)
        supported = [c for c in cases if c["claims"][0]["label"] == "supported"]
        assert len(supported) == 100
        for case in supported[:30]:
            premise = str(case["premise"])
            claim = str(case["claims"][0]["text"])
            assert _norm(claim) in _norm(premise)
            assert len(premise) <= 800


def test_auto_unsupported_guard_sample() -> None:
    for path in (AUTO_ES, AUTO_EN):
        cases = _load_cases(path)
        unsupported = [c for c in cases if c["claims"][0]["label"] == "unsupported"]
        assert len(unsupported) == 100
        for case in unsupported[:30]:
            premise = str(case["premise"])
            claim = str(case["claims"][0]["text"])
            assert _norm(claim) not in _norm(premise)
            assert not (set(re.findall(r"\d+", premise)) & set(re.findall(r"\d+", claim)))


def test_auto_premises_are_real_chunks() -> None:
    manifest = {str(e["document_id"]): e for e in _load_manifest() if isinstance(e, dict)}
    for path, lang in ((AUTO_ES, "es"), (AUTO_EN, "en")):
        cases = _load_cases(path)
        sample = sorted(cases, key=lambda c: str(c["id"]))[:10]
        for case in sample:
            doc_id = str(case["document_id"])
            entry = manifest[doc_id]
            text = (Path("eval") / str(entry["path"])).read_text(encoding="utf-8")
            fragment = Fragment(text, {"type": "offset", "start": 0, "end": len(text)})
            extraction = ExtractionResult([fragment])
            chunks = split_document(
                extraction,
                uuid5(NAMESPACE_URL, doc_id),
                uuid5(NAMESPACE_URL, "ragmur-auto-tenant"),
                None,
                size=800,
                overlap=120,
            ).chunks
            assert str(case["premise"]) in [chunk.text for chunk in chunks]
            locator = case.get("premise_locator")
            assert isinstance(locator, dict) and locator.get("type") == "offset"
        assert lang in ("es", "en")


def test_auto_splitter_sentences_in_premise() -> None:
    for path in (AUTO_ES, AUTO_EN):
        cases = _load_cases(path)
        case = next(c for c in cases if c["claims"][0]["label"] == "supported")
        premise = str(case["premise"])
        sents = split_claims(premise, max_claims=20, max_chars=4096)
        assert _norm(str(case["claims"][0]["text"])) in [_norm(s) for s in sents] or _norm(
            str(case["claims"][0]["text"])
        ) in _norm(premise)


def test_auto_leak_checks_green() -> None:
    assert run_auto_checks(AUTO_MANIFEST, AUTO_ES, AUTO_EN, Path("eval/results")) == []


def test_auto_rejects_burnt_and_weak() -> None:
    manifest = {"eua-es-amazon-0": {"split": "dev", "lang": "es"}}
    burnt = {"eua-es-001"}
    good = [
        {
            "id": "eua-es-001",
            "document_id": "eua-es-amazon-0",
            "split": "dev",
            "premise": "El oxígeno se descubrió en 1774 por Priestley en Wiltshire.",
            "premise_locator": {"type": "offset", "start": 0, "end": 58},
            "lang": "es",
            "gold": False,
            "status": "auto_rule_v1",
            "rule": "supported_verbatim",
            "claims": [{"text": "El oxígeno se descubrió en 1774.", "label": "supported"}],
        }
    ]
    errors = auto_dataset_errors("auto", good, manifest, burnt, {})
    assert any("quemado" in error for error in errors)
    weak = [
        {
            "id": "eua-es-002",
            "document_id": "eua-es-amazon-0",
            "split": "dev",
            "premise": "fuente con contenido suficiente para la prueba",
            "premise_locator": {"type": "offset", "start": 0, "end": 10},
            "lang": "es",
            "gold": False,
            "status": "auto_rule_v1",
            "rule": "supported_verbatim",
            "claims": [{"text": "afirmación", "label": "weak"}],
        }
    ]
    errors = auto_dataset_errors("auto", weak, manifest, set(), {})
    assert any("nunca usa weak" in error for error in errors)
    invalid = [
        {
            "id": "eua-es-003",
            "document_id": "eua-es-amazon-0",
            "split": "dev",
            "premise": "fuente con contenido suficiente para la prueba",
            "premise_locator": {"type": "offset", "start": 0, "end": 10},
            "lang": "es",
            "gold": False,
            "status": "auto_rule_v1",
            "rule": "supported_verbatim",
            "claims": [{"text": "afirmación", "label": "bogus"}],
        }
    ]
    errors = auto_dataset_errors("auto", invalid, manifest, set(), {})
    assert any("inválida" in error for error in errors)
    assert not any("nunca usa weak" in error for error in errors)


def test_auto_manifest_rejects_wrong_counts() -> None:
    entries = _load_manifest()
    bad = [dict(e) for e in entries]
    assert isinstance(bad[0], dict)
    bad[0] = dict(bad[0])
    bad[0]["split"] = "test"
    _, errors = auto_manifest_map(bad)
    assert any("26/9" in error or "11/15" in error for error in errors)


def test_frozen_test_opened_once_with_reviewed_pairs() -> None:
    """F03: la reserva se abrió una vez con pares humanos, ya no está pendiente."""
    from eval.check_nli_leak import BLESSED_TEST_OPENING, collect_burnt_ids, manifest_map

    raw = FROZEN_TEST.read_bytes()
    assert b"PENDING HUMAN REVIEW" not in raw
    cases = yaml.safe_load(raw)
    assert isinstance(cases, list) and len(cases) > 0
    manifest, errors = manifest_map(yaml.safe_load(FROZEN_MANIFEST.read_text(encoding="utf-8")))
    assert not errors
    burnt = collect_burnt_ids()
    for case in cases:
        assert case["split"] == "test"
        assert manifest[case["document_id"]] == "test"
        assert case["id"] not in burnt
        for claim in case["claims"]:
            assert claim["label"] in ("supported", "contradicted", "unsupported")
    assert BLESSED_TEST_OPENING == "nli-eu-test-2026-11-18.json"


def test_thresholds_intact_in_config() -> None:
    text = Path("src/ragmur/core/config.py").read_text(encoding="utf-8")
    assert "verify_supported_threshold: float = Field(default=0.75" in text
    assert "verify_weak_threshold: float = Field(default=0.5" in text
    assert "verify_contradiction_threshold: float = Field(default=0.75" in text


def test_auto_ids_not_burnt() -> None:
    burnt = collect_burnt_ids()
    assert not any(item.startswith("eua-") for item in burnt)
    for path in (AUTO_ES, AUTO_EN):
        for case in _load_cases(path):
            assert isinstance(case, dict)
            case_id = str(case.get("id"))
            assert case_id not in burnt
            assert not case_id.startswith("eut-")
            assert not case_id.startswith("euh2-")


def test_auto_manifest_hashes_match_corpus() -> None:
    for entry in _load_manifest():
        assert isinstance(entry, dict)
        digest = hashlib.sha256((Path("eval") / str(entry["path"])).read_bytes()).hexdigest()
        assert digest == entry["sha256"]


def _unsupported_case(case_id: str, premise: str, claim_text: str) -> dict[str, Any]:
    return {
        "id": case_id,
        "document_id": "eua-es-amazon-0",
        "split": "dev",
        "premise": premise,
        "premise_locator": {"type": "offset", "start": 0, "end": len(premise)},
        "lang": "es",
        "gold": False,
        "status": "auto_rule_v1",
        "rule": "unsupported_crossdoc",
        "claims": [{"text": claim_text, "label": "unsupported"}],
    }


def test_auto_lexical_guard_threshold_is_0_3() -> None:
    assert LEXICAL_JACCARD_THRESHOLD == 0.3
    manifest = {"eua-es-amazon-0": {"split": "dev", "lang": "es"}}
    premise = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    below = _unsupported_case("eua-es-101", premise, "alpha beta gamma lorem ipsum dolor")
    assert auto_dataset_errors("auto", [below], manifest, set(), {}) == []
    above = _unsupported_case("eua-es-102", premise, "alpha beta gamma delta lorem ipsum")
    errors = auto_dataset_errors("auto", [above], manifest, set(), {})
    assert any("guarda léxica" in error for error in errors)


def test_auto_test_detection_robust_to_spacing(tmp_path: Path) -> None:
    auto_sha = "a" * 64
    payload_test = {
        "auto_marker": True,
        "split": "test",
        "dataset_sha256": auto_sha,
    }
    target = tmp_path / "nli-auto-dev-2026-11-13.json"
    target.write_text(json.dumps(payload_test, separators=(",", ":")), encoding="utf-8")
    assert "auto" in target.read_text(encoding="utf-8").lower()
    assert '"split": "test"' not in target.read_text(encoding="utf-8")
    errors = auto_test_execution_errors(tmp_path, {auto_sha})
    assert any("split test" in error for error in errors)
    payload_dev = {
        "auto_marker": True,
        "split": "dev",
        "dataset_sha256": auto_sha,
    }
    target.write_text(json.dumps(payload_dev), encoding="utf-8")
    assert auto_test_execution_errors(tmp_path, {auto_sha}) == []
