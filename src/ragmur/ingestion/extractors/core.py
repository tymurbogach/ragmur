"""Extracción acotada de texto y localizadores de origen."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

import pypdfium2  # type: ignore[import-untyped]
from docx import Document
from docx.oxml import parse_xml
from docx.text.paragraph import Paragraph


class ExtractionError(Exception):
    """El contenido no puede extraerse de forma segura."""


class UnsupportedDocumentError(ExtractionError):
    """El documento no contiene texto utilizable."""


@dataclass(frozen=True, slots=True)
class Fragment:
    """Texto extraído con su localizador."""

    text: str
    locator: dict[str, str | int | list[str]]


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Resultado anterior al troceado y al indexado."""

    fragments: list[Fragment]
    page_count: int | None = None
    warnings: list[str] = field(default_factory=list)


def _fenced_code_ranges(text: str) -> list[tuple[int, int]]:
    """Devuelve los rangos de texto que ocupan los bloques de código cercados.

    Un bloque abre con una línea de tres o más ``` o ~~~ y cierra con otra línea
    del mismo carácter, al menos la misma longitud y sin texto detrás. Un bloque
    sin cierre llega hasta el final del texto, como en CommonMark.
    """
    ranges: list[tuple[int, int]] = []
    open_start = 0
    marker = ""
    position = 0
    for line in text.splitlines(keepends=True):
        fence = re.match(r"[ ]{0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
        if fence is not None:
            found, rest = fence.group(1), fence.group(2)
            if not marker:
                # Un cercado de acentos graves no admite acentos graves en su texto.
                if not (found[0] == "`" and "`" in rest):
                    marker = found
                    open_start = position
            elif found[0] == marker[0] and len(found) >= len(marker) and not rest.strip():
                ranges.append((open_start, position + len(line)))
                marker = ""
        position += len(line)
    if marker:
        ranges.append((open_start, len(text)))
    return ranges


def extract_text(path: Path, mime_type: str, max_chars: int) -> ExtractionResult:
    """Decodifica texto UTF-8 y conserva sus posiciones."""
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("El fichero no es UTF-8 válido") from exc
    if "\x00" in text:
        raise ExtractionError("El texto contiene bytes nulos")
    if len(text) > max_chars:
        raise ExtractionError("El texto extraído supera el límite")
    if not text.strip():
        raise UnsupportedDocumentError("El documento no contiene texto")
    if mime_type == "text/markdown":
        code_ranges = _fenced_code_ranges(text)
        headings = [
            heading
            for heading in re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", text)
            if not any(start <= heading.start() < end for start, end in code_ranges)
        ]
        if headings:
            fragments = []
            if headings[0].start():
                fragments.append(
                    Fragment(
                        text[: headings[0].start()],
                        {"type": "offset", "start": 0, "end": headings[0].start()},
                    )
                )
            section_path: list[str] = []
            for index, heading in enumerate(headings):
                level = len(heading.group(1))
                title = heading.group(2).strip()
                section_path = section_path[: level - 1]
                section_path.append(title)
                end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
                fragments.append(
                    Fragment(
                        text[heading.start() : end],
                        {
                            "type": "section",
                            "value": title,
                            "path": section_path.copy(),
                            "ordinal": index + 1,
                        },
                    )
                )
            return ExtractionResult(fragments)
    return ExtractionResult([Fragment(text, {"type": "offset", "start": 0, "end": len(text)})])


def _is_read_paragraph(paragraph: Any, body: Any, namespace: str) -> bool:
    """Indica si el lector lee este párrafo: del cuerpo o de una tabla de primer nivel."""
    container = paragraph.getparent()
    if container is body:
        return True
    if container is None or container.tag != f"{namespace}tc":
        return False
    row = container.getparent()
    table = row.getparent() if row is not None else None
    return table is not None and table.getparent() is body


def _read_paragraphs(document: Any) -> list[Paragraph]:
    """Devuelve los párrafos del cuerpo y de sus tablas, en orden de documento."""
    paragraphs: list[Paragraph] = []
    for item in document.iter_inner_content():
        if isinstance(item, Paragraph):
            paragraphs.append(item)
            continue
        # row.cells repite la celda de origen en las filas de una combinación
        # vertical; los elementos <w:tc> reales no se repiten.
        for row in item.rows:
            for cell in row._tr.tc_lst:
                paragraphs.extend(Paragraph(para, item) for para in cell.p_lst)
    return paragraphs


def extract_docx(path: Path, max_chars: int, max_expanded_bytes: int) -> ExtractionResult:
    """Comprueba el ZIP antes de abrir el documento DOCX.

    Raises ExtractionError si el fichero es inválido.
    Raises UnsupportedDocumentError si no hay texto utilizable.
    """
    try:
        with ZipFile(path) as archive:
            entries = archive.infolist()
            if sum(entry.file_size for entry in entries) > max_expanded_bytes:
                raise ExtractionError("El DOCX expandido supera el límite")
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise ExtractionError("El fichero no es un DOCX válido")
        document = Document(str(path))
        # Paragraph.text reads direct runs and hyperlinks, but not nested content.
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        body = document.element.body
        omitted = False
        for node in body.iter(f"{namespace}t"):
            if not (node.text or "").strip():
                continue
            parent = node.getparent()
            if parent is None or parent.tag != f"{namespace}r":
                omitted = True
                break
            parent = parent.getparent()
            if parent is not None and parent.tag == f"{namespace}hyperlink":
                parent = parent.getparent()
            if (
                parent is None
                or parent.tag != f"{namespace}p"
                or not _is_read_paragraph(parent, body, namespace)
            ):
                omitted = True
                break
        for part in document.part.package.parts:
            name = str(part.partname)
            if re.fullmatch(r"/word/(?:header\d+|footer\d+|footnotes|endnotes)\.xml", name):
                element = parse_xml(part.blob)
                if any((node.text or "").strip() for node in element.iter(f"{namespace}t")):
                    omitted = True
                    break
        fragments: list[Fragment] = []
        offset = 0
        section_path: list[str] = []
        current_section: dict[str, str | int | list[str]] | None = None
        section_number = 0
        for paragraph in _read_paragraphs(document):
            text = paragraph.text + "\n"
            end = offset + len(text)
            if end > max_chars:
                raise ExtractionError("El texto extraído supera el límite")
            style_id = paragraph.style.style_id if paragraph.style else ""
            heading = re.fullmatch(r"(?:Heading|Ttulo|T[ií]tulo)([1-9])", style_id)
            if heading and paragraph.text.strip():
                level = int(heading.group(1))
                section_path = section_path[: level - 1]
                section_path.append(paragraph.text.strip())
                section_number += 1
                current_section = {
                    "type": "section",
                    "value": paragraph.text.strip(),
                    "path": section_path.copy(),
                    "ordinal": section_number,
                }
            locator = current_section or {"type": "offset", "start": offset, "end": end}
            fragments.append(Fragment(text, locator.copy()))
            offset = end
    except (BadZipFile, ValueError, KeyError, OSError) as exc:
        raise ExtractionError("El fichero DOCX no es válido") from exc
    if not any(fragment.text.strip() for fragment in fragments):
        if omitted:
            raise UnsupportedDocumentError("El DOCX solo tiene texto en elementos no extraídos")
        raise UnsupportedDocumentError("El documento no contiene texto")
    warnings = (
        ["El DOCX tiene texto en cabeceras, pies, notas u otros elementos no extraídos"]
        if omitted
        else []
    )
    return ExtractionResult(fragments, warnings=warnings)


def extract_pdf(path: Path, max_chars: int, max_pages: int, min_chars: int) -> ExtractionResult:
    """Extrae las páginas de un PDF desde un proceso aislado.

    Raises ExtractionError si el fichero es inválido.
    Raises UnsupportedDocumentError si no hay texto extraíble.
    """
    try:
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise ExtractionError("La firma del PDF no es válida")
        document = pypdfium2.PdfDocument(path)
        try:
            count = len(document)
            if count > max_pages:
                raise ExtractionError("El PDF supera el límite de páginas")
            fragments = []
            total = 0
            for index in range(count):
                page = document[index]
                try:
                    textpage = page.get_textpage()
                    try:
                        text = textpage.get_text_range()
                    finally:
                        textpage.close()
                finally:
                    page.close()
                total += len(text)
                if total > max_chars:
                    raise ExtractionError("El texto extraído supera el límite")
                fragments.append(
                    Fragment(text, {"type": "page", "start": index + 1, "end": index + 1})
                )
        finally:
            document.close()
    except pypdfium2.PdfiumError as exc:
        raise ExtractionError("El fichero PDF no es válido o está protegido") from exc
    weak_pages = sum(len(fragment.text.strip()) < min_chars for fragment in fragments)
    if not count or weak_pages == count:
        raise UnsupportedDocumentError("El PDF no contiene suficiente texto extraíble")
    warnings = []
    if weak_pages:
        warnings.append(f"{weak_pages} páginas contienen poco o ningún texto")
    return ExtractionResult(fragments, count, warnings)
