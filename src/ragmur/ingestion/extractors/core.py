"""Extracción acotada de texto y localizadores de origen."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pypdfium2  # type: ignore[import-untyped]
from docx import Document
from docx.oxml import parse_xml


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
        headings = list(re.finditer(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", text))
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


def extract_docx(path: Path, max_chars: int, max_expanded_bytes: int) -> ExtractionResult:
    """Comprueba el ZIP antes de abrir el documento DOCX."""
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
            if parent is None or parent.tag != f"{namespace}p" or parent.getparent() is not body:
                omitted = True
                break
        for part in document.part.package.parts:
            name = str(part.partname)
            if re.fullmatch(r"/word/(?:header\d+|footer\d+|footnotes|endnotes)\.xml", name):
                element = parse_xml(part.blob)
                if any((node.text or "").strip() for node in element.iter(f"{namespace}t")):
                    omitted = True
                    break
        if omitted:
            raise UnsupportedDocumentError(
                "El DOCX contiene texto en tablas u otros elementos no extraídos"
            )
        fragments: list[Fragment] = []
        offset = 0
        section_path: list[str] = []
        current_section: dict[str, str | int | list[str]] | None = None
        section_number = 0
        for paragraph in document.paragraphs:
            text = paragraph.text + "\n"
            end = offset + len(text)
            if end > max_chars:
                raise ExtractionError("El texto extraído supera el límite")
            style_id = paragraph.style.style_id if paragraph.style else ""
            heading = re.fullmatch(r"Heading([1-9])", style_id)
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
        raise UnsupportedDocumentError("El documento no contiene texto")
    return ExtractionResult(fragments)


def extract_pdf(path: Path, max_chars: int, max_pages: int, min_chars: int) -> ExtractionResult:
    """Extrae las páginas de un PDF desde un proceso aislado."""
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
