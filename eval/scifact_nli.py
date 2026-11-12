"""Prepara fragmentos de SciFact con evidencia anotada por documento."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import yaml  # type: ignore[import-untyped]

from eval.scifact import partition_queries
from ragmur.ingestion.chunker import split_document
from ragmur.ingestion.extractors.core import ExtractionResult, Fragment

HASHES = {
    "corpus.jsonl": "b8d6c89624cb2ed74dee8938effc4f5d8bd2086887880af8110d64be4ceade62",
    "claims_train.jsonl": "f4c8fa82d8bd0653a9cc8d61a6ea48c25eacea64e90af5dbf390ebb1b74372f0",
}
LABELS = {"SUPPORT": "supported", "CONTRADICT": "contradicted"}


def evidence_chunk(sentences: list[str], evidence: list[int]) -> str | None:
    """Devuelve un fragmento real que contiene todas las frases anotadas."""
    if not evidence or any(index < 0 or index >= len(sentences) for index in evidence):
        raise ValueError("Invalid evidence sentence indices")
    text = "\n".join(sentences)
    spans: list[tuple[int, int]] = []
    offset = 0
    for sentence in sentences:
        spans.append((offset, offset + len(sentence)))
        offset += len(sentence) + 1
    extraction = ExtractionResult(
        [Fragment(text, {"type": "offset", "start": 0, "end": len(text)})]
    )
    chunks = split_document(
        extraction,
        uuid5(NAMESPACE_URL, text),
        uuid5(NAMESPACE_URL, "scifact-nli"),
        None,
        size=800,
        overlap=120,
    ).chunks
    for chunk in chunks:
        if all(
            chunk.start <= spans[index][0] and chunk.end >= spans[index][1] for index in evidence
        ):
            return chunk.text
    return None


def prepare_cases(
    documents: list[dict[str, Any]], claims: list[dict[str, Any]]
) -> list[dict[str, object]]:
    """Agrupa por afirmación y documento antes de separar las particiones."""
    docs = {str(doc["doc_id"]): doc for doc in documents}
    if len(docs) != len(documents):
        raise ValueError("Duplicate document IDs")
    relevance = {
        str(claim["id"]): {
            str(doc): 1 for doc, annotations in claim["evidence"].items() if annotations
        }
        for claim in claims
        if claim["evidence"]
    }
    groups = partition_queries(relevance)
    candidates: list[tuple[str, str, str, str, str]] = []
    for claim in claims:
        claim_id = str(claim["id"])
        for doc_id, entries in claim["evidence"].items():
            if str(doc_id) not in docs:
                raise ValueError("Evidence references a missing document")
            labels = {entry["label"] for entry in entries}
            if len(labels) != 1 or not labels <= LABELS.keys():
                raise ValueError("Conflicting or unsupported evidence labels")
            for annotation in entries:
                chunk = evidence_chunk(docs[str(doc_id)]["abstract"], annotation["sentences"])
                if chunk is not None:
                    candidates.append(
                        (claim_id, str(doc_id), claim["claim"], annotation["label"], chunk)
                    )
                    break
    candidates.sort(key=lambda row: hashlib.sha256((row[0] + ":" + row[1]).encode()).digest())
    cases: list[dict[str, object]] = []
    used_docs: set[str] = set()
    used_claims: set[str] = set()
    for claim_id, doc_id, text, label, chunk in candidates:
        if doc_id in used_docs or claim_id in used_claims:
            continue
        used_docs.add(doc_id)
        used_claims.add(claim_id)
        cases.append(
            {
                "id": f"scifact-{claim_id}-{doc_id}",
                "split": "test" if groups[claim_id] == "holdout" else "dev",
                "premise": chunk,
                "claims": [{"text": text, "label": LABELS[label]}],
            }
        )
    if not cases or {case["split"] for case in cases} != {"dev", "test"}:
        raise ValueError("Both partitions must contain labeled evidence")
    return cases


def main() -> None:
    """Genera el YAML de evaluación fuera del repositorio."""
    parser = argparse.ArgumentParser(description="Prepara evidencia de SciFact")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for filename, expected in HASHES.items():
        if hashlib.sha256((args.input / filename).read_bytes()).hexdigest() != expected:
            raise ValueError(f"SciFact hash mismatch: {filename}")
    docs = [json.loads(line) for line in (args.input / "corpus.jsonl").read_text().splitlines()]
    claims = [
        json.loads(line) for line in (args.input / "claims_train.jsonl").read_text().splitlines()
    ]
    cases = prepare_cases(docs, claims)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(cases, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
