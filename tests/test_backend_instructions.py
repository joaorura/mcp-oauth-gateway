import pytest
from fastmcp import FastMCP

from src.backend import combine_instructions, fetch_backend_instructions

# --- combine_instructions: funcao pura ---


def test_combine_nenhuma_definida_retorna_none():
    assert combine_instructions(None, None) is None


def test_combine_so_gateway():
    assert combine_instructions("do gateway", None) == "do gateway"


def test_combine_so_backend():
    assert combine_instructions(None, "do backend") == "do backend"


def test_combine_as_duas_gateway_primeiro():
    resultado = combine_instructions("do gateway", "do backend")
    assert resultado.startswith("do gateway")
    assert resultado.endswith("do backend")
    assert resultado.index("do gateway") < resultado.index("do backend")


def test_combine_trata_string_vazia_como_ausente():
    # "" e falsy — nao deveria virar uma secao vazia no meio do texto.
    assert combine_instructions("", "do backend") == "do backend"
    assert combine_instructions("do gateway", "") == "do gateway"


# --- fetch_backend_instructions: contra um backend real (in-memory) ---


@pytest.mark.asyncio
async def test_fetch_retorna_instructions_quando_backend_tem():
    backend = FastMCP(name="Backend", instructions="use a ferramenta X")

    @backend.tool
    def x() -> str:
        return "ok"

    resultado = await fetch_backend_instructions(backend)

    assert resultado == "use a ferramenta X"


@pytest.mark.asyncio
async def test_fetch_retorna_none_quando_backend_nao_tem():
    backend = FastMCP(name="Backend")

    @backend.tool
    def x() -> str:
        return "ok"

    resultado = await fetch_backend_instructions(backend)

    assert resultado is None


@pytest.mark.asyncio
async def test_fetch_retorna_none_em_vez_de_lancar_quando_inalcancavel():
    # Porta que quase certamente nao tem nada escutando.
    from fastmcp.client.transports import StreamableHttpTransport

    transporte = StreamableHttpTransport(url="http://127.0.0.1:1/mcp")

    resultado = await fetch_backend_instructions(transporte)

    assert resultado is None
