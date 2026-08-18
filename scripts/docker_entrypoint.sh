#!/usr/bin/env bash
# Render / Docker entry: create data dirs, start API immediately.
# Do not block on ingest — Render health checks /health while this process boots.
# Empty-index ingest is AUTO_INGEST_ON_EMPTY (in-process) or POST /v1/admin/ingest.
set -euo pipefail
cd /app

export PYTHONPATH="${PYTHONPATH:-/app}"
export PORT="${PORT:-8000}"

mkdir -p "${CHROMA_PERSIST_DIR:-/app/data/chroma}" \
         "${RAW_HTML_DIR:-/app/data/raw}" \
         "${AUDIT_LOG_DIR:-/app/data/audit}" \
         "${METRICS_LOG_DIR:-/app/data/metrics}"

exec python -m uvicorn src.api.app:app --host 0.0.0.0 --port "${PORT}"
