"""Los cuatro códigos de salida y su precedencia 2, 1, 3, 0."""

from eval.phase1.runner import (
    EXIT_HARD,
    EXIT_INFRA,
    EXIT_OK,
    EXIT_QUALITY,
    combine_exit_codes,
    report_exit,
    stage_to_exit,
)


def test_todo_bien_da_cero() -> None:
    assert combine_exit_codes([EXIT_OK, EXIT_OK]) == EXIT_OK


def test_precedencia_infra_despues_duro_despues_calidad() -> None:
    assert combine_exit_codes([EXIT_OK, EXIT_QUALITY]) == EXIT_QUALITY
    assert combine_exit_codes([EXIT_HARD, EXIT_QUALITY, EXIT_OK]) == EXIT_HARD
    assert combine_exit_codes([EXIT_INFRA, EXIT_HARD, EXIT_QUALITY, EXIT_OK]) == EXIT_INFRA


def test_sin_codigos_es_incompleta() -> None:
    assert combine_exit_codes([]) == EXIT_INFRA


def test_estados_de_etapa_a_codigo() -> None:
    assert stage_to_exit("passed") == EXIT_OK
    assert stage_to_exit("hard_failed") == EXIT_HARD
    assert stage_to_exit("infra_error") == EXIT_INFRA
    assert stage_to_exit("incomplete") == EXIT_INFRA
    assert stage_to_exit("quality_failed") == EXIT_QUALITY
    assert stage_to_exit("known_failed") == EXIT_QUALITY
    assert stage_to_exit("otro") == EXIT_INFRA


def _estado(states: dict[str, str]) -> dict[str, object]:
    return {"stages": {name: {"state": state} for name, state in states.items()}}


def test_nunca_cero_con_etapa_ausente() -> None:
    assert report_exit(_estado({"static": "passed"}), ["static", "suite"]) == EXIT_INFRA
    assert report_exit({}, ["static"]) == EXIT_INFRA
    ambas = _estado({"static": "passed", "suite": "passed"})
    assert report_exit(ambas, ["static", "suite"]) == EXIT_OK


def test_calidad_sola_da_tres_y_duro_gana() -> None:
    solo_calidad = _estado({"static": "passed", "suite": "quality_failed"})
    assert report_exit(solo_calidad, ["static", "suite"]) == EXIT_QUALITY
    mixto = _estado({"static": "hard_failed", "suite": "quality_failed"})
    assert report_exit(mixto, ["static", "suite"]) == EXIT_HARD
