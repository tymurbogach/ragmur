"""Comprobación de que PostgreSQL responde."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def ping(engine: AsyncEngine) -> str:
    """Ejecuta la consulta más barata que existe y devuelve la versión del servidor.

    `SELECT 1` no basta por sí solo para saber si la base de datos está sana, pero sí
    para saber que hay una conexión viva y que acepta consultas, que es lo que un
    chequeo de salud debe responder. Cualquier cosa más cara castigaría a quien lo
    consulta cada pocos segundos.
    """
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        version = await conn.scalar(text("SHOW server_version"))
    return str(version)
