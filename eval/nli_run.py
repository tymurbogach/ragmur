"""Evalúa ejemplos NLI con umbrales fijados y el modelo local."""

import argparse
import hashlib
import json
import logging
import math
import os
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from ragmur.core.config import get_settings
from ragmur.verification.nli import load_verifier

LABELS = ("supported", "weak", "unsupported", "contradicted")


def wilson_interval(successes: int, total: int) -> tuple[float, float] | None:
    """Calcula el intervalo de Wilson del 95 % para una proporción."""
    if total < 0 or successes < 0 or successes > total:
        raise ValueError("Invalid counts")
    if total == 0:
        return None
    z = 1.959963984540054
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return max(0.0, center - margin), min(1.0, center + margin)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("eval/nli_cases.yaml"))
    parser.add_argument("--details", type=Path, help="Optional output for per-claim scores")
    args = parser.parse_args()
    path = args.dataset
    raw = path.read_bytes()
    cases = yaml.safe_load(raw)
    selected = [case for case in cases if case["split"] == args.split]
    if not selected:
        raise ValueError("Selected evaluation split is empty")
    settings = get_settings()
    verifier = load_verifier(settings)
    premises = [case["premise"] for case in selected for claim in case["claims"]]
    claims = [claim for case in selected for claim in case["claims"]]
    identifiers = [
        (case["id"], index) for case in selected for index, _ in enumerate(case["claims"])
    ]
    scores = verifier.score_pairs(
        premises, [claim["text"] for claim in claims], settings.nli_batch_size
    )
    matrix = {actual: dict.fromkeys(LABELS, 0) for actual in LABELS}
    details = []
    for claim, (ent, contra), (case_id, claim_index) in zip(
        claims, scores, identifiers, strict=True
    ):
        if contra >= settings.verify_contradiction_threshold:
            verdict = "contradicted"
        elif ent >= settings.verify_supported_threshold:
            verdict = "supported"
        elif ent >= settings.verify_weak_threshold:
            verdict = "weak"
        else:
            verdict = "unsupported"
        matrix[claim["label"]][verdict] += 1
        details.append(
            {
                "case_id": case_id,
                "claim_index": claim_index,
                "expected": claim["label"],
                "verdict": verdict,
                "entailment": ent,
                "contradiction": contra,
            }
        )
    counts = Counter(claim["label"] for claim in claims)
    unsupported = counts["unsupported"] + counts["contradicted"]
    false_support = matrix["unsupported"]["supported"] + matrix["contradicted"]["supported"]
    cpu_model = next(
        (
            line.partition(":")[2].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "unknown",
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    result = {
        "date": datetime.now(UTC).isoformat(),
        "split": args.split,
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "model": settings.nli_model,
        "revision": settings.nli_revision,
        "device": settings.resolved_device,
        "hardware": {"platform": platform.platform(), "cpu": cpu_model},
        "thread_settings": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        },
        "commit": commit,
        "thresholds": {
            "supported": settings.verify_supported_threshold,
            "weak": settings.verify_weak_threshold,
            "contradicted": settings.verify_contradiction_threshold,
        },
        "counts": dict(counts),
        "confusion_matrix": matrix,
        "false_support": {
            "numerator": false_support,
            "denominator": unsupported,
            "rate": false_support / unsupported if unsupported else None,
            "wilson_95": wilson_interval(false_support, unsupported),
        },
        "limitations": "Results apply only to this dataset; review relevance independently.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if args.details is not None:
        args.details.parent.mkdir(parents=True, exist_ok=True)
        args.details.write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
    logging.warning("NLI evaluation saved to %s", args.output)


if __name__ == "__main__":
    main()
