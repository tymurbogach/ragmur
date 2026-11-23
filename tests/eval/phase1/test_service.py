"""Etapa service C05: flujo y clasificación con un doble de la API.

Todo corre sin red ni GPU: el falso implementa el contrato HTTP en memoria y
los ganchos sustituyen el reinicio, el borrado del tenant y la carga. La etapa
real sobre Skynet usa el mismo ``run_flow`` con el cliente de verdad.
"""

import hashlib
import io
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from eval.phase1 import service, skynet, stages

_MARKERS = {hashlib.sha256(fix.content).hexdigest(): fix.marker for fix in service.build_fixtures()}


def _hit(marker: str, query: str) -> bool:
    """Una palabra larga del marcador basta para dar con el documento."""
    words = [word for word in marker.replace("-", " ").split() if len(word) > 3]
    lowered = query.lower()
    return any(word in lowered for word in words)


class FakeClient:
    """Doble en memoria del contrato HTTP con fallos inyectables."""

    def __init__(self) -> None:
        self.keys = {"key-a": "tenant-a", "key-b": "tenant-b"}
        self.docs: dict[str, dict[str, Any]] = {}
        self.counter = 0
        self.fail_500: dict[str, int] = {}
        self.flaky_limited: dict[str, int] = {}
        self.always_limited: set[str] = set()
        self.leak_search = False
        self.resurrect = False
        self.restarted = False

    def _guard(self, method: str, key: str) -> service.HttpResponse | None:
        """Aplica 500, limitado o 401 antes de la lógica del método."""
        if self.fail_500.get(method, 0) > 0:
            self.fail_500[method] -= 1
            return service.HttpResponse(status=500, data={})
        if method in self.always_limited:
            return service.HttpResponse(status=429, data={})
        if self.flaky_limited.get(method, 0) > 0:
            self.flaky_limited[method] -= 1
            return service.HttpResponse(status=503, data={})
        if key not in self.keys:
            return service.HttpResponse(status=401, data={})
        return None

    def ready(self) -> service.HttpResponse:
        """El servicio falso siempre está listo."""
        return service.HttpResponse(status=200, data={"status": "ok"})

    def upload(
        self, key: str, owner: str, filename: str, content: bytes, mime: str
    ) -> service.HttpResponse:
        """Acepta con 202 o devuelve el duplicado con 200."""
        denied = self._guard("upload", key)
        if denied is not None:
            return denied
        tenant = self.keys[key]
        digest = hashlib.sha256(content).hexdigest()
        for doc_id, doc in self.docs.items():
            if doc["tenant"] == tenant and doc["owner"] == owner and doc["sha"] == digest:
                return service.HttpResponse(
                    status=200,
                    data={"document_id": doc_id, "status": "indexed", "duplicate": True},
                )
        self.counter += 1
        doc_id = f"doc-{tenant}-{self.counter}"
        self.docs[doc_id] = {
            "tenant": tenant,
            "owner": owner,
            "filename": filename,
            "status": "indexed",
            "sha": digest,
            "marker": _MARKERS.get(digest, ""),
            "deleted": False,
        }
        return service.HttpResponse(status=202, data={"document_id": doc_id, "status": "pending"})

    def document(self, key: str, doc_id: str, owner: str | None = None) -> service.HttpResponse:
        """Devuelve metadatos o 404 si no está en el espacio autorizado."""
        denied = self._guard("document", key)
        if denied is not None:
            return denied
        doc = self.docs.get(doc_id)
        if doc is None or doc["tenant"] != self.keys[key]:
            return service.HttpResponse(status=404, data={})
        if owner is not None and doc["owner"] != owner:
            return service.HttpResponse(status=404, data={})
        if doc["deleted"] and not self.resurrect:
            return service.HttpResponse(status=404, data={})
        return service.HttpResponse(
            status=200, data={"document_id": doc_id, "status": doc["status"]}
        )

    def delete_document(
        self, key: str, doc_id: str, owner: str | None = None
    ) -> service.HttpResponse:
        """Borra del espacio autorizado; con resurrección lo conserva marcado."""
        denied = self._guard("delete_document", key)
        if denied is not None:
            return denied
        doc = self.docs.get(doc_id)
        if doc is None or doc["tenant"] != self.keys[key]:
            return service.HttpResponse(status=404, data={})
        if owner is not None and doc["owner"] != owner:
            return service.HttpResponse(status=404, data={})
        if self.resurrect:
            doc["deleted"] = True
        else:
            del self.docs[doc_id]
        return service.HttpResponse(status=204, data={})

    def search(
        self,
        key: str,
        query: str,
        owner: str | None = None,
        top_k: int = 5,
        candidates: int = 30,
        rerank: bool = True,
    ) -> service.HttpResponse:
        """Busca por marcador dentro del espacio autorizado."""
        denied = self._guard("search", key)
        if denied is not None:
            return denied
        tenant = self.keys[key]
        results = []
        for doc_id, doc in self.docs.items():
            if doc["deleted"] and not self.resurrect:
                continue
            if not self.leak_search:
                if doc["tenant"] != tenant:
                    continue
                if owner is not None and doc["owner"] != owner:
                    continue
            hit = _hit(str(doc.get("marker", "")), query)
            if hit or self.leak_search:
                results.append({"document_id": doc_id, "chunk_id": f"{doc_id}-c1", "text": "texto"})
        return service.HttpResponse(status=200, data={"results": results[:top_k]})

    def verify(
        self, key: str, answer: str, chunk_ids: list[str], owner: str | None = None
    ) -> service.HttpResponse:
        """Puntúa cada frase como respaldada."""
        denied = self._guard("verify", key)
        if denied is not None:
            return denied
        claims = [
            {"text": part.strip(), "verdict": "supported", "score": 0.9}
            for part in answer.split(".")
            if part.strip()
        ]
        return service.HttpResponse(
            status=200,
            data={
                "claims": claims,
                "summary": {"supported": len(claims)},
            },
        )


