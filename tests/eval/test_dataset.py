"""Validación de corpus y consultas de evaluación."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from eval.dataset import load_manifest, load_queries, validate_dataset
from pydantic import ValidationError


def write_yaml(path: Path, value: object) -> None:
    path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")


def test_manifest_checks_hash_and_references(tmp_path: Path) -> None:
    data = b"Evidence text"
    (tmp_path / "source.txt").write_bytes(data)
    manifest_file = tmp_path / "manifest.yaml"
    write_yaml(
        manifest_file,
        {
            "documents": [
                {
                    "key": "doc",
                    "path": "source.txt",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "source": "test",
                    "license": "test",
                    "tenant": "demo",
                }
            ]
        },
    )
    manifest = load_manifest(manifest_file)
    queries_file = tmp_path / "golden.yaml"
    query: dict[str, Any] = {
        "id": "q1",
        "split": "dev",
        "scope": {"tenant": "demo", "owner_id": None},
        "query": "Where?",
        "expected": [
            {
                "evidence_id": "e1",
                "document": "doc",
                "locator": {"type": "offset", "start": 0, "end": 8},
                "quote": "Evidence",
            }
        ],
        "note": "test",
    }
    write_yaml(queries_file, [query])
    assert load_queries(queries_file, manifest)[0].expected[0].document == "doc"
    query["expected"][0]["document"] = "unknown"
    write_yaml(queries_file, [query])
    with pytest.raises(ValueError, match="unknown document"):
        load_queries(queries_file, manifest)
    (tmp_path / "source.txt").write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_manifest(manifest_file)


def test_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    manifest_file = tmp_path / "manifest.yaml"
    write_yaml(
        manifest_file,
        {
            "documents": [
                {
                    "key": "doc",
                    "path": "../outside.txt",
                    "sha256": "a" * 64,
                    "source": "test",
                    "license": "test",
                    "tenant": "demo",
                }
            ]
        },
    )
    with pytest.raises(ValueError, match="Invalid corpus path"):
        load_manifest(manifest_file)


def test_query_validation_rejects_duplicates_and_requires_partitions(tmp_path: Path) -> None:
    data = b"a"
    (tmp_path / "a.txt").write_bytes(data)
    manifest_file = tmp_path / "manifest.yaml"
    write_yaml(
        manifest_file,
        {
            "documents": [
                {
                    "key": "a",
                    "path": "a.txt",
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "source": "test",
                    "license": "test",
                    "tenant": "demo",
                }
            ]
        },
    )
    manifest = load_manifest(manifest_file)
    query = {
        "id": "q1",
        "split": "dev",
        "scope": {"tenant": "demo"},
        "query": "Why?",
        "expected": [],
        "note": "negative",
    }
    queries_file = tmp_path / "queries.yaml"
    write_yaml(queries_file, [query, query])
    with pytest.raises(ValueError, match="unique"):
        load_queries(queries_file, manifest)
    write_yaml(queries_file, [query])
    with pytest.raises(ValueError, match="25 to 30"):
        validate_dataset(load_queries(queries_file, manifest))
    query["scope"] = {"tenant": "demo", "owner_id": " "}
    write_yaml(queries_file, [query])
    with pytest.raises(ValidationError):
        load_queries(queries_file, manifest)
