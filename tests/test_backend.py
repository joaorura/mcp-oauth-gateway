import pytest
from fastmcp.client.transports import StdioTransport, StreamableHttpTransport

from src.backend import build_backend_transport


def test_http_sem_bearer_nao_envia_header_authorization(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "http")
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:3000/mcp")
    monkeypatch.delenv("BACKEND_BEARER_TOKEN", raising=False)

    transport = build_backend_transport()

    assert isinstance(transport, StreamableHttpTransport)
    assert "authorization" not in {k.lower() for k in transport.headers}


def test_http_com_bearer_envia_header_em_minusculas(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "http")
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:3000/mcp")
    monkeypatch.setenv("BACKEND_BEARER_TOKEN", "meu-token-secreto")

    transport = build_backend_transport()

    assert isinstance(transport, StreamableHttpTransport)
    assert transport.headers == {"authorization": "Bearer meu-token-secreto"}


def test_http_sem_url_levanta_erro_acionavel(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "http")
    monkeypatch.delenv("BACKEND_URL", raising=False)

    with pytest.raises(ValueError, match="BACKEND_URL"):
        build_backend_transport()


def test_stdio_constroi_comando_e_args(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "stdio")
    monkeypatch.setenv("BACKEND_COMMAND", "npx")
    monkeypatch.setenv("BACKEND_ARGS", "-y algum-pacote-mcp serve --vault /caminho")

    transport = build_backend_transport()

    assert isinstance(transport, StdioTransport)
    assert transport.command == "npx"
    assert transport.args == ["-y", "algum-pacote-mcp", "serve", "--vault", "/caminho"]


def test_stdio_entende_aspas_para_caminhos_com_espaco(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "stdio")
    monkeypatch.setenv("BACKEND_COMMAND", "npx")
    monkeypatch.setenv("BACKEND_ARGS", '-y algum-pacote-mcp --vault "C:\\caminho com espaco"')

    transport = build_backend_transport()

    assert transport.args[-1] == "C:\\caminho com espaco"


def test_stdio_sem_args_funciona(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "stdio")
    monkeypatch.setenv("BACKEND_COMMAND", "meu-mcp-server")
    monkeypatch.delenv("BACKEND_ARGS", raising=False)

    transport = build_backend_transport()

    assert transport.command == "meu-mcp-server"
    assert transport.args == []


def test_stdio_sem_command_levanta_erro_acionavel(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "stdio")
    monkeypatch.delenv("BACKEND_COMMAND", raising=False)

    with pytest.raises(ValueError, match="BACKEND_COMMAND"):
        build_backend_transport()


def test_transport_invalido_levanta_erro_acionavel(monkeypatch):
    monkeypatch.setenv("BACKEND_TRANSPORT", "websocket-magico")

    with pytest.raises(ValueError, match="websocket-magico"):
        build_backend_transport()


def test_transport_ausente_levanta_erro_acionavel(monkeypatch):
    monkeypatch.delenv("BACKEND_TRANSPORT", raising=False)

    with pytest.raises(ValueError, match="BACKEND_TRANSPORT"):
        build_backend_transport()
