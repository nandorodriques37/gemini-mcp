"""Entrada da Vercel.

O app HTTP do FastMCP exige o lifespan ASGI para iniciar o gerenciador de sessões,
e a Vercel não garante enviar lifespan a um app ASGI genérico. Por isso cada
requisição monta um app novo e roda o lifespan dele em volta da chamada.
Com stateless_http=True não há estado a perder entre requisições.
"""

import os

from gemini_mcp.auth import TokenMiddleware
from gemini_mcp.server import mcp


def _novo_app():
    return mcp.http_app(path="/mcp", stateless_http=True, json_response=True)


async def _mcp_por_requisicao(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
    app = _novo_app()
    async with app.router.lifespan_context(app):
        await app(scope, receive, send)


app = TokenMiddleware(_mcp_por_requisicao, os.environ.get("MCP_TOKEN"))
