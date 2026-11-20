# Gemini MCP — Plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: superpowers:subagent-driven-development (recomendada) ou superpowers:executing-plans. Passos com checkbox (`- [ ]`).

**Objetivo:** servidor MCP remoto que deixa o Claude consultar o Gemini, protegido por token, publicado na Vercel.

**Arquitetura:** app ASGI do FastMCP (Streamable HTTP, stateless, JSON) envolvido por um middleware de token. Toda chamada ao Google passa por `gemini_mcp/gemini.py`. A Vercel serve `api/index.py`.

**Stack:** Python 3.12, `fastmcp`, `google-genai`, `httpx`, `pytest`, Vercel Python runtime.

**Spec:** `docs/superpowers/specs/2026-11-20-gemini-mcp-design.md`

## Restrições globais
- Segredos só em variáveis de ambiente: `GEMINI_API_KEY`, `MCP_TOKEN`, `GEMINI_MODEL`.
- Modelo padrão quando `GEMINI_MODEL` vazio: `gemini-3.7-flash`.
- Limite de arquivos base64 somados: 3 MB (3 * 1024 * 1024 bytes decodificados).
- URLs: no máximo 3, cada uma até 10 MB.
- Rota MCP: `/mcp` (cabeçalho) e `/mcp/<MCP_TOKEN>` (plano B).
- Mensagens de erro em PT-BR. Nunca incluir a chave ou o token em mensagem ou log.
- Timeout da chamada ao Gemini: 55 s; `maxDuration` da função: 60 s.
- Testes nunca chamam a internet: Gemini e downloads sempre simulados.

## Foco de revisão
1. `MCP_TOKEN` ausente ou vazio → o servidor recusa tudo com 401 (falha fechada), nunca aceita token vazio. → Tarefa 1.
2. Esquema do cabeçalho em minúsculas (`bearer x`) ou com espaços extras → aceito. → Tarefa 1.
3. base64 inválido → erro claro "arquivo <nome> não é base64 válido", não erro 500. → Tarefa 2.
4. URL com 404, timeout ou tamanho acima do limite → erro claro citando a URL. → Tarefa 2.
5. Gemini sem texto na resposta (bloqueio de segurança) → mensagem "o Gemini não retornou texto (motivo: …)", não string vazia. → Tarefa 2.

---

## Lote 1 — núcleo testável

### Task 1: Projeto e middleware de token

**Arquivos:**
- Criar: `requirements.txt`, `pyproject.toml` (só config do pytest: `pythonpath = ["."]`), `gemini_mcp/__init__.py`, `gemini_mcp/auth.py`, `.gitignore`
- Teste: `tests/test_auth.py`

**Interfaces:**
- Produz: `class TokenMiddleware(app: ASGIApp, token: str | None, mcp_path: str = "/mcp")` — ASGI. Repassa escopos `lifespan` sem checar. Em `http`: aceita `Authorization: Bearer <token>` (esquema sem diferenciar maiúsculas, `strip()`) ou caminho `/mcp/<token>` reescrito para `/mcp` (também `raw_path`). Compara com `hmac.compare_digest`. Recusa com 401 e JSON `{"erro": "não autorizado"}`.

- [ ] **Passo 1: testes que falham** (app interno de eco que devolve o `path` recebido; `starlette.testclient.TestClient`)
  - `test_sem_token_401`: POST `/mcp` sem cabeçalho → 401.
  - `test_token_errado_401`: `Bearer errado` → 401.
  - `test_header_ok`: `Bearer segredo` → 200, path `/mcp`.
  - `test_header_esquema_minusculo`: `bearer   segredo ` → 200.
  - `test_path_ok_reescreve`: POST `/mcp/segredo` → 200, path recebido `/mcp`.
  - `test_path_errado_401`: `/mcp/outro` → 401.
  - `test_token_configurado_vazio_fecha`: middleware com `token=""` e `Bearer ` → 401; com `token=None` → 401.
