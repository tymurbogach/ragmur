"""Contenedor Qdrant efímero para pruebas de integración."""

import subprocess
from collections.abc import Iterator

import pytest


@pytest.fixture
def isolated_qdrant() -> Iterator[str]:
    container = subprocess.run(
        ["docker", "run", "--rm", "-d", "-p", "127.0.0.1::6333", "qdrant/qdrant:v1.19.0"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    try:
        port = (
            subprocess.run(
                ["docker", "port", container, "6333/tcp"],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .rsplit(":", 1)[1]
        )
        yield f"http://127.0.0.1:{port}"
    finally:
        subprocess.run(["docker", "stop", container], check=True, capture_output=True)
