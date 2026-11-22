"""Acceso a Skynet por SSH, sin tocar el Docker del portátil.

Toda invocación a Docker sale como ``ssh <host> docker ...`` cuando hay un
host configurado, de modo que el binario ``docker`` local nunca se ejecuta.
Sin host se conserva el comportamiento de CI (``docker`` local). Cada orden
remota es una sola invocación, sin tuberías ni ``;``: el host es Windows y su
shell por defecto no las entiende.
"""

from __future__ import annotations

import contextlib
import os
import secrets
import socket
import subprocess
import time
from collections.abc import Sequence
from subprocess import Popen

SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=10")
QDRANT_IMAGE = "qdrant/qdrant:v1.19.0"
POSTGRES_IMAGE = "postgres:17-alpine"


class SkynetError(RuntimeError):
    """Fallo de infraestructura remota (sale con código 2)."""


def docker_cmd(host: str | None, *args: str) -> list[str]:
    """Construye el argv para hablar con Docker.

    Con host, el primer ejecutable es ``ssh`` y ``docker`` solo aparece como
    argumento remoto: el Docker local no se toca. Sin host, se usa ``docker``
    local, como en CI.
    """
    if host:
        return ["ssh", *SSH_OPTIONS, host, *args]
    return ["docker", *args]


def remote(host: str | None, *args: str, timeout: float = 120.0) -> str:
    """Ejecuta una orden Docker y devuelve su salida recortada."""
    try:
        completed = subprocess.run(
            docker_cmd(host, *args),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except OSError as exc:
        raise SkynetError(f"no se pudo lanzar la orden: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise SkynetError(f"orden agotada ({timeout:g} s): {' '.join(args)}") from exc
    if completed.returncode != 0:
        raise SkynetError(f"orden remota fallida: {' '.join(args)}: {completed.stderr.strip()}")
    return completed.stdout.strip()


def prefix(run_id: str) -> str:
    """Prefijo de todos los recursos de una ejecución."""
    return f"ragmur-p1-{run_id}"


def label(run_id: str) -> str:
    """Etiqueta que identifica los recursos de una ejecución."""
    return f"ragmur.p1.run={run_id}"


def _free_local_port() -> int:
    """Reserva un puerto local libre y lo libera para el túnel."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_tcp(port: int, deadline: float, what: str) -> None:
    """Espera a que un puerto local acepte conexiones."""
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2.0)
            try:
                sock.connect(("127.0.0.1", port))
                return
            except OSError:
                time.sleep(1.0)
    raise SkynetError(f"{what} no abrió su puerto a tiempo")


def open_tunnel(host: str, remote_port: int, timeout: float = 60.0) -> tuple[Popen[bytes], int]:
    """Abre un túnel SSH hacia un puerto remoto. Solo se usa con host."""
    local = _free_local_port()
    try:
        proc = Popen(
            [
                "ssh",
                *SSH_OPTIONS,
                "-N",
                "-L",
                f"127.0.0.1:{local}:127.0.0.1:{remote_port}",
                host,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        raise SkynetError(f"no se pudo abrir el túnel: {exc}") from exc
    try:
        wait_tcp(local, time.time() + timeout, f"túnel hacia {remote_port}")
    except SkynetError:
        proc.terminate()
        raise
    return proc, local


def close_tunnel(proc: Popen[bytes]) -> None:
    """Cierra un túnel SSH sin fallar si ya murió."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            proc.kill()


def remote_port(host: str | None, container: str, port: int) -> int:
    """Lee el puerto publicado de un contenedor (``docker port``)."""
    out = remote(host, "docker", "port", container, f"{port}/tcp")
    # Formato esperado: ``127.0.0.1:32768``. Se toma lo que sigue al último ``:``.
    tail = out.strip().splitlines()[-1].rsplit(":", 1)[1]
    return int(tail)


def list_resources(host: str | None, run_id: str) -> dict[str, list[str]]:
    """Lista contenedores y redes de una ejecución por su etiqueta."""
    wanted = label(run_id)
    containers = remote(host, "docker", "ps", "-aq", "--filter", f"label={wanted}")
    networks = remote(host, "docker", "network", "ls", "-q", "--filter", f"label={wanted}")
    return {
        "containers": [line for line in containers.splitlines() if line.strip()],
        "networks": [line for line in networks.splitlines() if line.strip()],
    }


def create_network(host: str | None, run_id: str) -> str:
    """Crea la red aislada de una ejecución."""
    name = f"{prefix(run_id)}-net"
    remote(host, "docker", "network", "create", "--label", label(run_id), name)
    return name


def run_postgres(host: str | None, run_id: str, network: str, password: str) -> str:
    """Levanta un PostgreSQL desechable en la red de la ejecución."""
    name = f"{prefix(run_id)}-pg"
    remote(
        host,
        "docker",
        "run",
        "--rm",
        "-d",
        "--name",
        name,
        "--network",
        network,
        "--label",
        label(run_id),
        "--tmpfs",
        "/var/lib/postgresql/data",
        "-e",
        "POSTGRES_USER=ragmur",
        "-e",
        f"POSTGRES_PASSWORD={password}",
        "-e",
        "POSTGRES_DB=ragmur_test",
        "-p",
        "127.0.0.1::5432",
        POSTGRES_IMAGE,
    )
    return name


def run_qdrant(host: str | None, run_id: str, network: str | None = None) -> str:
    """Levanta un Qdrant desechable con la imagen fijada del proyecto."""
    token = secrets.token_hex(4)
    name = f"{prefix(run_id)}-q-{token}" if network is None else f"{prefix(run_id)}-q"
    args: list[str] = ["docker", "run", "--rm", "-d", "--name", name, "--label", label(run_id)]
    if network is not None:
        args += ["--network", network]
    args += ["-p", "127.0.0.1::6333", QDRANT_IMAGE]
    remote(host, *args)
    return name


def stop_container(host: str | None, name: str) -> None:
    """Para un contenedor sin fallar si ya no existe."""
    with contextlib.suppress(SkynetError):
        remote(host, "docker", "stop", name, timeout=60.0)


def remove_network(host: str | None, name: str) -> None:
    """Borra una red sin fallar si ya no existe."""
    with contextlib.suppress(SkynetError):
        remote(host, "docker", "network", "rm", name, timeout=60.0)


def tunnel_pids_alive(pids: Sequence[int]) -> list[int]:
    """Devuelve los PIDs de túnel que siguen vivos."""
    alive: list[int] = []
    for pid in pids:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except PermissionError:
            alive.append(pid)
        else:
            alive.append(pid)
    return alive


def cleanup_run(host: str | None, run_id: str) -> dict[str, int]:
    """Retira los restos de una ejecución. Nunca toca otros recursos.

    Solo filtra por la etiqueta de la ejecución, así que por construcción no
    puede parar ni borrar ``ragmur_deploy*`` ni nada ajeno al prefijo.
    """
    found = {"containers": 0, "networks": 0}
    try:
        resources = list_resources(host, run_id)
    except SkynetError:
        return found
    for container in resources["containers"]:
        found["containers"] += 1
        stop_container(host, container)
    # Los nombres de red llevan el prefijo; se reintenta por nombre además de por id.
    for network in resources["networks"]:
        found["networks"] += 1
        remove_network(host, network)
    remove_network(host, f"{prefix(run_id)}-net")
    return found
