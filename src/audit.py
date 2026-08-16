"""Log de auditoria do gateway: quem tentou o que, e se foi permitido.

Modulo separado (como allowlist.py e upstream.py) para que a configuracao de
rotacao seja testavel sem precisar subir o gateway inteiro.

O gateway e a UNICA camada que sabe qual identidade fez a chamada -- o
backend so enxerga um bearer token interno (ou nada, se BACKEND_BEARER_TOKEN
estiver vazio), sem ideia de quem esta por tras. Por isso este log nao pode
depender do log do backend.

Rotacao por TAMANHO, nao por tempo: um RotatingFileHandler com backupCount
fixo mantem o disco limitado independente de quanto trafego passar pelo
gateway, ao contrario de uma rotacao diaria que cresce sem teto se o
trafego aumentar.
"""

import logging
import logging.handlers
import os

MAX_BYTES = 5 * 1024 * 1024  # 5 MB por arquivo
BACKUP_COUNT = 3  # access.log + .1 + .2 + .3 -- teto de ~20 MB no total


def build_audit_logger(
    log_dir: str,
    *,
    max_bytes: int = MAX_BYTES,
    backup_count: int = BACKUP_COUNT,
    name: str = "mcp_oauth_gateway.audit",
) -> logging.Logger:
    """Cria (ou reaproveita) o logger de auditoria, com rotacao por tamanho.

    Idempotente por `name`: chamar duas vezes com o mesmo nome nao duplica
    handler nem duplica linhas de log — o gateway pode importar este modulo
    mais de uma vez sem que o access.log receba cada evento em dobro. O
    parametro `name` existe sobretudo para os testes: `logging.getLogger`
    e um singleton por nome dentro do processo, entao testes que usassem
    todos o nome padrao contaminariam uns aos outros com handlers de
    diretorios temporarios diferentes.
    """
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            os.path.join(log_dir, "access.log"),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)

    return logger


def log_access(
    logger: logging.Logger,
    *,
    method: str,
    email: str | None,
    allowed: bool,
    latency_s: float | None = None,
    error: str | None = None,
) -> None:
    """Registra uma tentativa de acesso ao gateway.

    `email` pode ser None quando a identidade nao pode ser extraida dos
    claims — nesse caso registramos "desconhecido" em vez de omitir o
    campo, para que uma negacao sem e-mail legivel nao passe despercebida
    numa varredura do log.
    """
    quem = email or "desconhecido"
    if error:
        logger.warning("method=%s quem=%s permitido=%s erro=%s", method, quem, allowed, error)
    elif not allowed:
        logger.warning("method=%s quem=%s permitido=%s negado", method, quem, allowed)
    else:
        sufixo = f" latencia={latency_s:.2f}s" if latency_s is not None else ""
        logger.info("method=%s quem=%s permitido=%s%s", method, quem, allowed, sufixo)
