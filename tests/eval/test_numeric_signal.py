"""Tests unitarios de la señal numérica offline y conservadora."""

from eval.numeric_signal import extract_mentions, numeric_review_signal


def test_normalizes_thousands_separators_without_flagging_match() -> None:
    signal = numeric_review_signal(
        "El objetivo es movilizar hasta 300.000 millones de euros entre 2021 y 2027.",
        "El objetivo es movilizar hasta 300 000 millones de euros entre 2021 y 2027.",
    )
    assert signal.needs_review is False
    assert signal.reason == "match"


def test_flags_174_vs_17_days_case() -> None:
    signal = numeric_review_signal(
        "Los componentes de transferencia de conocimientos importantes fueron "
        "174 días de formación y visitas de demostración.",
        "La transferencia de conocimientos sumó 17 días de formación y visitas.",
    )
    assert signal.needs_review is True
    assert signal.reason == "mismatch"


def test_minimum_cap_subset_does_not_flag() -> None:
    signal = numeric_review_signal(
        "Todos los Estados miembros deben ofrecer un pago anual de hasta 3 000 EUR.",
        "Las explotaciones pueden optar por un pago anual de hasta 3 000 euros.",
    )
    assert signal.needs_review is False


def test_claim_above_maximum_cap_flags() -> None:
    # La afirmación exacta supera la cota máxima: disjunción clara.
    signal = numeric_review_signal(
        "Un plan inicial gratuito para un máximo de 5 colonias.",
        "El plan inicial gratuito cubre 50 colonias.",
    )
    assert signal.needs_review is True
    assert signal.reason == "bound_violation"


def test_weaker_claim_cap_includes_premise_cap_without_flagging() -> None:
    # La segunda cota incluye la primera: debilitamiento, no contradicción.
    signal = numeric_review_signal(
        "La ayuda es de hasta 10 euros.",
        "La ayuda es de hasta 20 euros.",
    )
    assert signal.needs_review is False
    assert signal.reason == "match"


def test_no_supera_is_an_inclusive_upper_bound() -> None:
    signal = numeric_review_signal(
        "La estrategia moviliza hasta 300 000 millones de euros.",
        "El objetivo no supera los 300 000 millones de euros.",
    )
    assert signal.needs_review is False


def test_year_inside_stated_range_does_not_flag() -> None:
    signal = numeric_review_signal(
        "El objetivo cubre el periodo entre 2021 y 2027.",
        "El periodo incluye 2024.",
    )
    assert signal.needs_review is False


