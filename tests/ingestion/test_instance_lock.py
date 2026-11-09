"""Comprueba la exclusión de escritores en PostgreSQL."""

import pytest

from ragmur.core.config import get_settings
from ragmur.db.session import acquire_database_lock, create_engine


async def test_database_lock_rejects_second_writer() -> None:
    first = create_engine(get_settings().database_url)
    second = create_engine(get_settings().database_url)
    try:
        lock = await acquire_database_lock(first)
        with pytest.raises(RuntimeError, match="Otra instancia"):
            await acquire_database_lock(second)
        await lock.close()
    finally:
        await first.dispose()
        await second.dispose()
