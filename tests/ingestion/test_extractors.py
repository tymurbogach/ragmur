"""Pruebas de límites y localizadores de los extractores."""

from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document
from docx.oxml import OxmlElement

from ragmur.ingestion.extractors.core import (
    ExtractionError,
    UnsupportedDocumentError,
    extract_docx,
    extract_pdf,
    extract_text,
)


def test_text_extraction_and_limits(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("ábc", encoding="utf-8")
    result = extract_text(path, "text/plain", 10)
    assert result.fragments[0].text == "ábc"
    assert result.fragments[0].locator == {"type": "offset", "start": 0, "end": 3}
    with pytest.raises(ExtractionError):
        extract_text(path, "text/plain", 2)
    path.write_bytes(b"\xff")
    with pytest.raises(ExtractionError):
        extract_text(path, "text/plain", 10)


def test_docx_extraction_and_expansion_limit(tmp_path: Path) -> None:
    path = tmp_path / "sample.docx"
    document = Document()
    document.add_paragraph("Primero")
    document.add_paragraph("Segundo")
    document.save(str(path))
    result = extract_docx(path, 100, 1_000_000)
    assert [fragment.text for fragment in result.fragments] == ["Primero\n", "Segundo\n"]
    assert result.fragments[1].locator["start"] == len("Primero\n")
    with pytest.raises(ExtractionError):
        extract_docx(path, 100, 10)


@pytest.mark.parametrize("with_body_text", [False, True])
def test_docx_rejects_omitted_table_text(tmp_path: Path, with_body_text: bool) -> None:
    path = tmp_path / "table.docx"
    document = Document()
    if with_body_text:
        document.add_paragraph("Texto fuera de la tabla")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Texto de la tabla"
    document.save(str(path))

    with pytest.raises(UnsupportedDocumentError, match="tablas"):
        extract_docx(path, 100, 1_000_000)


@pytest.mark.parametrize("location", ["header", "footer", "nested"])
def test_docx_rejects_other_omitted_text(tmp_path: Path, location: str) -> None:
    path = tmp_path / "omitted.docx"
    document = Document()
    paragraph = document.add_paragraph("Texto visible")
    if location == "nested":
        wrapper = OxmlElement("w:sdt")
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = "Texto omitido"
        run.append(text)
        wrapper.append(run)
        paragraph._p.append(wrapper)
    else:
        part = getattr(document.sections[0], location)
        part.paragraphs[0].text = "Texto omitido"
    document.save(str(path))
    with pytest.raises(UnsupportedDocumentError, match="no extraídos"):
        extract_docx(path, 1000, 1_000_000)


def test_docx_rejects_wrong_structure(tmp_path: Path) -> None:
    path = tmp_path / "bad.docx"
    with ZipFile(path, "w") as archive:
        archive.writestr("other", "content")
    with pytest.raises(ExtractionError):
        extract_docx(path, 100, 1000)


def test_pdf_rejects_invalid_signature(tmp_path: Path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a PDF")
    with pytest.raises(ExtractionError):
        extract_pdf(path, 100, 10, 1)


def test_empty_text_is_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("  ", encoding="utf-8")
    with pytest.raises(UnsupportedDocumentError):
        extract_text(path, "text/plain", 10)


async def test_subprocess_extraction(tmp_path: Path) -> None:
    from ragmur.ingestion.extractors.runner import extract_in_process

    path = tmp_path / "file.txt"
    path.write_text("Hola", encoding="utf-8")
    result = await extract_in_process(
        path,
        "text/plain",
        max_chars=100,
        max_pages=10,
        min_chars=1,
        max_expanded_bytes=1000,
        deadline_seconds=10,
    )
    assert result["status"] == "ok"
    assert result["result"]["fragments"][0]["text"] == "Hola"


async def test_subprocess_timeout(tmp_path: Path) -> None:
    from ragmur.ingestion.extractors.runner import extract_in_process

    path = tmp_path / "file.txt"
    path.write_text("Hola", encoding="utf-8")
    with pytest.raises(TimeoutError):
        await extract_in_process(
            path,
            "text/plain",
            max_chars=100,
            max_pages=10,
            min_chars=1,
            max_expanded_bytes=1000,
            deadline_seconds=0,
        )


def test_blank_pdf_is_unsupported_and_pages_are_bounded(tmp_path: Path) -> None:
    import pypdfium2  # type: ignore[import-untyped]

    path = tmp_path / "blank.pdf"
    document = pypdfium2.PdfDocument.new()
    page = document.new_page(100, 100)
    page.close()
    document.save(str(path))
    document.close()
    with pytest.raises(UnsupportedDocumentError):
        extract_pdf(path, 1000, 10, 1)
    with pytest.raises(ExtractionError):
        extract_pdf(path, 1000, 0, 1)


def test_markdown_sections_preserve_text_and_distinguish_repeated_titles(tmp_path: Path) -> None:
    path = tmp_path / "sections.md"
    text = "Intro\n# Uno\nA\n## Detalle\nB\n# Uno\nC\n"
    path.write_text(text, encoding="utf-8")
    fragments = extract_text(path, "text/markdown", 1000).fragments
    assert "".join(fragment.text for fragment in fragments) == text
    assert fragments[1].locator["path"] == ["Uno"]
    assert fragments[2].locator["path"] == ["Uno", "Detalle"]
    assert fragments[3].locator["ordinal"] != fragments[1].locator["ordinal"]


def test_pdf_with_text_keeps_page_locator(tmp_path: Path) -> None:
    path = tmp_path / "text.pdf"
    contents = b"BT /F1 12 Tf 20 50 Td (Hello PDF) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(contents)).encode() + b" >>\nstream\n" + contents + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    path.write_bytes(data)
    result = extract_pdf(path, 1000, 10, 1)
    assert "Hello PDF" in result.fragments[0].text
    assert result.fragments[0].locator == {"type": "page", "start": 1, "end": 1}
    assert result.page_count == 1
    import pypdfium2

    mixed = tmp_path / "mixed.pdf"
    document = pypdfium2.PdfDocument(path)
    page = document.new_page(100, 100)
    page.close()
    document.save(str(mixed))
    document.close()
    mixed_result = extract_pdf(mixed, 1000, 10, 1)
    assert mixed_result.page_count == 2
    assert len(mixed_result.warnings) == 1


def test_docx_headings_keep_section_paths_and_ordinals(tmp_path: Path) -> None:
    path = tmp_path / "headings.docx"
    document = Document()
    document.add_paragraph("Introducción")
    document.add_heading("Tema", level=1)
    document.add_paragraph("Texto")
    document.add_heading("Detalle", level=2)
    document.add_paragraph("Otro texto")
    document.add_heading("Tema", level=1)
    document.save(str(path))
    fragments = extract_docx(path, 1000, 1_000_000).fragments
    assert fragments[0].locator["type"] == "offset"
    assert fragments[1].locator == fragments[2].locator
    assert fragments[3].locator["path"] == ["Tema", "Detalle"]
    assert fragments[5].locator["path"] == ["Tema"]
    assert fragments[1].locator["ordinal"] != fragments[5].locator["ordinal"]
