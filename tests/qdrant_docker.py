"""Ayudante compartido de Qdrant desechable para los tests.

Sin ``RAGMUR_TEST_SSH_HOST`` conserva el comportamiento de CI (Docker
local). Con la variable, levanta el contenedor en Skynet por SSH y abre un
túnel: el binario ``docker`` local no se ejecuta nunca en ese modo.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager

from eval.phase1 import skynet

QDRANT_HTTP_PORT = 6333


def _wait_http(url: str, timeout: float = 120.0) -> None:
    """Espera a que Qdrant responda en /healthz."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/healthz", timeout=5) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Qdrant no respondió en {url}/healthz")


@contextmanager
def _local_qdrant() -> Iterator[str]:
    """Contenedor local, como en CI."""
    container = subprocess.run(
        ["docker", "run", "--rm", "-d", "-p", "127.0.0.1::6333", skynet.QDRANT_IMAGE],
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
        url = f"http://127.0.0.1:{port}"
        _wait_http(url)
        yield url
    finally:
        subprocess.run(["docker", "stop", container], check=True, capture_output=True)


@contextmanager
def _skynet_qdrant(host: str) -> Iterator[str]:
    """Contenedor en Skynet con túnel; cero llamadas al Docker local."""
    run_id = f"fix-{os.getpid()}-{secrets.token_hex(4)}"
    name = skynet.run_qdrant(host, run_id)
    tunnel = None
    try:
        remote_port = skynet.remote_port(host, name, QDRANT_HTTP_PORT)
        tunnel, local = skynet.open_tunnel(host, remote_port)
        url = f"http://127.0.0.1:{local}"
        _wait_http(url)
        yield url
    finally:
        if tunnel is not None:
            skynet.close_tunnel(tunnel)
        skynet.stop_container(host, name)


@contextmanager
def isolated_qdrant_url() -> Iterator[str]:
    """Qdrant desechable: en Skynet con túnel si hay host, local si no."""
    host = os.environ.get("RAGMUR_TEST_SSH_HOST", "").strip()
    if host:
        with _skynet_qdrant(host) as url:
            yield url
    else:
        with _local_qdrant() as url:
            yield url
