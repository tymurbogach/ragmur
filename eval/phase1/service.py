"""Etapa service C05: la API real de principio a fin y bajo carga.

El portátil orquesta y Skynet calcula: la etapa levanta una API aislada con
el código del commit, modelos reales, migraciones y claves de prueba. El
cliente corre en el portátil por un túnel SSH: sube TXT, MD, DOCX y PDF,
espera el indexado, busca, verifica, deduplica, borra, reinicia el contenedor,
repite con otro tenant y otro dueño, borra el primer tenant y pasa la carga
mixta de ``benchmarks/load.py``.

Clasificación: paso incorrecto, fuga entre tenants o dueños, 500 o dato
borrado que reaparece es fallo duro (salida 1) y queda registrado sin impedir
que la etapa complete todos los pasos. Los 429 y 503 se cuentan aparte y no
tumban la etapa. Sin Skynet no hay GPU ni servicio aislado y la etapa queda
como error de infraestructura.

La etapa nunca registra claves: viajan solo en memoria.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

from eval.phase1 import skynet
from eval.phase1.runner import REPO_ROOT, write_json

API_IMAGE = "ragmur_deploy-api:latest"
MODEL_VOLUME = "ragmur_deploy_model_data"
VRAM_WAIT_SECONDS = 900.0
POLL_EVERY_SECONDS = 5.0
READY_TIMEOUT_SECONDS = 1800.0
INDEXED_TIMEOUT_SECONDS = 600.0
SERVICE_TIMEOUT_FALLBACK = 10800.0
LOAD_TIMEOUT_SECONDS = 3600.0
# El tenant A sube 4 documentos y la etapa borra 1 antes de borrar el tenant.
TENANT_A_REMAINING = 3

HARD_KINDS = frozenset({"wrong", "leak", "resurrect", "server500"})

Step = dict[str, Any]


@dataclass(frozen=True)
class Fixture:
    """Un fichero de prueba con su marcador único y su pregunta."""

    name: str
    filename: str
    content: bytes
    mime: str
    marker: str
    query: str
    answer: str


def build_txt() -> Fixture:
    """Construye el TXT con un marcador que no existe en ningún otro formato."""
    text = (
        "El faro de Meridia guía a los barcos en la noche.\n\n"
        "Su luz gira cada doce segundos sobre la bahía.\n\n"
        "El marcador de esta prueba es meridia-faro-c05 y solo vive aquí.\n"
    )
    return Fixture(
        name="txt",
        filename="faro.txt",
        content=text.encode("utf-8"),
        mime="text/plain",
        marker="meridia-faro-c05",
        query="faro de Meridia que guía a los barcos",
        answer="El faro de Meridia guía a los barcos en la noche.",
    )


def build_md() -> Fixture:
    """Construye el Markdown con título y marcador propio."""
    text = (
        "# Puente de Alborada\n\n"
        "El puente de Alborada cruza el río con siete arcos de piedra.\n\n"
        "## Dato de prueba\n\n"
        "El marcador de esta prueba es alborada-puente-c05 y solo vive aquí.\n"
    )
    return Fixture(
        name="md",
        filename="puente.md",
        content=text.encode("utf-8"),
        mime="text/markdown",
        marker="alborada-puente-c05",
        query="puente de Alborada con siete arcos",
        answer="El puente de Alborada cruza el río con siete arcos de piedra.",
    )


def _docx_xml(text: str) -> bytes:
    """Arma el XML mínimo de un DOCX con un párrafo por línea."""
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    paras = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{line}</w:t></w:r></w:p>'
        for line in escaped.split("\n")
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{paras}</w:body></w:document>"
    ).encode()


def build_docx() -> Fixture:
    """Construye un DOCX mínimo válido con la librería estándar."""
    marker = "molino-viento-c05"
    text = (
        "El molino de viento de Cerros Altos muele el grano del valle.\n"
        f"El marcador de esta prueba es {marker} y solo vive aquí."
    )
    buf = BytesIO()
    fixed = (2026, 1, 1, 0, 0, 0)
    entries = (
        (
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument'
            '.wordprocessingml.document.main+xml"/>'
            "</Types>",
        ),
        (
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships'
            '/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        ),
        ("word/document.xml", _docx_xml(text).decode("utf-8")),
    )
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as package:
        for name, text_entry in entries:
            info = zipfile.ZipInfo(name, date_time=fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            package.writestr(info, text_entry)
    return Fixture(
        name="docx",
        filename="molino.docx",
        content=buf.getvalue(),
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        marker=marker,
        query="molino de viento de Cerros Altos",
        answer="El molino de viento de Cerros Altos muele el grano del valle.",
    )


def build_pdf() -> Fixture:
    """Construye un PDF mínimo de una página con referencias calculadas."""
    marker = "huerta-naranjos-c05"
    line = f"La huerta de los naranjos riega cada manana. {marker}."
    stream = f"BT /F1 18 Tf 72 720 Td ({line}) Tj ET".encode("ascii")
    length = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n"
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        length + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF".encode(
        "ascii"
    )
    return Fixture(
        name="pdf",
        filename="huerta.pdf",
        content=bytes(out),
        mime="application/pdf",
        marker=marker,
        query="huerta de los naranjos que riega cada manana",
        answer="La huerta de los naranjos riega cada manana.",
    )


def build_fixtures() -> list[Fixture]:
    """Devuelve los cuatro ficheros de la etapa, uno por formato."""
    return [build_txt(), build_md(), build_docx(), build_pdf()]


@dataclass
class HttpResponse:
    """Respuesta mínima del cliente: estado, JSON, cabeceras o error de red."""

    status: int | None
    data: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None


class ServiceClient(Protocol):
    """Lo que la etapa necesita de HTTP; el falso de los tests lo implementa."""

    def ready(self) -> HttpResponse: ...
    def upload(
        self, key: str, owner: str, filename: str, content: bytes, mime: str
    ) -> HttpResponse: ...
    def document(self, key: str, doc_id: str, owner: str | None = None) -> HttpResponse: ...
    def delete_document(self, key: str, doc_id: str, owner: str | None = None) -> HttpResponse: ...
    def search(
        self,
        key: str,
        query: str,
        owner: str | None = None,
        top_k: int = 5,
        candidates: int = 30,
        rerank: bool = True,
    ) -> HttpResponse: ...
    def verify(
        self, key: str, answer: str, chunk_ids: list[str], owner: str | None = None
    ) -> HttpResponse: ...


class ServiceHooks(Protocol):
    """Acciones de infraestructura que los tests sustituyen por dobles."""

    def restart_api(self) -> None: ...
    def delete_tenant(self) -> int: ...
    def run_load(self, key: str) -> dict[str, Any]: ...


def _ok(name: str, detail: str) -> Step:
    """Un paso que salió como se esperaba."""
    return {"name": name, "ok": True, "kind": "ok", "detail": detail}


def _bad(name: str, kind: str, detail: str) -> Step:
    """Un paso que falló, con su clase para la puntuación final."""
    return {"name": name, "ok": False, "kind": kind, "detail": detail}


def _limited(response: HttpResponse) -> bool:
    """429 y 503 son capacidad o cuota, no un veredicto del producto."""
    return response.status in (429, 503)


def _classify(
    name: str,
    response: HttpResponse,
    expected: set[int],
    problem: Callable[[HttpResponse], str | None],
    ok_detail: str,
) -> Step:
    """Traduce una respuesta HTTP a paso: red, 500, limitado, incorrecto u ok."""
    if response.status is None:
        return _bad(name, "infra", f"sin conexión: {response.error}")
    if response.status == 500:
        return _bad(name, "server500", "la API devolvió 500")
    if _limited(response):
        return _bad(name, "limited", f"persistió el {response.status}")
    if response.status not in expected:
        return _bad(name, "wrong", f"código {response.status}, se esperaba {sorted(expected)}")
    detail = problem(response)
    if detail is not None:
        return _bad(name, "wrong", detail)
    return _ok(name, ok_detail)


class FlowRunner:
    """Ejecuta los pasos contra un cliente y cuenta los 429/503 aparte."""

    def __init__(
        self, client: ServiceClient, hooks: ServiceHooks, retry_sleep: float = 1.0
    ) -> None:
        self._client = client
        self._hooks = hooks
        self._retry_sleep = retry_sleep
        self.limited = 0

    def call(self, func: Callable[..., HttpResponse], *args: Any, **kwargs: Any) -> HttpResponse:
        """Llama con reintentos ante 429/503 y cuenta cada limitado."""
        last: HttpResponse = HttpResponse(status=None, error="sin respuesta")
        for attempt in range(4):
            last = func(*args, **kwargs)
            if last.status is None or not _limited(last):
                return last
            self.limited += 1
            time.sleep(self._retry_sleep * (1.0 + attempt))
        return last

    def wait_indexed(
        self, key: str, owner: str, doc_ids: list[str], timeout: float
    ) -> HttpResponse | None:
        """Espera a que todos los documentos queden indexados antes del plazo."""
        deadline = time.time() + timeout
        last: HttpResponse | None = None
        pending = set(doc_ids)
        while pending and time.time() < deadline:
            for doc_id in sorted(pending):
                response = self.call(self._client.document, key, doc_id, owner)
                if response.status is None:
                    return None
                if _limited(response):
                    break
                last = response
                status = response.data.get("status")
                if status == "indexed":
                    pending.discard(doc_id)
                elif status in ("failed", "unsupported"):
                    return response
            if pending:
                time.sleep(3.0)
        return last


def _search_has(response: HttpResponse, doc_id: str) -> bool:
    """Comprueba si el documento aparece entre los resultados de búsqueda."""
    results = response.data.get("results")
    if not isinstance(results, list):
        return False
    return any(
        isinstance(item, dict) and str(item.get("document_id")) == doc_id for item in results
    )


def _chunk_ids(response: HttpResponse, doc_id: str, limit: int = 3) -> list[str]:
    """Extrae hasta N identificadores de fragmento de un documento."""
    results = response.data.get("results")
    if not isinstance(results, list):
        return []
    found: list[str] = []
    for item in results:
        if isinstance(item, dict) and str(item.get("document_id")) == doc_id:
            chunk = item.get("chunk_id")
            if isinstance(chunk, str) and chunk:
                found.append(chunk)
        if len(found) >= limit:
            break
    return found


def run_flow(
    client: ServiceClient,
    hooks: ServiceHooks,
    key_a: str,
    key_b: str,
    owner_a: str = "duena-c05",
    owner_b: str = "dueno-c05",
    indexed_timeout: float = INDEXED_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Ejecuta los diez pasos del servicio y los puntúa sin detenerse.

    Un fallo duro queda registrado y la etapa continúa con el paso siguiente;
    solo un error de red interrumpe el flujo.
    """
    runner = FlowRunner(client, hooks)
    fixtures = build_fixtures()
    steps: list[Step] = []
    ids_a: dict[str, str] = {}
    chunks: dict[str, list[str]] = {}
    verdicts: dict[str, int] = {}

    uploads = [
        runner.call(client.upload, key_a, owner_a, fix.filename, fix.content, fix.mime)
        for fix in fixtures
    ]

    def _upload_problem(response: HttpResponse) -> str | None:
        """El último 202 debe traer su identificador."""
        if not isinstance(response.data.get("document_id"), str):
            return "la subida no trae document_id"
        return None

    last_upload = uploads[-1]
    if any(response.status is None for response in uploads):
        step = _bad("upload", "infra", "la subida perdió la conexión")
    elif any(response.status == 500 for response in uploads):
        step = _bad("upload", "server500", "la subida devolvió 500")
    elif any(response.status != 202 for response in uploads):
        got = [response.status for response in uploads]
        step = _bad("upload", "wrong", f"códigos inesperados al subir: {got}")
    elif any(_upload_problem(response) for response in uploads):
        step = _bad("upload", "wrong", "una subida no trae document_id")
    else:
        step = _classify("upload", last_upload, {202}, _upload_problem, "4 ficheros aceptados")
    if step["ok"]:
        for fix, response in zip(fixtures, uploads, strict=True):
            ids_a[fix.name] = str(response.data["document_id"])
    steps.append(step)
    if step["kind"] == "infra":
        return {"steps": steps, "limited": runner.limited, "aborted": True}

    if step["ok"]:
        last = runner.wait_indexed(key_a, owner_a, list(ids_a.values()), indexed_timeout)
        if last is None:
            steps.append(_bad("indexed", "infra", "el sondeo perdió la conexión"))
            return {"steps": steps, "limited": runner.limited, "aborted": True}
        if _limited(last):
            steps.append(_bad("indexed", "limited", f"persistió el {last.status}"))
        else:
            missing = [
                name
                for name, doc_id in ids_a.items()
                if (
                    runner.call(client.document, key_a, doc_id, owner_a).data.get("status")
                    != "indexed"
                )
            ]
            if missing:
                steps.append(_bad("indexed", "wrong", f"sin indexar antes del plazo: {missing}"))
            else:
                steps.append(_ok("indexed", "los 4 documentos quedaron indexados"))

    if steps[-1]["ok"]:
        bad: list[str] = []
        severe: Step | None = None
        for fix in fixtures:
            response = runner.call(client.search, key_a, fix.query, owner_a)
            if response.status is None:
                severe = _bad("search", "infra", "la búsqueda perdió la conexión")
                break

            def _problem(answered: HttpResponse, want: str = ids_a[fix.name]) -> str | None:
                """El marcador de este formato debe recuperar su documento."""
                if _search_has(answered, want):
                    return None
                return "el marcador no recupera su documento"

            probe = _classify("search", response, {200}, _problem, "")
            if probe["kind"] in ("server500", "limited", "infra"):
                severe = _bad("search", str(probe["kind"]), str(probe["detail"]))
                break
            if not probe["ok"]:
                bad.append(fix.name)
            else:
                chunks[fix.name] = _chunk_ids(response, ids_a[fix.name])
        if severe is not None:
            steps.append(severe)
            if severe["kind"] == "infra":
                return {"steps": steps, "limited": runner.limited, "aborted": True}
        elif bad:
            steps.append(_bad("search", "wrong", f"el marcador no recupera su documento: {bad}"))
        else:
            steps.append(_ok("search", "los 4 marcadores devuelven su documento"))

    if steps[-1]["ok"]:
        response = runner.call(
            client.verify, key_a, fixtures[0].answer, chunks.get("txt", []), owner_a
        )

        def _verify_problem(answered: HttpResponse) -> str | None:
            """La verificación debe puntuar al menos una frase con veredicto válido."""
            claims = answered.data.get("claims")
            if not isinstance(claims, list) or not claims:
                return "la verificación no devolvió frases"
            for claim in claims:
                verdict = claim.get("verdict") if isinstance(claim, dict) else None
                if verdict in ("supported", "weak", "unsupported", "contradicted"):
                    verdicts[verdict] = verdicts.get(verdict, 0) + 1
                else:
                    return f"veredicto inválido: {verdict!r}"
            return None

        step = _classify("verify", response, {200}, _verify_problem, "")
        if step["ok"]:
            step["detail"] = f"{sum(verdicts.values())} frases puntuadas: {verdicts}"
        steps.append(step)
        if step["kind"] == "infra":
            return {"steps": steps, "limited": runner.limited, "aborted": True}

    if ids_a:
        first = fixtures[0]
        response = runner.call(
            client.upload, key_a, owner_a, "otra-copia.txt", first.content, first.mime
        )

        def _dedup_problem(answered: HttpResponse) -> str | None:
            """El repetido debe señalar al original."""
            if answered.data.get("document_id") != ids_a.get("txt"):
                return f"el duplicado apunta a otro id: {answered.data}"
            if answered.data.get("duplicate") is not True:
                return "el duplicado no se marcó como tal"
            return None

        step = _classify("dedup", response, {200}, _dedup_problem, "el repetido apunta al original")
        steps.append(step)
        if step["kind"] == "infra":
            return {"steps": steps, "limited": runner.limited, "aborted": True}

    pdf_id = ids_a.get("pdf")
    if pdf_id is not None:
        response = runner.call(client.delete_document, key_a, pdf_id, owner_a)
        step = _classify("delete", response, {204}, lambda _: None, "")
        if step["ok"]:
            gone = runner.call(client.document, key_a, pdf_id, owner_a)
            search_back = runner.call(client.search, key_a, fixtures[3].query)
            if gone.status == 200:
                step = _bad("delete", "resurrect", "el documento borrado sigue visible")
            elif search_back.status == 200 and _search_has(search_back, pdf_id):
                step = _bad("delete", "resurrect", "el borrado reaparece en la búsqueda")
            elif gone.status == 404:
                step = _ok("delete", "borrado con 204 y sin reaparición")
            else:
                step = _classify("delete", gone, {404}, lambda _: None, "")
        steps.append(step)
        if step["kind"] == "infra":
            return {"steps": steps, "limited": runner.limited, "aborted": True}

    try:
        hooks.restart_api()
    except (OSError, RuntimeError, TimeoutError) as exc:
        steps.append(_bad("restart", "infra", f"el reinicio falló: {exc}"))
        return {"steps": steps, "limited": runner.limited, "aborted": True}
    probe_txt = runner.call(client.document, key_a, ids_a.get("txt", ""), owner_a)
    step = _classify(
        "restart",
        probe_txt,
        {200},
        lambda answered: (
            None if answered.data.get("status") == "indexed" else "el documento no sigue indexado"
        ),
        "tras reiniciar todo sigue indexado",
    )
    steps.append(step)
    if step["kind"] == "infra":
        return {"steps": steps, "limited": runner.limited, "aborted": True}

    tenant_b_doc = ""
    other = runner.call(
        client.upload, key_b, owner_b, "copia-b.txt", fixtures[1].content, fixtures[1].mime
    )

    def _tenant_b_problem(answered: HttpResponse) -> str | None:
        """El segundo tenant debe recibir su propio identificador."""
        if not isinstance(answered.data.get("document_id"), str):
            return "el segundo tenant no trae document_id"
        return None

    step = _classify("tenants", other, {202}, _tenant_b_problem, "")
    if step["ok"]:
        tenant_b_doc = str(other.data["document_id"])
        leaks: list[str] = []
        cross = runner.call(client.search, key_b, fixtures[0].query)
        if cross.status == 200 and _search_has(cross, ids_a.get("txt", "")):
            leaks.append("el tenant B ve documentos del tenant A")
        back = runner.call(client.search, key_a, fixtures[1].query)
        if back.status == 200 and _search_has(back, tenant_b_doc):
            leaks.append("el tenant A ve documentos del tenant B")
        filtered = runner.call(client.search, key_a, fixtures[0].query, owner_b)
        if filtered.status == 200 and _search_has(filtered, ids_a.get("txt", "")):
            leaks.append("otro dueño ve documentos ajenos del mismo tenant")
        direct = runner.call(client.document, key_b, ids_a.get("txt", ""))
        if direct.status == 200:
            leaks.append("lectura cruzada por id entre tenants")
        if leaks:
            step = _bad("tenants", "leak", "; ".join(leaks))
        else:
            step = _ok("tenants", "sin fugas entre tenants ni entre dueños")
    steps.append(step)
    if step["kind"] == "infra":
        return {"steps": steps, "limited": runner.limited, "aborted": True}

    try:
        deleted = hooks.delete_tenant()
    except (OSError, RuntimeError, TimeoutError) as exc:
        steps.append(_bad("delete_tenant", "infra", f"borrar el tenant falló: {exc}"))
        return {"steps": steps, "limited": runner.limited, "aborted": True}
    if deleted != TENANT_A_REMAINING:
        steps.append(
            _bad("delete_tenant", "wrong", f"borró {deleted}, se esperaban {TENANT_A_REMAINING}")
        )
    else:
        absent = runner.call(client.search, key_b, fixtures[0].query)
        old_key = runner.call(client.document, key_a, ids_a.get("txt", ""))
        if absent.status == 200 and _search_has(absent, ids_a.get("txt", "")):
            steps.append(_bad("delete_tenant", "resurrect", "el tenant borrado reaparece"))
        elif old_key.status == 200:
            steps.append(_bad("delete_tenant", "leak", "la clave del tenant borrado sigue válida"))
        elif old_key.status == 401 and absent.status in (200, 404):
            steps.append(_ok("delete_tenant", "3 documentos borrados, clave invalidada"))
        else:
            step = _classify("delete_tenant", old_key, {401}, lambda _: None, "")
            steps.append(step)

    try:
        load = hooks.run_load(key_b)
    except (OSError, RuntimeError, TimeoutError) as exc:
        steps.append(_bad("load", "infra", f"la carga falló: {exc}"))
        return {
            "steps": steps,
            "limited": runner.limited,
            "verdicts": verdicts,
            "aborted": True,
        }
    if not isinstance(load, dict) or load.get("saw_500"):
        steps.append(_bad("load", "server500", "la carga observó un 500"))
    else:
        totals = load.get("totals") if isinstance(load.get("totals"), dict) else {}
        load_codes: Any = totals.get("codes") if isinstance(totals, dict) else {}
        steps.append(_ok("load", f"1,4,16,32 sin 500; códigos {load_codes}"))
    return {
        "steps": steps,
        "limited": runner.limited,
        "verdicts": verdicts,
        "load": load if isinstance(load, dict) else {},
        "aborted": False,
    }


