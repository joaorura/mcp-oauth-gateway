from src.gateway import build_gateway


def _base_env(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "http")
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:9/mcp")
    monkeypatch.delenv("BACKEND_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "fake.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("ALLOWED_EMAILS", "fulano@gmail.com")


def test_instructions_ausente_vira_none(monkeypatch, tmp_path):
    _base_env(monkeypatch)
    monkeypatch.delenv("GATEWAY_INSTRUCTIONS", raising=False)
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    mcp = build_gateway()

    assert mcp.instructions is None


def test_instructions_vazia_vira_none(monkeypatch, tmp_path):
    # Cadeia vazia e "nao configurado", nao "instrucao vazia intencional".
    _base_env(monkeypatch)
    monkeypatch.setenv("GATEWAY_INSTRUCTIONS", "")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    mcp = build_gateway()

    assert mcp.instructions is None


def test_instructions_preenchida_e_repassada(monkeypatch, tmp_path):
    _base_env(monkeypatch)
    monkeypatch.setenv("GATEWAY_INSTRUCTIONS", "Vault pessoal de Fulano, uso interno.")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    mcp = build_gateway()

    assert mcp.instructions == "Vault pessoal de Fulano, uso interno."
