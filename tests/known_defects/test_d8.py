"""D8 (contrato actual, test normal): sin owner_id se busca en todo el tenant.

La búsqueda sin ``owner_id`` recorre todos los usuarios del tenant. Es el
comportamiento correcto para un corpus compartido (ver ARCHITECTURE.md
«Aislamiento»). U01 decidirá si este contrato cambia; este test lo fija.
"""

from typing import Any
from uuid import uuid4

from ragmur.retrieval import store


class _FakeClient:
    """Qdrant falso con puntos de dos dueños del mismo tenant (sin red)."""

    def __init__(self, tenant_id: object) -> None:
        self._tenant = tenant_id

    async def collection_exists(self, collection: str) -> bool:
        """La colección existe para que la lectura llegue a hacerse."""
        return True

    async def retrieve(self, **kwargs: Any) -> list[Any]:
        """Devuelve un punto de alice y otro de bob del mismo tenant."""
        from types import SimpleNamespace

        return [
            SimpleNamespace(
                id=uuid4(), payload={"tenant_id": str(self._tenant), "owner_id": "alice"}
            ),
            SimpleNamespace(
                id=uuid4(), payload={"tenant_id": str(self._tenant), "owner_id": "bob"}
            ),
        ]


async def test_d8_search_without_owner_covers_whole_tenant() -> None:
    """Sin owner_id se leen los puntos de todos los dueños del tenant."""
    tenant_id = uuid4()
    client = _FakeClient(tenant_id)
    points = await store.retrieve_points(tenant_id, client, "ragmur_chunks", [uuid4()], None)  # type: ignore[arg-type]
    assert {point.payload["owner_id"] for point in points} == {"alice", "bob"}


async def test_d8_search_with_owner_stays_scoped() -> None:
    """Con owner_id los puntos de otros dueños siguen fuera del alcance."""
    tenant_id = uuid4()
    client = _FakeClient(tenant_id)
    points = await store.retrieve_points(tenant_id, client, "ragmur_chunks", [uuid4()], "alice")  # type: ignore[arg-type]
    assert [point.payload["owner_id"] for point in points] == ["alice"]