def summarize(
    flow: dict[str, Any], deploy_equal: bool, elapsed_s: float
) -> tuple[str, str, dict[str, Any]]:
    """Puntúa el flujo: duro ante fugas o 500, blando ante 429/503.

    Los pasos con solo 429/503 persistentes no tumban la etapa: quedan
    contados aparte en el resumen para que se vean sin esconder nada.
    """
    steps = flow.get("steps")
    if not isinstance(steps, list) or not steps:
        return "infra_error", "flujo sin pasos registrados", {}
    hard = [step for step in steps if isinstance(step, dict) and not step.get("ok")]
    kinds = {str(step.get("kind")) for step in hard}
    if "infra" in kinds:
        reason = "; ".join(str(step.get("detail")) for step in hard if step.get("kind") == "infra")
        return "infra_error", reason, {"steps": steps}
    limited_only = kinds <= {"limited"}
    hard_hits = [step for step in hard if step.get("kind") in HARD_KINDS]
    summary: dict[str, Any] = {
        "steps": steps,
        "passed": sum(1 for step in steps if isinstance(step, dict) and step.get("ok")),
        "failed": len(hard),
        "limited_429_503": flow.get("limited", 0),
        "verdicts": flow.get("verdicts", {}),
        "deploy_equal": deploy_equal,
        "elapsed_s": round(elapsed_s, 1),
    }
    load = flow.get("load")
    if isinstance(load, dict) and load:
        totals = load.get("totals") if isinstance(load.get("totals"), dict) else {}
        summary["load"] = {
            "levels": load.get("levels"),
            "totals": totals,
            "saw_429": load.get("saw_429"),
            "saw_503": load.get("saw_503"),
            "saw_500": load.get("saw_500"),
            "isolation": load.get("isolation"),
        }
    if hard_hits:
        reason = "; ".join(f"{step.get('name')}: {step.get('detail')}" for step in hard_hits)
        return "hard_failed", reason, summary
    if not deploy_equal:
        return "hard_failed", "el despliegue cambió durante la etapa", summary
    if limited_only:
        return "passed", f"pasos solo con limitados: {len(hard)}", summary
    return "passed", f"{summary['passed']} pasos, {summary['limited_429_503']} limitados", summary


