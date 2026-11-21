"""Troceado por caracteres con spans y localizadores de origen."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from uuid import UUID, uuid4

from ragmur.ingestion.extractors.core import ExtractionResult

Locator = dict[str, str | int | list[str]]


@dataclass(frozen=True, slots=True)
class Chunk:
    """Fragmento localizado dentro del texto normalizado."""

    id: UUID
    document_id: UUID
    tenant_id: UUID
    owner_id: str | None
    ordinal: int
    text: str
    start: int
    end: int
    locator: Locator


@dataclass(frozen=True, slots=True)
class NormalizedSegment:
    """Rango de texto y localizador proporcionado por el extractor."""

    start: int
    end: int
    locator: Locator


@dataclass(frozen=True, slots=True)
class ChunkedDocument:
    """Texto normalizado y fragmentos con spans sobre ese texto."""

    text: str
    chunks: list[Chunk]


def normalize_extraction(result: ExtractionResult) -> tuple[str, list[NormalizedSegment]]:
    """Normaliza saltos de línea y registra el origen de cada rango."""
    pieces: list[str] = []
    segments: list[NormalizedSegment] = []
    position = 0
    page_fragments = bool(result.fragments) and all(
        part.locator.get("type") == "page" for part in result.fragments
    )
    for index, part in enumerate(result.fragments):
        text = part.text.replace("\r\n", "\n").replace("\r", "\n")
        if page_fragments and index < len(result.fragments) - 1:
            text += "\n"
        if not text:
            continue
        pieces.append(text)
        end = position + len(text)
        segments.append(NormalizedSegment(position, end, part.locator.copy()))
        position = end
    return "".join(pieces), segments


def _end_at_boundary(text: str, start: int, limit: int, overlap: int) -> int:
    """Busca un separador, de párrafos a caracteres, sin impedir el avance."""
    maximum = min(start + limit, len(text))
    if maximum == len(text):
        return maximum
    minimum = start + overlap + 1

    def choose_separator_end(separators: tuple[str, ...]) -> int:
        if not separators:
            return maximum
        separator = separators[0]
        index = text.rfind(separator, max(start, minimum - len(separator)), maximum)
        end = index + len(separator)
        if index >= start and minimum <= end <= maximum:
            return end
        return choose_separator_end(separators[1:])

    return choose_separator_end(("\n\n", "\n", " "))


def split_document(
    extraction: ExtractionResult,
    document_id: UUID,
    tenant_id: UUID,
    owner_id: str | None,
    *,
    size: int,
    overlap: int,
) -> ChunkedDocument:
    """Divide texto normalizado sin cruzar secciones y conserva sus spans."""
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("size must be positive and 0 <= overlap < size")
    text, segments = normalize_extraction(extraction)
    chunks: list[Chunk] = []
    groups: list[tuple[int, int]] = []
    previous_locator: Locator | None = None
    for segment in segments:
        is_section = segment.locator.get("type") == "section"
        previous_type = previous_locator.get("type") if previous_locator else None
        same_section = is_section and previous_locator == segment.locator
        same_nonsection_type = not is_section and previous_type == segment.locator.get("type")
        if groups and (same_nonsection_type or same_section):
            prev_start, _ = groups[-1]
            groups[-1] = (prev_start, segment.end)
        else:
            groups.append((segment.start, segment.end))
        previous_locator = segment.locator
    starts = [segment.start for segment in segments]
    ends = [segment.end for segment in segments]
    for group_start, group_end in groups:
        group_text = text[group_start:group_end]
        cursor = 0
        while cursor < len(group_text):
            end = _end_at_boundary(group_text, cursor, size, overlap)
            start_pos, end_pos = group_start + cursor, group_start + end
            origins = segments[bisect_right(ends, start_pos) : bisect_left(starts, end_pos)]
            origin = origins[0].locator
            if origin.get("type") == "page":
                locator: Locator = {
                    "type": "page",
                    "start": origin["start"],
                    "end": origins[-1].locator["end"],
                }
            elif origin.get("type") == "section":
                locator = origin.copy()
            else:
                locator = {"type": "offset", "start": start_pos, "end": end_pos}
            chunks.append(
                Chunk(
                    id=uuid4(),
                    document_id=document_id,
                    tenant_id=tenant_id,
                    owner_id=owner_id,
                    ordinal=len(chunks),
                    text=text[start_pos:end_pos],
                    start=start_pos,
                    end=end_pos,
                    locator=locator,
                )
            )
            if end == len(group_text):
                break
            cursor = end - overlap
    return ChunkedDocument(text, chunks)
