"""Smoke real contra un proveedor vivo; saltado salvo `RAGMUR_LLM_LIVE=1`.

El orquestador lo ejecuta con el entorno ya configurado (`LLM_MODEL` y
`LLM_API_KEY` en `.env`); aquí solo se comprueba que la llamada completa
devuelve texto y recuento de tokens.
"""

import os

import pytest

from ragmur.core.config import Settings
from ragmur.llm.provider import ChatMessage, complete

pytestmark = pytest.mark.llm_live


async def test_live_completion_returns_text_and_usage() -> None:
    if os.environ.get("RAGMUR_LLM_LIVE") != "1":
        pytest.skip("solo con RAGMUR_LLM_LIVE=1")
    result = await complete(
        [ChatMessage(role="user", content="Responde solo: OK")], settings=Settings()
    )
    assert result.text.strip()
    assert result.prompt_tokens > 0
