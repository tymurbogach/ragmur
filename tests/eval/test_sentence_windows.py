"""Ventanas de frases: segmentacion, limites, contexto y agregacion NLI."""

import pytest
from eval.sentence_windows import (
    aggregate_window_scores,
    build_premise_windows,
    build_sentence_windows,
    decide_verdict,
    expand_window_pairs,
    split_sentences,
)


def test_split_basic_two_sentences() -> None:
    assert split_sentences("El plazo es de 48 horas. El transporte va incluido.") == [
        "El plazo es de 48 horas.",
        "El transporte va incluido.",
    ]


def test_split_collapses_pdf_line_breaks() -> None:
    assert split_sentences("La línea quedó\ncortada en el PDF. Siguiente frase.") == [
        "La línea quedó cortada en el PDF.",
        "Siguiente frase.",
    ]


def test_split_keeps_decimals_and_percentages_intact() -> None:
    assert split_sentences("El importe es 3.14 millones. Sigue creciendo.") == [
        "El importe es 3.14 millones.",
        "Sigue creciendo.",
    ]
    assert split_sentences("La meta es 43 %. El resto es 30 %.") == [
        "La meta es 43 %.",
        "El resto es 30 %.",
    ]


def test_split_protects_common_abbreviation_before_uppercase() -> None:
    assert split_sentences("El Sr. García vino. Habló con ella.") == [
        "El Sr. García vino.",
        "Habló con ella.",
    ]


def test_split_handles_questions_and_inverted_marks() -> None:
    assert split_sentences("¿Vienes mañana? Sí, voy.") == ["¿Vienes mañana?", "Sí, voy."]


def test_split_blank_fails_instead_of_returning_nothing() -> None:
    with pytest.raises(ValueError, match="blank"):
        split_sentences("   \n  ")


def test_split_too_many_sentences_fails_instead_of_truncating() -> None:
    text = " ".join(f"Frase número {index}." for index in range(61))
    with pytest.raises(ValueError, match="Too many sentences"):
        split_sentences(text)


def test_windows_first_alone_rest_with_previous() -> None:
    sentences = ["La empresa facturó 10 M.", "Este importe creció.", "El resto cayó."]
    assert build_sentence_windows(sentences) == [
        "La empresa facturó 10 M.",
        "La empresa facturó 10 M. Este importe creció.",
        "Este importe creció. El resto cayó.",
    ]


def test_windows_keep_anaphoric_antecedent_in_next_window() -> None:
    windows = build_premise_windows("La empresa facturó 10 M. Este importe creció un 5 %.")
    assert len(windows) == 2
    assert "La empresa facturó 10 M." in windows[1]
    assert "Este importe" in windows[1]


def test_windows_cover_every_sentence_without_silent_drops() -> None:
    sentences = ["Primera.", "Segunda.", "Tercera."]
    windows = build_sentence_windows(sentences)
    assert len(windows) == len(sentences)
    for sentence in sentences:
        assert any(sentence in window for window in windows)


def test_windows_reject_empty_or_blank_input() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        build_sentence_windows([])
    with pytest.raises(ValueError, match="must not be blank"):
        build_sentence_windows(["Válida.", "   "])


def test_expand_pairs_aligns_windows_with_claim_index() -> None:
    premises, hypotheses, owner = expand_window_pairs(
        [["w0", "w0 w1"], ["v0"]], ["afirmación A", "afirmación B"]
    )
    assert premises == ["w0", "w0 w1", "v0"]
    assert hypotheses == ["afirmación A", "afirmación A", "afirmación B"]
    assert owner == [0, 0, 1]


def test_expand_pairs_rejects_misalignment_and_silent_drops() -> None:
    with pytest.raises(ValueError, match="align"):
        expand_window_pairs([["w0"]], ["A", "B"])
    with pytest.raises(ValueError, match="at least one window"):
        expand_window_pairs([[]], ["A"])
    with pytest.raises(ValueError, match="blank"):
        expand_window_pairs([["w0"]], ["   "])


