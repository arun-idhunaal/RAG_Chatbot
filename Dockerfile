# syntax=docker/dockerfile:1
# Deploy target: Railway / Render / any Docker host with persistent volume for data/chroma.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CHROMA_PERSIST_DIR=/app/data/chroma \
    RAW_HTML_DIR=/app/data/raw \
    AUDIT_LOG_DIR=/app/data/audit \
    METRICS_LOG_DIR=/app/data/metrics \
    HOME=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY app ./app
COPY eval ./eval
COPY DOCS ./DOCS
COPY .streamlit ./.streamlit

RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install -e ".[playwright]" \
    && playwright install --with-deps chromium

# Persist Chroma + audit across restarts (mount a volume at /app/data).
VOLUME ["/app/data"]

EXPOSE 8501

COPY scripts/docker_entrypoint.sh /app/scripts/docker_entrypoint.sh
RUN chmod +x /app/scripts/docker_entrypoint.sh

ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]
