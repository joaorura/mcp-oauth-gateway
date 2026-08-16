from src.allowlist import extract_identity, get_allowed_emails, is_allowed

# --- get_allowed_emails: leitura do ambiente ---


def test_le_lista_csv_normalizando_espaco_e_caixa(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", " Fulano@Gmail.com , ciclano@gmail.com ")
    assert get_allowed_emails() == frozenset({"fulano@gmail.com", "ciclano@gmail.com"})


def test_retorna_vazio_quando_variavel_ausente(monkeypatch):
    monkeypatch.delenv("ALLOWED_EMAILS", raising=False)
    assert get_allowed_emails() == frozenset()


def test_ignora_entradas_vazias_no_csv(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com,,  ,ciclano@gmail.com")
    assert get_allowed_emails() == frozenset({"fulano@gmail.com", "ciclano@gmail.com"})


# --- is_allowed: os casos de seguranca ---


def test_permite_email_da_allowlist_verificado(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "fulano@gmail.com", "email_verified": True}
    assert is_allowed(claims) is True


def test_nega_email_fora_da_allowlist(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "estranho@gmail.com", "email_verified": True}
    assert is_allowed(claims) is False


def test_nega_quando_allowlist_esta_vazia(monkeypatch):
    # Allowlist vazia = negar tudo. NUNCA "permitir tudo por falta de regra".
    monkeypatch.delenv("ALLOWED_EMAILS", raising=False)
    claims = {"email": "fulano@gmail.com", "email_verified": True}
    assert is_allowed(claims) is False


def test_nega_email_nao_verificado(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "fulano@gmail.com", "email_verified": False}
    assert is_allowed(claims) is False


def test_nega_quando_falta_o_claim_email_verified(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "fulano@gmail.com"}
    assert is_allowed(claims) is False


def test_nega_quando_falta_o_claim_email(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email_verified": True}
    assert is_allowed(claims) is False


def test_nega_claims_vazio_ou_nulo(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    assert is_allowed({}) is False
    assert is_allowed(None) is False


def test_nega_claims_do_tipo_errado_sem_lancar_excecao(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    for ruim in ("string qualquer", [], 42, object()):
        assert is_allowed(ruim) is False  # type: ignore[arg-type]


def test_nega_email_verified_como_string_truthy(monkeypatch):
    # "false" e uma string nao vazia, logo truthy: comparar por identidade com True
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "fulano@gmail.com", "email_verified": "false"}
    assert is_allowed(claims) is False


def test_permite_email_verified_como_string_true_do_tokeninfo(monkeypatch):
    # O endpoint `tokeninfo` do Google devolve a STRING "true", nao booleano.
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "fulano@gmail.com", "email_verified": "true"}
    assert is_allowed(claims) is True


def test_aceita_string_true_com_espacos_e_maiusculas(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    for valor in ("True", " TRUE ", "true"):
        claims = {"email": "fulano@gmail.com", "email_verified": valor}
        assert is_allowed(claims) is True, f"deveria permitir email_verified={valor!r}"


def test_normaliza_caixa_e_espacos(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "  Fulano@Gmail.com  ", "email_verified": True}
    assert is_allowed(claims) is True


def test_nega_email_que_apenas_contem_o_endereco_permitido(monkeypatch):
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {"email": "fulano@gmail.com.attacker.tld", "email_verified": True}
    assert is_allowed(claims) is False


def test_permite_claims_aninhados_em_upstream_claims(monkeypatch):
    # O OAuthProxy do FastMCP pode embutir os claims do provedor sob "upstream_claims".
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {
        "sub": "123",
        "upstream_claims": {"email": "fulano@gmail.com", "email_verified": True},
    }
    assert is_allowed(claims) is True


def test_upstream_claims_ignorado_quando_email_esta_no_nivel_de_cima(monkeypatch):
    # Se o nivel de cima ja tem email, ele manda — nao da para escalar
    # privilegio injetando um upstream_claims falso.
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")
    claims = {
        "email": "estranho@gmail.com",
        "email_verified": True,
        "upstream_claims": {"email": "fulano@gmail.com", "email_verified": True},
    }
    assert is_allowed(claims) is False


# --- extract_identity: contrato publico usado pelo audit ---


def test_extract_identity_retorna_email_e_verificado():
    claims = {"email": "fulano@gmail.com", "email_verified": True}
    assert extract_identity(claims) == ("fulano@gmail.com", True)


def test_extract_identity_retorna_none_false_para_claims_invalido():
    assert extract_identity(None) == (None, False)
    assert extract_identity("string") == (None, False)  # type: ignore[arg-type]
