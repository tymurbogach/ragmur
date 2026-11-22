"""D4: un # dentro de un bloque de código Markdown no es un título."""

from pathlib import Path

import pytest

from ragmur.ingestion.extractors.core import extract_text


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="D4: # en bloque de código tomado por título"
)
def test_d4_hash_in_code_block_is_not_a_title(tmp_path: Path) -> None:
    """El código cercado no abre secciones aunque empiece por #."""
    path = tmp_path / "codigo.md"
    path.write_text(
        "# Informe\n\nTexto previo.\n\n```\n# no es un titulo\ncodigo()\n```\n\nTexto final.\n",
        encoding="utf-8",
    )
    fragments = extract_text(path, "text/markdown", 100_000).fragments
    values = [fragment.locator.get("value") for fragment in fragments]
    assert "no es un titulo" not in values, f"D4: el código abrió sección: {values}"
