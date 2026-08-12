"""Modelos declarativos de SQLAlchemy.

Las tablas del dominio (`tenants`, `api_keys`, `documents`) llegan en la fase 1. Aquí
está solo la base común de la que heredan todas.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Sin esto, PostgreSQL inventa el nombre de cada índice y cada restricción. El nombre
# inventado no es estable, así que `alembic --autogenerate` detecta diferencias que no
# existen y `downgrade` no sabe qué borrar.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base de todos los modelos."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
