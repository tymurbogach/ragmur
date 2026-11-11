"""Evalúa ejemplos NLI con umbrales fijados y el modelo local."""

import argparse
import hashlib
import json
import logging
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from ragmur.core.config import get_settings
from ragmur.verification.nli import load_verifier

LABELS = ("supported", "weak", "unsupported", "contradicted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = Path("eval/nli_cases.yaml")
    raw = path.read_bytes()
    cases = yaml.safe_load(raw)
    settings = get_settings()
    verifier = load_verifier(settings)
    selected = [case for case in cases if case["split"] == args.split]
    premises = [case["premise"] for case in selected for claim in case["claims"]]
    claims = [claim for case in selected for claim in case["claims"]]
    scores = verifier.score_pairs(
        premises, [claim["text"] for claim in claims], settings.nli_batch_size
    )
    matrix = {actual: dict.fromkeys(LABELS, 0) for actual in LABELS}
    for claim, (ent, contra) in zip(claims, scores, strict=True):
        if contra >= settings.verify_contradiction_threshold:
            verdict = "contradicted"
        elif ent >= settings.verify_supported_threshold:
            verdict = "supported"
        elif ent >= settings.verify_weak_threshold:
            verdict = "weak"
        else:
            verdict = "unsupported"
        matrix[claim["label"]][verdict] += 1
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
        },
        "limitations": "Small manually authored functional set; not representative of deployment.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    logging.warning("NLI evaluation saved to %s", args.output)


if __name__ == "__main__":
    main()