class _LiveClient:
    """Vista viva del cliente: sigue al recuadro aunque el túnel se reenlace.

    El flujo guarda esta vista una sola vez; cada llamada se resuelve contra
    el cliente vigente en ese momento, nunca contra uno ya cerrado.
    """

    def __init__(self, box: dict[str, Any]) -> None:
        self._box = box

    def __getattr__(self, name: str) -> Any:
        """Reenvía cualquier método al cliente vigente."""
        return getattr(self._box["client"], name)


class HttpxClient:
    """Cliente real sobre el túnel SSH; solo vive en el portátil."""

    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        import httpx

        self._http: Any = httpx.Client(base_url=base_url, timeout=timeout)

    def close(self) -> None:
        """Cierra las conexiones del cliente."""
        self._http.close()

    def _wrap(self, response: Any) -> HttpResponse:
        """Traduce una respuesta httpx al formato mínimo de la etapa."""
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return HttpResponse(status=response.status_code, data=data, headers=dict(response.headers))

    def ready(self) -> HttpResponse:
        """Pregunta por /ready sin clave, como hace el orquestador."""
        import httpx

        try:
            return self._wrap(self._http.get("/ready"))
        except httpx.HTTPError as exc:
            return HttpResponse(status=None, error=str(exc))

    def upload(
        self, key: str, owner: str, filename: str, content: bytes, mime: str
    ) -> HttpResponse:
        """Sube un original con su dueño."""
        import httpx

        try:
            response = self._http.post(
                "/v1/documents",
                headers={"X-API-Key": key},
                files={"file": (filename, content, mime)},
                data={"owner_id": owner},
            )
            return self._wrap(response)
        except httpx.HTTPError as exc:
            return HttpResponse(status=None, error=str(exc))

    def document(self, key: str, doc_id: str, owner: str | None = None) -> HttpResponse:
        """Lee los metadatos de un documento."""
        import httpx

        try:
            params = {"owner_id": owner} if owner is not None else None
            response = self._http.get(
                f"/v1/documents/{doc_id}", headers={"X-API-Key": key}, params=params
            )
            return self._wrap(response)
        except httpx.HTTPError as exc:
            return HttpResponse(status=None, error=str(exc))

    def delete_document(self, key: str, doc_id: str, owner: str | None = None) -> HttpResponse:
        """Borra un documento."""
        import httpx

        try:
            params = {"owner_id": owner} if owner is not None else None
            response = self._http.delete(
                f"/v1/documents/{doc_id}", headers={"X-API-Key": key}, params=params
            )
            return self._wrap(response)
        except httpx.HTTPError as exc:
            return HttpResponse(status=None, error=str(exc))

    def search(
        self,
        key: str,
        query: str,
        owner: str | None = None,
        top_k: int = 5,
        candidates: int = 30,
        rerank: bool = True,
    ) -> HttpResponse:
        """Busca dentro del espacio autorizado."""
        import httpx

        body: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "candidates": candidates,
            "rerank": rerank,
        }
        if owner is not None:
            body["owner_id"] = owner
        try:
            response = self._http.post("/v1/search", headers={"X-API-Key": key}, json=body)
            return self._wrap(response)
        except httpx.HTTPError as exc:
            return HttpResponse(status=None, error=str(exc))

    def verify(
        self, key: str, answer: str, chunk_ids: list[str], owner: str | None = None
    ) -> HttpResponse:
        """Verifica una respuesta contra sus fragmentos."""
        import httpx

        body: dict[str, Any] = {"answer": answer, "chunk_ids": chunk_ids}
        if owner is not None:
            body["owner_id"] = owner
        try:
            response = self._http.post("/v1/verify", headers={"X-API-Key": key}, json=body)
            return self._wrap(response)
        except httpx.HTTPError as exc:
            return HttpResponse(status=None, error=str(exc))


