"""baseline

Primera revisión, deliberadamente vacía.

No crea ninguna tabla porque la fase 0 no tiene dominio todavía: `tenants` y
`api_keys` son la tarea 1.1 y crearlas aquí adelantaría trabajo de otra fase. Lo que
sí hace es cerrar el circuito completo —`alembic.ini`, `env.py`, el motor asíncrono,
la conexión con `asyncpg` y la tabla `alembic_version`—, que es lo que la fase 0
necesita demostrar. La siguiente revisión ya encadena con esta por `down_revision`.

Revision ID: 0001
Revises:
Create Date: 2026-08-12
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Sin cambios de esquema."""


def downgrade() -> None:
    """Sin cambios de esquema."""
