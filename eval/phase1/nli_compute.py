"""Cálculo NLI sobre los preparados (corre en el contenedor ``$P-api``).

Lee ``prepared/nli.json`` (práctica ya seleccionada en el portátil), puntúa con
el verificador real del servicio y escribe un JSON con un veredicto por par
para 1, 3 y 5 textos. No importa ningún cargador de conjuntos: solo
``eval.phase1.nli_data`` (selección y veredicto puros) y el servicio.

Se ejecuta con ``PYTHONPATH=/tmp/code/src:/tmp/code`` y el Python del contenedor.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Define la línea de órdenes del cálculo."""
    parser = argparse.ArgumentParser(prog="python -m eval.phase1.nli_compute")
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--log", type=Path, default=None)
    parser.add_argument("--outer-batch", type=int, default=64)
    return parser


def score_all(
    verifier: Any, premises: list[str], hypotheses: list[str], batch_size: int, outer: int
) -> list[tuple[float, float]]:
    """Puntúa por bloques para no cargar la tokenización de golpe."""
    output: list[tuple[float, float]] = []
    for start in range(0, len(premises), outer):
        output.extend(
            verifier.score_pairs(
                premises[start : start + outer], hypotheses[start : start + outer], batch_size
            )
        )
    return output


def main(argv: list[str] | None = None) -> int:
    """Puntúa los pares preparados y escribe veredictos para 1, 3 y 5 textos."""
    from eval.phase1 import nli_data
    from ragmur.core.config import get_settings
    from ragmur.verification.nli import load_verifier

    args = build_parser().parse_args(argv)
    started = time.time()
    logging.basicConfig(
        level=logging.INFO,
        filename=str(args.log) if args.log else None,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    pairs_data = json.loads(args.prepared.read_text(encoding="utf-8"))
    pairs = [nli_data.Pair(**item) for item in pairs_data]
    settings = get_settings()
    verifier = load_verifier(settings)
    logger.warning(
        "nli_compute: %d pares, dispositivo %s, umbrales %s",
        len(pairs),
        settings.resolved_device,
        [
            settings.verify_supported_threshold,
            settings.verify_weak_threshold,
            settings.verify_contradiction_threshold,
        ],
    )
    base = score_all(
        verifier,
        [pair.premise for pair in pairs],
        [pair.hypothesis for pair in pairs],
        settings.nli_batch_size,
        args.outer_batch,
    )
    extra: dict[int, list[tuple[float, float]]] = {index: [] for index in range(len(pairs))}
    flat_premises: list[str] = []
    flat_hypotheses: list[str] = []
    flat_owner: list[int] = []
    for index, pair in enumerate(pairs):
        for extra_pair in nli_data.distractors(pairs, pair, 5)[1:]:
            flat_premises.append(extra_pair.premise)
            flat_hypotheses.append(pair.hypothesis)
            flat_owner.append(index)
    for owner, scores in zip(
        flat_owner,
        score_all(
            verifier, flat_premises, flat_hypotheses, settings.nli_batch_size, args.outer_batch
        ),
        strict=True,
    ):
        extra[owner].append(scores)
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs):
        ent, contra = base[index]
        entry: dict[str, Any] = {
            "id": pair.id,
            "y": pair.label,
            "kind": pair.anno,
            "e": ent,
            "c": contra,
            "v": nli_data.apply_verdict(
                ent,
                contra,
                settings.verify_supported_threshold,
                settings.verify_weak_threshold,
                settings.verify_contradiction_threshold,
            ),
        }
        for key, count in (("v3", 3), ("v5", 5)):
            scored = [base[index], *extra[index][: count - 1]]
            entry[key] = nli_data.apply_verdict(
                max(score[0] for score in scored),
                max(score[1] for score in scored),
                settings.verify_supported_threshold,
                settings.verify_weak_threshold,
                settings.verify_contradiction_threshold,
            )
        rows.append(entry)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "device": settings.resolved_device,
                "thresholds": [
                    settings.verify_supported_threshold,
                    settings.verify_weak_threshold,
                    settings.verify_contradiction_threshold,
                ],
                "elapsed_s": round(time.time() - started, 1),
                "rows": rows,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    sys.stdout.write(f"nli_compute: {len(rows)} pares en {time.time() - started:.0f} s\n")
    (args.out.parent / "nli-done").write_text("ok\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
