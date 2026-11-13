"""Compara umbrales de respaldo sobre puntuaciones ya calculadas."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast


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


def select_support_threshold(
    details: list[dict[str, Any]],
    candidates: list[float],
    contradiction: float,
    weak: float,
    minimum_recall: float = 0.5,
) -> dict[str, Any]:
    """Elige en desarrollo la menor tasa de respaldo falso con recall mínimo."""
    if not candidates or not 0 <= weak < 1 or not 0 < minimum_recall <= 1:
        raise ValueError("Invalid calibration parameters")
    if any(item.get("split") != "dev" for item in details):
        raise ValueError("Threshold selection requires development scores")
    if any(value <= weak for value in candidates):
        raise ValueError("Support thresholds must exceed the weak threshold")
    options = []
    for threshold in sorted(set(candidates)):
        counts = summarize(details, threshold, contradiction)
        if not counts["expected_supported"] or not counts["expected_not_supported"]:
            raise ValueError("Development set needs supported and non-supported claims")
        recall = counts["true_supported"] / counts["expected_supported"]
        false_rate = counts["false_supported"] / counts["expected_not_supported"]
        options.append(
            {
                "supported_threshold": threshold,
                "counts": counts,
                "supported_recall": recall,
                "false_support_rate": false_rate,
                "eligible": recall >= minimum_recall,
            }
        )
    eligible = [option for option in options if option["eligible"]]
    if not eligible:
        raise ValueError("No threshold meets minimum supported recall")
    selected = min(
        eligible,
        key=lambda option: (
            cast(float, option["false_support_rate"]),
            -cast(float, option["supported_recall"]),
            -cast(float, option["supported_threshold"]),
        ),
    )
    return {
        "selected": selected,
        "candidates": options,
        "contradiction_threshold": contradiction,
        "weak_threshold": weak,
        "minimum_supported_recall": minimum_recall,
    }


def main() -> None:
    """Calibra el respaldo en datos de desarrollo y guarda la selección."""
    parser = argparse.ArgumentParser(description="Calibra el respaldo en datos de desarrollo")
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--support", type=float, action="append", required=True)
    parser.add_argument("--contradiction", type=float, required=True)
    parser.add_argument("--weak", type=float, default=0.5)
    parser.add_argument("--minimum-recall", type=float, default=0.5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.details.read_bytes()
    details = json.loads(raw)
    selection = select_support_threshold(
        details, args.support, args.contradiction, args.weak, args.minimum_recall
    )
    report = {
        "details_sha256": hashlib.sha256(raw).hexdigest(),
        **selection,
        "limitations": "Development selection only; the held-out set requires a separate run.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
