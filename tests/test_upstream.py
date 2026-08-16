from src.upstream import upstream_auth_headers


def test_usa_chave_em_minusculas():
    """A chave PRECISA ser minuscula.

    O FastMCP monta os headers do upstream como
        get_http_headers(include={"authorization"}) | self.headers
    e `get_http_headers` devolve a chave em minusculas. Se a nossa vier
    capitalizada, as duas sobrevivem no dict (sao chaves distintas) e o
    Authorization do chamador vaza para o backend, que responde 401.
    """
    headers = upstream_auth_headers("tok123")
    assert list(headers.keys()) == ["authorization"]


def test_formata_como_bearer():
    assert upstream_auth_headers("tok123") == {"authorization": "Bearer tok123"}


def test_sobrescreve_o_header_de_entrada_em_vez_de_duplicar():
    # Reproduz a uniao que o FastMCP faz internamente.
    entrada = {"authorization": "Bearer TOKEN-DO-CHAMADOR"}
    resultado = entrada | upstream_auth_headers("TOKEN-INTERNO")
    assert resultado == {"authorization": "Bearer TOKEN-INTERNO"}
    assert len(resultado) == 1, "chave duplicada faria o token do chamador vazar"


def test_rejeita_token_vazio():
    for ruim in ("", "   ", None):
        try:
            upstream_auth_headers(ruim)  # type: ignore[arg-type]
        except ValueError:
            continue
        raise AssertionError(f"deveria recusar token {ruim!r}")
