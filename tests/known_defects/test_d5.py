"""D5: los fragmentos de continuación no empiezan a mitad de palabra."""

import random
from uuid import uuid4

from ragmur.ingestion.chunker import split_document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment


def test_d5_chunks_start_at_word_boundaries() -> None:
    """Cada continuación empieza en frontera de palabra, no dentro de una."""
    rng = random.Random(20261122)
    words = [
        "plazo",
        "entrega",
        "contrato",
        "transporte",
        "factura",
        "cliente",
        "servicio",
        "garantia",
    ]
    text = " ".join(rng.choice(words) for _ in range(120))
    extraction = ExtractionResult(
        [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
    )
    chunks = split_document(extraction, uuid4(), uuid4(), "alice", size=120, overlap=30).chunks
    bad = [
        chunk.ordinal
        for chunk in chunks
        if chunk.start > 0
        and not text[chunk.start - 1].isspace()
        and not text[chunk.start].isspace()
    ]
    assert not bad, f"D5: {len(bad)} fragmentos empiezan a mitad de palabra: {bad[:5]}"
