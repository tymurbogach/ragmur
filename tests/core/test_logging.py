"""Los registros de acceso no deben contener parámetros sensibles."""

import logging

from ragmur.core.logging import AccessQueryFilter, JsonFormatter


def test_access_log_omits_query() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %s',
        ("127.0.0.1", "GET", "/v1/documents?owner_id=private", "1.1", 200),
        None,
    )
    AccessQueryFilter().filter(record)
    rendered = JsonFormatter().format(record)
    assert "/v1/documents" in rendered
    assert "private" not in rendered and "owner_id" not in rendered
