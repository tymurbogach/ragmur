"""Tests de `GET /health`.

Son de integración: PostgreSQL y Qdrant se levantan con Docker y no se simulan. Un
chequeo de salud contra dependencias simuladas comprueba la simulación, no el
servicio.
"""

from httpx import AsyncClient


async def test_health_con_dependencias_vivas(client: AsyncClient) -> None:
    """Camino correcto: ambas dependencias responden."""
    respuesta = await client.get("/health")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["dependencies"]["postgres"]["status"] == "ok"
    assert cuerpo["dependencies"]["qdrant"]["status"] == "ok"


async def test_health_reporta_la_version_de_cada_dependencia(client: AsyncClient) -> None:
    """El detalle sirve para saber contra qué versión se está corriendo."""
    cuerpo = (await client.get("/health")).json()

    assert cuerpo["dependencies"]["postgres"]["detail"]
    assert cuerpo["dependencies"]["qdrant"]["detail"]


async def test_health_devuelve_503_si_las_dependencias_no_responden(
    client_sin_dependencias: AsyncClient,
) -> None:
    """Camino de error: 503 y el motivo de cada fallo, sin propagar la excepción."""
    respuesta = await client_sin_dependencias.get("/health")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "degraded"
    assert cuerpo["dependencies"]["postgres"]["status"] == "error"
    assert cuerpo["dependencies"]["qdrant"]["status"] == "error"
    assert cuerpo["dependencies"]["postgres"]["detail"]
