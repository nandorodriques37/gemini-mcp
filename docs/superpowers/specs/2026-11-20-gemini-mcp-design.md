# Gemini MCP — spec de design

Data: 20/11/2026 · Dono: João Fernando Rodrigues · Status: aguardando revisão

## Objetivo
Permitir que o Claude consulte o Gemini como ferramenta, a partir de um conector
personalizado (remote MCP). Uso pessoal do João.

## Critério de aceite
1. O conector é adicionado no Claude e aparece com as ferramentas `perguntar_gemini` e `listar_modelos`.
2. "Pergunte ao Gemini X" devolve a resposta do Gemini no chat.
3. Uma chamada sem token ou com token errado recebe HTTP 401 e não chega ao Gemini.
4. Uma imagem pequena (até ~3 MB) enviada pelo Claude é analisada pelo Gemini.

## Escopo
Dentro: texto, imagens e PDFs pequenos (base64), arquivos por URL pública, escolha de modelo.
Fora (v1): geração de imagem, streaming, histórico de conversa no servidor, OAuth, multiusuário.

## Arquitetura
Claude (nuvem Anthropic) → `POST https://<app>.vercel.app/mcp`
com `Authorization: Bearer <MCP_TOKEN>` → função Python na Vercel (FastMCP,
transporte Streamable HTTP, stateless, resposta JSON) → SDK `google-genai` → Gemini API.

Plano B de autenticação, se a tela do Claude não oferecer campo de cabeçalho:
token no caminho, `https://<app>.vercel.app/mcp/<MCP_TOKEN>`. O servidor aceita os dois.

## Componentes
| Arquivo | Responsabilidade |
|---|---|
| `api/index.py` | Entrada da Vercel: monta o app ASGI e aplica o middleware de token |
| `gemini_mcp/server.py` | Define o FastMCP e as ferramentas |
| `gemini_mcp/gemini.py` | Encapsula a chamada ao Gemini (único ponto que usa o SDK) |
| `gemini_mcp/auth.py` | Middleware: valida o token (cabeçalho ou caminho), comparação em tempo constante |
| `tests/` | Testes com o Gemini simulado |
| `vercel.json`, `requirements.txt`, `README.md` | Deploy, dependências, passo a passo |

## Ferramentas
`perguntar_gemini(prompt: str, instrucoes: str | None, modelo: str | None,
arquivos: list[{nome, mime, base64}] | None, urls: list[str] | None) -> str`
- `modelo` vazio usa `GEMINI_MODEL`.
- `urls`: o servidor baixa e envia ao Gemini (máx. 3 URLs, 10 MB cada).
- Soma de `arquivos` acima de 3 MB → erro claro pedindo URL.

`listar_modelos() -> list[str]` — modelos disponíveis na chave que suportam geração de conteúdo.

## Configuração (variáveis de ambiente na Vercel)
- `GEMINI_API_KEY` — chave do Google AI Studio. Cadastrada pelo João, nunca no código nem no chat.
- `MCP_TOKEN` — segredo aleatório de 32+ caracteres.
- `GEMINI_MODEL` — padrão `gemini-3.7-flash`; confirmar com `listar_modelos` após o deploy.

## Erros
| Situação | Resposta |
|---|---|
| Sem token ou token errado | HTTP 401, sem chamar o Gemini |
| Variável de ambiente ausente | Erro de ferramenta: "configuração ausente: <nome>" |
| Cota ou limite do Gemini | Erro de ferramenta com a mensagem do Google, sem a chave |
| Timeout | Erro de ferramenta sugerindo modelo Flash ou prompt menor |
| Arquivo grande | Erro de ferramenta pedindo URL |

## Testes
- Unitários: middleware (sem token, token certo no cabeçalho, token certo no caminho, token errado);
  montagem do pedido ao Gemini com texto, arquivo e URL; limites de tamanho.
- Integração local: cliente MCP chamando `tools/list` e `perguntar_gemini` com o Gemini simulado.
- Pós-deploy: `tools/list` com e sem token contra a URL real.

## Premissas e riscos
- Plano gratuito do Gemini pode usar o conteúdo para melhorar produtos do Google: ativar faturamento antes de enviar dado da Pague Menos.
- Plano gratuito da Vercel limita corpo da requisição (~4,5 MB) e duração da função: começar com Flash.
- Base64 consome tokens do Claude: usar só para arquivo pequeno.
- Repositório privado `nandorodriques37/gemini-mcp`, ligado à conta pessoal da Vercel.
