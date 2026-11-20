# Gemini MCP

Servidor MCP que deixa o Claude consultar o Google Gemini como ferramenta.
Publicado na Vercel e protegido por token.

Ferramentas:
- `perguntar_gemini(prompt, instrucoes?, modelo?, arquivos?, urls?)`
- `listar_modelos()`

## 1. Chave do Gemini
1. Acesse https://aistudio.google.com e crie uma API key.
2. **Antes de enviar dado da empresa, ative o faturamento.** No plano gratuito, o Google pode usar o conteúdo para melhorar os produtos dele.

## 2. Token do conector
Gere um segredo aleatório:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 3. Publicar na Vercel
1. Vercel → Add New → Project → importe o repositório `gemini-mcp`.
2. Em Settings → Environment Variables, cadastre:

| Variável | Valor |
|---|---|
| `GEMINI_API_KEY` | chave do passo 1 |
| `MCP_TOKEN` | segredo do passo 2 |
| `GEMINI_MODEL` | opcional; padrão `gemini-3.7-flash` |

3. Deploy. Sem `MCP_TOKEN`, o servidor recusa todas as chamadas.

## 4. Adicionar no Claude (web ou desktop)
Configurações → Conectores → Adicionar conector personalizado.

- **Preferido:** URL `https://<seu-app>.vercel.app/mcp` e, na autenticação, cabeçalho `Authorization` com `Bearer <MCP_TOKEN>`.
- **Plano B** (se não houver campo de cabeçalho): URL `https://<seu-app>.vercel.app/mcp/<MCP_TOKEN>` com "sem login".
  O token passa a aparecer no caminho, inclusive nos logs da Vercel. Troque-o se suspeitar de vazamento.

## 5. Testar
No chat: "liste os modelos do Gemini" e depois "pergunte ao Gemini …".
Se o modelo padrão não existir, ajuste `GEMINI_MODEL` com um nome da lista.

## Limites
- Arquivos em base64: até 3 MB somados (consomem tokens do Claude).
- URLs: até 3, com até 10 MB cada.
- Cada chamada tem até 60 s: até 12 s de downloads e até 45 s de Gemini. Para respostas longas, prefira um modelo Flash.

## Desenvolvimento

```bash
pip install -r requirements.txt pytest
pytest -q
```
