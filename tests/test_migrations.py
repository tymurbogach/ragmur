import runpy
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from alembic import context

MIGRATIONS_ENV = Path(__file__).resolve().parents[1] / "src/ragmur/db/migrations/env.py"


async def test_migration_failure_disposes_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    config = Mock()
    config.config_file_name = None
    config.config_ini_section = "alembic"
    config.get_section.return_value = {}
    monkeypatch.setattr(context, "config", config, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True, raising=False)
    monkeypatch.setattr(context, "configure", Mock(), raising=False)
    transaction = MagicMock()
    monkeypatch.setattr(context, "begin_transaction", lambda: transaction, raising=False)
    monkeypatch.setattr(context, "run_migrations", Mock(), raising=False)
    namespace = runpy.run_path(str(MIGRATIONS_ENV))

    connection = MagicMock()
    active_connection = Mock()
    active_connection.run_sync = AsyncMock(side_effect=RuntimeError("migration failure"))
    connection.__aenter__ = AsyncMock(return_value=active_connection)
    engine = Mock()
    engine.connect.return_value = connection
    engine.dispose = AsyncMock()
    run_migrations = namespace["run_async_migrations"]
    monkeypatch.setitem(run_migrations.__globals__, "_database_url", lambda: "unused")
    monkeypatch.setitem(
        run_migrations.__globals__, "async_engine_from_config", Mock(return_value=engine)
    )

    with pytest.raises(RuntimeError, match="migration failure"):
        await run_migrations()
    engine.dispose.assert_awaited_once()
