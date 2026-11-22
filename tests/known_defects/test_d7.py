"""D7: el apoyo mayoritario debe ganar a una contradicción aislada."""

import asyncio
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from ragmur.api.routes import verify as verify_route
from ragmur.api.schemas import VerifyRequest
from ragmur.retrieval.store import StoredPoint


class _Session:
    """Sesión falsa: todos los documentos consultados están indexados."""

    def __init__(self, document_ids: list[Any]) -> None:
        self._ids = document_ids

    async def scalars(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
        """Devuelve los identificadores del espacio autorizado."""
        return SimpleNamespace(all=lambda: list(self._ids))


class _SessionFactory:
    """Fábrica que imita ``resources.sessions()`` como contexto asíncrono."""

    def __init__(self, document_ids: list[Any]) -> None:
        self._ids = document_ids

    def __call__(self) -> "_SessionFactory":
        """Se llama como ``resources.sessions()`` y devuelve el contexto."""
        return self

    async def __aenter__(self) -> _Session:
        """Abre la sesión falsa."""
        return _Session(self._ids)

    async def __aexit__(self, *args: Any) -> None:
        """Cierra sin hacer nada."""


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="D7: una contradicción gana a todo apoyo"
)
async def test_d7_support_beats_single_contradiction(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dos apoyos fuertes (0,95) ganan a una contradicción aislada (0,80)."""
    support_id, contra_id = uuid4(), uuid4()
    document_id = uuid4()
    points = [
        StoredPoint(
            id=support_id,
            payload={"document_id": str(document_id), "text": "El plazo es 48 horas."},
        ),
        StoredPoint(
            id=contra_id,
            payload={"document_id": str(document_id), "text": "El plazo es 24 horas."},
        ),
    ]

    async def fake_retrieve(*args: Any, **kwargs: Any) -> list[StoredPoint]:
        return list(points)

    async def fake_inference(*args: Any, **kwargs: Any) -> list[tuple[float, float]]:
        return [(0.95, 0.05), (0.10, 0.80)]

    monkeypatch.setattr("ragmur.retrieval.store.retrieve_points", fake_retrieve)
    monkeypatch.setattr(verify_route, "run_inference", fake_inference)
    resources = SimpleNamespace(
        qdrant=object(),
        sessions=_SessionFactory([document_id]),
        models=SimpleNamespace(lock=asyncio.Lock()),
        verifier=SimpleNamespace(check_hypothesis=lambda claim: None, score_pairs=object()),
    )
    request = VerifyRequest(
        answer="El plazo de entrega es de 48 horas.",
        chunk_ids=[support_id, contra_id],
    )
    response = await verify_route.verify(request, uuid4(), resources)  # type: ignore[arg-type]
    assert response.claims[0].verdict == "supported", (
        f"D7: el apoyo 0,95 pierde ante la contradicción 0,80: {response.claims[0].verdict}"
    )