def start_service(
    host: str,
    run_id: str,
    network: str,
    pg: str,
    qdrant: str,
    db_password: str,
    hmac_secret: str,
    storage: str,
) -> str:
    """Levanta el contenedor de la API con GPU y modelos reales de solo lectura."""
    name = f"{skynet.prefix(run_id)}-api"
    skynet.remote(
        host,
        "docker",
        "run",
        "--rm",
        "-d",
        "--init",
        "--name",
        name,
        "--network",
        network,
        "--label",
        skynet.label(run_id),
        "--memory",
        "10g",
        "--gpus",
        "all",
        "-p",
        "127.0.0.1::8000",
        "-v",
        f"{MODEL_VOLUME}:/app/models:ro",
        "-v",
        f"{storage}:/app/storage",
        "-w",
        "/tmp",
        "-e",
        "HF_HUB_OFFLINE=1",
        "-e",
        "MODEL_CACHE_DIR=/app/models/huggingface",
        "-e",
        "STORAGE_DIR=/app/storage",
        "-e",
        "EMBEDDING_DEVICE=cuda",
        "-e",
        f"API_KEY_HMAC_SECRET={hmac_secret}",
        "-e",
        f"DATABASE_URL=postgresql+asyncpg://ragmur:{db_password}@{pg}:5432/ragmur_test",
        "-e",
        f"QDRANT_URL=http://{qdrant}:6333",
        "-e",
        "PYTHONPATH=/tmp/code/src:/tmp/code",
        API_IMAGE,
        "sleep",
        "28800",
        timeout=180.0,
    )
    return name