class FakeHooks:
    """Ganchos de mentira: reinicio, borrado de tenant y carga enlatada."""

    def __init__(self, client: FakeClient) -> None:
        self.client = client
        self.restarts = 0
        self.load_key = ""

    def restart_api(self) -> None:
        """El reinicio falso no pierde nada."""
        self.restarts += 1
        self.client.restarted = True

    def delete_tenant(self) -> int:
        """Borra los documentos del tenant A e invalida su clave."""
        removed = sum(1 for doc in self.client.docs.values() if doc["tenant"] == "tenant-a")
        self.client.docs = {
            doc_id: doc for doc_id, doc in self.client.docs.items() if doc["tenant"] != "tenant-a"
        }
        self.client.keys.pop("key-a", None)
        return removed

    def run_load(self, key: str) -> dict[str, Any]:
        """Devuelve una carga limpia con los cuatro niveles."""
        self.load_key = key
        return {
            "levels": [{"concurrency": n} for n in (1, 4, 16, 32)],
            "totals": {"codes": {"200": 100}},
            "saw_429": False,
            "saw_503": False,
            "saw_500": False,
            "isolation": {"ok": True},
        }


def _run(client: FakeClient, hooks: FakeHooks) -> dict[str, Any]:
    """Ejecuta el flujo contra el falso con un plazo corto de indexado."""
    return service.run_flow(client, hooks, "key-a", "key-b", indexed_timeout=5.0)


def test_ficheros_validos_y_marcadores_unicos() -> None:
    """Los cuatro formatos se abren con sus lectores y cada marcador es único."""
    fixtures = service.build_fixtures()
    assert [fix.name for fix in fixtures] == ["txt", "md", "docx", "pdf"]
    assert len({fix.marker for fix in fixtures}) == 4
    assert fixtures[0].content.startswith(b"El faro")
    assert fixtures[3].content.startswith(b"%PDF-")
    assert fixtures[2].content.startswith(b"PK\x03\x04")
    import docx

    document = docx.Document(io.BytesIO(fixtures[2].content))
    texto = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert fixtures[2].marker in texto
    import pypdfium2 as pdfium  # type: ignore[import-untyped]

    page = pdfium.PdfDocument(io.BytesIO(fixtures[3].content))[0]
    assert fixtures[3].marker in page.get_textpage().get_text_range()


def test_flujo_completo_en_verde() -> None:
    """El camino feliz pasa los diez pasos sin limitados."""
    client = FakeClient()
    flow = _run(client, FakeHooks(client))
    assert flow["aborted"] is False
    assert [step["name"] for step in flow["steps"]] == [
        "upload",
        "indexed",
        "search",
        "verify",
        "dedup",
        "delete",
        "restart",
        "tenants",
        "delete_tenant",
        "load",
    ]
    assert all(step["ok"] for step in flow["steps"])
    assert flow["limited"] == 0
    estado, _, resumen = service.summarize(flow, True, 1.0)
    assert estado == "passed"
    assert resumen["passed"] == 10 and resumen["deploy_equal"] is True


