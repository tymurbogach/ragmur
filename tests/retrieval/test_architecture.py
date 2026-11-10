"""Reglas de acceso al almacén vectorial."""

import ast
import inspect
from pathlib import Path

from ragmur.retrieval import store


def test_qdrant_client_imports_are_confined_to_store() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "ragmur"
    for path in root.rglob("*.py"):
        if path == root / "retrieval" / "store.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(not item.name.startswith("qdrant_client") for item in node.names), path
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("qdrant_client"), path


def test_public_store_functions_require_tenant_first() -> None:
    for name, function in inspect.getmembers(store, inspect.isfunction):
        if name.startswith("_") or function.__module__ != store.__name__:
            continue
        if name in {"create_client", "ping"}:
            continue
        parameters = list(inspect.signature(function).parameters.values())
        assert parameters and parameters[0].name == "tenant_id", name
        assert parameters[0].default is inspect.Parameter.empty, name
