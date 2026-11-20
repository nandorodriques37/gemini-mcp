"""Entrada da Vercel."""

import os

from gemini_mcp.auth import TokenMiddleware
from gemini_mcp.server import mcp

app = TokenMiddleware(
    mcp.http_app(path="/mcp", stateless_http=True, json_response=True),
    os.environ.get("MCP_TOKEN"),
)