- [ ] **Passo 2:** `pytest tests/test_auth.py -v` → FALHA (módulo inexistente).
- [ ] **Passo 3:** implementar `TokenMiddleware` em `gemini_mcp/auth.py`.
- [ ] **Passo 4:** `pytest tests/test_auth.py -v` → 7 PASS.
- [ ] **Passo 5:** `git commit -m "feat: middleware de token"`

### Task 2: Cliente Gemini

**Arquivos:**
- Criar: `gemini_mcp/gemini.py`
- Teste: `tests/test_gemini.py`

**Interfaces:**
- Produz:
  - `class GeminiErro(Exception)` — mensagem já pronta para o usuário.
  - `montar_partes(arquivos: list[dict] | None, urls: list[str] | None, baixar: Callable[[str], tuple[bytes, str]] = baixar_url) -> list[types.Part]` — `arquivos` = `{"nome", "mime", "base64"}`; usa `types.Part.from_bytes`.
  - `baixar_url(url: str) -> tuple[bytes, str]` — `httpx`, timeout 20 s, segue redirect, interrompe ao passar de 10 MB; devolve bytes e o mime do `content-type` (sem parâmetros).
  - `gerar(prompt: str, instrucoes: str | None = None, modelo: str | None = None, partes: list | None = None) -> str`
  - `listar_modelos() -> list[str]` — nomes sem o prefixo `models/`, só os que suportam `generateContent`.
  - `_cliente() -> genai.Client` — lê `GEMINI_API_KEY`; ausente → `GeminiErro("configuração ausente: GEMINI_API_KEY")`; `http_options=types.HttpOptions(timeout=55_000)`. Os testes trocam `_cliente` via `monkeypatch`.

- [ ] **Passo 1: testes que falham** (cliente falso com `models.generate_content` e `models.list`)
  - `test_partes_base64_ok`: um PNG de 10 bytes → 1 parte com `mime_type == "image/png"`.
  - `test_base64_invalido`: `"@@@"` → `GeminiErro` contendo "não é base64 válido".
  - `test_base64_acima_3mb`: soma decodificada de 3 MB + 1 byte → `GeminiErro` contendo "use uma URL".
  - `test_mais_de_3_urls`: 4 URLs → `GeminiErro`.
  - `test_url_falha`: `baixar` falso que lança `httpx.HTTPError` → `GeminiErro` contendo a URL.
  - `test_gerar_usa_modelo_padrao`: sem `modelo` e sem `GEMINI_MODEL` → chamada com `model="gemini-3.7-flash"`; com `GEMINI_MODEL=x` → `"x"`; argumento `modelo` vence os dois.
  - `test_gerar_instrucoes_vao_no_config`: `instrucoes="seja breve"` → `config.system_instruction == "seja breve"`.
  - `test_gerar_sem_texto`: resposta com `text=None` e motivo `SAFETY` → `GeminiErro` contendo "não retornou texto" e "SAFETY".
  - `test_gerar_erro_api_sem_chave`: cliente lança `errors.APIError` → `GeminiErro` cuja mensagem não contém o valor de `GEMINI_API_KEY`.
  - `test_gerar_timeout`: cliente lança `httpx.TimeoutException` → `GeminiErro` contendo "Flash".
  - `test_sem_api_key`: env vazio → `GeminiErro("configuração ausente: GEMINI_API_KEY")`.
  - `test_listar_modelos_filtra`: dois modelos, um sem `generateContent` → só o outro, sem `models/`.
- [ ] **Passo 2:** `pytest tests/test_gemini.py -v` → FALHA.
- [ ] **Passo 3:** implementar `gemini_mcp/gemini.py`. Timeout (`httpx.TimeoutException` ou erro de deadline) → `GeminiErro` sugerindo modelo Flash ou prompt menor.
- [ ] **Passo 4:** `pytest tests/test_gemini.py -v` → 12 PASS.
- [ ] **Passo 5:** `git commit -m "feat: cliente Gemini com limites e erros"`

