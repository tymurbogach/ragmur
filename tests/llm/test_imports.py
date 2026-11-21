"""Solo `provider.py` puede importar un SDK de proveedor LLM (regla 7)."""

import ast
from pathlib import Path

_SDK_PREFIXES = ("litellm", "openai", "anthropic")

# `sys.modules["litellm"]` (acceso por subíndice, sin importar) queda
# permitido: `tests/llm/test_provider.py` lo usa para simular `acompletion`
# sin traer `litellm` al espacio del test, lo que rompería este confinamiento.


def _is_sdk_literal(node: ast.AST) -> bool:
    """Cadena literal que nombra un SDK (`"litellm"`, `"openai"`, ...)."""
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.split(".")[0] in _SDK_PREFIXES
    )


def _check_dynamic_import(node: ast.Call, path: Path) -> None:
    """Rechaza `importlib.import_module("litellm")` y `__import__("...")`."""
    func = node.func
    if isinstance(func, ast.Name) and func.id == "__import__":
        assert not (node.args and _is_sdk_literal(node.args[0])), path
    elif (
        isinstance(func, ast.Attribute)
        and func.attr == "import_module"
        and node.args
        and _is_sdk_literal(node.args[0])
    ):
        raise AssertionError(path)


def test_llm_sdk_imports_are_confined_to_provider() -> None:
    root = Path(__file__).resolve().parents[2]
    allowed = root / "src" / "ragmur" / "llm" / "provider.py"
    assert allowed.is_file()
    scanned = 0
    for base in ("src", "eval", "tests", "benchmarks"):
        base_dir = root / base
        if not base_dir.is_dir():
            continue
        for path in sorted(base_dir.rglob("*.py")):
            if path == allowed:
                continue
            scanned += 1
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for item in node.names:
                        assert item.name.split(".")[0] not in _SDK_PREFIXES, path
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    assert module.split(".")[0] not in _SDK_PREFIXES, path
                    for item in node.names:
                        assert item.name.split(".")[0] not in _SDK_PREFIXES, path
                elif isinstance(node, ast.Call):
                    _check_dynamic_import(node, path)
    assert scanned > 0
