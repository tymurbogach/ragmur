"""Compara umbrales de respaldo sobre puntuaciones ya calculadas."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def summarize(
    details: list[dict[str, Any]], support: float, contradiction: float
) -> dict[str, int]:
    """Cuenta respaldos verdaderos y falsos con precedencia de contradicción."""
    if not details or any(
        not math.isfinite(value) or not 0 <= value <= 1 for value in (support, contradiction)
    ):
        raise ValueError("Thresholds must be finite probabilities and details must not be empty")
    result = {
        "true_supported": 0,
        "false_supported": 0,
        "expected_supported": 0,
        "expected_not_supported": 0,
    }
    for item in details:
        label = item["expected"]
        if label not in {"supported", "unsupported", "contradicted"}:
            raise ValueError("Unsupported reference label")
        ent, contra = float(item["entailment"]), float(item["contradiction"])
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in (ent, contra)):
            raise ValueError("Scores must be finite probabilities")
        expected = label == "supported"
        result["expected_supported" if expected else "expected_not_supported"] += 1
        if contra < contradiction and ent >= support:
            result["true_supported" if expected else "false_supported"] += 1
    return result


def main() -> None:
    """Guarda comparaciones descriptivas sin seleccionar umbrales automáticamente."""
    parser = argparse.ArgumentParser(description="Compara umbrales de respaldo")
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--support", type=float, action="append", required=True)
    parser.add_argument("--contradiction", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.details.read_bytes()
    details = json.loads(raw)
    results = {str(value): summarize(details, value, args.contradiction) for value in args.support}
    report = {
        "details_sha256": hashlib.sha256(raw).hexdigest(),
        "contradiction_threshold": args.contradiction,
        "support_thresholds": results,
        "limitations": "Development only; no threshold selection or held-out validation.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
