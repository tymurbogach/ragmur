"""Motor y sesiones de base de datos.

El motor mantiene un grupo de conexiones abiertas y se crea una sola vez por proceso,
al arrancar. Abrir una conexión por petición costaría más que la propia consulta.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str) -> AsyncEngine:
    """Crea el motor asíncrono contra la URL dada."""
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Fábrica de sesiones ligada a un motor.

    `expire_on_commit=False` evita que los objetos ya cargados vuelvan a consultarse
    tras un `commit()`: con un motor asíncrono esa recarga implícita ocurriría fuera
    del `await` y reventaría.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Abre una sesión, la cede y la cierra pase lo que pase."""
    async with factory() as session:
        yield session
