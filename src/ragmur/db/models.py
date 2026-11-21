"""Modelos declarativos de SQLAlchemy."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

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


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    key_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Longitud máxima de `owner_id`; la validan la API y la restricción CHECK con el mismo valor.
OWNER_ID_MAX_LENGTH = 256


class Document(Base):
    """Metadatos y estado de un original conservado en disco."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "owner_id", "content_sha256", postgresql_nulls_not_distinct=True
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'extracted', 'indexed', "
            "'failed', 'unsupported', 'deleting')",
            name="status",
        ),
        CheckConstraint(
            f"owner_id IS NULL OR char_length(owner_id) <= {OWNER_ID_MAX_LENGTH}",
            name="owner_id_length",
        ),
        Index("ix_documents_tenant_id_owner_id", "tenant_id", "owner_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    owner_id: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int | None]
    chunk_count: Mapped[int | None]
    error: Mapped[str | None] = mapped_column(Text)
    diagnostic: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
