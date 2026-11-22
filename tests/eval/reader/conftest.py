"""Contenedor Qdrant efímero para el banco XQuAD-es."""

from collections.abc import Iterator

import pytest
from tests.qdrant_docker import isolated_qdrant_url


@pytest.fixture
def isolated_qdrant() -> Iterator[str]:
    with isolated_qdrant_url() as url:
        yield url
