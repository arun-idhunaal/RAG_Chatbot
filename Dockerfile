# syntax=docker/dockerfile:1
# Render Free (512 MB, no disk, spins down after idle).
# Do NOT install torch/Playwright — they OOM this instance.

FROM node:20-bookworm-slim AS web
WORKDIR /web
COPY web/package.json ./
RUN npm install
COPY web/ ./
RUN npm run build

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    CHROMA_PERSIST_DIR=/app/data/chroma \
    RAW_HTML_DIR=/app/data/raw \
    AUDIT_LOG_DIR=/app/data/audit \
    METRICS_LOG_DIR=/app/data/metrics \
    HOME=/app \
    PORT=8000 \
    EMBEDDING_BACKEND=huggingface \
    ALLOW_PLAYWRIGHT=false \
    AUTO_INGEST_ON_EMPTY=true \
    EMBEDDING_BATCH_SIZE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-render.txt pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY eval ./eval
COPY --from=web /web/dist ./web/dist

RUN pip install --upgrade pip \
    && pip install -r requirements-render.txt

EXPOSE 8000

COPY scripts/docker_entrypoint.sh /app/scripts/docker_entrypoint.sh
RUN chmod +x /app/scripts/docker_entrypoint.sh

ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]
