"""Middleware ASGI que exige o token do conector antes de chegar ao MCP."""

import hmac
import json

_RECUSA = json.dumps({"erro": "não autorizado"}, ensure_ascii=False).encode("utf-8")


class TokenMiddleware:
    """Aceita `Authorization: Bearer <token>` ou o caminho `<mcp_path>/<token>`.

    Sem token configurado, recusa tudo (falha fechada).
    """

    def __init__(self, app, token: str | None, mcp_path: str = "/mcp"):
        self.app = app
        self.token = (token or "").strip()
        self.mcp_path = mcp_path.rstrip("/")

    def _confere(self, candidato: str) -> bool:
        if not self.token or not candidato:
            return False
        return hmac.compare_digest(candidato.encode("utf-8"), self.token.encode("utf-8"))

    def _token_do_cabecalho(self, scope) -> str:
        for nome, valor in scope.get("headers", []):
            if nome == b"authorization":
                partes = valor.decode("latin-1").strip().split(None, 1)
                if len(partes) == 2 and partes[0].lower() == "bearer":
                    return partes[1].strip()
        return ""

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self._confere(self._token_do_cabecalho(scope)):
            await self.app(scope, receive, send)
            return

        prefixo = self.mcp_path + "/"
        caminho = scope.get("path", "")
        if caminho.startswith(prefixo):
            candidato = caminho[len(prefixo):].strip("/")
            if self._confere(candidato):
                novo = dict(scope)
                novo["path"] = self.mcp_path
                novo["raw_path"] = self.mcp_path.encode("ascii")
                await self.app(novo, receive, send)
                return

        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(_RECUSA)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": _RECUSA})
