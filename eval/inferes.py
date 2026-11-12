"""Prepara una muestra determinista de InferES sin repetir premisas."""

from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

import yaml  # type: ignore[import-untyped]

SHA256 = {
    "train": "6e7fcef798b3d37522588dbcb5c88e574139aae4cb334fc163168744f12bbe7c",
    "test": "faa73fb8567b7664cf03f5f01cf4aae1e0c940a64dc57ad8b36d1fcaeaeffc1a",
}
LABELS = {"neutral": "unsupported", "ent": "supported", "cnt": "contradicted"}
TOPICS = {"train": {"1", "2", "3", "4", "5"}, "test": {"6", "10"}}
SAMPLE_PER_LABEL = {"train": 80, "test": 60}


def load_rows(path: Path, partition: str) -> list[dict[str, str]]:
    """Comprueba la huella y carga la partición original."""
    expected = SHA256[partition]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"InferES {partition} hash mismatch")
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def select_rows(rows: list[dict[str, str]], partition: str) -> list[dict[str, str]]:
    """Selecciona ejemplos equilibrados con una única hipótesis por premisa."""
    candidates = [
        row for row in rows if row["Topic"] in TOPICS[partition] and row["Anno_Type"] != "Automated"
    ]
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    # Selecciona primero la clase con menos premisas disponibles.
    for label in ("neutral", "ent", "cnt"):
        ordered = sorted(
            (row for row in candidates if row["Label"] == label),
            key=lambda row: hashlib.sha256(row["ID"].encode()).digest(),
        )
        count = 0
        for row in ordered:
            premise = " ".join(row["Premise"].split()).casefold()
            if not premise or not row["Hypothesis"].strip() or premise in seen:
                continue
            seen.add(premise)
            selected.append(row)
            count += 1
            if count == SAMPLE_PER_LABEL[partition]:
                break
        if count != SAMPLE_PER_LABEL[partition]:
            raise ValueError(f"Insufficient unique premises for {partition}/{label}")
    return selected


def make_cases(train: list[dict[str, str]], test: list[dict[str, str]]) -> list[dict[str, object]]:
    """Comprueba la separación y adapta las etiquetas al evaluador existente."""
    selections = {"dev": select_rows(train, "train"), "test": select_rows(test, "test")}
    premises = {
        split: {" ".join(row["Premise"].split()).casefold() for row in rows}
        for split, rows in selections.items()
    }
    if premises["dev"] & premises["test"]:
        raise ValueError("Development and test premises overlap")
    cases: list[dict[str, object]] = []
    for split, rows in selections.items():
        for row in rows:
            cases.append(
                {
                    "id": "inferes-" + row["ID"],
                    "split": split,
                    "premise": row["Premise"],
                    "claims": [{"text": row["Hypothesis"], "label": LABELS[row["Label"]]}],
                }
            )
    if len({str(case["id"]) for case in cases}) != len(cases):
        raise ValueError("Duplicate InferES identifiers")
    return cases


def main() -> None:
    """Genera un YAML fuera del repositorio a partir de los CSV publicados."""
    parser = argparse.ArgumentParser(description="Prepara una muestra de InferES")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    train = load_rows(args.input / "train.csv", "train")
    test = load_rows(args.input / "test.csv", "test")
    cases = make_cases(train, test)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(cases, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    counts = Counter(str(case["split"]) for case in cases)
    if counts != {"dev": 240, "test": 180}:
        raise RuntimeError("Unexpected partition sizes")


if __name__ == "__main__":
    main()