def start_admin(
    host: str,
    run_id: str,
    network: str,
    pg: str,
    qdrant: str,
    db_password: str,
    storage: str,
) -> str:
    """Levanta un contenedor de administración con el mismo almacenamiento.

    Solo sirve para borrar el tenant con la API detenida: comparte red,
    base de datos, Qdrant y volumen, y se para solo al terminar.
    """
    name = f"{skynet.prefix(run_id)}-admin"
    skynet.remote(
        host,
        "docker",
        "run",
        "--rm",
        "-d",
        "--init",
        "--name",
        name,
        "--network",
        network,
        "--label",
        skynet.label(run_id),
        "--memory",
        "2g",
        "-v",
        f"{storage}:/app/storage",
        "-w",
        "/tmp",
        "-e",
        "HF_HUB_OFFLINE=1",
        "-e",
        "STORAGE_DIR=/app/storage",
        "-e",
        "API_KEY_HMAC_SECRET=test-only-admin",
        "-e",
        f"DATABASE_URL=postgresql+asyncpg://ragmur:{db_password}@{pg}:5432/ragmur_test",
        "-e",
        f"QDRANT_URL=http://{qdrant}:6333",
        "-e",
        "PYTHONPATH=/tmp/code/src:/tmp/code",
        API_IMAGE,
        "sleep",
        "3600",
        timeout=180.0,
    )
    return name


