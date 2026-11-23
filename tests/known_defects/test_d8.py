"""D8 (contrato actual, test normal): sin owner_id se busca en todo el tenant.

La búsqueda sin ``owner_id`` recorre todos los usuarios del tenant. Es el
comportamiento correcto para un corpus compartido (ver ARCHITECTURE.md
«Aislamiento»). U01 decidirá si este contrato cambia; este test lo fija.
"""

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from ragmur.retrieval import store


def _point(tenant: str, owner: str) -> Any:
    """Un punto mínimo con id y payload, sin importar Qdrant."""
    return SimpleNamespace(id=uuid4(), payload={"tenant_id": tenant, "owner_id": owner})


class _FakeClient:
    """Qdrant falso que aplica el filtro de la petición (sin red)."""

    def __init__(self, tenant_id: object) -> None:
        self._tenant = tenant_id
        self._points = [
            _point(str(self._tenant), "alice"),
            _point(str(self._tenant), "bob"),
        ]

    async def collection_exists(self, collection: str) -> bool:
        """La colección existe para que la lectura llegue a hacerse."""
        return True

    async def scroll(self, **kwargs: Any) -> tuple[list[Any], None]:
        """Devuelve los puntos que pasan el filtro tenant/duendo/ids."""
        scroll_filter = kwargs.get("scroll_filter")
        conditions: list[Any] = list(getattr(scroll_filter, "must", []) or [])
        wanted_owner: str | None = None
        wanted_ids: set[str] | None = None
        for cond in conditions:
            key = getattr(cond, "key", None)
            if key == "owner_id":
                wanted_owner = str(getattr(getattr(cond, "match", None), "value", ""))
            if hasattr(cond, "has_id"):
                wanted_ids = {str(value) for value in cond.has_id}
        out = []
        for point in self._points:
            if wanted_ids is not None and str(point.id) not in wanted_ids:
                continue
            if wanted_owner is not None and point.payload.get("owner_id") != wanted_owner:
                continue
            out.append(point)
        return out, None


async def test_d8_search_without_owner_covers_whole_tenant() -> None:
    """Sin owner_id se leen los puntos de todos los dueños del tenant."""
    tenant_id = uuid4()
    client = _FakeClient(tenant_id)
    ids: list[UUID] = [point.id for point in client._points]
    points = await store.retrieve_points(tenant_id, client, "ragmur_chunks", ids, None)  # type: ignore[arg-type]
    assert {point.payload["owner_id"] for point in points} == {"alice", "bob"}


async def test_d8_search_with_owner_stays_scoped() -> None:
    """Con owner_id los puntos de otros dueños siguen fuera del alcance."""
    tenant_id = uuid4()
    client = _FakeClient(tenant_id)
    ids: list[UUID] = [point.id for point in client._points]
    points = await store.retrieve_points(tenant_id, client, "ragmur_chunks", ids, "alice")  # type: ignore[arg-type]
    assert [point.payload["owner_id"] for point in points] == ["alice"]
