"""Servidor MCP: ferramentas que o Claude enxerga."""

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from gemini_mcp import gemini
from gemini_mcp.gemini import GeminiErro, gerar, montar_partes

mcp = FastMCP("Gemini")


class Arquivo(BaseModel):
    nome: str
    mime: Annotated[str, Field(description="Tipo MIME, ex.: image/png, application/pdf")]
    base64: Annotated[str, Field(description="Conteúdo do arquivo em base64")]


@mcp.tool
def perguntar_gemini(
    prompt: Annotated[str, Field(description="Pergunta ou tarefa para o Gemini")],
    instrucoes: Annotated[str | None, Field(description="Instruções de sistema opcionais")] = None,
    modelo: Annotated[str | None, Field(description="Modelo; vazio usa o padrão do servidor")] = None,
    arquivos: Annotated[list[Arquivo] | None, Field(description="Arquivos pequenos em base64, até 3 MB somados")] = None,
    urls: Annotated[list[str] | None, Field(description="Até 3 URLs públicas de arquivos, até 10 MB cada")] = None,
) -> str:
    """Envia uma pergunta ao Google Gemini e devolve a resposta em texto.

    Use para uma segunda opinião ou para analisar imagens e PDFs.
    Arquivo pequeno: mande em `arquivos` (base64). Arquivo grande: mande o link público em `urls`.
    """
    try:
        partes = montar_partes([a.model_dump() for a in arquivos or []], urls)
        return gerar(prompt, instrucoes=instrucoes, modelo=modelo, partes=partes)
    except GeminiErro as e:
        raise ToolError(str(e)) from None


@mcp.tool
def listar_modelos() -> list[str]:
    """Lista os modelos do Gemini disponíveis para a chave configurada."""
    try:
        return gemini.listar_modelos()
    except GeminiErro as e:
        raise ToolError(str(e)) from None
