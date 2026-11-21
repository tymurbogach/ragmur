"""Lector extractivo del banco: plantillas congeladas y llamada al LLM.

Toda llamada al modelo pasa por `ragmur.llm.provider.complete` (regla 7):
este módulo no importa ningún SDK de proveedor.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from ragmur.core.config import Settings
from ragmur.llm.provider import ChatMessage, Completion, complete

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
WITH_CONTEXT_PROMPT = "reader_v1.md"
NO_CONTEXT_PROMPT = "reader_v1_nocontext.md"
READER_TEMPERATURE = 0.0


@dataclass(frozen=True, slots=True)
class RenderedPrompt:
    """Mensajes `system` y `user` listos para enviar al modelo."""

    system: str
    user: str


def prompt_path(name: str) -> Path:
    """Ruta de una plantilla del lector dentro de `eval/reader/prompts/`."""
    return PROMPTS_DIR / name


def prompt_sha256(path: Path) -> str:
    """SHA-256 de los bytes del fichero de plantilla (va al resumen)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_template(raw: str) -> RenderedPrompt:
    """Separa una plantilla en mensajes `system` y `user` por sus marcadores."""
    system_marker, user_marker = "\n## system\n", "\n## user\n"
    system_at = raw.find(system_marker)
    user_at = raw.find(user_marker)
    if system_at < 0 or user_at < 0 or user_at < system_at:
        raise ValueError("Reader template must contain '## system' then '## user'")
    return RenderedPrompt(
        system=raw[system_at + len(system_marker) : user_at].strip(),
        user=raw[user_at + len(user_marker) :].strip(),
    )


def load_templates() -> tuple[RenderedPrompt, RenderedPrompt]:
    """Carga las plantillas con y sin fragmentos desde sus ficheros."""
    with_template = split_template(prompt_path(WITH_CONTEXT_PROMPT).read_text(encoding="utf-8"))
    without_template = split_template(prompt_path(NO_CONTEXT_PROMPT).read_text(encoding="utf-8"))
    return with_template, without_template


def render_fragments(fragments: list[tuple[str, str]]) -> str:
    """Delimita y numera los fragmentos con su `chunk_id` para el prompt.

    Escapa `<` y `>` del texto (`&lt;`/`&gt;`) para que un fragmento nunca
    rompa los delimitadores `<fragmento>` ni invente atributos.
    """
    return "\n\n".join(
        f'<fragmento n="{position}" id="{chunk_id}">\n{escape_fragment(text)}\n</fragmento>'
        for position, (chunk_id, text) in enumerate(fragments, 1)
    )


def escape_fragment(text: str) -> str:
    """Escapa `<` y `>` del fragmento antes de insertarlo entre delimitadores."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_with_context(
    template: RenderedPrompt, question: str, fragments: list[tuple[str, str]]
) -> RenderedPrompt:
    """Rellena la plantilla con fragmentos: pregunta más contexto delimitado."""
    if "{question}" not in template.user or "{fragments}" not in template.user:
        raise ValueError("With-context template must contain {question} and {fragments}")
    user = template.user.replace("{question}", question).replace(
        "{fragments}", render_fragments(fragments)
    )
    return RenderedPrompt(system=template.system, user=user)


def render_without_context(template: RenderedPrompt, question: str) -> RenderedPrompt:
    """Rellena la plantilla de control: la misma pregunta sin contexto."""
    if "{question}" not in template.user:
        raise ValueError("No-context template must contain {question}")
    user = template.user.replace("{question}", question)
    return RenderedPrompt(system=template.system, user=user)


async def call_reader(
    prompt: RenderedPrompt, *, settings: Settings, seed: int | None
) -> Completion:
    """Envía el prompt al modelo configurado con temperatura 0 y semilla fija.

    Un solo modelo por identificador, sin `fallback`: lo garantiza
    `provider.complete`, la única puerta al LLM.
    """
    messages = [
        ChatMessage(role="system", content=prompt.system),
        ChatMessage(role="user", content=prompt.user),
    ]
    completion = await complete(
        messages, settings=settings, temperature=READER_TEMPERATURE, seed=seed
    )
    logger.info(
        "lector completado",
        extra={
            "model": completion.model,
            "prompt_tokens": completion.prompt_tokens,
            "completion_tokens": completion.completion_tokens,
        },
    )
    return completion
