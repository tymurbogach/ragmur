"""Único punto de acceso a Qdrant.

Ningún otro módulo importa `qdrant_client`. La razón es que una consulta que olvide
filtrar por `tenant_id` devuelve datos de otro cliente sin dar ningún error, así que
el filtro no puede quedar repartido por el código: se aplica aquí y solo aquí.

De ahí la regla de que toda función pública reciba `tenant_id` como primer argumento
obligatorio. Las dos de este fichero son la excepción: abrir la conexión y comprobar
que el servidor responde no leen ni escriben puntos de ninguna colección, así que no
hay espacio de tenant que aislar. Cualquier función que sí toque datos la cumple.
"""

from qdrant_client import AsyncQdrantClient

# El tipo se reexporta a propósito: quien necesite anotar un cliente de Qdrant lo
# importa de aquí y no de `qdrant_client`, de modo que la regla «solo este módulo
# importa la biblioteca» siga siendo cierta sin excepciones y comprobable con un
# simple test de imports.
__all__ = ["AsyncQdrantClient", "create_client", "ping"]


def create_client(url: str, timeout_seconds: float) -> AsyncQdrantClient:
    """Abre el cliente asíncrono contra el Qdrant configurado."""
    return AsyncQdrantClient(url=url, timeout=int(timeout_seconds))


async def ping(client: AsyncQdrantClient) -> str:
    """Comprueba que el servidor responde y devuelve su versión.

    Lanza la excepción del cliente si no hay servidor al otro lado; quien llama
    decide qué hacer con ella.
    """
    info = await client.info()
    return info.version
