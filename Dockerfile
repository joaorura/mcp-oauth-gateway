# Imagem do gateway. Contem SOMENTE o Python e o codigo deste projeto.
#
# Nota sobre BACKEND_TRANSPORT=stdio em Docker: neste modo o gateway SPAWNA o
# processo do backend, entao o runtime dele (Node, Go, outro Python...) teria
# que existir DENTRO desta imagem. Isso incha a imagem e acopla ela ao backend
# especifico. Em Docker, prefira BACKEND_TRANSPORT=http com o backend em um
# servico separado do compose -- cada um com sua propria imagem enxuta, se
# falando pela rede interna. Ver docker-compose.yml.

FROM python:3.12-slim

# PYTHONUNBUFFERED: sem isso o stdout do Python fica em buffer e os logs so
# aparecem em blocos (ou se perdem se o container morrer), o que torna
# `docker compose logs` inutil justamente quando voce mais precisa dele.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copia so os metadados de dependencia primeiro: enquanto pyproject.toml nao
# mudar, o Docker reaproveita a camada de instalacao em cada rebuild, mesmo
# que o codigo tenha mudado.
COPY pyproject.toml ./
RUN pip install --no-cache-dir fastmcp>=3.4 python-dotenv>=1.0

COPY src/ ./src/

# Usuario nao-root: se alguem escapar do processo do gateway, cai num usuario
# sem privilegio em vez de root dentro do container.
RUN useradd --create-home --uid 10001 gateway \
    && mkdir -p /app/logs \
    && chown -R gateway:gateway /app
USER gateway

EXPOSE 8000

# GATEWAY_HOST precisa ser 0.0.0.0 DENTRO do container: 127.0.0.1 (o default
# do projeto, correto para rodar direto no host) so aceitaria conexoes de
# dentro do proprio container, e o mapeamento de porta do Docker nunca
# alcancaria o processo. O isolamento continua vindo do Docker -- a porta so
# fica publicada onde o compose mandar.
ENV GATEWAY_HOST=0.0.0.0 \
    GATEWAY_PORT=8000 \
    LOG_DIR=/app/logs

CMD ["python", "-m", "src.gateway"]
