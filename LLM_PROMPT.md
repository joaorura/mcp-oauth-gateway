# Prompt para adaptar este gateway a um novo MCP

Copie o bloco abaixo, preencha os campos entre `< >` com os detalhes do seu
caso, e cole numa conversa com um assistente de IA (Claude Code, Cursor,
etc.) com acesso ao terminal e ao repositório clonado. O prompt foi escrito
para produzir um `.env` completo e correto, sem que o assistente precise
editar nenhum código Python.

---

```
Você está configurando o mcp-oauth-gateway (leia o README.md deste
repositório inteiro antes de agir) para proteger o seguinte servidor MCP:

- Nome/descrição do meu MCP: <ex: "um servidor que le minha agenda do Google Calendar">
- Como ele roda hoje: <escolha um>
  (a) Já tenho um comando/URL HTTP que eu uso para falar com ele: <cole o comando ou URL>
  (b) Só sei rodar via linha de comando (stdio): <cole o comando exato, ex: "npx -y meu-pacote-mcp --flag valor">
  (c) Ainda não decidi / preciso que você descubra a partir do código dele: <cole o caminho ou repositório>
- Esse MCP exige autenticação própria (um token, uma API key)? <sim/não — se sim, qual variável ou header ele espera>
- Máquina onde isso vai rodar: <Windows / Linux / macOS>
- E-mail(is) Google que devem ter acesso: <lista>
- Já tenho uma forma de expor isso publicamente (Tailscale, Cloudflare, domínio próprio)? <sim, qual / não, me ajude a escolher>

Sua tarefa:
1. Determine se BACKEND_TRANSPORT deve ser "http" ou "stdio" com base no que
   descrevi. Se eu descrevi um comando de linha (npx, python -m, um binário),
   é stdio. Se eu tenho uma URL que já aceita POST com corpo JSON-RPC, é http.
2. Preencha um .env completo a partir de .env.example — NÃO invente valores
   que dependem de mim (Client ID/Secret do Google, a URL pública) e NÃO
   prossiga com eles vazios sem antes ME PERGUNTAR. Tudo o resto, preencha.
3. Se eu escolhi stdio (BACKEND_COMMAND/BACKEND_ARGS), teste a ponte ANTES
   de mexer em qualquer configuração de OAuth: escreva um script Python
   descartável que importa `build_backend_transport()` de src/backend.py,
   abre um `fastmcp.Client` contra ele, e chama `list_tools()`. Me mostre
   quantas ferramentas apareceram e os primeiros nomes. Isso prova que a
   ponte funciona antes de gastarmos tempo configurando o Google.
4. Se eu não tenho ainda uma forma de expor isso publicamente, me pergunte
   se quero usar Tailscale Funnel ou Cloudflare Tunnel (ambos documentados no
   README) e me guie pelos comandos — NÃO instale nada sem eu confirmar.
5. Depois que eu tiver PUBLIC_BASE_URL definida, ME LEMBRE explicitamente
   que preciso criar o OAuth Client no Google Cloud Console com o redirect
   URI = PUBLIC_BASE_URL + "/auth/callback" (passo a passo no README, seção
   "Criando o OAuth Client no Google") — essa parte não pode ser feita sem
   mim, porque exige login na minha conta Google.
6. Depois de tudo preenchido, rode `pytest -v` para confirmar que nada
   quebrou, e então rode scripts/start-gateway.ps1 (Windows) — ou
   `python -m src.gateway` diretamente — e verifique com curl que:
   - GET/POST em <PUBLIC_BASE_URL>/mcp devolve 401 (prova que o servidor
     subiu e a camada de auth está ativa — NÃO é erro)
   - GET em <PUBLIC_BASE_URL>/.well-known/oauth-authorization-server
     devolve 200 com um JSON contendo "registration_endpoint"
7. NÃO declare a configuração como "pronta" sem ter rodado os dois curls do
   passo 6 e me mostrado a saída literal. "Deveria funcionar" não é prova.
8. Ao final, me dê um resumo do que ficou configurado e um lembrete de que
   o e-mail cadastrado como usuário de teste no Google Cloud Console precisa
   bater exatamente com o que está em ALLOWED_EMAILS no .env — são duas
   barreiras independentes, e as duas precisam estar corretas.
```

---

## Por que o prompt é estruturado assim

Alguns pontos merecem explicação para quem for adaptar este prompt:

- **Pede para testar a ponte stdio isoladamente antes do OAuth.** Isso separa
  dois problemas que, misturados, são difíceis de depurar: "meu comando
  stdio está certo?" e "meu OAuth está certo?" são perguntas independentes,
  e a primeira é muito mais rápida de responder.
- **Proíbe expor a máquina publicamente sem confirmação explícita.** Ativar
  um túnel (Tailscale Funnel, Cloudflare Tunnel) é a única ação, em todo o
  processo de configuração, que torna a máquina alcançável pela internet
  pública. Não é uma ação para um assistente tomar sozinho.
- **Proíbe declarar sucesso sem evidência de comando rodado.** "Deveria
  funcionar" é uma armadilha comum em configuração assistida por IA — os
  dois `curl` do passo 6 são baratos e definitivos.
- **Separa o que a IA pode preencher sozinha do que exige você.** Credenciais
  do Google e a URL pública dependem de ações que só você pode fazer (login,
  criar recursos na sua conta). Um assistente que inventa esses valores ou
  os deixa vazios sem avisar te entrega uma configuração quebrada
  silenciosamente.
