"""Credencial que o gateway usa para falar com o MCP de tras.

Existe como modulo separado por causa de um detalhe que custa caro se voce
nao souber dele:

O FastMCP, ao proxiar, monta os headers do upstream assim
(fastmcp/client/transports/http.py):

    headers = get_http_headers(include={"authorization"}) | self.headers

`get_http_headers` devolve a chave em MINUSCULAS. Se `self.headers` usar
"Authorization" capitalizado, as duas chaves coexistem no dicionario — uniao
de dicts nao normaliza caixa — e o `Authorization` do CHAMADOR (o token que o
cliente MCP apresentou ao gateway) segue para o backend junto com o seu. O
backend honra o errado e responde 401, derrubando o handshake inteiro com um
erro que nao aponta para a causa real.

Usar a chave minuscula faz a uniao sobrescrever de verdade, e tem o efeito
colateral desejavel de NAO vazar a credencial do chamador para o servico de
tras.
"""


def upstream_auth_headers(token: str) -> dict[str, str]:
    """Header de autorizacao para o backend, com a chave em minusculas."""
    if not isinstance(token, str) or not token.strip():
        raise ValueError("token do upstream ausente ou vazio")
    return {"authorization": f"Bearer {token}"}
