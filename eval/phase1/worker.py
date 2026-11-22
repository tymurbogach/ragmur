"""Trabajador desatendido: ejecuta las etapas de una ejecución existente."""

from __future__ import annotations

import sys

from eval.phase1.runner import EXIT_INFRA, run_worker


def main(argv: list[str]) -> int:
    """Punto de entrada del proceso hijo desacoplado."""
    if len(argv) != 2:
        return EXIT_INFRA
    return run_worker(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