def test_500_es_duro_y_completa() -> None:
    """Un 500 queda registrado como duro sin impedir los pasos siguientes."""
    client = FakeClient()
    client.fail_500["search"] = 4
    flow = _run(client, FakeHooks(client))
    search = next(step for step in flow["steps"] if step["name"] == "search")
    assert search["kind"] == "server500"
    assert flow["aborted"] is False
    assert flow["steps"][-1]["name"] == "load"
    assert flow["steps"][-1]["ok"] is True
    estado, motivo, _ = service.summarize(flow, True, 1.0)
    assert estado == "hard_failed" and "search" in motivo


def test_fuga_entre_tenants_es_dura() -> None:
    """Ver documentos ajenos es fuga aunque el resto salga bien."""
    client = FakeClient()
    client.leak_search = True
    flow = _run(client, FakeHooks(client))
    tenants = next(step for step in flow["steps"] if step["name"] == "tenants")
    assert tenants["kind"] == "leak"
    assert service.summarize(flow, True, 1.0)[0] == "hard_failed"


def test_dato_borrado_que_reaparece_es_duro() -> None:
    """El borrado que sigue visible es resurrección, no un 404 tardío."""
    client = FakeClient()
    client.resurrect = True
    flow = _run(client, FakeHooks(client))
    delete = next(step for step in flow["steps"] if step["name"] == "delete")
    assert delete["kind"] == "resurrect"
    assert service.summarize(flow, True, 1.0)[0] == "hard_failed"


