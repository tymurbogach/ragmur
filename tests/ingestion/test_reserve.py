"""Reserva de capacidad sin duplicados."""

from unittest.mock import Mock
from uuid import uuid4

from ragmur.core.config import get_settings
from ragmur.ingestion.pipeline import IngestionCoordinator


def test_reserve_rejects_duplicate_ids() -> None:
    settings = get_settings()
    coordinator = IngestionCoordinator(Mock(), settings, None)
    document_id = uuid4()
    assert coordinator.reserve(document_id) is True
    assert coordinator.reserve(document_id) is False
    coordinator.release(document_id)
    assert coordinator.reserve(document_id) is True
