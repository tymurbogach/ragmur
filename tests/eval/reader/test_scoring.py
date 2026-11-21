"""Normalización, extracción y reglas de puntuación del lector, sin red."""

import random

import pytest
from eval.reader.scoring import (
    answer_kind,
    build_counterfactual_fragments,
    choose_substitute,
    classify_counterfactual,
    classify_outcome,
    contains_match,
    contains_span,
    exact_match,
    extract_json_object,
    golds_kind,
    is_abstention,
    normalize_es,
    parse_reader_output,
    proportion,
    retrieval_hit,
    substitute_answers,
    substitute_discard_reason,
    token_f1,
    valid_citations,
)

from eval.reader import scoring


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("El NIÑO", "nino"),
        ("CAMIÓN", "camion"),
        ("año", "ano"),
        ("pingüino", "pinguino"),
        ("¡Hola, Mundo!", "hola mundo"),
        ("  de   la   casa  ", "de casa"),
        ("el la los las un una unos unas lo", ""),
        ("Los Panthers cedieron solo 308 puntos", "panthers cedieron solo 308 puntos"),
        ("bienvenido-a", "bienvenidoa"),
        ("¿De qué colores?", "de que colores"),
    ],
)
def test_normalize_es_vectors(raw: str, expected: str) -> None:
    assert normalize_es(raw) == expected


def test_exact_match_ignores_case_accents_and_articles() -> None:
    assert exact_match("Negro y Amarillo", ("negro y amarillo",))
    assert exact_match("EL NINO", ("el niño",))
    assert not exact_match("rojo", ("negro y amarillo",))


def test_token_f1_identical_partial_and_disjoint() -> None:
    assert token_f1("negro y amarillo", ("negro y amarillo",)) == pytest.approx(1.0)
    assert token_f1("negro", ("negro y amarillo",)) == pytest.approx(1 / 2)
    assert token_f1("verde", ("negro y amarillo",)) == 0.0


def test_token_f1_takes_max_over_golds() -> None:
    assert token_f1("negro", ("verde", "negro")) == pytest.approx(1.0)


def test_extract_json_object_plain_fenced_and_noisy() -> None:
    plain = '{"answer": "308", "citations": ["a"], "found": true}'
    assert extract_json_object(plain)["answer"] == "308"
    fenced = '```json\n{"answer": "308", "citations": [], "found": true}\n```'
    assert extract_json_object(fenced)["found"] is True
    noisy = 'Creo que es {"answer": "308", "citations": [], "found": true} seguro.'
    assert extract_json_object(noisy)["answer"] == "308"


def test_extract_json_object_rejects_garbage() -> None:
    with pytest.raises(scoring.ParseError):
        extract_json_object("no hay json aquí")
    with pytest.raises(scoring.ParseError):
        extract_json_object('{"answer": sin cerrar')


def test_parse_reader_output_schema() -> None:
    parsed = parse_reader_output('{"answer": "308", "citations": ["a"], "found": true}')
    assert (parsed.answer, parsed.citations, parsed.found) == ("308", ("a",), True)
    with pytest.raises(scoring.ParseError):
        parse_reader_output('{"answer": "308", "found": true}')
    with pytest.raises(scoring.ParseError):
        parse_reader_output('{"answer": 308, "citations": [], "found": true}')
    with pytest.raises(scoring.ParseError):
        parse_reader_output('{"answer": "x", "citations": "a", "found": true}')
    with pytest.raises(scoring.ParseError):
        parse_reader_output('{"answer": "x", "citations": [], "found": "yes"}')


def test_is_abstention() -> None:
    assert is_abstention("lo que sea", False)
    assert is_abstention("NO CONSTA", True)
    assert is_abstention(" no consta. ", True)
    assert not is_abstention("308", True)


def test_valid_citations() -> None:
    context = {"a": "el logotipo era negro y amarillo", "b": "texto sin relación"}
    assert valid_citations(["a"], {"a", "b"}, context, ("negro y amarillo",)) == ["a"]
    assert valid_citations(["b"], {"a", "b"}, context, ("negro y amarillo",)) == []
    assert valid_citations(["z"], {"a", "b"}, context, ("negro y amarillo",)) == []
    assert valid_citations(["a", "a"], {"a", "b"}, context, ("negro y amarillo",)) == ["a"]


def test_retrieval_hit() -> None:
    assert retrieval_hit(["era Negro y Amarillo el logo"], ("negro y amarillo",))
    assert not retrieval_hit(["otro texto cualquiera"], ("negro y amarillo",))


def test_classify_outcome() -> None:
    assert classify_outcome(em=True, abstained=False) == "correct"
    assert classify_outcome(em=False, abstained=False) == "wrong"
    assert classify_outcome(em=False, abstained=True) == "abstained"


def test_substitute_answers_case_and_accent_insensitive() -> None:
    assert substitute_answers("El Negro Y Amarillo", [("negro y amarillo", "rojo")]) == "El rojo"
    assert substitute_answers("llevaba un CAMION", [("camión", "tren")]) == "llevaba un tren"


