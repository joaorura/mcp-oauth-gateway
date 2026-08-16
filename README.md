# mcp-oauth-gateway

Um gateway OAuth (Google) genérico para colocar na frente de **qualquer**
servidor MCP e expô-lo com segurança a clientes remotos (Claude, ChatGPT,
Cursor em modo HTTP, etc.), sem depender do MCP em si ter algum conceito de
autenticação.

Nasceu de um caso concreto: expor um servidor MCP local (um vault do
Obsidian) para o Claude Cowork, que só enxerga MCPs via HTTP autenticado —
não stdio local. O gateway resultante não tem nada de Obsidian nele; tudo que
é específico do seu MCP vive em variáveis de ambiente.

## Por que isso existe

MCP não tem autenticação embutida. Se o seu servidor MCP roda localmente
(stdio, ou HTTP sem auth em `127.0.0.1`), ele é perfeitamente seguro — só
processos na sua própria máquina alcançam. No momento em que você precisa que
um cliente **remoto** (fora da sua máquina) o alcance, você precisa de duas
coisas que o MCP não te dá de graça: uma forma de **provar quem está do outro
lado**, e uma forma de **decidir quem tem permissão**.

Este gateway resolve as duas: autenticação via Google OAuth (delegando a
verificação de identidade para um provedor que você já confia) e uma
allowlist de e-mails (a decisão de permissão, que o OAuth sozinho não faz —
ele autentica qualquer conta Google, não restringe nada por si só).

## Arquitetura

```
Cliente MCP remoto (Claude, etc.)
        │  HTTPS
        ▼
   URL pública (Tailscale Funnel / Cloudflare Tunnel / seu domínio)
        │
        ▼
┌─────────────────────────────────────────┐
│              mcp-oauth-gateway            │
│                                           │
│  1. GoogleProvider — exige login Google   │
│  2. AllowlistMiddleware — barra quem não  │
│     está em ALLOWED_EMAILS                │
│  3. audit.py — registra quem fez o quê    │
└───────────────────┬───────────────────────┘
                     │ backend.py: http ou stdio,
                     │ com ou sem bearer
                     ▼
            O SEU servidor MCP
       (Obsidian, GitHub, um MCP seu, ...)
```

O gateway nunca sabe o que o backend faz. Ele só sabe: como falar com ele
(`BACKEND_TRANSPORT`), e quem tem permissão de falar através dele
(`ALLOWED_EMAILS`).

## Por que a allowlist é o perímetro de verdade

Este ponto é fácil de subestimar: **o `GoogleProvider` sozinho autentica
qualquer conta Google.** Ele não sabe nada sobre o seu caso de uso — só
confirma "esta pessoa realmente controla este e-mail". Sem a
`AllowlistMiddleware`, qualquer pessoa com um Gmail e a URL do seu gateway
teria acesso ao que estiver atrás dele.

A allowlist falha **fechada** por padrão: se `ALLOWED_EMAILS` estiver ausente
ou vazia, ninguém passa — não é "todo mundo passa por engano". Veja
`src/allowlist.py` e seus testes para os casos extremos que ela cobre
(claims malformados, tipos incorretos, tentativa de forjar identidade via
`upstream_claims` aninhado).

**Antes de colocar isso em produção, rode o teste negativo:** troque
temporariamente `ALLOWED_EMAILS` para um e-mail que não existe, reinicie o
gateway, confirme que uma conta que deveria ter acesso é **barrada**, e só
então reverta. Ver ter o caminho positivo funcionar não prova que o caminho
de negação existe de verdade — só o teste negativo prova isso.

## Instalação

Requer Python 3.12+.

```bash
git clone <url-do-seu-fork> mcp-oauth-gateway
cd mcp-oauth-gateway
python -m venv .venv

# Windows
.venv\Scripts\pip install -e .
.venv\Scripts\pip install pytest   # se for rodar os testes

# Linux/macOS
.venv/bin/pip install -e .
.venv/bin/pip install pytest
```

```bash
cp .env.example .env   # Windows: Copy-Item .env.example .env
```

Preencha o `.env` — as seções abaixo explicam cada bloco.

## Configurando o backend

`BACKEND_TRANSPORT` escolhe como o gateway fala com o seu MCP. É a única
variável que determina o comportamento — nenhum código muda.

### `http`, sem autenticação

Para um backend local que só confia em estar em `127.0.0.1`:

```env
BACKEND_TRANSPORT=http
BACKEND_URL=http://127.0.0.1:3000/mcp
BACKEND_BEARER_TOKEN=
```

### `http`, com bearer token

Para um backend que exige um token fixo:

```env
BACKEND_TRANSPORT=http
BACKEND_URL=http://127.0.0.1:3000/mcp
BACKEND_BEARER_TOKEN=o-token-que-o-backend-espera
```

### `stdio`

