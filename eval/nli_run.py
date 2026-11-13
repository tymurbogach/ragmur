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
from typing import Any

import yaml  # type: ignore[import-untyped]

from ragmur.core.config import get_settings
from ragmur.verification.nli import load_verifier

LABELS = ("supported", "weak", "unsupported", "contradicted")


def validate_cases(cases: object, *, require_document_id: bool = False) -> list[dict[str, Any]]:
    """Rechaza duplicados, etiquetas inválidas y fugas entre documentos.

    Con ``require_document_id=True`` todo caso exige un ``document_id``
    no vacío y se comprueba que ningún documento cruce particiones.
    Con ``False`` (datasets exploratorios heredados) el campo es opcional
    y la comprobación de fuga solo cubre los casos que lo aportan, sin
    afirmar separación por documento del conjunto completo.
    """
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation dataset must be a non-empty list")
    identifiers: set[str] = set()
    document_splits: dict[str, str] = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Evaluation case must be a mapping")
        case_id, split = case.get("id"), case.get("split")
        document_id = case.get("document_id")
        if not isinstance(case_id, str) or not case_id or case_id in identifiers:
            raise ValueError("Evaluation case identifiers must be unique")
        if split not in ("dev", "test"):
            raise ValueError("Evaluation case needs a split and document identifier")
        if require_document_id:
            if not isinstance(document_id, str) or not document_id:
                raise ValueError("Evaluation case needs a document identifier")
        elif document_id is None:
            document_id = None
        elif not isinstance(document_id, str) or not document_id:
            raise ValueError("Evaluation case needs a document identifier")
        if (
            document_id is not None
            and document_id in document_splits
            and document_splits[document_id] != split
        ):
            raise ValueError("Source document appears in both evaluation splits")
        premise, claims = case.get("premise"), case.get("claims")
        if not isinstance(premise, str) or not premise.strip() or not isinstance(claims, list):
            raise ValueError("Evaluation case needs a premise and claims")
        if not claims or any(
            not isinstance(claim, dict)
            or not isinstance(claim.get("text"), str)
            or not claim["text"].strip()
            or claim.get("label") not in ("supported", "unsupported", "contradicted")
            for claim in claims
        ):
            raise ValueError("Evaluation claim needs text and a reference label")
        identifiers.add(case_id)
        if document_id is not None:
            document_splits[document_id] = split
    return cases


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
    parser.add_argument(
        "--require-document-id",
        action="store_true",
        help="Strict source-document validation for the acceptance corpus",
    )
    args = parser.parse_args()
    if args.split == "test" and (args.output.exists() or (args.details and args.details.exists())):
        raise ValueError("Reserved evaluation output already exists")
    path = args.dataset
    raw = path.read_bytes()
    cases = validate_cases(yaml.safe_load(raw), require_document_id=args.require_document_id)
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
                "split": args.split,
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
    supported_total = counts["supported"]
    supported_found = matrix["supported"]["supported"]
    supported_recall = supported_found / supported_total if supported_total else None
    false_support_interval = wilson_interval(false_support, unsupported)
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
            "wilson_95": false_support_interval,
        },
        "supported_recall": {
            "numerator": supported_found,
            "denominator": supported_total,
            "rate": supported_recall,
        },
        "numeric_acceptance": (
            false_support / unsupported <= 0.05
            and false_support_interval is not None
            and false_support_interval[1] <= 0.10
            and supported_recall is not None
            and supported_recall >= 0.5
        )
        if args.split == "test" and unsupported and supported_total
        else None,
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
