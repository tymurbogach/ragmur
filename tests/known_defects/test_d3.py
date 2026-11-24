"""D3: el estilo de título del Word en español (Ttulo1) es un título."""

from pathlib import Path
from zipfile import ZipFile

from docx import Document

from ragmur.ingestion.extractors.core import extract_docx


def _spanish_style(path: Path) -> None:
    """Renombra Heading1 a Ttulo1 como hace Word en español."""
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    for name in ("word/document.xml", "word/styles.xml"):
        entries[name] = entries[name].replace(b"Heading1", b"Ttulo1")
    with ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)


def test_d3_spanish_heading_style_detected(tmp_path: Path) -> None:
    """Un encabezado con estilo Ttulo1 abre sección como Heading1."""
    path = tmp_path / "titulo.docx"
    document = Document()
    document.add_paragraph("Introducción")
    document.add_heading("Tema", level=1)
    document.add_paragraph("Texto")
    document.save(str(path))
    _spanish_style(path)
    fragments = extract_docx(path, 100_000, 10_000_000).fragments
    sections = [fragment for fragment in fragments if fragment.locator.get("type") == "section"]
    assert {fragment.locator.get("value") for fragment in sections} == {"Tema"}
    assert fragments[0].locator.get("type") == "offset"
    assert fragments[-1].locator.get("path") == ["Tema"]
