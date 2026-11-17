"""Evaluación aislada de la señal numérica sobre dev post hoc (IA).

Solo diagnóstico: el dataset deriva de observaciones del modelo, con
etiquetas IA sin revisión humana; no sirve para aceptación ni para
cambiar umbrales. No ejecuta NLI ni abre particiones reservadas.
Detalles por caso en /tmp; el resumen agregado va a eval/results/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from eval.numeric_signal import numeric_review_signal


def _baseline_needs_review(premise: str, claim: str) -> bool:
    """Baseline ingenuo: difiere algún dígito literal de la afirmación."""
    import re

    premise_digits = set(re.findall(r"\d+", premise.replace("\u00a0", " ")))
    claim_digits = re.findall(r"\d+", claim.replace("\u00a0", " "))
    return any(d not in premise_digits for d in claim_digits) and bool(claim_digits)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    cases = yaml.safe_load(raw)
    if not isinstance(cases, list) or not cases:
        raise ValueError("Dataset must be a non-empty list")
    rows: list[dict[str, Any]] = []
    for case in cases:
        if case.get("split") != "dev":
            raise ValueError("Solo split dev en esta evaluación diagnóstica")
        for claim in case["claims"]:
            signal = numeric_review_signal(case["premise"], claim["text"])
            rows.append(
                {
                    "case_id": case["id"],
                    "label": claim["label"],
                    "numeric": bool(case.get("phenomenon", {}).get("numeric")),
                    "needs_review": signal.needs_review,
                    "reason": signal.reason,
                    "baseline": _baseline_needs_review(case["premise"], claim["text"]),
                }
            )
    by_label: dict[str, Counter[str]] = {}
    for row in rows:
        by_label.setdefault(row["label"], Counter())[str(row["needs_review"])] += 1
    numeric_rows = [r for r in rows if r["numeric"]]
    supported = [r for r in rows if r["label"] == "supported"]
    contradicted = [r for r in rows if r["label"] == "contradicted"]
    unsupported = [r for r in rows if r["label"] == "unsupported"]
    eu223 = [r for r in rows if r["case_id"] == "eu-dev-223"]
    if len(eu223) != 1:
        raise ValueError("eu-dev-223 debe aparecer exactamente una vez")
    code = Path("eval/numeric_signal.py").read_bytes()
    summary = {
        "header": (
            "DIAGNÓSTICO dev post hoc con etiquetas IA sin revisión humana. "
            "Datos reescritos tras observar errores; NO representativo, NO "
            "aceptación, NO prueba independiente, NO revisión humana completada. "
            "Umbrales NLI 0.75/0.5/0.75 sin cambios."
        ),
        "date": datetime.now(UTC).isoformat(),
        "dataset": {
            "path": str(args.dataset),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "n_cases": len(rows),
        },
        "code": {
            "path": "eval/numeric_signal.py",
            "sha256": hashlib.sha256(code).hexdigest(),
        },
        "script": "eval/numeric_signal_eval.py",
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "hardware": {"platform": platform.platform()},
        "eu_dev_223": eu223[0],
        "coverage": {
            "comparable": sum(1 for r in rows if r["reason"] != "unknown") / len(rows),
            "unknown": sum(1 for r in rows if r["reason"] == "unknown") / len(rows),
        },
        "signal_flag_rate": {
            "all": sum(1 for r in rows if r["needs_review"]) / len(rows),
            "supported": sum(1 for r in supported if r["needs_review"]) / (len(supported) or 1),
            "contradicted": sum(1 for r in contradicted if r["needs_review"])
            / (len(contradicted) or 1),
            "unsupported": sum(1 for r in unsupported if r["needs_review"])
            / (len(unsupported) or 1),
        },
        "baseline_flag_rate": {
            "all": sum(1 for r in rows if r["baseline"]) / len(rows),
            "supported": sum(1 for r in supported if r["baseline"]) / (len(supported) or 1),
        },
        "numeric_subset_flag_rate": {
            "supported": sum(
                1 for r in numeric_rows if r["label"] == "supported" and r["needs_review"]
            )
            / (sum(1 for r in numeric_rows if r["label"] == "supported") or 1),
            "contradicted": sum(
                1 for r in numeric_rows if r["label"] == "contradicted" and r["needs_review"]
            )
            / (sum(1 for r in numeric_rows if r["label"] == "contradicted") or 1),
            "unsupported": sum(
                1 for r in numeric_rows if r["label"] == "unsupported" and r["needs_review"]
            )
            / (sum(1 for r in numeric_rows if r["label"] == "unsupported") or 1),
        },
        "by_label": {k: dict(v) for k, v in by_label.items()},
        "limitations": (
            "Numerales en palabras no analizados; unidades distintas no comparables; "
            "aproximadores nunca avisan. Baseline ingenuo solo para contraste."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    args.details.parent.mkdir(parents=True, exist_ok=True)
    args.details.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
