"""Variante NLI con premisas por ventanas de frases (experimento de desarrollo).

Puntua cada afirmacion contra ventanas de una frase mas su anterior contigua
y agrega maximos separados de entailment y contradiction, con la misma
precedencia y umbrales que el baseline de chunk completo. No modifica ``src/``,
configuracion, umbrales, modelo ni chunking de ingesta.

Solo particion dev. Los detalles por caso se escriben SOLO en /tmp; el resumen
agregado va a ``eval/results/``. Etiquetas de IA sin revision humana, datos
post hoc y afirmaciones correlacionadas: el resumen no declara ninguna mejora
como validada.
"""

import argparse
import hashlib
import json
import logging
import os
import platform
import subprocess
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from eval.nli_run import validate_cases, wilson_interval
from eval.sentence_windows import (
    aggregate_window_scores,
    build_premise_windows,
    decide_verdict,
    expand_window_pairs,
)
from ragmur.core.config import get_settings
from ragmur.verification.nli import load_verifier

LABELS = ("supported", "weak", "unsupported", "contradicted")
PAIR_BATCH_SIZE = 256


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.partition(":")[2].strip()
    except OSError:
        pass
    return "unknown"


def _git_state() -> tuple[str, bool]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
        return head, dirty
    except (subprocess.CalledProcessError, OSError):
        return "unknown", True


