"""Perimetro de seguranca: decide quais identidades Google podem usar o gateway.

Modulo puro de proposito unico — sem rede, sem FastMCP, sem I/O alem da
leitura de uma variavel de ambiente — para que a regra que protege o backend
possa ser testada isoladamente.

A lista de e-mails permitidos vem de `ALLOWED_EMAILS` no ambiente (formato
CSV: "fulano@gmail.com,ciclano@gmail.com"), lida A CADA CHAMADA em vez de
uma vez na importacao do modulo. Duas razoes:
  1. testabilidade: cada teste pode setar o ambiente que precisa sem
     reimportar o modulo nem sujar o estado global entre testes;
  2. correcao em producao: ler uma vez na importacao criaria uma janela em
     que uma allowlist mal configurada (ausente, vazia, com erro de
     digitacao) so seria percebida depois que algum bug de import-order
     silencioso escondesse o problema. Ler sempre torna o comportamento
     obvio e imediato.

Sobre o formato dos claims: o GoogleProvider do FastMCP e um OAuthProxy, entao
o token que chega aqui pode ter os dados de identidade em dois lugares:
  - planos, em claims["email"]                       (verificacao direta do token Google)
  - aninhados, em claims["upstream_claims"]["email"] (token FastMCP com claims embutidos)
Alem disso, o endpoint `tokeninfo` do Google devolve `email_verified` como a
STRING "true", enquanto o endpoint `userinfo` v2 devolve booleano. Aceitamos os
dois, e somente os dois — qualquer outro valor e tratado como nao verificado.
"""

import os
from typing import Any


def get_allowed_emails() -> frozenset[str]:
    """Le ALLOWED_EMAILS do ambiente. CSV, espacos e caixa sao normalizados.

    Retorna frozenset vazio se a variavel estiver ausente ou vazia — e
    `is_allowed` trata isso como "negar tudo", nao como "permitir tudo".
    Uma allowlist vazia e quase sempre um erro de configuracao, e o erro
    seguro e fechar o acesso, nao abri-lo.
    """
    raw = os.environ.get("ALLOWED_EMAILS", "")
    return frozenset(e.strip().lower() for e in raw.split(",") if e.strip())


def extract_identity(claims: dict | None) -> tuple[str | None, bool]:
    """Extrai (email, verificado) de qualquer um dos formatos de claims.

    Retorna (None, False) para qualquer entrada que nao case — falha fechada.

    Publica (nao prefixada com "_") porque o log de auditoria do gateway
    tambem precisa saber QUEM foi negado, nao so que foi negado — reusa
    esta funcao em vez de duplicar a logica de extracao.
    """
    if not isinstance(claims, dict):
        return None, False

    source: dict[str, Any] = claims
    if "email" not in source:
        nested = claims.get("upstream_claims")
        if isinstance(nested, dict):
            source = nested

    email = source.get("email")
    if not isinstance(email, str):
        return None, False

    raw = source.get("email_verified")
    verified = raw is True or (isinstance(raw, str) and raw.strip().lower() == "true")
    return email, verified


def is_allowed(claims: dict | None) -> bool:
    """Retorna True somente para um e-mail da allowlist que o provedor confirmou
    como verificado. Qualquer duvida resulta em False (falha fechada).
    """
    email, verified = extract_identity(claims)
    if not verified or email is None:
        return False

    allowed = get_allowed_emails()
    if not allowed:
        return False  # allowlist ausente/vazia = negar tudo, nunca abrir

    return email.strip().lower() in allowed
