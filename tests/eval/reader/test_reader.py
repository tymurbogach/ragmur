"""Plantillas congeladas y llamada al lector, con el proveedor simulado."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from eval.reader.reader import (
    NO_CONTEXT_PROMPT,
    WITH_CONTEXT_PROMPT,
    RenderedPrompt,
    call_reader,
    escape_fragment,
    load_templates,
    prompt_path,
    prompt_sha256,
    render_with_context,
    render_without_context,
    split_template,
)

from eval.reader import reader
from ragmur.core.config import Settings
from ragmur.llm.provider import Completion

WITH_SHA_PINNED = "c949c3e371a7c3d5dc80fdd55dea6441dd22f940cbf69a1ac3c0a28eea41dfd5"
WITHOUT_SHA_PINNED = "18f6a3962b0b3a475d24e7c52a3a846a9376e8b173a5827615477f2f0b625a7a"


def make_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://lector:lector@127.0.0.1:5432/nada",
        api_key_hmac_secret="test-only-hmac-secret",
    )


def test_prompt_files_exist_and_are_stable() -> None:
    with_path = prompt_path(WITH_CONTEXT_PROMPT)
    without_path = prompt_path(NO_CONTEXT_PROMPT)
    assert with_path.is_file() and without_path.is_file()
    assert prompt_sha256(with_path) == WITH_SHA_PINNED
    assert prompt_sha256(without_path) == WITHOUT_SHA_PINNED
    assert len(prompt_sha256(without_path)) == 64


def test_templates_split_into_system_and_user() -> None:
    with_template, without_template = load_templates()
    assert with_template.system and "{question}" in with_template.user
    assert "{fragments}" in with_template.user
    assert without_template.system and "{question}" in without_template.user
    assert "{fragments}" not in without_template.user
    # El ejemplo positivo sin contexto es un hecho común: un dato inventado
    # enseñaría al modelo a adivinar sin fragmentos (revisión G03b, N1).
    assert "Lucía Ferrán" in with_template.system
    assert "Lucía Ferrán" not in without_template.system
    assert "París" in without_template.system
    assert "NO CONSTA" in with_template.system and "NO CONSTA" in without_template.system


def test_templates_cite_id_not_position() -> None:
    with_template, _without_template = load_templates()
    assert "atributo `id`" in with_template.system
    assert "posición" in with_template.system


def test_split_template_rejects_missing_markers() -> None:
    with pytest.raises(ValueError, match="## system"):
        split_template("sin marcadores")


def test_render_with_context_delimits_and_numbers_fragments() -> None:
    template = RenderedPrompt(system="s", user="Q: {question}\n{fragments}")
    rendered = render_with_context(template, "¿Color?", [("id-1", "negro"), ("id-2", "rojo")])
    assert "¿Color?" in rendered.user
    assert '<fragmento n="1" id="id-1">\nnegro\n</fragmento>' in rendered.user
    assert '<fragmento n="2" id="id-2">' in rendered.user
    with pytest.raises(ValueError, match="fragments"):
        render_with_context(RenderedPrompt(system="s", user="Q: {question}"), "¿Color?", [])


def test_escape_fragment_keeps_delimiters_safe() -> None:
    assert escape_fragment('a<b id="x">c') == 'a&lt;b id="x"&gt;c'
    template = RenderedPrompt(system="s", user="Q: {question}\n{fragments}")
    rendered = render_with_context(template, "¿Q?", [("a", 'texto <raro> con "id"')])
    assert "&lt;raro&gt;" in rendered.user
    assert "<raro>" not in rendered.user


def test_render_without_context_has_no_fragments() -> None:
    template = RenderedPrompt(system="s", user="Q: {question}")
    rendered = render_without_context(template, "¿Color?")
    assert "¿Color?" in rendered.user and "<fragmento" not in rendered.user


async def test_call_reader_uses_temperature_zero_and_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    async def fake_complete(messages: object, **kwargs: object) -> Completion:
        seen.update(kwargs)
        seen["messages"] = messages
        return Completion(
            text='{"answer": "x", "citations": [], "found": true}',
            model="fake",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1.0,
            attempts=1,
        )

    monkeypatch.setattr(reader, "complete", AsyncMock(side_effect=fake_complete))
    completion = await call_reader(
        RenderedPrompt(system="s", user="u"), settings=make_settings(), seed=20261121
    )
    assert completion.model == "fake"
    assert seen["temperature"] == 0.0 and seen["seed"] == 20261121
    messages = seen["messages"]
    assert [message.role for message in messages] == ["system", "user"]