def test_stronger_claim_cap_is_compatible_but_unconfirmed() -> None:
    # La afirmación refuerza la cota sin contradecirla: compatible,
    # pero la premisa no la establece; no se afirma respaldo.
    signal = numeric_review_signal(
        "La ayuda es de hasta 10 euros.",
        "La ayuda es de hasta 5 euros.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_ambiguous_spanish_comma_separator_is_unknown() -> None:
    # "1,500" es ambiguo (miles ingleses o decimal español con ceros):
    # sin contexto explícito no se afirma comparación alguna.
    signal = numeric_review_signal(
        "La ayuda es de 1,500 euros.",
        "La ayuda es de 1,5 euros.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_spanish_grouped_decimal_is_one_number() -> None:
    signal = numeric_review_signal(
        "El importe fue de 1.234,50 euros.",
        "El importe fue de 1234,5 euros.",
    )
    assert signal.needs_review is False
    assert signal.reason == "match"
    assert [m.value for m in extract_mentions("El importe fue de 1.234,50 euros.")] == [1234.5]


def test_numeric_match_does_not_claim_entity_match() -> None:
    signal = numeric_review_signal(
        "Hay 10 alumnos en Madrid.",
        "Hay 10 alumnos en Sevilla.",
    )
    assert signal.reason == "match"
    assert "entidad y significado no verificados" in signal.detail


def test_unambiguous_thousands_with_commas_still_match() -> None:
    # Varias comas fijan miles sin ambigüedad.
    signal = numeric_review_signal(
        "El presupuesto es de 1,500,000 euros.",
        "El presupuesto es de 1500000 euros.",
    )
    assert signal.needs_review is False
    assert signal.reason == "match"


def test_shared_figure_across_entities_is_unknown() -> None:
    # La cifra 20 coincide, pero pertenece a otra entidad (Sevilla);
    # la premisa asocia 10 a Madrid. Mera coincidencia no es respaldo.
    signal = numeric_review_signal(
        "Hay 10 alumnos de Madrid y 20 alumnos de Sevilla.",
        "Hay 20 alumnos de Madrid.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_strict_lower_bound_excludes_equal_value() -> None:
    # "más de 10" es estricto: 10 queda fuera y avisa.
    signal = numeric_review_signal(
        "La estancia requiere más de 10 días.",
        "La estancia fue de 10 días.",
    )
    assert signal.needs_review is True
    assert signal.reason == "bound_violation"


def test_inclusive_lower_bound_covers_equal_value_without_flagging() -> None:
    # "al menos 10" es inclusivo: 10 es compatible, aunque la premisa
    # no establece el valor exacto; no se afirma respaldo.
    signal = numeric_review_signal(
        "Se requieren al menos 10 días.",
        "Fueron 10 días.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_strict_upper_bound_excludes_equal_value() -> None:
    # "menos de 10" es estricto: 10 queda fuera y avisa.
    signal = numeric_review_signal(
        "El plazo es de menos de 10 días.",
        "El plazo fue de 10 días.",
    )
    assert signal.needs_review is True
    assert signal.reason == "bound_violation"


def test_inclusive_upper_bound_covers_equal_value() -> None:
    # "hasta 10" es inclusivo: 10 es compatible y no avisa, aunque la
    # premisa no establece el valor exacto; no se afirma respaldo.
    signal = numeric_review_signal(
        "La ayuda es de hasta 10 euros.",
        "La ayuda es de 10 euros.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_exact_premise_narrower_claim_bound_flags() -> None:
    # El valor exacto 10 queda fuera de "hasta 5": disjunción clara.
    signal = numeric_review_signal(
        "La ayuda es de 10 euros.",
        "La ayuda es de hasta 5 euros.",
    )
    assert signal.needs_review is True
    assert signal.reason == "bound_violation"


def test_exact_premise_wider_claim_bound_matches() -> None:
    # El valor exacto 10 queda dentro de "hasta 20": respaldo por inclusión.
    signal = numeric_review_signal(
        "La ayuda es de 10 euros.",
        "La ayuda es de hasta 20 euros.",
    )
    assert signal.needs_review is False
    assert signal.reason == "match"


def test_matching_range_does_not_flag() -> None:
    signal = numeric_review_signal(
        "La ayuda media a nivel nacional en virtud de la ayuda decreciente a la "
        "renta por superfcie oscilará entre 130 y 240 EUR por hectárea.",
        "La ayuda media nacional por superficie se situará en una horquilla de 130 "
        "a 240 euros por hectárea.",
    )
    assert signal.needs_review is False


def test_disjoint_range_flags() -> None:
    signal = numeric_review_signal(
        "La estrategia moviliza fondos entre 2021 y 2027.",
        "El objetivo cubre únicamente el periodo 2028-2034.",
    )
    assert signal.needs_review is True


def test_different_units_are_unknown_not_flagged() -> None:
    signal = numeric_review_signal(
        "Se ofrecieron aproximadamente 100 jornadas de formación.",
        "El Fondo de Innovación financió 5 proyectos de hidrógeno renovable.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_word_numerals_are_unknown_not_flagged() -> None:
    signal = numeric_review_signal(
        "Se centra en cinco sectores: digital, clima y energía.",
        "Se centra en tres sectores: defensa, pesca y turismo.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_approximate_hedge_never_flags() -> None:
    signal = numeric_review_signal(
        "Se ofrecieron aproximadamente 100 jornadas de formación.",
        "Se ofrecieron unas 10 jornadas de formación.",
    )
    assert signal.needs_review is False


def test_percentages_with_comma_decimals() -> None:
    mentions = extract_mentions("La media fue del 20,2 % frente al 24,5 %.")
    values = sorted(m.value for m in mentions if m.unit == "percent")
    assert values == [20.2, 24.5]


def test_dates_with_different_values_flag() -> None:
    signal = numeric_review_signal(
        "El Reglamento MDR entró en vigor el 26 de mayo de 2021.",
        "El MDR entró en vigor el 26 de mayo de 2022.",
    )
    assert signal.needs_review is True


def test_new_number_without_common_unit_does_not_false_flag() -> None:
    # Soporte válido con una cifra repetida más detalle nuevo sin unidad común.
    signal = numeric_review_signal(
        "La plataforma tiene más de 45 millones de usuarios en la UE.",
        "Las plataformas con más de 45 millones de usuarios deben evaluar riesgos.",
    )
    assert signal.needs_review is False


def test_subset_of_table_values_is_unknown_without_entity_linking() -> None:
    # Ambas cifras aparecen en la tabla, pero el prototipo no verifica a
    # qué fila pertenece cada una; una permuta daría el mismo resultado.
    # Mera coincidencia no implica respaldo.
    signal = numeric_review_signal(
        "PROGRAMAS METAS 43 % Fondo 43 % Programa 40 % Mecanismo 70 % Instrumento 30 %",
        "El Mecanismo tiene la meta más alta, un 70 %, frente al 30 % del Instrumento.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"


def test_repeated_dates_without_entity_linking_is_unknown() -> None:
    # Ambas fechas aparecen en ambos textos, pero el prototipo no puede
    # distinguir MDR/2021 + IVDR/2022 de la permuta; no afirma respaldo.
    signal = numeric_review_signal(
        "El MDR entró en vigor el 26 de mayo de 2021. El IVDR entró en vigor "
        "el 26 de mayo de 2022.",
        "El MDR entró en vigor el 26 de mayo de 2021 y el IVDR el 26 de mayo de 2022.",
    )
    assert signal.needs_review is False
    assert signal.reason == "unknown"
