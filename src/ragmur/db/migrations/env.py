"""Arranque de Alembic.

Alembic ejecuta este fichero antes de cada migración. Aquí se hacen dos cosas que la
plantilla por defecto deja en blanco: coger la URL de la base de datos de `Settings`
en vez de `alembic.ini`, y apuntar `target_metadata` a la base de los modelos para
que `--autogenerate` sepa contra qué comparar.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from ragmur.core.config import get_settings
from ragmur.db.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """URL de la base de datos, siempre desde la configuración del servicio.

    No se escribe en `alembic.ini` para no tener la contraseña en un fichero
    versionado, y para que las migraciones apunten exactamente a la misma base de
    datos que el servicio.
    """
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse a nada."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Aplica las migraciones sobre una conexión asíncrona.

    Alembic es síncrono por dentro, de ahí el `run_sync`: abre la conexión con
    `asyncpg` y le pasa a Alembic una vista síncrona de ella.
    """
    section = config.get_section(config.config_ini_section, {})
    # Se inyecta aquí y no con `set_main_option` porque una contraseña con el
    # carácter `%` rompería la interpolación del fichero .ini.
    section["sqlalchemy.url"] = _database_url()

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
