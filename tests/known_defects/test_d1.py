"""D1: la petición a Qdrant filtra por tenant (regla 3 de AGENTS.md)."""

from typing import Any
from uuid import uuid4

from ragmur.retrieval import store


class _FakeClient:
    """Qdrant falso que graba con qué filtro se le pidió (sin red)."""

    def __init__(self) -> None:
        self.calls: dict[str, Any] = {}

    async def collection_exists(self, collection: str) -> bool:
        """La colección existe para que la petición llegue a hacerse."""
        return True

    async def scroll(self, **kwargs: Any) -> tuple[list[Any], None]:
        """Graba los argumentos y devuelve cero puntos."""
        self.calls.update(kwargs)
        return [], None


async def test_d1_qdrant_request_filters_by_tenant() -> None:
    """La petición a Qdrant ya lleva el filtro de tenant autorizado."""
    tenant_id = uuid4()
    client = _FakeClient()
    await store.retrieve_points(tenant_id, client, "ragmur_chunks", [uuid4()], None)  # type: ignore[arg-type]
    sent = client.calls.get("scroll_filter")
    assert sent is not None, "D1: la petición a Qdrant no filtra por tenant"
    assert str(tenant_id) in str(sent), "D1: el filtro no menciona al tenant"
