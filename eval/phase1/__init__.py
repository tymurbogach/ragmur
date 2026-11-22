"""Orquestador desatendido de la fase 1 (C01).

Lanza pruebas largas que sobreviven a la shell que las lanzó y no tocan el
Docker del portátil. Todo el Docker desechable vive en Skynet vía SSH.
"""

from eval.phase1.runner import (
    EXIT_HARD,
    EXIT_INFRA,
    EXIT_OK,
    EXIT_QUALITY,
    STAGES,
    combine_exit_codes,
    stage_to_exit,
)

__all__ = [
    "EXIT_HARD",
    "EXIT_INFRA",
    "EXIT_OK",
    "EXIT_QUALITY",
    "STAGES",
    "combine_exit_codes",
    "stage_to_exit",
]