Para um MCP que só fala stdio (a maioria dos servidores "de linha de
comando" — `npx algum-pacote-mcp`, `python -m algum_modulo`, etc.). O gateway
spawna o processo e fala com ele diretamente; não há HTTP nem bearer neste
modo:

```env
BACKEND_TRANSPORT=stdio
BACKEND_COMMAND=npx
BACKEND_ARGS=-y algum-pacote-mcp serve --vault "C:\caminho com espaco"
```

`BACKEND_ARGS` é interpretado como uma linha de shell (`shlex.split`), então
aspas para caminhos com espaço funcionam como você espera.

### Subindo o backend junto com o gateway (opcional)

Se o seu backend HTTP precisa ser iniciado por algum comando (em vez de já
estar rodando, ou de ser stdio, que o próprio gateway spawna), defina
`BACKEND_START_COMMAND` / `BACKEND_START_ARGS` e o script
`scripts/start-gateway.ps1` sobe os dois processos na ordem certa, com
health-check entre eles. Deixe ambos vazios se isso não se aplica ao seu
caso.

## Criando o OAuth Client no Google

1. [Google Cloud Console](https://console.cloud.google.com/projectcreate) →
   crie um projeto novo.
2. **APIs e serviços → Tela de consentimento OAuth**: tipo *Externo*, nome do
   app, e-mail de suporte.
3. **Dados de acesso / Scopes**: adicione exatamente dois escopos, ambos
   **não sensíveis** (não exigem verificação do Google):
   - `openid`
   - `https://www.googleapis.com/auth/userinfo.email`
4. **Público / Test users**: adicione o(s) e-mail(is) que vão usar o gateway
   como usuários de teste. Isso cria uma **segunda barreira**, independente
   da allowlist do código: em modo *Testing*, o próprio Google recusa
   qualquer conta fora dessa lista, antes mesmo do seu código rodar.
   Contrapartida: em *Testing*, refresh tokens expiram em 7 dias — o cliente
   MCP vai pedir reautenticação semanalmente. Publicar o app remove essa
   expiração (os escopos são não sensíveis, então a publicação é imediata,
   sem revisão do Google), ao custo de deixar a allowlist como única
   barreira.
5. **Credenciais → Criar credenciais → ID do cliente OAuth**, tipo *Aplicativo
   da Web*. Em **URIs de redirecionamento autorizados**, adicione:

   ```
   <PUBLIC_BASE_URL>/auth/callback
   ```

   Exatamente essa URL, sem barra final extra. Uma divergência de um
   caractere aqui quebra o login inteiro com `redirect_uri_mismatch`.

6. Copie o **Client ID** e o **Client Secret** para `GOOGLE_CLIENT_ID` e
   `GOOGLE_CLIENT_SECRET` no `.env`.

## Expondo o gateway publicamente

Clientes MCP remotos (Claude, etc.) precisam alcançar seu gateway por HTTPS.
Duas opções testadas:

**Tailscale Funnel** (usado no desenvolvimento deste projeto):
```bash
tailscale funnel --bg <GATEWAY_PORT>
```
Dá uma URL fixa (`https://sua-maquina.seu-tailnet.ts.net`), gratuita, sem
precisar de domínio próprio. Pode exigir habilitar o recurso Funnel uma vez
no painel do seu tailnet.

**Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:<GATEWAY_PORT>`
para um túnel rápido com URL aleatória, ou um túnel nomeado (exige domínio
próprio na Cloudflare) para URL estável.

Qualquer uma dessas — ou seu próprio domínio com reverse proxy — funciona.
`PUBLIC_BASE_URL` no `.env` é a URL resultante, e é ela que precisa bater com
o redirect URI configurado no Google.

## Rodando

```bash
# Windows
.venv\Scripts\python.exe -m src.gateway

# Linux/macOS
.venv/bin/python -m src.gateway
```

O gateway sobe em `GATEWAY_HOST:GATEWAY_PORT` (padrão `127.0.0.1:8000`).
Verifique com:

```bash
curl -i https://<PUBLIC_BASE_URL>/mcp
# esperado: 401 com header WWW-Authenticate — prova que o servidor está de
# pé e a camada de auth está ativa.

curl https://<PUBLIC_BASE_URL>/.well-known/oauth-authorization-server
# esperado: JSON com registration_endpoint, authorization_endpoint, token_endpoint
```

Depois, adicione como *custom connector* no cliente MCP que for usar (no
Claude: claude.ai → Settings → Connectors → Add custom connector → cole a URL
`<PUBLIC_BASE_URL>/mcp`, deixe os campos de OAuth Client vazios — o gateway
suporta registro dinâmico de cliente).

## Autostart no Windows

```powershell
pwsh -File scripts\install-scheduled-task.ps1
```

Registra uma Tarefa Agendada que sobe o gateway (e o backend, se
`BACKEND_START_COMMAND` estiver configurado) a cada logon.

**O reinício diário é opcional.** Um bearer fixo no `.env`, sem reinício
programado nenhum, é um uso totalmente válido e é o caminho mais simples —
nada aqui exige rotação. O gatilho diário
(`$DailyRestartTime` em `scripts\install-scheduled-task.ps1`) só existe como
mecanismo *opcional* de rotação — ver a seção seguinte. Para desativá-lo,
edite o script e defina `$DailyRestartTime = $null` antes de rodar a
instalação.

**Linux/macOS:** não há script de autostart pronto neste repositório — os
scripts em `scripts/` são PowerShell (Task Scheduler). Um serviço `systemd`
chamando `python -m src.gateway` com `WorkingDirectory` e `EnvironmentFile`
apontando para o `.env` cobre o mesmo caso de uso, mas isso não foi testado
como parte deste projeto; contribuições são bem-vindas.

## Rotacionando credenciais (avançado, opcional)

`BACKEND_BEARER_TOKEN` no `.env` é lido uma vez, como qualquer outra
variável — um valor fixo funciona para sempre, sem necessidade de reinício.

Se o seu backend suportar gerar um token novo a cada execução (ex.: um
comando `gen-token` como o de alguns servidores MCP) e você quiser que o
bearer interno tenha um TTL efetivo em vez de validade indefinida, o truque é
este: **uma variável de ambiente já presente no processo antes do gateway
subir tem prioridade sobre o `.env`** (`python-dotenv` usa `override=False`
por padrão — o `.env` nunca sobrescreve o que já existe no ambiente). Ou
seja, um script de boot pode gerar um token novo e exportá-lo via
`$env:BACKEND_BEARER_TOKEN` (PowerShell) ou `export BACKEND_BEARER_TOKEN=...`
(shell) *antes* de chamar `python -m src.gateway`, sem precisar editar o
`.env` nem o código do gateway. Combine isso com o gatilho diário do Task
Scheduler para um TTL de até 24h.

Este repositório **não** implementa a geração do token em si — isso é
específico de cada backend. O que ele garante é que, se você tiver essa
peça, plugá-la não exige tocar em nenhum código deste projeto.

## Adaptando para o seu MCP

Na prática, adaptar este gateway a um MCP diferente é preencher o `.env` —
nenhum arquivo Python precisa mudar. Se quiser que uma IA faça isso por você
(ler seu MCP e preencher a configuração certa), veja
[`LLM_PROMPT.md`](LLM_PROMPT.md).

Se o seu caso não cabe nas duas opções de transporte (`http` / `stdio`),
`src/backend.py` é o único arquivo que precisaria de uma terceira opção —
ele é deliberadamente pequeno e sem nenhuma lógica de negócio misturada.

## Testes

```bash
.venv\Scripts\pytest.exe -v      # Windows
.venv/bin/pytest -v              # Linux/macOS
```

Cobrem: a lógica da allowlist (incluindo os casos de segurança — claims
malformados, tentativa de escalada via claims aninhados), a construção dos
dois transportes de backend (incluindo os casos de erro), o log de auditoria
(rotação, idempotência), e o detalhe do header HTTP descrito no
Troubleshooting abaixo.

## Troubleshooting

**Connector conecta (OAuth completa) mas nenhuma ferramenta aparece /
"McpServerError".** A causa mais provável, e a que motivou o teste
`test_sobrescreve_o_header_de_entrada_em_vez_de_duplicar` em
`tests/test_upstream.py`: o FastMCP monta os headers do upstream unindo o
header de entrada (a credencial que o *cliente* apresentou ao gateway) com o
header configurado para o backend. Se as chaves não forem literalmente
idênticas — `Authorization` capitalizado é uma chave diferente de
`authorization` minúsculo para um `dict` Python — **as duas sobrevivem**, e
a credencial do cliente vaza para o backend, que a rejeita. Este projeto já
usa a chave minúscula (`src/upstream.py`); se você editar esse arquivo,
mantenha a chave em minúsculas.

**`redirect_uri_mismatch` no login do Google.** O redirect URI cadastrado no
Google Cloud Console precisa ser exatamente `PUBLIC_BASE_URL + /auth/callback`,
sem barra extra, protocolo e host idênticos.

**Conector nunca completa o handshake, fica alternando 400/200.** Verifique
se o gateway está rodando com `stateless_http=True` (já é o padrão em
`src/gateway.py`). Em modo stateful, alguns clientes disputam a negociação de
`Mcp-Session-Id` com o proxy.

## Limitações conhecidas

- **Sem supervisão real de processo.** O script de autostart do Windows
  confirma que o gateway subiu com sucesso, mas nada o reinicia se ele cair
  horas depois — só no próximo logon ou gatilho diário. Para supervisão de
  verdade, rode via um serviço dedicado (NSSM, systemd, etc.).
- **Um segredo compartilhado é tudo-ou-nada.** `BACKEND_BEARER_TOKEN` não tem
  escopo por chamador — quem o possui tem o mesmo acesso que o gateway tem
  ao backend.
- **A allowlist é uma lista simples.** Não há papéis, nem permissões por
  ferramenta — é "está na lista" ou "não está". Se o seu backend expõe
  operações de escrita, todo mundo na allowlist as tem.

## Licença

MIT — ver [`LICENSE`](LICENSE).
