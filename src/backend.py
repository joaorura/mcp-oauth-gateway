"""Constroi o transporte para o backend (o MCP que este gateway protege).

Este e o UNICO arquivo cujo comportamento muda dependendo de qual servidor
MCP voce esta protegendo -- e ele muda por CONFIGURACAO (variaveis de
ambiente), nao por edicao de codigo. Trocar de Obsidian para GitHub para
Slack para o seu proprio MCP interno e uma questao de mudar o `.env`.

Dois transportes suportados, escolhidos por `BACKEND_TRANSPORT`:

  http  -- o backend ja fala Streamable HTTP (a maioria dos MCPs remotos e
           dos servidores locais rodados com `serve-http`, `--transport http`
           etc.). `BACKEND_BEARER_TOKEN` e OPCIONAL: se vazio, nenhum header
           Authorization e enviado ao backend -- util para backends locais
           sem autenticacao propria, protegidos so pelo `127.0.0.1` e pelo
           OAuth deste gateway.

  stdio -- o backend so fala stdio (a maioria dos MCPs "de linha de comando",
           ex.: `npx -y algum-pacote-mcp`, `python -m algum_modulo`). O
           FastMCP spawna o processo e fala com ele por stdio, e o gateway
           expoe isso como HTTP+OAuth para o mundo de fora. Nao ha conceito
           de bearer aqui -- a "autenticacao" do processo filho, se houver,
           e resolvida por variaveis de ambiente especificas dele (fora do
           escopo deste gateway).
"""

import os
import shlex

from fastmcp import Client
from fastmcp.client.transports import ClientTransport, StdioTransport, StreamableHttpTransport

from src.upstream import upstream_auth_headers


def build_backend_transport() -> ClientTransport:
    """Le BACKEND_TRANSPORT do ambiente e constroi o transporte correspondente.

    Levanta ValueError com uma mensagem acionavel para qualquer configuracao
    incompleta ou desconhecida -- falhar cedo e alto, na inicializacao, e
    preferivel a um erro obscuro na primeira chamada MCP.
    """
    transport = os.environ.get("BACKEND_TRANSPORT", "").strip().lower()
    if transport == "http":
        return _build_http_backend()
    if transport == "stdio":
        return _build_stdio_backend()
    raise ValueError(
        f"BACKEND_TRANSPORT invalido ou ausente: {transport!r}. "
        "Defina 'http' ou 'stdio' no .env."
    )


def _build_http_backend() -> StreamableHttpTransport:
    url = os.environ.get("BACKEND_URL", "").strip()
    if not url:
        raise ValueError("BACKEND_URL e obrigatorio quando BACKEND_TRANSPORT=http")

    token = os.environ.get("BACKEND_BEARER_TOKEN", "").strip()
    headers = upstream_auth_headers(token) if token else {}
    return StreamableHttpTransport(url=url, headers=headers)


def _build_stdio_backend() -> StdioTransport:
    command = os.environ.get("BACKEND_COMMAND", "").strip()
    if not command:
        raise ValueError("BACKEND_COMMAND e obrigatorio quando BACKEND_TRANSPORT=stdio")

    # shlex.split entende aspas ('--vault "C:\caminho com espaco"'), ao
    # contrario de um .split(",") ingenuo -- importante porque caminhos de
    # arquivo com espaco sao o caso comum, nao a excecao.
    args_raw = os.environ.get("BACKEND_ARGS", "").strip()
    args = shlex.split(args_raw) if args_raw else []

    return StdioTransport(command=command, args=args)


async def fetch_backend_instructions(transport: ClientTransport) -> str | None:
    """Pergunta ao backend suas proprias `instructions` (campo nativo do MCP).

    `create_proxy` NAO propaga isso sozinho: se o gateway definir suas
    proprias `instructions`, elas SUBSTITUEM as do backend sem aviso; se o
    gateway nao definir nenhuma, o cliente final simplesmente nao ve as do
    backend. Esta funcao existe para o chamador poder CONCATENAR as duas em
    vez de perder uma delas silenciosamente -- ver `combine_instructions`.

    Retorna None em qualquer falha (backend fora do ar no boot, timeout,
    etc.) -- espiar as instructions do backend e um extra, nunca deve
    impedir o gateway de subir.
    """
    try:
        async with Client(transport) as c:
            return c.initialize_result.instructions
    except Exception:
        return None


def combine_instructions(gateway_text: str | None, backend_text: str | None) -> str | None:
    """Junta as instructions do gateway com as do backend, sem perder nenhuma.

    Ordem deliberada: as do gateway vem primeiro porque tipicamente tratam
    de QUEM pode usar o servidor (ex.: confirmar identidade), uma
    preocupacao anterior a COMO usar as ferramentas, que e do que as
    instructions do backend costumam tratar.
    """
    partes = [t for t in (gateway_text, backend_text) if t]
    if not partes:
        return None
    return "\n\n---\n\n".join(partes)
