import base64
from types import SimpleNamespace

import httpx
import pytest
from google.genai import errors

from gemini_mcp import gemini
from gemini_mcp.gemini import GeminiErro, gerar, listar_modelos, montar_partes

CHAVE = "chave-secreta-xyz"


class ClienteFalso:
    def __init__(self, resposta=None, erro=None, modelos=()):
        self.chamadas = []
        self._resposta = resposta
        self._erro = erro
        self._modelos = modelos
        self.models = self

    def generate_content(self, **kw):
        self.chamadas.append(kw)
        if self._erro:
            raise self._erro
        return self._resposta

    def list(self):
        return list(self._modelos)


def _resposta(texto="ok", motivo="STOP"):
    return SimpleNamespace(text=texto, candidates=[SimpleNamespace(finish_reason=motivo)])


@pytest.fixture
def falso(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", CHAVE)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    cliente = ClienteFalso(resposta=_resposta())
    monkeypatch.setattr(gemini, "_cliente", lambda: cliente)
    return cliente


def _b64(n):
    return base64.b64encode(b"x" * n).decode()


def test_partes_base64_ok():
    partes = montar_partes([{"nome": "a.png", "mime": "image/png", "base64": _b64(10)}], None)
    assert len(partes) == 1
    assert partes[0].inline_data.mime_type == "image/png"


def test_base64_invalido():
    with pytest.raises(GeminiErro, match="não é base64 válido"):
        montar_partes([{"nome": "a.png", "mime": "image/png", "base64": "@@@"}], None)


def test_base64_acima_3mb():
    grande = [{"nome": "a.bin", "mime": "application/pdf", "base64": _b64(3 * 1024 * 1024 + 1)}]
    with pytest.raises(GeminiErro, match="use uma URL"):
        montar_partes(grande, None)


def test_mais_de_3_urls():
    with pytest.raises(GeminiErro):
        montar_partes(None, ["https://a/1", "https://a/2", "https://a/3", "https://a/4"], baixar=lambda u, p: (b"x", "text/plain"))


def test_url_falha():
    def baixar(url, prazo):
        raise httpx.HTTPError("404")

    with pytest.raises(GeminiErro, match="https://exemplo.com/x.pdf"):
        montar_partes(None, ["https://exemplo.com/x.pdf"], baixar=baixar)


def test_url_ok_vira_parte():
    partes = montar_partes(None, ["https://a/doc.pdf"], baixar=lambda u, p: (b"%PDF", "application/pdf"))
    assert partes[0].inline_data.mime_type == "application/pdf"


def test_gerar_usa_modelo_padrao(falso, monkeypatch):
    gerar("oi")
    assert falso.chamadas[-1]["model"] == "gemini-3.7-flash"
    monkeypatch.setenv("GEMINI_MODEL", "x")
    gerar("oi")
    assert falso.chamadas[-1]["model"] == "x"
    gerar("oi", modelo="y")
    assert falso.chamadas[-1]["model"] == "y"


def test_gerar_instrucoes_vao_no_config(falso):
    assert gerar("oi", instrucoes="seja breve") == "ok"
    assert falso.chamadas[-1]["config"].system_instruction == "seja breve"


def test_gerar_sem_texto(falso):
    falso._resposta = _resposta(texto=None, motivo="SAFETY")
    with pytest.raises(GeminiErro, match="não retornou texto") as e:
        gerar("oi")
    assert "SAFETY" in str(e.value)


def test_gerar_erro_api_sem_chave(falso):
    falso._erro = errors.APIError(429, {"error": {"message": f"cota excedida key={CHAVE}", "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(GeminiErro) as e:
        gerar("oi")
    assert CHAVE not in str(e.value)
    assert "cota" in str(e.value)


def test_gerar_timeout(falso):
    falso._erro = httpx.TimeoutException("lento")
    with pytest.raises(GeminiErro, match="Flash"):
        gerar("oi")


def test_sem_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(GeminiErro, match="configuração ausente: GEMINI_API_KEY"):
        gemini._cliente()


def test_listar_modelos_filtra(falso):
    falso._modelos = [
        SimpleNamespace(name="models/gemini-a", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/embed-b", supported_actions=["embedContent"]),
    ]
    assert listar_modelos() == ["gemini-a"]


def test_gerar_timeout_httpx2(falso):
    import httpx2
    falso._erro = httpx2.ReadTimeout("lento")
    with pytest.raises(GeminiErro, match="Flash"):
        gerar("oi")


def test_gerar_falha_conexao_httpx2(falso):
    import httpx2
    falso._erro = httpx2.ConnectError("sem rede")
    with pytest.raises(GeminiErro, match="não consegui falar com o Gemini"):
        gerar("oi")


def test_orcamento_cabe_em_60s():
    assert gemini.TIMEOUT_GEMINI_MS / 1000 + gemini.DOWNLOAD_TOTAL_S < 60


def test_downloads_compartilham_prazo():
    import time
    prazos = []

    def baixar(url, prazo):
        prazos.append(prazo)
        return b"x", "text/plain"

    antes = time.monotonic()
    montar_partes(None, ["https://a/1", "https://a/2"], baixar=baixar)
    assert len(set(prazos)) == 1
    assert prazos[0] - antes <= gemini.DOWNLOAD_TOTAL_S + 0.1


def test_baixar_url_corta_no_prazo():
    import time
    transporte = httpx.MockTransport(lambda req: httpx.Response(200, content=b"abc"))
    with httpx.Client(transport=transporte) as c:
        with pytest.raises(GeminiErro, match="https://lento/x"):
            gemini.baixar_url("https://lento/x", prazo=time.monotonic() - 1, cliente=c)
