"""D1: la petición a Qdrant debe filtrar por tenant (regla 3 de AGENTS.md)."""

from typing import Any
from uuid import uuid4

import pytest

from ragmur.retrieval import store


class _FakeClient:
    """Qdrant falso que graba con qué filtro se le pidió (sin red)."""

    def __init__(self) -> None:
        self.calls: dict[str, Any] = {}

    async def collection_exists(self, collection: str) -> bool:
        """La colección existe para que la petición llegue a hacerse."""
        return True

    async def retrieve(self, **kwargs: Any) -> list[Any]:
        """Graba los argumentos y devuelve cero puntos."""
        self.calls.update(kwargs)
        return []


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="D1: retrieve_points filtra después, no en la petición",
)
async def test_d1_qdrant_request_filters_by_tenant() -> None:
    """La petición retrieve ya lleva el filtro de tenant autorizado."""
    tenant_id = uuid4()
    client = _FakeClient()
    await store.retrieve_points(tenant_id, client, "ragmur_chunks", [uuid4()], None)  # type: ignore[arg-type]
    sent = client.calls.get("filter")
    assert sent is not None, "D1: la petición a Qdrant no filtra por tenant"
    assert str(tenant_id) in str(sent), "D1: el filtro no menciona al tenant"
