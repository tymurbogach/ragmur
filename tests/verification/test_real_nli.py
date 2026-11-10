"""Verificación NLI con inferencia real; calibra umbrales y correferencia."""

import asyncio
import os

import pytest

from ragmur.core.config import Settings, get_settings
from ragmur.verification.nli import load_verifier


@pytest.mark.skipif(os.environ.get("RAGMUR_REAL_MODEL_TESTS") != "1", reason="Requires real models")
async def test_real_nli_supports_contradicts_and_marks_unknown() -> None:
    settings = Settings(
        database_url=get_settings().database_url,
        api_key_hmac_secret="test",
    )
    verifier = await asyncio.to_thread(load_verifier, settings)
    assert verifier.max_length >= 512
    premises = [
        "El plazo de entrega es de 48 horas.",
        "El plazo de entrega es de 48 horas.",
        "El plazo de entrega es de 48 horas.",
        "Tesla murió en 1943.",
        "Tesla murió en 1943.",
    ]
    hypotheses = [
        "El plazo de entrega es de 48 horas.",
        "El plazo de entrega es de una semana.",
        "El color del cielo es azul.",
        "Tesla murió en 1943.",
        "Tesla murió en 1960.",
    ]
    scores = await asyncio.to_thread(verifier.score_pairs, premises, hypotheses, 8)
    supported = scores[0][0]
    assert supported >= settings.verify_supported_threshold
    assert scores[0][1] < settings.verify_contradiction_threshold
    assert scores[1][1] >= settings.verify_contradiction_threshold
    assert scores[2][0] < settings.verify_weak_threshold
    assert scores[2][1] < settings.verify_contradiction_threshold
    assert scores[3][0] >= settings.verify_supported_threshold
    assert scores[4][1] >= settings.verify_contradiction_threshold


@pytest.mark.skipif(os.environ.get("RAGMUR_REAL_MODEL_TESTS") != "1", reason="Requires real models")
async def test_real_nli_coreference_without_mitigation() -> None:
    settings = Settings(
        database_url=get_settings().database_url,
        api_key_hmac_secret="test",
    )
    verifier = await asyncio.to_thread(load_verifier, settings)
    premise = "Tesla vivió en hoteles de Nueva York."
    isolated = await asyncio.to_thread(
        verifier.score_pairs, [premise], ["Este plazo es de 48 horas."], 8
    )
    with_context = await asyncio.to_thread(
        verifier.score_pairs,
        [premise],
        ["Tesla vivió en hoteles. Este plazo es de 48 horas."],
        8,
    )
    assert isolated[0][0] < settings.verify_weak_threshold
    assert with_context[0][0] < settings.verify_weak_threshold
