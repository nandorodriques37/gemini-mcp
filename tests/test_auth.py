from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from gemini_mcp.auth import TokenMiddleware


async def _eco(request: Request):
    return JSONResponse({"path": request.url.path})


_interno = Starlette(routes=[Route("/mcp", _eco, methods=["POST"])])


def _cliente(token="segredo"):
    return TestClient(TokenMiddleware(_interno, token))


def test_sem_token_401():
    r = _cliente().post("/mcp")
    assert r.status_code == 401
    assert r.json() == {"erro": "não autorizado"}


def test_token_errado_401():
    r = _cliente().post("/mcp", headers={"Authorization": "Bearer errado"})
    assert r.status_code == 401


def test_header_ok():
    r = _cliente().post("/mcp", headers={"Authorization": "Bearer segredo"})
    assert r.status_code == 200
    assert r.json() == {"path": "/mcp"}


def test_header_esquema_minusculo():
    r = _cliente().post("/mcp", headers={"Authorization": "bearer   segredo "})
    assert r.status_code == 200


def test_path_ok_reescreve():
    r = _cliente().post("/mcp/segredo")
    assert r.status_code == 200
    assert r.json() == {"path": "/mcp"}


def test_path_errado_401():
    r = _cliente().post("/mcp/outro")
    assert r.status_code == 401


def test_token_configurado_vazio_fecha():
    assert _cliente("").post("/mcp", headers={"Authorization": "Bearer "}).status_code == 401
    assert _cliente(None).post("/mcp", headers={"Authorization": "Bearer None"}).status_code == 401
    assert _cliente(None).post("/mcp").status_code == 401