def test_counterfactual_guard_discards() -> None:
    fragments = ["el logo era negro y amarillo"]
    ok = build_counterfactual_fragments(fragments, ("negro y amarillo",), "rojo")
    assert (ok.discarded, ok.fragments) == (False, ("el logo era rojo",))
    present = build_counterfactual_fragments(
        ["el logo era rojo y amarillo"], ("negro y amarillo",), "rojo"
    )
    assert (present.discarded, present.reason) == (True, "substitute already present")
    remains = build_counterfactual_fragments(["el logo era rojo"], ("rojo",), "rojo oscuro")
    assert (remains.discarded, remains.reason) == (True, "original remains")
    equal = build_counterfactual_fragments(fragments, ("ROJO",), "rojo")
    assert (equal.discarded, equal.reason) == (True, "substitute equals original")


def test_choose_substitute_deterministic_and_excludes_own() -> None:
    candidates = ["rojo", "Negro y Amarillo", "azul"]
    first = choose_substitute(("negro y amarillo",), candidates, random.Random(7))
    second = choose_substitute(("negro y amarillo",), candidates, random.Random(7))
    assert first == second and first in ("azul", "rojo")
    assert choose_substitute(("a",), (), random.Random(7)) is None
    assert choose_substitute(("a",), ("A",), random.Random(7)) is None


def test_classify_counterfactual() -> None:
    assert classify_counterfactual("rojo", ("negro y amarillo",), "rojo") == "reads_context"
    assert (
        classify_counterfactual("negro y amarillo", ("negro y amarillo",), "rojo") == "uses_memory"
    )
    assert classify_counterfactual("NO CONSTA", ("negro y amarillo",), "rojo") == "other"


def test_proportion_wilson_shape() -> None:
    full = proportion(5, 5)
    assert full["rate"] == 1.0 and full["wilson_95"][0] <= 1.0
    empty = proportion(0, 0)
    assert empty["rate"] == 0.0 and empty["wilson_95"] is None
    with pytest.raises(ValueError):
        proportion(2, 1)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Łódź", "łodz"),
        ("Søren Kierkegaard", "søren kierkegaard"),
    ],
)
def test_normalize_keeps_non_ascii_letters(raw: str, expected: str) -> None:
    assert normalize_es(raw) == expected


def test_contains_span_word_boundaries() -> None:
    assert contains_span("panthers cedieron solo 308 puntos", "308")
    assert not contains_span("panthers cedieron 3080 puntos", "308")
    assert not contains_span("ano 2010", "10")
    assert contains_span("ano 10", "10")
    assert not contains_span("", "308")
    assert not contains_span("hola", "")


def test_retrieval_hit_whole_word() -> None:
    assert retrieval_hit(["cedieron solo 308 puntos"], ("308",))
    assert not retrieval_hit(["cedieron 3080 puntos"], ("308",))
    assert not retrieval_hit(["ano 2010"], ("10",))


def test_valid_citations_whole_word() -> None:
    context = {"a": "cedieron solo 308 puntos", "b": "cedieron 3080 puntos"}
    assert valid_citations(["a"], {"a", "b"}, context, ("308",)) == ["a"]
    assert valid_citations(["b"], {"a", "b"}, context, ("308",)) == []


def test_substitute_answers_word_boundaries() -> None:
    assert substitute_answers("cedieron 3080 puntos", [("308", "X")]) == "cedieron 3080 puntos"
    assert substitute_answers("cedieron 308 puntos", [("308", "X")]) == "cedieron X puntos"
    assert substitute_answers("ano 2010", [("10", "X")]) == "ano 2010"


def test_answer_kind() -> None:
    assert answer_kind("308") == "numeric"
    assert answer_kind("3,62 metros") == "numeric"
    assert answer_kind("Lucía Ferrán") == "proper"
    assert answer_kind("negro y amarillo") == "common"
    assert golds_kind(("negro y amarillo",)) == "common"


def test_choose_substitute_same_kind_only() -> None:
    rng = random.Random(7)
    assert choose_substitute(("308",), ("rojo", "azul"), rng) is None
    assert substitute_discard_reason(("308",), ("rojo", "azul")) == "type mismatch"
    assert substitute_discard_reason(("308",), ()) == "no substitute"
    picked = choose_substitute(("308",), ("310", "rojo"), random.Random(7))
    assert picked == "310"


def test_parse_reader_output_lenient() -> None:
    parsed = parse_reader_output(
        '{"answer": "x", "citations": ["a", 7, null, {"z": 1}], "found": "true"}'
    )
    assert parsed.citations == ("a", "7")
    assert parsed.found is True
    parsed_false = parse_reader_output('{"answer": "x", "citations": [], "found": "False"}')
    assert parsed_false.found is False
    with pytest.raises(scoring.ParseError):
        parse_reader_output('{"answer": "x", "citations": [], "found": "yes"}')


def test_contains_match_cap() -> None:
    assert contains_match("Mariana Solís", ("Mariana Solís",))
    assert not contains_match("NO CONSTA", ("Mariana Solís",))
    # Oro de dos tokens: tope min(2+3, 2*2)=4; seis tokens no cabe.
    assert not contains_match("Mariana Solís restauró el faro del puerto", ("Mariana Solís",))
    assert contains_match("solo 308", ("308",))


def test_classify_counterfactual_both_and_cap() -> None:
    assert classify_counterfactual("rojo y negro", ("negro",), "rojo") == "both"
    assert classify_counterfactual("rojo", ("negro",), "rojo") == "reads_context"
    # Sustituto contenido pero demasiado largo: otro, no lectura.
    assert (
        classify_counterfactual("rojo restauró el faro del puerto", ("negro",), "rojo") == "other"
    )