def _read_baseline(
    summary_path: Path, details_path: Path
) -> tuple[dict[str, Any], dict[tuple[str, int], dict[str, Any]]]:
    summary: dict[str, Any] = json.loads(summary_path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = json.loads(details_path.read_text(encoding="utf-8"))
    by_key: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["case_id"]), int(row["claim_index"]))
        by_key[key] = row
    return summary, by_key


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev",), required=True)
    parser.add_argument(
        "--dataset", type=Path, default=Path("eval/eu_nli_dev_chunks_ai_reviewed.yaml")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument(
        "--baseline-summary",
        type=Path,
        default=Path("eval/results/nli-ai-dev-realchunks-2026-11-13.json"),
    )
    parser.add_argument(
        "--baseline-details",
        type=Path,
        default=Path("/tmp/nli-ai-dev-realchunks-details-2026-11-13.json"),
    )
    args = parser.parse_args()
    details_path = args.details.resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    if details_path != tmp_root and tmp_root not in details_path.parents:
        raise ValueError("Per-claim details must live under /tmp")
    if args.split == "dev" and (args.output.exists() or details_path.exists()):
        raise ValueError("Variant output already exists; remove it explicitly to rerun")
    raw = args.dataset.read_bytes()
    cases = validate_cases(yaml.safe_load(raw), require_document_id=True)
    selected = [case for case in cases if case["split"] == args.split]
    if not selected:
        raise ValueError("Selected evaluation split is empty")
    baseline_summary, baseline_by_key = _read_baseline(args.baseline_summary, args.baseline_details)
    settings = get_settings()
    thresholds = {
        "supported": settings.verify_supported_threshold,
        "weak": settings.verify_weak_threshold,
        "contradicted": settings.verify_contradiction_threshold,
    }
    started = time.perf_counter()
    verifier = load_verifier(settings)
    load_seconds = time.perf_counter() - started
    claims = [claim for case in selected for claim in case["claims"]]
    identifiers = [
        (case["id"], index) for case in selected for index, _ in enumerate(case["claims"])
    ]
    premises_windows: list[list[str] | None] = []
    exclusions: list[dict[str, Any]] = []
    for case, (case_id, claim_index) in zip(selected, identifiers, strict=True):
        try:
            premises_windows.append(build_premise_windows(case["premise"]))
        except ValueError as exc:
            premises_windows.append(None)
            exclusions.append(
                {
                    "case_id": case_id,
                    "claim_index": claim_index,
                    "stage": "segmentation",
                    "reason": str(exc),
                }
            )
    scorable = [index for index, windows in enumerate(premises_windows) if windows is not None]
    for index in scorable:
        try:
            verifier.check_hypothesis(claims[index]["text"])
        except ValueError as exc:
            case_id, claim_index = identifiers[index]
            exclusions.append(
                {
                    "case_id": case_id,
                    "claim_index": claim_index,
                    "stage": "hypothesis-limit",
                    "reason": str(exc),
                }
            )
    scorable = [
        index
        for index in scorable
        if not any(
            entry["case_id"] == identifiers[index][0]
            and entry["claim_index"] == identifiers[index][1]
            for entry in exclusions
        )
    ]
    scored_positions = {original: position for position, original in enumerate(scorable)}
    pair_premises, pair_hypotheses, pair_owner_global = expand_window_pairs(
        [premises_windows[index] or [] for index in scorable],
        [claims[index]["text"] for index in scorable],
    )
    pair_owner = [scored_positions[scorable[owner]] for owner in pair_owner_global]
    inference_started = time.perf_counter()
    batched_scores: list[tuple[float, float]] = []
    batches = 0
    for start in range(0, len(pair_premises) or 1, PAIR_BATCH_SIZE):
        chunk_premises = pair_premises[start : start + PAIR_BATCH_SIZE]
        chunk_hypotheses = pair_hypotheses[start : start + PAIR_BATCH_SIZE]
        if not chunk_premises:
            break
        batched_scores.extend(
            verifier.score_pairs(chunk_premises, chunk_hypotheses, settings.nli_batch_size)
        )
        batches += 1
    inference_seconds = time.perf_counter() - inference_started
    aggregated = aggregate_window_scores(batched_scores, pair_owner, len(scorable))
    matrix = {actual: dict.fromkeys(LABELS, 0) for actual in LABELS}
    variant_by_key: dict[tuple[str, int], dict[str, Any]] = {}
    details: list[dict[str, Any]] = []
    windows_per_claim: list[int] = []
    for position, original in enumerate(scorable):
        ent, contra = aggregated[position]
        verdict, score = decide_verdict(
            ent,
            contra,
            supported_threshold=thresholds["supported"],
            weak_threshold=thresholds["weak"],
            contradiction_threshold=thresholds["contradicted"],
        )
        case_id, claim_index = identifiers[original]
        claim = claims[original]
        windows = premises_windows[original] or []
        windows_per_claim.append(len(windows))
        matrix[claim["label"]][verdict] += 1
        baseline_row = baseline_by_key.get((case_id, claim_index))
        if baseline_row is None:
            raise ValueError(f"Baseline details lack claim {case_id}#{claim_index}")
        variant_by_key[(case_id, claim_index)] = {
            "verdict": verdict,
            "entailment": ent,
            "contradiction": contra,
        }
        details.append(
            {
                "case_id": case_id,
                "split": args.split,
                "claim_index": claim_index,
                "expected": claim["label"],
                "baseline_verdict": baseline_row["verdict"],
                "baseline_entailment": baseline_row["entailment"],
                "baseline_contradiction": baseline_row["contradiction"],
                "verdict": verdict,
                "entailment": ent,
                "contradiction": contra,
                "score": score,
                "windows": len(windows),
            }
        )
    for entry in exclusions:
        key = (entry["case_id"], entry["claim_index"])
        baseline_row = baseline_by_key.get(key)
        details.append(
            {
                "case_id": entry["case_id"],
                "split": args.split,
                "claim_index": entry["claim_index"],
                "expected": next(
                    claim["label"]
                    for (case_id, claim_index), claim in zip(identifiers, claims, strict=True)
                    if (case_id, claim_index) == key
                ),
                "baseline_verdict": baseline_row["verdict"] if baseline_row else None,
                "baseline_entailment": baseline_row["entailment"] if baseline_row else None,
                "baseline_contradiction": baseline_row["contradiction"] if baseline_row else None,
                "verdict": None,
                "entailment": None,
                "contradiction": None,
                "score": None,
                "windows": 0,
                "excluded": entry,
            }
        )
    counts = Counter(claim["label"] for claim in claims)
    unsupported = counts["unsupported"] + counts["contradicted"]
    false_support = matrix["unsupported"]["supported"] + matrix["contradicted"]["supported"]
    supported_total = counts["supported"]
    supported_found = matrix["supported"]["supported"]
    supported_recall = supported_found / supported_total if supported_total else None
    false_support_interval = wilson_interval(false_support, unsupported)
    transitions: dict[str, dict[str, int]] = {actual: dict.fromkeys(LABELS, 0) for actual in LABELS}
    agreements = 0
    compared = 0
    for (case_id, claim_index), variant in variant_by_key.items():
        baseline_row = baseline_by_key[(case_id, claim_index)]
        transitions[baseline_row["verdict"]][variant["verdict"]] += 1
        compared += 1
        if baseline_row["verdict"] == variant["verdict"]:
            agreements += 1
    baseline_false = baseline_summary["false_support"]
    baseline_recall = baseline_summary["supported_recall"]
    total_seconds = time.perf_counter() - started
    commit, dirty = _git_state()
    root = Path(__file__).resolve().parent.parent
    result = {
        "task": "nli-ai-dev-realchunks-sentence-window",
        "date": datetime.now(UTC).isoformat(),
        "split": args.split,
        "dataset": {
            "path": str(args.dataset),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "cases": len(selected),
            "claims": len(claims),
            "label_counts": dict(counts),
            "documents_distinct": len({case["document_id"] for case in selected}),
        },
        "code_hashes": {
            "eval_sentence_windows_py": _file_sha256(root / "eval" / "sentence_windows.py"),
            "eval_nli_sentence_window_run_py": _file_sha256(
                root / "eval" / "nli_sentence_window_run.py"
            ),
            "eval_nli_run_py": _file_sha256(root / "eval" / "nli_run.py"),
            "src_ragmur_verification_nli_py": _file_sha256(
                root / "src" / "ragmur" / "verification" / "nli.py"
            ),
            "src_ragmur_core_config_py": _file_sha256(
                root / "src" / "ragmur" / "core" / "config.py"
            ),
        },
        "model": settings.nli_model,
        "revision": settings.nli_revision,
        "device": settings.resolved_device,
        "batch_size": settings.nli_batch_size,
        "pair_batch_size": PAIR_BATCH_SIZE,
        "thresholds": thresholds,
        "thresholds_modified": False,
        "hardware": {"platform": platform.platform(), "cpu": _cpu_model()},
        "thread_settings": {
            "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
            "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        },
        "timing": {
            "model_load_seconds": load_seconds,
            "inference_seconds": inference_seconds,
            "total_seconds": total_seconds,
            "per_claim_ms": (inference_seconds / len(scorable) * 1000) if scorable else None,
        },
        "windows": {
            "total_pairs": len(pair_premises),
            "claims_scored": len(scorable),
            "per_premise_min": min(windows_per_claim) if windows_per_claim else None,
            "per_premise_max": max(windows_per_claim) if windows_per_claim else None,
            "per_premise_mean": (
                sum(windows_per_claim) / len(windows_per_claim) if windows_per_claim else None
            ),
            "score_batches": batches,
        },
        "baseline": {
            "summary": str(args.baseline_summary),
            "summary_sha256": _file_sha256(args.baseline_summary),
            "counts": baseline_summary["counts"],
            "confusion_matrix": baseline_summary["confusion_matrix"],
            "false_support": baseline_false,
            "supported_recall": baseline_recall,
        },
        "variant": {
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
        },
        "paired": {
            "compared_claims": compared,
            "agreements": agreements,
            "changed": compared - agreements,
            "transitions_baseline_to_variant": transitions,
            "recall_delta_variant_minus_baseline": (
                (supported_recall - baseline_recall["rate"])
                if supported_recall is not None and baseline_recall["rate"] is not None
                else None
            ),
            "false_support_delta_variant_minus_baseline": (
                (false_support / unsupported - baseline_false["rate"])
                if unsupported and baseline_false["rate"] is not None
                else None
            ),
            "warning": (
                "Las 276 afirmaciones comparten 247 chunks y 18 documentos; "
                "las metricas pareadas describen este desarrollo correlacionado "
                "y no demuestran una mejora general."
            ),
        },
        "exclusions": exclusions,
        "complete": not exclusions,
        "commit": commit,
        "dirty": dirty,
        "limitations": [
            "Etiquetas generadas por IA con revision ciega, sin revision humana.",
            "Dataset de desarrollo parcialmente post hoc; no es conjunto dorado.",
            "276 afirmaciones de 247 chunks y 18 documentos: no son muestras independientes.",
            "Solo particion dev; la reserva no se abrio, leyo ni reevaluo.",
            "Umbrales vigentes sin modificar; sin declaracion de aceptacion ni marca de roadmap.",
            "La variante no se integra en src/ ni cambia el chunking de ingesta.",
        ],
        "reserve_untouched": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    details_path.parent.mkdir(parents=True, exist_ok=True)
    details_path.write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")
    logging.warning("NLI sentence-window evaluation saved to %s", args.output)
    if exclusions:
        raise SystemExit(f"Incomplete: {len(exclusions)} claim(s) excluded; see summary")


if __name__ == "__main__":
    main()
