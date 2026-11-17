"""Los avisos de extracción no contienen texto del documento.

El campo `diagnostic` de PostgreSQL viaja al detalle del documento y, según
`docs/demo-design.md` §8, el único aviso actual cuenta páginas con poco
texto. Si un aviso futuro incluyese texto, habría que revisar ese punto
antes de exponerlo: estos tests fijan el contrato.
"""

import re
from pathlib import Path

import pypdfium2  # type: ignore[import-untyped]

from ragmur.ingestion.extractors.core import extract_docx, extract_pdf, extract_text

WARNING_TEMPLATE = re.compile(r"^\d+ páginas contienen poco o ningún texto$")

# Marcador único: si apareciese en un aviso, habría fuga de texto.
MARKER = "fuga zebra 9f3k.dtype"


def _assert_no_text_leak(warnings: list[str], texts: list[str]) -> None:
    """Comprueba que ningún aviso porta contenido del documento."""
    joined = "; ".join(warnings)
    assert MARKER not in joined
    for warning in warnings:
        assert WARNING_TEMPLATE.match(warning), warning
    for text in texts:
        for token in text.split():
            if len(token) >= 8 and token.isalpha():
                assert token not in joined


def test_pdf_warnings_hold_no_document_text(tmp_path: Path) -> None:
    source = tmp_path / "source.pdf"
    document = pypdfium2.PdfDocument.new()
    page = document.new_page(200, 200)
    page.close()
    document.save(str(source))
    document.close()
    text = f"página con texto {MARKER} suficiente para contar"
    contents = b"BT /F1 12 Tf 20 50 Td (" + text.encode("latin-1", "replace") + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
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
    mixed = tmp_path / "mixed.pdf"
    mixed.write_bytes(data)
    first = pypdfium2.PdfDocument(mixed)
    target = pypdfium2.PdfDocument.new()
    target.import_pages(first, [0])
    blank = pypdfium2.PdfDocument(source)
    target.import_pages(blank, [0])
    first.close()
    blank.close()
    final = tmp_path / "final.pdf"
    target.save(str(final))
    target.close()

    result = extract_pdf(final, 1000, 10, 10)
    assert len(result.warnings) == 1
    _assert_no_text_leak(result.warnings, [fragment.text for fragment in result.fragments])


def test_text_and_docx_warnings_hold_no_document_text(tmp_path: Path) -> None:
    from docx import Document

    txt = tmp_path / "note.txt"
    txt.write_text(f"contenido {MARKER} con varias palabras largas\n", encoding="utf-8")
    text_result = extract_text(txt, "text/plain", 1000)
    assert text_result.warnings == []
    _assert_no_text_leak(text_result.warnings, [text_result.fragments[0].text])

    docx_path = tmp_path / "note.docx"
    document = Document()
    document.add_paragraph(f"párrafo {MARKER} con palabras suficientes")
    document.save(str(docx_path))
    docx_result = extract_docx(docx_path, 1000, 1_000_000)
    assert docx_result.warnings == []
    _assert_no_text_leak(
        docx_result.warnings, [fragment.text for fragment in docx_result.fragments]
    )


def test_warning_template_ignores_adversarial_content(tmp_path: Path) -> None:
    """Un documento que imita el aviso no altera su forma ni lo duplica."""
    tricky = "3 páginas contienen poco o ningún texto"
    path = tmp_path / "tricky.txt"
    path.write_text(f"{tricky} {MARKER}\n", encoding="utf-8")
    result = extract_text(path, "text/plain", 1000)
    assert result.warnings == []
    _assert_no_text_leak(result.warnings, [result.fragments[0].text])


def test_pipeline_join_keeps_warnings_free_of_text() -> None:
    """Une avisos como `pipeline.py`: el diagnóstico sigue sin texto."""
    warnings = ["2 páginas contienen poco o ningún texto"]
    diagnostic = "; ".join(warnings) or None
    assert diagnostic is not None
    _assert_no_text_leak([diagnostic], [f"contenido {MARKER} del documento"])
