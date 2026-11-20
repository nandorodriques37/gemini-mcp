"""Único ponto do projeto que conversa com a API do Gemini."""

import base64
import binascii
import os
from typing import Callable

import httpx
from google import genai
from google.genai import errors, types

MODELO_PADRAO = "gemini-3.7-flash"
MAX_INLINE_BYTES = 3 * 1024 * 1024
MAX_URLS = 3
MAX_URL_BYTES = 10 * 1024 * 1024
TIMEOUT_GEMINI_MS = 55_000
TIMEOUT_DOWNLOAD_S = 20


class GeminiErro(Exception):
    """Erro com mensagem pronta para mostrar ao usuário."""


def _cliente() -> genai.Client:
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    if not chave:
        raise GeminiErro("configuração ausente: GEMINI_API_KEY")
    return genai.Client(api_key=chave, http_options=types.HttpOptions(timeout=TIMEOUT_GEMINI_MS))


def baixar_url(url: str) -> tuple[bytes, str]:
    """Baixa a URL com limite de tamanho. Devolve (bytes, mime)."""
    with httpx.stream("GET", url, follow_redirects=True, timeout=TIMEOUT_DOWNLOAD_S) as r:
        r.raise_for_status()
        dados = bytearray()
        for bloco in r.iter_bytes():
            dados.extend(bloco)
            if len(dados) > MAX_URL_BYTES:
                raise GeminiErro(f"arquivo em {url} passa de 10 MB")
        mime = r.headers.get("content-type", "application/octet-stream").split(";")[0].strip()
    return bytes(dados), mime


def montar_partes(
    arquivos: list[dict] | None,
    urls: list[str] | None,
    baixar: Callable[[str], tuple[bytes, str]] = baixar_url,
) -> list[types.Part]:
    partes: list[types.Part] = []
    total = 0
    for arq in arquivos or []:
        nome = arq.get("nome", "sem nome")
        try:
            dados = base64.b64decode(arq.get("base64", ""), validate=True)
        except (binascii.Error, ValueError):
            raise GeminiErro(f"arquivo {nome} não é base64 válido") from None
        total += len(dados)
        if total > MAX_INLINE_BYTES:
            raise GeminiErro("arquivos somam mais de 3 MB: use uma URL pública")
        partes.append(types.Part.from_bytes(data=dados, mime_type=arq.get("mime", "application/octet-stream")))

    urls = urls or []
    if len(urls) > MAX_URLS:
        raise GeminiErro(f"no máximo {MAX_URLS} URLs por chamada")
    for url in urls:
        try:
            dados, mime = baixar(url)
        except GeminiErro:
            raise
        except httpx.HTTPError as e:
            raise GeminiErro(f"não consegui baixar {url}: {type(e).__name__}") from None
        partes.append(types.Part.from_bytes(data=dados, mime_type=mime))
    return partes


def _sem_segredo(texto: str) -> str:
    chave = os.environ.get("GEMINI_API_KEY", "").strip()
    return texto.replace(chave, "***") if chave else texto


def gerar(prompt: str, instrucoes: str | None = None, modelo: str | None = None, partes: list | None = None) -> str:
    nome_modelo = modelo or os.environ.get("GEMINI_MODEL", "").strip() or MODELO_PADRAO
    config = types.GenerateContentConfig(system_instruction=instrucoes) if instrucoes else types.GenerateContentConfig()
    try:
        resposta = _cliente().models.generate_content(
            model=nome_modelo, contents=[*(partes or []), prompt], config=config
        )
    except errors.APIError as e:
        raise GeminiErro(_sem_segredo(f"erro do Gemini ({e.code}): {e.message}")) from None
    except httpx.TimeoutException:
        raise GeminiErro("o Gemini demorou demais: use um modelo Flash ou um prompt menor") from None

    if not resposta.text:
        motivo = "desconhecido"
        if getattr(resposta, "candidates", None):
            motivo = str(resposta.candidates[0].finish_reason)
        raise GeminiErro(f"o Gemini não retornou texto (motivo: {motivo})")
    return resposta.text


def listar_modelos() -> list[str]:
    try:
        modelos = _cliente().models.list()
    except errors.APIError as e:
        raise GeminiErro(_sem_segredo(f"erro do Gemini ({e.code}): {e.message}")) from None
    return [
        m.name.removeprefix("models/")
        for m in modelos
        if "generateContent" in (m.supported_actions or [])
    ]
