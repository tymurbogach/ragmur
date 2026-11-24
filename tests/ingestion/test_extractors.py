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


def test_docx_reads_table_text_in_document_order(tmp_path: Path) -> None:
    path = tmp_path / "table.docx"
    document = Document()
    document.add_paragraph("Antes")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Celda A"
    table.cell(0, 1).text = "Celda B"
    document.add_paragraph("Después")
    document.save(str(path))

    result = extract_docx(path, 1000, 1_000_000)

    assert [fragment.text for fragment in result.fragments] == [
        "Antes\n",
        "Celda A\n",
        "Celda B\n",
        "Después\n",
    ]
    assert result.warnings == []


def test_docx_merged_cell_is_read_once(tmp_path: Path) -> None:
    path = tmp_path / "merged.docx"
    document = Document()
    table = document.add_table(rows=1, cols=2)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "Combinada"
    document.save(str(path))

    result = extract_docx(path, 1000, 1_000_000)

    assert [fragment.text for fragment in result.fragments] == ["Combinada\n"]


def test_docx_table_only_text_is_extracted(tmp_path: Path) -> None:
    path = tmp_path / "solo-tabla.docx"
    document = Document()
    document.add_table(rows=1, cols=1).cell(0, 0).text = "Solo en la tabla"
    document.save(str(path))

    result = extract_docx(path, 1000, 1_000_000)

    assert "Solo en la tabla" in "".join(fragment.text for fragment in result.fragments)


@pytest.mark.parametrize("location", ["header", "footer", "nested"])
def test_docx_warns_about_other_omitted_text(tmp_path: Path, location: str) -> None:
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

    result = extract_docx(path, 1000, 1_000_000)

    joined = "".join(fragment.text for fragment in result.fragments)
    assert "Texto visible" in joined
    assert "Texto omitido" not in joined
    assert len(result.warnings) == 1
    assert "no extraídos" in result.warnings[0]


def test_docx_nested_table_text_warns(tmp_path: Path) -> None:
    path = tmp_path / "anidada.docx"
    document = Document()
    document.add_paragraph("Texto visible")
    outer = document.add_table(rows=1, cols=1)
    outer.cell(0, 0).add_table(rows=1, cols=1).cell(0, 0).text = "Texto anidado"
    document.save(str(path))

    result = extract_docx(path, 1000, 1_000_000)

    assert "Texto anidado" not in "".join(fragment.text for fragment in result.fragments)
    assert len(result.warnings) == 1


def test_docx_with_text_only_in_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "solo-cabecera.docx"
    document = Document()
    document.sections[0].header.paragraphs[0].text = "Solo cabecera"
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


def test_markdown_fenced_code_does_not_open_sections(tmp_path: Path) -> None:
    path = tmp_path / "cercas.md"
    path.write_text(
        "# Uno\n\n~~~~\n# dentro tilde\n~~~\n# aun dentro\n~~~~\n\n"
        "```python\n# dentro comillas\n```\n\n## Dos\n\ntexto\n",
        encoding="utf-8",
    )

    fragments = extract_text(path, "text/markdown", 10_000).fragments

    assert [fragment.locator.get("value") for fragment in fragments] == ["Uno", "Dos"]
    assert "".join(fragment.text for fragment in fragments) == path.read_text(encoding="utf-8")


def test_markdown_unclosed_fence_runs_to_the_end(tmp_path: Path) -> None:
    path = tmp_path / "sin-cierre.md"
    path.write_text("# Uno\n\n```\n# no es titulo\ntexto\n", encoding="utf-8")

    fragments = extract_text(path, "text/markdown", 10_000).fragments

    assert [fragment.locator.get("value") for fragment in fragments] == ["Uno"]


def test_docx_vertically_merged_cell_is_read_once(tmp_path: Path) -> None:
    path = tmp_path / "vertical.docx"
    document = Document()
    table = document.add_table(rows=3, cols=2)
    table.cell(0, 0).merge(table.cell(2, 0)).text = "Vertical"
    for row, value in enumerate("ABC"):
        table.cell(row, 1).text = value
    document.save(str(path))

    result = extract_docx(path, 1000, 1_000_000)

    assert [fragment.text for fragment in result.fragments] == [
        "Vertical\n",
        "A\n",
        "\n",
        "B\n",
        "\n",
        "C\n",
    ]


def test_markdown_fence_closes_only_without_trailing_text(tmp_path: Path) -> None:
    path = tmp_path / "cierre.md"
    path.write_text(
        "# Uno\n\n````\n```python\n# dentro\n```\n````\n\n## Dos\n\ntexto\n",
        encoding="utf-8",
    )

    fragments = extract_text(path, "text/markdown", 10_000).fragments

    assert [fragment.locator.get("value") for fragment in fragments] == ["Uno", "Dos"]


def test_markdown_inline_code_at_line_start_is_not_a_fence(tmp_path: Path) -> None:
    path = tmp_path / "inline.md"
    path.write_text("# Uno\n\n```codigo``` en linea\n\n## Dos\n\ntexto\n", encoding="utf-8")

    fragments = extract_text(path, "text/markdown", 10_000).fragments

    assert [fragment.locator.get("value") for fragment in fragments] == ["Uno", "Dos"]


def test_worker_returns_docx_warnings(tmp_path: Path) -> None:
    from ragmur.ingestion.extractors.worker import process

    path = tmp_path / "aviso.docx"
    document = Document()
    document.add_paragraph("Texto visible")
    document.sections[0].header.paragraphs[0].text = "Texto de cabecera"
    document.save(str(path))

    response = process(
        {
            "path": str(path),
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "max_chars": 1000,
            "max_expanded_bytes": 1_000_000,
        }
    )

    assert response["status"] == "ok"
    assert len(response["result"]["warnings"]) == 1