## Lote 2 — servidor MCP e entrada da Vercel

### Task 3: Ferramentas MCP e app da Vercel

**Arquivos:**
- Criar: `gemini_mcp/server.py`, `api/index.py`, `vercel.json`, `README.md`
- Teste: `tests/test_server.py`

**Interfaces:**
- Consome: `gerar`, `montar_partes`, `listar_modelos`, `GeminiErro` (Tarefa 2); `TokenMiddleware` (Tarefa 1).
- Produz:
  - `gemini_mcp/server.py`: `mcp = FastMCP("Gemini")` com as ferramentas `perguntar_gemini(prompt: str, instrucoes: str | None = None, modelo: str | None = None, arquivos: list[Arquivo] | None = None, urls: list[str] | None = None) -> str` e `listar_modelos() -> list[str]`. `Arquivo` = Pydantic `{nome: str, mime: str, base64: str}`. `GeminiErro` → `fastmcp.exceptions.ToolError` com a mesma mensagem. Docstrings em PT-BR explicam ao Claude quando usar base64 e quando usar URL.
  - `api/index.py`: `app = TokenMiddleware(mcp.http_app(path="/mcp", stateless_http=True, json_response=True), os.environ.get("MCP_TOKEN"))`.
  - `vercel.json`: rewrite de `/(.*)` para `/api/index`; `functions."api/index.py".maxDuration = 60`.

- [ ] **Passo 1: testes que falham**
  - `test_lista_ferramentas`: `fastmcp.Client(mcp)` em memória → nomes `{"perguntar_gemini", "listar_modelos"}`.
  - `test_perguntar_repassa`: `gerar` simulado devolve "oi" → `call_tool("perguntar_gemini", {"prompt": "x"})` devolve "oi".
  - `test_erro_vira_tool_error`: `gerar` lança `GeminiErro("cota")` → chamada falha com "cota".
  - `test_app_http_com_token`: `TestClient(app)` com `MCP_TOKEN=segredo`, POST `/mcp` JSON-RPC `initialize` com `Bearer segredo` e `Accept: application/json, text/event-stream` → 200; sem token → 401. (Importar `api.index` depois de definir o env.)
- [ ] **Passo 2:** `pytest tests/test_server.py -v` → FALHA.
- [ ] **Passo 3:** implementar `server.py`, `api/index.py`, `vercel.json`. Testes em memória usam `asyncio.run`, sem pytest-asyncio.
- [ ] **Passo 4:** `pytest -v` → todos PASS (23).
- [ ] **Passo 5:** README: variáveis, como gerar o token (`python -c "import secrets; print(secrets.token_urlsafe(32))"`), como adicionar o conector (cabeçalho primeiro, URL com token como plano B, alertando que o caminho pode aparecer nos logs da Vercel), alerta de faturamento no Google.
- [ ] **Passo 6:** `git commit -m "feat: servidor MCP e entrada Vercel"`

## Lote 3 — publicação (com o João)

### Task 4: Deploy e teste real

- [ ] **Passo 1:** João cria o projeto na Vercel a partir do repositório `gemini-mcp` e cadastra `GEMINI_API_KEY`, `MCP_TOKEN` e `GEMINI_MODEL`.
- [ ] **Passo 2:** teste pós-deploy: `initialize` sem token → 401; com token → 200; `tools/list` → 2 ferramentas.
- [ ] **Passo 3:** João adiciona o conector no Claude (web ou desktop) com o cabeçalho; se não houver campo, usa a URL com token.
- [ ] **Passo 4:** no chat: `listar_modelos` → confirmar ou trocar `GEMINI_MODEL`; uma pergunta de texto; uma imagem pequena. Critérios 1 a 4 da spec atendidos.
