"""Respuesta de error compartida por los middlewares de límite.

Los tres middlewares devuelven el mismo esquema (`code` + `detail`) con dos
serializaciones históricas: `json_limit` usa la forma compacta de
`JSONResponse`, mientras `upload_limit` e `inference_limit` usan `json.dumps`
con separadores por defecto y otro orden de cabeceras. El helper conserva byte
a byte cada formato para no cambiar ningún contrato; `compact=True` reproduce
el primero.
"""

import json

from starlette.types import Send


async def send_error(
    send: Send, status_code: int, detail: str, *, retry_after: bool = False, compact: bool = False
) -> None:
    """Envía el error JSON con los bytes y cabeceras históricos del middleware."""
    payload = {"code": f"http_{status_code}", "detail": detail}
    separators = (",", ":") if compact else (", ", ": ")
    body = json.dumps(payload, separators=separators).encode()
    length = str(len(body)).encode()
    if compact:
        headers = [(b"content-length", length), (b"content-type", b"application/json")]
    else:
        headers = [(b"content-type", b"application/json"), (b"content-length", length)]
    if retry_after:
        headers.append((b"retry-after", b"1"))
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": body})
