"""D2: el texto de tablas no debe condenar el cuerpo legible del DOCX."""

from pathlib import Path

import pytest
from docx import Document

from ragmur.ingestion.extractors.core import (
    UnsupportedDocumentError,
    extract_docx,
)


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="D2: DOCX rechazado entero por texto en tablas"
)
def test_d2_docx_table_text_does_not_reject_body(tmp_path: Path) -> None:
    """El cuerpo se extrae aunque una tabla tenga texto (con aviso, no rechazo)."""
    path = tmp_path / "tabla.docx"
    document = Document()
    document.add_paragraph("Texto visible del cuerpo")
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Texto de la tabla"
    document.save(str(path))
    try:
        result = extract_docx(path, 100_000, 10_000_000)
    except UnsupportedDocumentError:
        result = None
    assert result is not None, "D2: el DOCX se rechaza entero aunque el cuerpo es legible"
    assert "Texto visible" in "".join(fragment.text for fragment in result.fragments)
