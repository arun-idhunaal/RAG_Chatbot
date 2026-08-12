#!/usr/bin/env bash
# Container entry: health → ingest if empty → Streamlit (EC-X-04 fail-closed until ready).
set -euo pipefail
cd /app

mkdir -p "${CHROMA_PERSIST_DIR:-data/chroma}" \
         "${RAW_HTML_DIR:-data/raw}" \
         "${AUDIT_LOG_DIR:-data/audit}" \
         "${METRICS_LOG_DIR:-data/metrics}"

if ! python -m scripts.health_check; then
  echo "Index unhealthy or empty — running ingest (cold start)…"
  python -m scripts.daily_refresh || true
  python -m scripts.health_check
fi

exec streamlit run app/streamlit_app.py \
  --server.port="${PORT:-8501}" \
  --server.address=0.0.0.0 \
  --browser.gatherUsageStats=false