def copy_code(host: str, api: str, log_path: Path) -> None:
    """Copia el código al contenedor (tubería local, sin shell remota).

    A diferencia del cálculo, el servicio no necesita los preparados de los
    conjuntos: solo el código que ejecuta la API.
    """
    skynet.remote(host, "docker", "exec", api, "mkdir", "-p", "/tmp/code")
    with log_path.open("ab") as handle:
        tar_proc = subprocess.Popen(
            [
                "tar",
                "-czf",
                "-",
                "src",
                "alembic.ini",
                "eval/__init__.py",
                "eval/phase1",
            ],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        try:
            ssh_proc = subprocess.Popen(
                [
                    "ssh",
                    *skynet.SSH_OPTIONS,
                    host,
                    "docker",
                    "exec",
                    "-i",
                    api,
                    "tar",
                    "--no-same-owner",
                    "--no-overwrite-dir",
                    "-xzf",
                    "-",
                    "-C",
                    "/tmp/code",
                ],
                stdin=tar_proc.stdout,
                stdout=handle,
                stderr=subprocess.STDOUT,
            )
            if tar_proc.stdout is not None:
                tar_proc.stdout.close()
            ssh_code = ssh_proc.wait(timeout=900.0)
            tar_code = tar_proc.wait(timeout=60.0)
        finally:
            for proc in (tar_proc, ssh_proc):
                if proc.poll() is None:
                    proc.kill()
        if tar_code != 0 or ssh_code != 0:
            raise skynet.SkynetError(f"copia de código fallida: tar={tar_code} ssh={ssh_code}")


def parse_deleted_count(output: str) -> int:
    """Lee el número de ``Deleted tenant with N documents``."""
    for token in output.strip().split():
        if token.isdigit():
            return int(token)
    raise ValueError(f"salida de delete-tenant ilegible: {output[:100]!r}")


def container_health(inspect_data: list[dict[str, Any]]) -> str:
    """Lee el estado de salud de un ``docker inspect``.

    Devuelve ``healthy`` solo cuando el chequeo del contenedor lo confirma;
    si no hay chequeo, devuelve si está en marcha.
    """
    if not inspect_data or not isinstance(inspect_data[0], dict):
        return "unknown"
    state = inspect_data[0].get("State")
    if not isinstance(state, dict):
        return "unknown"
    health = state.get("Health")
    if isinstance(health, dict) and isinstance(health.get("Status"), str):
        return str(health["Status"])
    if state.get("Running") is True:
        return "running"
    return "unknown"


def _inspect(host: str, api: str) -> list[dict[str, Any]]:
    """Lee el ``docker inspect`` de un contenedor como lista de objetos."""
    raw = skynet.remote(host, "docker", "inspect", api, timeout=60.0)
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def link_api(host: str, box: dict[str, Any]) -> None:
    """Abre el túnel hacia la API y renueva el cliente.

    Cierra el cliente y el túnel anteriores: tras recrear el contenedor o si
    el puerto publicado cambia, el túnel viejo apunta a la nada. Anota el PID
    en el estado para que ``cancel`` también retire este túnel.
    """
    old_client = box.get("client")
    if old_client is not None:
        with contextlib.suppress(Exception):
            old_client.close()
    old_tunnel = box.get("tunnel")
    if old_tunnel is not None:
        skynet.close_tunnel(old_tunnel)
    remote_port = skynet.remote_port(host, str(box["api"]), 8000)
    tunnel, local_port = skynet.open_tunnel(host, remote_port)
    box["tunnel"] = tunnel
    box["client"] = HttpxClient(f"http://127.0.0.1:{local_port}")
    box["base_url"] = f"http://127.0.0.1:{local_port}"
    rundir = box.get("rundir")
    if isinstance(rundir, Path) and tunnel.pid is not None:
        note_tunnel_pid(rundir, tunnel.pid)


def note_tunnel_pid(rundir: Path, pid: int) -> None:
    """Guarda el PID del túnel en un lateral que ``cancel`` también retira.

    El estado principal lo reescribe el latido cada 15 s y puede pisar una
    nota concurrente; este fichero solo lo toca la etapa y se lee al cancelar.
    """
    path = rundir / "service-tunnels.json"
    try:
        known = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = []
    if not isinstance(known, list):
        known = []
    if pid not in known:
        known.append(pid)
    with contextlib.suppress(OSError):
        path.write_text(json.dumps(known), encoding="utf-8")


def steady_ready(
    host: str, box: dict[str, Any], log: Callable[[str], None], ready_by: float
) -> None:
    """Espera a /ready reenlazando el túnel si la conexión muere.

    El puerto publicado puede cambiar a mitad de ejecución (el reenvío de
    Docker Desktop no es estable): ante fallos de conexión persistentes se
    vuelve a resolver el puerto y se abre un túnel nuevo en vez de rendirse.
    """
    while True:
        try:
            wait_ready(box["client"], min(ready_by, time.time() + 120.0), log)
            return
        except skynet.SkynetError:
            if time.time() >= ready_by:
                raise
            try:
                health = container_health(_inspect(host, str(box["api"])))
            except skynet.SkynetError:
                health = "desconocida"
            log(f"sin respuesta con salud {health}: se reenlaza el túnel")
            link_api(host, box)


def wait_ready(client: ServiceClient, deadline: float, log: Callable[[str], None]) -> None:
    """Espera a que /ready responda 200 antes del plazo."""
    while time.time() < deadline:
        response = client.ready()
        if response.status == 200:
            return
        log(f"en espera de /ready: {response.status}")
        time.sleep(POLL_EVERY_SECONDS)
    raise skynet.SkynetError("/ready no respondió 200 antes del plazo")


def run_load(
    base_url: str, key: str, directory: Path, timeout: float, log: Callable[[str], None]
) -> dict[str, Any]:
    """Pasa la carga mixta por el túnel con la clave de prueba y la resume."""
    out_path = directory / "load.json"
    env = dict(os.environ)
    env["DOCKER_HOST"] = "unix:///nonexistent"
    completed = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "benchmarks.load",
            "--profile",
            "mixed",
            "--levels",
            "1,4,16,32",
            "--base-url",
            base_url,
            "--api-key",
            key,
            "--output",
            str(out_path),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    log(f"carga: salida {completed.returncode}; {completed.stderr.strip()[-500:]}")
    if not out_path.is_file():
        raise skynet.SkynetError(f"la carga no escribió su resumen (salida {completed.returncode})")
    summary = json.loads(out_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise skynet.SkynetError("resumen de carga ilegible")
    return summary


def run_remote(
    host: str, run_id: str, directory: Path, log: Callable[[str], None], deadline: float
) -> dict[str, Any]:
    """Levanta PostgreSQL, Qdrant y la API, ejecuta el flujo y limpia siempre."""
    import secrets as secrets_mod

    from eval.phase1.nli import deploy_snapshot, wait_for_gpu

    before = deploy_snapshot(host)
    network = skynet.create_network(host, run_id)
    storage = f"{skynet.prefix(run_id)}-storage"
    skynet.remote(host, "docker", "volume", "create", "--label", skynet.label(run_id), storage)
    pg = ""
    qdrant = ""
    api = ""
    admin = ""
    password = secrets_mod.token_hex(16)
    hmac_secret = secrets_mod.token_hex(32)
    box: dict[str, Any] = {}
    try:
        wait_for_gpu(host, min(deadline, time.time() + VRAM_WAIT_SECONDS), log)
        pg = skynet.run_postgres(host, run_id, network, password)
        qdrant = skynet.run_qdrant(host, run_id, network)
        api = start_service(host, run_id, network, pg, qdrant, password, hmac_secret, storage)
        log_path = directory / "service-copy.log"
        copy_code(host, api, log_path)
        skynet.remote(
            host,
            "docker",
            "exec",
            "-w",
            "/tmp/code",
            api,
            "/app/.venv/bin/alembic",
            "upgrade",
            "head",
            timeout=600.0,
        )
        tenant_a = skynet.remote(
            host,
            "docker",
            "exec",
            "-w",
            "/tmp/code",
            api,
            "/app/.venv/bin/python",
            "-m",
            "ragmur.cli",
            "create-tenant",
            "p1-a",
            timeout=300.0,
        )
        tenant_b = skynet.remote(
            host,
            "docker",
            "exec",
            "-w",
            "/tmp/code",
            api,
            "/app/.venv/bin/python",
            "-m",
            "ragmur.cli",
            "create-tenant",
            "p1-b",
            timeout=300.0,
        )
        log(f"tenants creados: {tenant_a[:8]}… {tenant_b[:8]}…")
        key_a = skynet.remote(
            host,
            "docker",
            "exec",
            "-w",
            "/tmp/code",
            api,
            "/app/.venv/bin/python",
            "-m",
            "ragmur.cli",
            "issue-key",
            tenant_a,
            timeout=300.0,
        )
        key_b = skynet.remote(
            host,
            "docker",
            "exec",
            "-w",
            "/tmp/code",
            api,
            "/app/.venv/bin/python",
            "-m",
            "ragmur.cli",
            "issue-key",
            tenant_b,
            timeout=300.0,
        )

        def launch_uvicorn(target: str) -> None:
            """Arranca uvicorn como proceso separado dentro del contenedor.

            Escucha en 0.0.0.0 *del contenedor*: Docker reenvía el puerto
            publicado a la eth0 del contenedor, no a su loopback. Con
            127.0.0.1 solo entrarían el chequeo interno y las sondas por
            ``exec``. La exposición sigue acotada porque el puerto se
            publica solo en 127.0.0.1 del anfitrión.
            """
            skynet.remote(
                host,
                "docker",
                "exec",
                "-d",
                "-w",
                "/tmp/code",
                target,
                "/app/.venv/bin/python",
                "-m",
                "uvicorn",
                "ragmur.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
                timeout=120.0,
            )

        box["api"] = api
        box["rundir"] = directory
        launch_uvicorn(api)
        link_api(host, box)
        ready_by = min(deadline, time.time() + READY_TIMEOUT_SECONDS)
        steady_ready(host, box, log, ready_by)
        log("API lista; empieza el flujo")

        def restart_api() -> None:
            skynet.remote(host, "docker", "restart", str(box["api"]), timeout=300.0)
            launch_uvicorn(str(box["api"]))
            box["client"].close()
            box["client"] = HttpxClient(str(box["base_url"]))
            steady_ready(host, box, log, min(deadline, time.time() + READY_TIMEOUT_SECONDS))

        def delete_tenant() -> int:
            skynet.remote(host, "docker", "stop", str(box["api"]), timeout=120.0)
            helper = start_admin(host, run_id, network, pg, qdrant, password, storage)
            try:
                copy_code(host, helper, log_path)
                out = skynet.remote(
                    host,
                    "docker",
                    "exec",
                    "-w",
                    "/tmp/code",
                    helper,
                    "/app/.venv/bin/python",
                    "-m",
                    "ragmur.cli",
                    "delete-tenant",
                    tenant_a,
                    timeout=600.0,
                )
            finally:
                skynet.stop_container(host, helper)
            count = parse_deleted_count(out)
            fresh = start_service(host, run_id, network, pg, qdrant, password, hmac_secret, storage)
            box["api"] = fresh
            copy_code(host, fresh, log_path)
            launch_uvicorn(fresh)
            link_api(host, box)
            steady_ready(host, box, log, min(deadline, time.time() + READY_TIMEOUT_SECONDS))
            return count

        def run_load_hook(key: str) -> dict[str, Any]:
            remaining = max(1.0, deadline - time.time())
            return run_load(
                str(box["base_url"]), key, directory, min(remaining, LOAD_TIMEOUT_SECONDS), log
            )

        hooks = _LiveHooks(restart_api, delete_tenant, run_load_hook)
        flow = run_flow(_LiveClient(box), hooks, key_a, key_b)
        state, reason, summary = summarize(flow, True, 0.0)
        return {"flow": flow, "state": state, "reason": reason, "summary": summary}
    finally:
        client = box.get("client")
        if client is not None:
            with contextlib.suppress(Exception):
                client.close()
        old_tunnel = box.get("tunnel")
        if old_tunnel is not None:
            skynet.close_tunnel(old_tunnel)
        if admin:
            skynet.stop_container(host, admin)
        current_api = box.get("api", api)
        if current_api:
            skynet.stop_container(host, current_api)
        if qdrant:
            skynet.stop_container(host, qdrant)
        if pg:
            skynet.stop_container(host, pg)
        with contextlib.suppress(skynet.SkynetError):
            skynet.remote(host, "docker", "volume", "rm", storage, timeout=60.0)
        skynet.remove_network(host, network)
        after = deploy_snapshot(host)
        if after != before:
            raise skynet.SkynetError(
                f"el despliegue cambió: antes {sorted(before)} ahora {sorted(after)}"
            )


class _LiveHooks:
    """Adapta tres funciones al protocolo de ganchos del flujo."""

    def __init__(
        self,
        restart: Callable[[], None],
        delete: Callable[[], int],
        load: Callable[[str], dict[str, Any]],
    ) -> None:
        self._restart = restart
        self._delete = delete
        self._load = load

    def restart_api(self) -> None:
        """Reinicia el contenedor de la API."""
        self._restart()

    def delete_tenant(self) -> int:
        """Borra el primer tenant con la API detenida."""
        return self._delete()

    def run_load(self, key: str) -> dict[str, Any]:
        """Pasa la carga mixta con la clave dada."""
        return self._load(key)


def run(
    directory: Path,
    ssh_host: str | None,
    timeout: float = SERVICE_TIMEOUT_FALLBACK,
) -> dict[str, Any]:
    """Ejecuta la etapa service y escribe su log y su JSON."""
    log_path = directory / "service.log"
    json_path = directory / "service.json"

    def log(message: str) -> None:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")

    started = time.time()
    result: dict[str, Any] = {"state": "infra_error", "reason": "sin empezar"}
    try:
        if ssh_host is None:
            raise skynet.SkynetError("sin Skynet no hay servicio aislado para la etapa service")
        outcome = run_remote(ssh_host, directory.name, directory, log, time.time() + timeout)
        state = str(outcome["state"])
        reason = str(outcome["reason"])
        summary = outcome["summary"]
        assert isinstance(summary, dict)
        summary["elapsed_s"] = round(time.time() - started, 1)
        result = {
            "state": state,
            "reason": reason,
            "elapsed_s": summary["elapsed_s"],
            "summary": summary,
            "log": str(log_path),
            "json": str(json_path),
        }
    except skynet.SkynetError as exc:
        result = {
            "state": "infra_error",
            "reason": f"infraestructura: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        result = {
            "state": "infra_error",
            "reason": f"infraestructura: {exc}",
            "log": str(log_path),
            "json": str(json_path),
        }
    result.setdefault("log", str(log_path))
    result.setdefault("json", str(json_path))
    write_json(json_path, result)
    return result


__all__ = [
    "API_IMAGE",
    "HARD_KINDS",
    "INDEXED_TIMEOUT_SECONDS",
    "LOAD_TIMEOUT_SECONDS",
    "MODEL_VOLUME",
    "POLL_EVERY_SECONDS",
    "READY_TIMEOUT_SECONDS",
    "SERVICE_TIMEOUT_FALLBACK",
    "TENANT_A_REMAINING",
    "VRAM_WAIT_SECONDS",
    "Fixture",
    "FlowRunner",
    "HttpResponse",
    "HttpxClient",
    "ServiceClient",
    "ServiceHooks",
    "build_fixtures",
    "container_health",
    "copy_code",
    "link_api",
    "note_tunnel_pid",
    "parse_deleted_count",
    "run",
    "run_flow",
    "run_load",
    "run_remote",
    "start_admin",
    "start_service",
    "steady_ready",
    "summarize",
    "wait_ready",
]
