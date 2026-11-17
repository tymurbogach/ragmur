"""Evaluación diagnóstica de la señal numérica sobre cualquier dataset solo dev.

Solo diagnóstico: etiquetas IA sin revisión humana; NO sirve para aceptación
ni para cambiar umbrales. No ejecuta NLI ni abre particiones reservadas.
Detalles por caso en /tmp; el resumen agregado va a eval/results/.

Diferencias frente a eval/_archive_ai/numeric_signal_eval.py (al que no sustituye):
ningún ID concreto exigido; tasas null cuando el denominador es cero;
conteos explícitos; hash del script propio incluido.
`reason="match"` indica solo coincidencia numérica, no apoyo semántico.
Una alerta no es necesariamente falsa porque la referencia sea `unsupported`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from eval.numeric_signal import numeric_review_signal

_ALLOWED_LABELS = {"supported", "contradicted", "unsupported"}


def _baseline_needs_review(premise: str, claim: str) -> bool:
    """Baseline ingenuo: difiere algún dígito literal de la afirmación."""
    premise_digits = set(re.findall(r"\d+", premise.replace("\xa0", " ")))
    claim_digits = re.findall(r"\d+", claim.replace("\xa0", " "))
    return any(d not in premise_digits for d in claim_digits) and bool(claim_digits)


def _rate(flagged: int, total: int) -> float | None:
    """Tasa o null cuando no hay denominador; nunca 0 artificial."""
    if total == 0:
        return None
    return flagged / total


def _git_info() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {"commit": commit, "dirty": bool(status.strip()), "status_short": status[:2000]}


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
        claims = case.get("claims")
        if not isinstance(claims, list) or not claims:
            raise ValueError(f"Caso {case.get('id')} sin claims")
        for claim in claims:
            if claim.get("label") not in _ALLOWED_LABELS:
                raise ValueError(f"Etiqueta no válida en caso {case.get('id')}")
            signal = numeric_review_signal(case["premise"], claim["text"])
            rows.append(
                {
                    "case_id": case["id"],
                    "label": claim["label"],
                    "stress_type": case.get("stress_type"),
                    "numeric": bool(case.get("phenomenon", {}).get("numeric", False)),
                    "needs_review": signal.needs_review,
                    "reason": signal.reason,
                    "baseline": _baseline_needs_review(case["premise"], claim["text"]),
                }
            )
    by_label: dict[str, Counter[str]] = {}
    for row in rows:
        by_label.setdefault(row["label"], Counter())[str(row["needs_review"])] += 1
    by_stress: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("stress_type") or "unspecified")
        entry = by_stress.setdefault(key, {"total": 0, "flagged": 0, "by_label": Counter()})
        entry["total"] += 1
        entry["flagged"] += 1 if row["needs_review"] else 0
        entry["by_label"][row["label"]] += 1
    by_stress_out = {
        k: {
            "total": v["total"],
            "flagged": v["flagged"],
            "flag_rate": _rate(int(v["flagged"]), int(v["total"])),
            "by_label": dict(v["by_label"]),
        }
        for k, v in sorted(by_stress.items())
    }
    numeric_rows = [r for r in rows if r["numeric"]]
    supported = [r for r in rows if r["label"] == "supported"]
    contradicted = [r for r in rows if r["label"] == "contradicted"]
    unsupported = [r for r in rows if r["label"] == "unsupported"]
    code_path = Path("eval/numeric_signal.py")
    code = code_path.read_bytes()
    script_path = Path(__file__)
    try:
        script_rel = str(script_path.relative_to(Path.cwd()))
    except ValueError:
        script_rel = str(script_path)
    git = _git_info()
    total = len(rows)
    flagged = sum(1 for r in rows if r["needs_review"])
    unknown = sum(1 for r in rows if r["reason"] == "unknown")
    summary = {
        "header": (
            "DIAGNÓSTICO dev con etiquetas IA sin revisión humana. "
            "Datos de estrés construidos tras observar defectos; NO representativo, NO "
            "aceptación, NO prueba independiente, NO revisión humana completada. "
            "Umbrales NLI 0.75/0.5/0.75 sin cambios. match indica solo coincidencia "
            "numérica, no apoyo semántico. Una alerta no es necesariamente falsa "
            "porque la referencia sea unsupported."
        ),
        "date": datetime.now(UTC).isoformat(),
        "dataset": {
            "path": str(args.dataset),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "n_cases": len(cases),
            "n_claims": total,
        },
        "code": {
            "path": "eval/numeric_signal.py",
            "sha256": hashlib.sha256(code).hexdigest(),
        },
        "script": {
            "path": script_rel,
            "sha256": hashlib.sha256(script_path.read_bytes()).hexdigest(),
        },
        "commit": git["commit"],
        "dirty": git["dirty"],
        "git_status_short": git["status_short"],
        "hardware": {"platform": platform.platform()},
        "counts": {
            "cases": len(cases),
            "claims": total,
            "flagged": flagged,
            "unknown": unknown,
            "supported": len(supported),
            "contradicted": len(contradicted),
            "unsupported": len(unsupported),
            "numeric_claims": len(numeric_rows),
        },
        "coverage": {
            "comparable": _rate(total - unknown, total),
            "unknown": _rate(unknown, total),
            "comparable_count": total - unknown,
            "unknown_count": unknown,
            "total": total,
        },
        "signal_flag_rate": {
            "all": _rate(flagged, total),
            "supported": _rate(sum(1 for r in supported if r["needs_review"]), len(supported)),
            "contradicted": _rate(
                sum(1 for r in contradicted if r["needs_review"]), len(contradicted)
            ),
            "unsupported": _rate(
                sum(1 for r in unsupported if r["needs_review"]), len(unsupported)
            ),
        },
        "signal_flag_counts": {
            "all": {"flagged": flagged, "total": total},
            "supported": {
                "flagged": sum(1 for r in supported if r["needs_review"]),
                "total": len(supported),
            },
            "contradicted": {
                "flagged": sum(1 for r in contradicted if r["needs_review"]),
                "total": len(contradicted),
            },
            "unsupported": {
                "flagged": sum(1 for r in unsupported if r["needs_review"]),
                "total": len(unsupported),
            },
        },
        "baseline_flag_rate": {
            "all": _rate(sum(1 for r in rows if r["baseline"]), total),
            "supported": _rate(sum(1 for r in supported if r["baseline"]), len(supported)),
        },
        "baseline_flag_counts": {
            "all": {
                "flagged": sum(1 for r in rows if r["baseline"]),
                "total": total,
            },
            "supported": {
                "flagged": sum(1 for r in supported if r["baseline"]),
                "total": len(supported),
            },
        },
        "numeric_subset_flag_rate": {
            "supported": _rate(
                sum(1 for r in numeric_rows if r["label"] == "supported" and r["needs_review"]),
                sum(1 for r in numeric_rows if r["label"] == "supported"),
            ),
            "contradicted": _rate(
                sum(1 for r in numeric_rows if r["label"] == "contradicted" and r["needs_review"]),
                sum(1 for r in numeric_rows if r["label"] == "contradicted"),
            ),
            "unsupported": _rate(
                sum(1 for r in numeric_rows if r["label"] == "unsupported" and r["needs_review"]),
                sum(1 for r in numeric_rows if r["label"] == "unsupported"),
            ),
        },
        "numeric_subset_flag_counts": {
            "supported": {
                "flagged": sum(
                    1 for r in numeric_rows if r["label"] == "supported" and r["needs_review"]
                ),
                "total": sum(1 for r in numeric_rows if r["label"] == "supported"),
            },
            "contradicted": {
                "flagged": sum(
                    1 for r in numeric_rows if r["label"] == "contradicted" and r["needs_review"]
                ),
                "total": sum(1 for r in numeric_rows if r["label"] == "contradicted"),
            },
            "unsupported": {
                "flagged": sum(
                    1 for r in numeric_rows if r["label"] == "unsupported" and r["needs_review"]
                ),
                "total": sum(1 for r in numeric_rows if r["label"] == "unsupported"),
            },
        },
        "by_label": {k: dict(v) for k, v in by_label.items()},
        "by_stress_type": by_stress_out,
        "limitations": (
            "Numerales en palabras no analizados; unidades distintas no comparables; "
            "aproximadores nunca avisan. Baseline ingenuo solo para contraste. "
            "needs_review=true es aviso de revisión, no error ni veredicto; "
            "una alerta sobre referencia unsupported puede ser esperada. "
            "match indica solo coincidencia numérica; no verifica entidad ni significado."
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
