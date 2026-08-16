import itertools
import logging.handlers

from src.audit import build_audit_logger, log_access

# logging.getLogger() e um singleton por nome dentro do processo: se todos os
# testes usassem o nome padrao, o handler do primeiro teste sobreviveria e os
# demais escreveriam no diretorio temporario do primeiro em vez do proprio.
# Um contador garante um nome de logger unico por teste.
_contador = itertools.count()


def _nome_unico() -> str:
    return f"test.audit.{next(_contador)}"


def test_configura_rotating_file_handler_com_limites(tmp_path):
    logger = build_audit_logger(str(tmp_path), max_bytes=1234, backup_count=2, name=_nome_unico())
    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert handler.maxBytes == 1234
    assert handler.backupCount == 2


def test_idempotente_nao_duplica_handler(tmp_path):
    nome = _nome_unico()
    build_audit_logger(str(tmp_path), name=nome)
    logger = build_audit_logger(str(tmp_path), name=nome)
    assert len(logger.handlers) == 1


def test_cria_o_arquivo_access_log(tmp_path):
    build_audit_logger(str(tmp_path), name=_nome_unico())
    assert (tmp_path / "access.log").exists()


def test_log_access_registra_permitido_com_latencia(tmp_path):
    logger = build_audit_logger(str(tmp_path), name=_nome_unico())
    log_access(logger, method="tools/list", email="fulano@gmail.com", allowed=True, latency_s=0.42)
    for h in logger.handlers:
        h.flush()
    conteudo = (tmp_path / "access.log").read_text(encoding="utf-8")
    assert "method=tools/list" in conteudo
    assert "quem=fulano@gmail.com" in conteudo
    assert "permitido=True" in conteudo
    assert "latencia=0.42s" in conteudo


def test_log_access_registra_negado_como_warning(tmp_path):
    logger = build_audit_logger(str(tmp_path), name=_nome_unico())
    log_access(logger, method="initialize", email="estranho@gmail.com", allowed=False)
    for h in logger.handlers:
        h.flush()
    conteudo = (tmp_path / "access.log").read_text(encoding="utf-8")
    assert "WARNING" in conteudo
    assert "negado" in conteudo
    assert "quem=estranho@gmail.com" in conteudo


def test_log_access_usa_desconhecido_quando_email_e_none(tmp_path):
    logger = build_audit_logger(str(tmp_path), name=_nome_unico())
    log_access(logger, method="initialize", email=None, allowed=False)
    for h in logger.handlers:
        h.flush()
    conteudo = (tmp_path / "access.log").read_text(encoding="utf-8")
    assert "quem=desconhecido" in conteudo


def test_log_access_registra_erro(tmp_path):
    logger = build_audit_logger(str(tmp_path), name=_nome_unico())
    log_access(
        logger,
        method="tools/call",
        email="fulano@gmail.com",
        allowed=True,
        error="McpError: upstream indisponivel",
    )
    for h in logger.handlers:
        h.flush()
    conteudo = (tmp_path / "access.log").read_text(encoding="utf-8")
    assert "erro=McpError" in conteudo
