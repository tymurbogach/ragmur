"""Spans, solapes y localizadores del troceador."""

import random
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ragmur.core.config import Settings
from ragmur.ingestion.chunker import Chunk, ChunkedDocument, Locator, split_document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment


def split(result: ExtractionResult, size: int, overlap: int) -> ChunkedDocument:
    return split_document(result, uuid4(), uuid4(), "owner", size=size, overlap=overlap)


def reconstruct(chunks: list[Chunk]) -> str:
    position = 0
    output = ""
    for chunk in chunks:
        assert chunk.start <= position < chunk.end
        assert chunk.text
        output += chunk.text[position - chunk.start :]
        position = chunk.end
    return output


def test_reconstructs_unicode_and_line_endings() -> None:
    randomizer = random.Random(123)
    text = "".join(randomizer.choice("aé中 \n\r") for _ in range(5000))
    result = split(
        ExtractionResult([Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]), 89, 17
    )
    assert reconstruct(result.chunks) == result.text
    assert result.text == text.replace("\r\n", "\n").replace("\r", "\n")
    assert all(chunk.text == result.text[chunk.start : chunk.end] for chunk in result.chunks)
    assert all(len(chunk.text) <= 89 for chunk in result.chunks)
    assert all(
        chunk.locator == {"type": "offset", "start": chunk.start, "end": chunk.end}
        for chunk in result.chunks
    )
    assert [chunk.ordinal for chunk in result.chunks] == list(range(len(result.chunks)))
    assert all(chunk.owner_id == "owner" for chunk in result.chunks)


def test_page_ranges_follow_chunks_crossing_boundaries() -> None:
    source = ExtractionResult(
        [
            Fragment("abc", {"type": "page", "start": 1, "end": 1}),
            Fragment("def", {"type": "page", "start": 2, "end": 2}),
        ]
    )
    result = split(source, 5, 1)
    assert result.text == "abc\ndef"
    assert reconstruct(result.chunks) == result.text
    assert any(chunk.locator == {"type": "page", "start": 1, "end": 2} for chunk in result.chunks)


def test_sections_do_not_mix_and_keep_repeated_titles_distinct() -> None:
    source = ExtractionResult(
        [
            Fragment(
                "abcdef", {"type": "section", "value": "Title", "path": ["Title"], "ordinal": 1}
            ),
            Fragment(
                "ghijkl", {"type": "section", "value": "Title", "path": ["Title"], "ordinal": 2}
            ),
        ]
    )
    result = split(source, 4, 1)
    assert reconstruct(result.chunks) == "abcdefghijkl"
    assert all(not (chunk.start < 6 < chunk.end) for chunk in result.chunks)
    assert {chunk.locator["ordinal"] for chunk in result.chunks} == {1, 2}


def test_empty_document_and_invalid_parameters() -> None:
    assert split(ExtractionResult([]), 4, 0).chunks == []
    for size, overlap in [(0, 0), (4, 4), (4, -1)]:
        with pytest.raises(ValueError):
            split(ExtractionResult([]), size, overlap)
    with pytest.raises(ValidationError):
        Settings(database_url="postgresql+asyncpg://localhost/db", chunk_size=5, chunk_overlap=5)


def test_document_and_tenant_identifiers_are_preserved() -> None:
    document_id, tenant_id = uuid4(), uuid4()
    source = ExtractionResult([Fragment("abc def", {"type": "offset", "start": 0, "end": 7})])
    result = split_document(source, document_id, tenant_id, None, size=4, overlap=1)
    assert all(chunk.document_id == document_id for chunk in result.chunks)
    assert all(chunk.tenant_id == tenant_id and chunk.owner_id is None for chunk in result.chunks)
    assert len({chunk.id for chunk in result.chunks}) == len(result.chunks)


def test_paragraphs_of_same_section_can_share_a_chunk() -> None:
    locator: Locator = {"type": "section", "value": "Title", "path": ["Title"], "ordinal": 1}
    source = ExtractionResult([Fragment("heading\n", locator), Fragment("body", locator)])
    result = split(source, 100, 10)
    assert len(result.chunks) == 1
    assert result.chunks[0].text == "heading\nbody"
    assert result.chunks[0].locator == locator


def test_prefers_paragraph_boundary_without_overlap() -> None:
    text = "one\n\ntwo three four"
    result = split(
        ExtractionResult([Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]), 10, 0
    )
    assert result.chunks[0].text == "one\n\n"
    assert reconstruct(result.chunks) == text
