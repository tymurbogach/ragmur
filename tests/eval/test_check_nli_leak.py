"""Comprueba el control anti-fuga por documento sin inferencia real."""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from eval.check_nli_leak import dataset_errors, manifest_map, run_checks


def _manifest_entries() -> list[dict[str, str]]:
    return [
        {"document_id": f"dev-{index:02d}", "split": "dev", "sha256": "a" * 64}
        for index in range(18)
    ] + [
        {"document_id": f"test-{index:02d}", "split": "test", "sha256": "b" * 64}
        for index in range(6)
    ]


def _write(path: Path, payload: object, pending: bool = False) -> None:
    header = "# PENDING HUMAN REVIEW\n" if pending else ""
    path.write_text(header + yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")


def test_manifest_freeze_counts() -> None:
    manifest, errors = manifest_map(_manifest_entries())
    assert not errors
    assert len(manifest) == 24


def test_manifest_rejects_wrong_split_counts() -> None:
    entries = _manifest_entries()
    entries[0]["split"] = "test"
    _, errors = manifest_map(entries)
    assert any("18/6" in error for error in errors)


def test_dataset_rejects_document_in_both_splits() -> None:
    manifest = {
        **{f"dev-{i:02d}": "dev" for i in range(18)},
        **{f"test-{i:02d}": "test" for i in range(6)},
    }
    seen: dict[str, str] = {}
    dev = [
        {
            "id": "d1",
            "document_id": "dev-00",
            "split": "dev",
            "premise": "fuente",
            "claims": [{"text": "afirmación", "label": "supported"}],
        }
    ]
    assert not dataset_errors("dev", yaml.safe_dump(dev), dev, manifest, set(), seen)
    test = [
        {
            "id": "t1",
            "document_id": "dev-00",
            "split": "test",
            "premise": "fuente",
            "claims": [{"text": "afirmación", "label": "unsupported"}],
        }
    ]
    errors = dataset_errors("test", yaml.safe_dump(test), test, manifest, set(), seen)
    assert any("manifiesto" in error or "dev y en test" in error for error in errors)


def test_dataset_rejects_burnt_identifier() -> None:
    manifest = {"dev-00": "dev"}
    case = [
        {
            "id": "eut-001",
            "document_id": "dev-00",
            "split": "dev",
            "premise": "fuente",
            "claims": [{"text": "afirmación", "label": "supported"}],
        }
    ]
    errors = dataset_errors("dev", yaml.safe_dump(case), case, manifest, {"eut-001"}, {})
    assert any("quemado" in error for error in errors)


def test_pending_empty_dataset_passes(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    dev = tmp_path / "dev.yaml"
    test = tmp_path / "test.yaml"
    results = tmp_path / "results"
    results.mkdir()
    manifest.write_text(yaml.safe_dump(_manifest_entries()), encoding="utf-8")
    _write(dev, [], pending=True)
    _write(test, [], pending=True)
    assert run_checks(manifest, dev, test, results) == []


def test_forbids_frozen_test_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import eval.check_nli_leak as leak

    manifest = tmp_path / "manifest.yaml"
    dev = tmp_path / "dev.yaml"
    test = tmp_path / "test.yaml"
    results = tmp_path / "results"
    results.mkdir()
    manifest.write_text(yaml.safe_dump(_manifest_entries()), encoding="utf-8")
    _write(dev, [], pending=True)
    _write(test, [], pending=True)
    (results / "nli-eu-test-2026-11-13.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(leak, "collect_burnt_ids", lambda *args, **kwargs: set())
    monkeypatch.chdir(tmp_path)
    assert any("prohibido" in error for error in run_checks(manifest, dev, test, results))


def test_allows_blessed_f03_opening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import eval.check_nli_leak as leak

    manifest = tmp_path / "manifest.yaml"
    dev = tmp_path / "dev.yaml"
    test = tmp_path / "test.yaml"
    results = tmp_path / "results"
    results.mkdir()
    manifest.write_text(yaml.safe_dump(_manifest_entries()), encoding="utf-8")
    _write(dev, [], pending=True)
    _write(test, [], pending=True)
    (results / leak.BLESSED_TEST_OPENING).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(leak, "collect_burnt_ids", lambda *args, **kwargs: set())
    monkeypatch.chdir(tmp_path)
    assert run_checks(manifest, dev, test, results) == []
