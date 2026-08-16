"""Gateway OAuth (Google) generico na frente de qualquer servidor MCP.

Fluxo: cliente MCP (Claude, etc.) -> HTTPS publico -> este gateway (autentica
via Google, filtra por allowlist, audita) -> backend (src/backend.py:
http ou stdio, com ou sem bearer).

Este arquivo NAO sabe nada sobre qual MCP especifico esta atras dele -- essa
informacao inteira vem de variaveis de ambiente (ver .env.example). Adaptar
este gateway para proteger um MCP diferente e uma questao de trocar o `.env`,
nao de editar este arquivo. Veja o README para o passo a passo completo, e
LLM_PROMPT.md se quiser que uma IA faca a adaptacao para voce.
"""

import asyncio
import os
import time

from dotenv import load_dotenv
from fastmcp.server import create_proxy
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token
from fastmcp.server.middleware import Middleware, MiddlewareContext

from src.allowlist import extract_identity, is_allowed
from src.audit import build_audit_logger, log_access
from src.backend import build_backend_transport, combine_instructions, fetch_backend_instructions

load_dotenv()


class AllowlistMiddleware(Middleware):
    """Barra qualquer identidade fora da allowlist.

    O GoogleProvider autentica QUALQUER conta Google que complete o fluxo de
    consentimento; sozinho ele nao restringe nada. Esta classe e a barreira
    real. Ver src/allowlist.py para a logica de decisao.
    """

    def __init__(self, audit_logger) -> None:
        self._audit = audit_logger

    async def on_request(self, context: MiddlewareContext, call_next):
        method = getattr(context, "method", "?")
        token = get_access_token()
        claims = getattr(token, "claims", None) if token else None
        email, _verified = extract_identity(claims)
        allowed = is_allowed(claims)

        if not allowed:
            log_access(self._audit, method=method, email=email, allowed=False)
            raise PermissionError("Identidade nao autorizada para este gateway")

        inicio = time.monotonic()
        try:
            resultado = await call_next(context)
        except Exception as e:
            log_access(
                self._audit,
                method=method,
                email=email,
                allowed=True,
                error=f"{type(e).__name__}: {e}",
            )
            raise
        log_access(
            self._audit,
            method=method,
            email=email,
            allowed=True,
            latency_s=time.monotonic() - inicio,
        )
        return resultado


def build_gateway():
    """Monta o servidor: auth Google + middleware de allowlist + proxy pro backend."""
    log_dir = os.environ.get("LOG_DIR", "./logs")
    audit_logger = build_audit_logger(log_dir)

    auth = GoogleProvider(
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        base_url=os.environ["PUBLIC_BASE_URL"],
        required_scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
    )

    backend = build_backend_transport()

    # `instructions` e campo nativo do protocolo MCP: texto livre que o
    # servidor entrega no `initialize`, antes de qualquer ferramenta ser
    # chamada. `create_proxy` NAO herda as instructions do backend
    # automaticamente -- se passarmos as nossas, elas SUBSTITUEM (nunca
    # concatenam) as que o backend eventualmente tenha. Buscamos as do
    # backend explicitamente para juntar as duas em vez de perder uma.
    #
    # So para BACKEND_TRANSPORT=http: para stdio, isso exigiria spawnar um
    # processo extra so para espiar as instructions antes do processo "de
    # verdade" que o create_proxy vai spawnar em seguida -- desperdicio, e
    # com risco de efeito colateral se o processo do backend nao for
    # idempotente ao iniciar.
    backend_instructions = None
    if os.environ.get("BACKEND_TRANSPORT", "").strip().lower() == "http":
        backend_instructions = asyncio.run(fetch_backend_instructions(backend))

    instructions = combine_instructions(
        os.environ.get("GATEWAY_INSTRUCTIONS") or None,
        backend_instructions,
    )

    mcp = create_proxy(
        backend,
        name=os.environ.get("GATEWAY_NAME", "MCP OAuth Gateway"),
        instructions=instructions,
        auth=auth,
        middleware=[AllowlistMiddleware(audit_logger)],
    )
    return mcp


if __name__ == "__main__":
    gateway = build_gateway()
    host = os.environ.get("GATEWAY_HOST", "127.0.0.1")
    port = int(os.environ.get("GATEWAY_PORT", "8000"))
    # stateless_http=True: sem negociacao de `Mcp-Session-Id`. Em modo
    # stateful, alguns clientes disputam a sessao com o gateway (padrao
    # 400 -> 200 repetido sem completar o handshake) -- ver README,
    # secao "Troubleshooting", para o caso real que motivou isso.
    gateway.run(transport="http", host=host, port=port, stateless_http=True)