def test_aggregate_keeps_separate_maxima_per_claim() -> None:
    scores = [(0.9, 0.1), (0.2, 0.8), (0.4, 0.3)]
    assert aggregate_window_scores(scores, [0, 0, 1], 2) == [(0.9, 0.8), (0.4, 0.3)]


def test_aggregate_rejects_missing_or_out_of_range_claims() -> None:
    with pytest.raises(ValueError, match="align"):
        aggregate_window_scores([(0.5, 0.1)], [0, 1], 2)
    with pytest.raises(ValueError, match="out of range"):
        aggregate_window_scores([(0.5, 0.1)], [7], 2)
    with pytest.raises(ValueError, match="at least one window"):
        aggregate_window_scores([(0.5, 0.1)], [0], 2)


def test_decide_contradiction_prevails_over_support() -> None:
    verdict, score = decide_verdict(
        0.95, 0.80, supported_threshold=0.75, weak_threshold=0.5, contradiction_threshold=0.75
    )
    assert (verdict, score) == ("contradicted", 0.80)


def test_decide_supported_weak_and_unsupported_scores() -> None:
    assert decide_verdict(
        0.90, 0.10, supported_threshold=0.75, weak_threshold=0.5, contradiction_threshold=0.75
    ) == ("supported", 0.90)
    assert decide_verdict(
        0.60, 0.10, supported_threshold=0.75, weak_threshold=0.5, contradiction_threshold=0.75
    ) == ("weak", 0.60)
    assert decide_verdict(
        0.20, 0.10, supported_threshold=0.75, weak_threshold=0.5, contradiction_threshold=0.75
    ) == ("unsupported", 0.20)


def test_decide_threshold_equality_counts_as_verdict() -> None:
    verdict, _ = decide_verdict(
        0.10, 0.75, supported_threshold=0.75, weak_threshold=0.5, contradiction_threshold=0.75
    )
    assert verdict == "contradicted"
    verdict, _ = decide_verdict(
        0.75, 0.10, supported_threshold=0.75, weak_threshold=0.5, contradiction_threshold=0.75
    )
    assert verdict == "supported"


class _FakeVerifier:
    """Simula el NLI sin cargar ningun modelo."""

    def __init__(self, canned: list[tuple[float, float]]) -> None:
        self._canned = canned

    def check_hypothesis(self, hypothesis: str) -> None:
        if not hypothesis.strip():
            raise ValueError("Hypothesis must not be blank")

    def score_pairs(
        self, premises: list[str], hypotheses: list[str], batch_size: int
    ) -> list[tuple[float, float]]:
        assert len(premises) == len(hypotheses)
        assert batch_size > 0
        return list(self._canned[: len(premises)])


def _run_variant(premise: str, claim: str, canned: list[tuple[float, float]]) -> tuple[str, float]:
    verifier = _FakeVerifier(canned)
    verifier.check_hypothesis(claim)
    windows = build_premise_windows(premise)
    pair_premises, pair_hypotheses, pair_owner = expand_window_pairs(
        [[w for w in windows]], [claim]
    )
    scores = verifier.score_pairs(pair_premises, pair_hypotheses, 8)
    ent, contra = aggregate_window_scores(scores, pair_owner, 1)[0]
    return decide_verdict(
        ent, contra, supported_threshold=0.75, weak_threshold=0.5, contradiction_threshold=0.75
    )


def test_variant_pipeline_supports_through_context_window() -> None:
    verdict, _ = _run_variant(
        "La empresa facturó 10 M. Este importe creció un 5 %.",
        "La facturación creció un 5 %.",
        [(0.20, 0.05), (0.90, 0.05)],
    )
    assert verdict == "supported"


def test_variant_pipeline_contradiction_prevails_across_windows() -> None:
    verdict, score = _run_variant(
        "El plazo es de 48 horas. El plazo es de 72 horas.",
        "El plazo es de 48 horas.",
        [(0.95, 0.05), (0.10, 0.80)],
    )
    assert (verdict, score) == ("contradicted", 0.80)
