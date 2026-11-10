"""Tests de `GET /health` y `GET /ready`.

Son de integración: PostgreSQL y Qdrant se levantan con Docker y no se simulan.
`/health` solo dice que el proceso vive; `/ready` comprueba dependencias y
modelos simulados en la suite.
"""

from httpx import AsyncClient


async def test_health_indica_proceso_vivo(client: AsyncClient) -> None:
    """Camino correcto: el proceso responde sin comprobar dependencias."""
    respuesta = await client.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


async def test_ready_comprueba_dependencias_y_modelos(client: AsyncClient) -> None:
    """Camino correcto: dependencias reales y modelos simulados."""
    respuesta = await client.get("/ready")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["dependencies"]["postgres"]["status"] == "ok"
    assert cuerpo["dependencies"]["qdrant"]["status"] == "ok"
    assert cuerpo["dependencies"]["models"]["status"] == "ok"


async def test_ready_devuelve_503_si_las_dependencias_no_responden(
    client_sin_dependencias: AsyncClient,
) -> None:
    """Camino de error: 503 y el motivo de cada fallo, sin propagar la excepción."""
    respuesta = await client_sin_dependencias.get("/ready")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "degraded"
    assert cuerpo["dependencies"]["postgres"]["status"] == "error"
    assert cuerpo["dependencies"]["qdrant"]["status"] == "error"
    assert cuerpo["dependencies"]["postgres"]["detail"]
