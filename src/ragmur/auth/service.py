"""Operaciones de tenants y claves de API."""

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ragmur.db.models import ApiKey, Tenant


def key_hash(secret: str, server_secret: str) -> str:
    """Calcula la huella HMAC del secreto de una clave."""
    return hmac.new(server_secret.encode(), secret.encode(), hashlib.sha256).hexdigest()


async def create_tenant(session: AsyncSession, name: str) -> Tenant:
    """Crea un tenant."""
    tenant = Tenant(name=name)
    session.add(tenant)
    await session.commit()
    return tenant


async def issue_key(
    session: AsyncSession, tenant_id: uuid.UUID, name: str | None, server_secret: str
) -> str:
    """Emite una clave que solo se devuelve en esta llamada."""
    if await session.get(Tenant, tenant_id) is None:
        raise ValueError("Tenant not found")
    key_id = secrets.token_hex(16)
    secret = secrets.token_urlsafe(32)
    session.add(
        ApiKey(
            tenant_id=tenant_id, key_id=key_id, key_hash=key_hash(secret, server_secret), name=name
        )
    )
    await session.commit()
    return f"rgm_{key_id}_{secret}"


async def revoke_key(session: AsyncSession, key_id: str) -> bool:
    """Revoca una clave por su identificador público."""
    result = await session.execute(
        update(ApiKey)
        .where(ApiKey.key_id == key_id, ApiKey.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
        .returning(ApiKey.id)
    )
    await session.commit()
    return result.scalar_one_or_none() is not None


async def authenticate(session: AsyncSession, raw_key: str, server_secret: str) -> uuid.UUID | None:
    """Resuelve el tenant y registra el uso como máximo una vez por minuto."""
    parts = raw_key.split("_", 2)
    if len(parts) != 3 or parts[0] != "rgm" or not parts[1] or not parts[2]:
        return None
    key = await session.scalar(select(ApiKey).where(ApiKey.key_id == parts[1]))
    if key is None or key.revoked_at is not None:
        return None
    if not hmac.compare_digest(key.key_hash, key_hash(parts[2], server_secret)):
        return None
    now = datetime.now(UTC)
    if key.last_used_at is None or key.last_used_at <= now - timedelta(minutes=1):
        await session.execute(
            update(ApiKey)
            .where(
                ApiKey.id == key.id,
                ApiKey.revoked_at.is_(None),
                or_(
                    ApiKey.last_used_at.is_(None), ApiKey.last_used_at <= now - timedelta(minutes=1)
                ),
            )
            .values(last_used_at=now)
        )
        await session.commit()
    return key.tenant_id
