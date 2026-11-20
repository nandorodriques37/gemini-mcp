import asyncio
import importlib

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from starlette.testclient import TestClient

from gemini_mcp import server
from gemini_mcp.gemini import GeminiErro


def _chamar(nome, args=None):
    async def _run():
        async with Client(server.mcp) as c:
            return await c.call_tool(nome, args or {})
    return asyncio.run(_run())


def test_lista_ferramentas():
    async def _run():
        async with Client(server.mcp) as c:
            return {t.name for t in await c.list_tools()}
    assert asyncio.run(_run()) == {"perguntar_gemini", "listar_modelos"}


def test_perguntar_repassa(monkeypatch):
    recebido = {}

    def gerar(prompt, instrucoes=None, modelo=None, partes=None):
        recebido.update(prompt=prompt, partes=partes)
        return "oi"

    monkeypatch.setattr(server, "gerar", gerar)
    r = _chamar("perguntar_gemini", {"prompt": "x"})
    assert r.content[0].text == "oi"
    assert recebido == {"prompt": "x", "partes": []}


def test_erro_vira_tool_error(monkeypatch):
    def gerar(*a, **k):
        raise GeminiErro("cota")

    monkeypatch.setattr(server, "gerar", gerar)
    with pytest.raises(ToolError, match="cota"):
        _chamar("perguntar_gemini", {"prompt": "x"})


_INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "teste", "version": "0"}},
}
_HDR = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def test_app_http_com_token(monkeypatch):
    monkeypatch.setenv("MCP_TOKEN", "segredo")
    import api.index as entrada
    importlib.reload(entrada)
    with TestClient(entrada.app, base_url="https://gemini-mcp.vercel.app") as c:
        ok = c.post("/mcp", json=_INIT, headers={**_HDR, "Authorization": "Bearer segredo"})
        assert ok.status_code == 200, ok.text
        assert ok.json()["result"]["serverInfo"]["name"] == "Gemini"
        assert c.post("/mcp", json=_INIT, headers=_HDR).status_code == 401
        assert c.post("/mcp/segredo", json=_INIT, headers=_HDR).status_code == 200