def test_limitados_se_cuentan_aparte(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dos 503 reintentados no tumban; un 429 persistente se publica aparte."""
    monkeypatch.setattr("time.sleep", lambda _segundos: None)
    client = FakeClient()
    client.flaky_limited["search"] = 2
    client.always_limited.add("verify")
    flow = _run(client, FakeHooks(client))
    assert flow["limited"] >= 3
    verify = next(step for step in flow["steps"] if step["name"] == "verify")
    assert verify["kind"] == "limited"
    estado, motivo, resumen = service.summarize(flow, True, 1.0)
    assert estado == "passed"
    assert resumen["limited_429_503"] == flow["limited"]
    assert "limitados" in motivo


def test_clave_borrada_sigue_valida_es_fuga() -> None:
    """Si la clave vieja sigue entrando tras borrar el tenant, es fuga."""
    client = FakeClient()

    class _Hooks(FakeHooks):
        def delete_tenant(self) -> int:
            return 3

    flow = _run(client, _Hooks(client))
    delete_tenant = next(step for step in flow["steps"] if step["name"] == "delete_tenant")
    assert delete_tenant["kind"] == "leak"
    assert service.summarize(flow, True, 1.0)[0] == "hard_failed"


def test_sin_skynet_es_infra(tmp_path: Path) -> None:
    """Sin host no hay servicio aislado: infra, sin red."""
    resultado = stages.run_service(tmp_path, None, timeout=10.0)
    assert resultado["state"] == "infra_error"
    assert (tmp_path / "service.json").is_file()


def test_etapa_sin_llm_ni_cargadores() -> None:
    """La etapa no importa LLM ni cargadores de conjuntos."""
    source = (Path(__file__).resolve().parents[3] / "eval" / "phase1" / "service.py").read_text(
        encoding="utf-8"
    )
    for marker in (
        "eval.inferes",
        "eval.reader",
        "load_dataset",
        "snapshot_download",
        "litellm",
        "openai",
    ):
        assert marker not in source, f"service.py menciona {marker}"


def test_interfaz_service_explica_su_plazo() -> None:
    """La etapa documenta su plazo largo de servicio en el valor por defecto."""
    assert stages.SERVICE_TIMEOUT_FALLBACK == 10800.0


def test_salud_del_contenedor() -> None:
    """Solo ``healthy`` confirma que la API atiende; el resto no basta."""
    healthy = [{"State": {"Running": True, "Health": {"Status": "healthy"}}}]
    assert service.container_health(healthy) == "healthy"
    starting = [{"State": {"Running": True, "Health": {"Status": "starting"}}}]
    assert service.container_health(starting) == "starting"
    assert service.container_health([{"State": {"Running": True}}]) == "running"
    assert service.container_health([]) == "unknown"
    assert service.container_health([{}]) == "unknown"


def test_listo_renlaza_si_el_tunel_muere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tras fallos de conexión persistentes reabre el túnel y sigue."""
    real_enlaces = 0
    intentos = 0

    def _falso_ready(cliente: Any, plazo: float, bitacora: Any) -> None:
        nonlocal intentos
        intentos += 1
        if intentos == 1:
            raise skynet.SkynetError("cortado")
        return None

    def _falso_enlace(host: str, caja_enlace: dict[str, Any]) -> None:
        nonlocal real_enlaces
        real_enlaces += 1

    monkeypatch.setattr(service, "wait_ready", _falso_ready)
    monkeypatch.setattr(service, "link_api", _falso_enlace)
    monkeypatch.setattr(service, "_inspect", lambda host, api: [{"State": {"Running": True}}])
    caja: dict[str, Any] = {"api": "api", "client": Mock()}
    service.steady_ready("h", caja, lambda _: None, 9999999999.0)
    assert real_enlaces == 1
    assert intentos == 2


def test_listo_agota_el_plazo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin tiempo no hay reintento: la infraestructura queda registrada."""

    def _siempre_cortado(cliente: Any, plazo: float, bitacora: Any) -> None:
        raise skynet.SkynetError("cortado")

    monkeypatch.setattr(service, "wait_ready", _siempre_cortado)
    monkeypatch.setattr(service, "link_api", lambda host, caja_enlace: None)
    caja: dict[str, Any] = {"api": "api", "client": Mock()}
    with pytest.raises(skynet.SkynetError, match="cortado"):
        service.steady_ready("h", caja, lambda _: None, 0.0)


def test_espera_lista_ok_y_agotada() -> None:
    """Un 200 vuelve enseguida; sin plazo no se intenta ni una lectura."""
    cliente = FakeClient()
    service.wait_ready(cliente, 9999999999.0, lambda _: None)
    with pytest.raises(skynet.SkynetError, match="/ready"):
        service.wait_ready(cliente, 0.0, lambda _: None)


def test_enlace_anota_el_tunel_para_cancel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El PID del túnel queda en el lateral para que ``cancel`` lo retire."""
    from eval.phase1.runner import read_sidecar_tunnels

    monkeypatch.setattr(skynet, "remote_port", Mock(return_value=60000))
    monkeypatch.setattr(skynet, "open_tunnel", Mock(return_value=(Mock(pid=424242), 12345)))
    monkeypatch.setattr(skynet, "close_tunnel", Mock())
    caja: dict[str, Any] = {"api": "api", "rundir": tmp_path}
    service.link_api("h", caja)
    assert read_sidecar_tunnels(tmp_path) == [424242]
    caja["client"].close()


def test_enlace_renueva_tunel_y_cliente(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tras recrear, el túnel viejo se cierra y el cliente apunta al nuevo."""
    viejo_tunel = Mock()
    viejo_cliente = Mock()
    caja: dict[str, Any] = {
        "api": "api-nueva",
        "tunnel": viejo_tunel,
        "client": viejo_cliente,
        "base_url": "http://127.0.0.1:1",
    }
    monkeypatch.setattr(skynet, "remote_port", Mock(return_value=60000))
    monkeypatch.setattr(skynet, "open_tunnel", Mock(return_value=(Mock(), 12345)))
    monkeypatch.setattr(skynet, "close_tunnel", Mock())
    service.link_api("h", caja)
    viejo_cliente.close.assert_called_once_with()
    assert skynet.close_tunnel.call_count == 1  # type: ignore[attr-defined]
    assert caja["base_url"] == "http://127.0.0.1:12345"
    assert isinstance(caja["client"], service.HttpxClient)
    caja["client"].close()


def test_despliegue_cambiado_es_duro() -> None:
    """Tocar el despliegue durante la etapa es fallo duro aunque todo mida bien."""
    client = FakeClient()
    flow = _run(client, FakeHooks(client))
    estado, motivo, _ = service.summarize(flow, False, 1.0)
    assert estado == "hard_failed" and "despliegue" in motivo


def test_flujo_sin_pasos_es_infra() -> None:
    """Un resumen vacío no puede dar verde."""
    assert service.summarize({}, True, 1.0)[0] == "infra_error"


def test_parse_deleted_count() -> None:
    """El número de documentos borrados se lee de la salida del CLI."""
    assert service.parse_deleted_count("Deleted tenant with 3 documents\n") == 3
    with pytest.raises(ValueError, match="ilegible"):
        service.parse_deleted_count("Tenant not found")


def test_run_load_exige_resumen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """La carga sin fichero de resumen es error de infraestructura."""

    def _falso_run(*args: Any, **kwargs: Any) -> Any:
        acabado = Mock()
        acabado.returncode = 0
        acabado.stderr = ""
        return acabado

    monkeypatch.setattr(subprocess, "run", _falso_run)
    with pytest.raises(skynet.SkynetError, match="no escribió su resumen"):
        service.run_load("http://127.0.0.1:9", "clave", tmp_path, 10.0, lambda _: None)


def test_run_load_devuelve_el_resumen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """El resumen JSON de la carga llega intacto a la etapa."""

    def _falso_run(*args: Any, **kwargs: Any) -> Any:
        (tmp_path / "load.json").write_text(
            json.dumps({"saw_500": False, "totals": {"codes": {"200": 1}}}), encoding="utf-8"
        )
        acabado = Mock()
        acabado.returncode = 0
        acabado.stderr = ""
        return acabado

    monkeypatch.setattr(subprocess, "run", _falso_run)
    resumen = service.run_load("http://127.0.0.1:9", "clave", tmp_path, 10.0, lambda _: None)
    assert resumen["totals"] == {"codes": {"200": 1}}


def test_carga_con_500_es_dura() -> None:
    """Si la carga ve un 500, el paso de carga es duro."""

    class _Hooks(FakeHooks):
        def run_load(self, key: str) -> dict[str, Any]:
            return {"saw_500": True, "totals": {"codes": {"500": 1}}}

    client = FakeClient()
    flow = _run(client, _Hooks(client))
    load = next(step for step in flow["steps"] if step["name"] == "load")
    assert load["kind"] == "server500"
    assert service.summarize(flow, True, 1.0)[0] == "hard_failed"


def test_cancel_retira_tuneles_del_lateral(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``cancel`` mata también los PIDs que la etapa anotó fuera del estado."""
    import eval.phase1.runner as runner_mod

    monkeypatch.setattr(runner_mod, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(runner_mod, "LOCK_FILE", tmp_path / ".lock")
    monkeypatch.setattr(skynet, "cleanup_run", Mock(return_value={}))
    monkeypatch.setattr(
        skynet, "list_resources", Mock(return_value={"containers": [], "networks": []})
    )
    vistos: list[list[int]] = []

    def _anota(pids: list[int]) -> list[int]:
        """Registra los PIDs que se matarían sin tocar a nadie real."""
        vistos.append(list(pids))
        return []

    monkeypatch.setattr(runner_mod, "_kill_pids", _anota)
    estado = runner_mod.initial_status("cancela2", ["service"], "abc", [], "skynet-ts")
    estado["pid"] = 2**30
    runner_mod.write_status(estado)
    runner_mod.write_lock("cancela2", 2**30)
    (tmp_path / "cancela2").mkdir(exist_ok=True)
    (tmp_path / "cancela2" / "service-tunnels.json").write_text("[112233]", encoding="utf-8")
    runner_mod.cancel_run("cancela2")
    assert any(112233 in llamada for llamada in vistos)


def test_lateral_ilegible_da_lista_vacia(tmp_path: Path) -> None:
    """Sin fichero o con basura no se mata a nadie por error."""
    from eval.phase1.runner import read_sidecar_tunnels

    assert read_sidecar_tunnels(tmp_path / "inexistente") == []
    (tmp_path / "service-tunnels.json").write_text("basura", encoding="utf-8")
    assert read_sidecar_tunnels(tmp_path) == []


def test_cliente_vivo_sigue_al_reenlace() -> None:
    """La vista del flujo usa el cliente vigente aunque cambie el túnel."""
    primero = FakeClient()
    segundo = FakeClient()
    caja: dict[str, Any] = {"client": primero}
    vista = service._LiveClient(caja)
    assert vista.ready().status == 200
    caja["client"] = segundo
    assert vista.ready().status == 200
