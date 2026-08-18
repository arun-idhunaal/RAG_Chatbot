# INDmoney MF FAQ Chatbot (RAG)

Facts-only mutual fund FAQ chatbot scoped to ICICI Prudential (5 schemes).

**GitHub:** https://github.com/arun-idhunaal/RAG_Chatbot  
**Stack:** `bge-m3` · Chroma · FastAPI · React + Vite · hybrid classifier · extract→template comparisons

## Local setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e ".[dev]"
# Optional (local scrape):
# pip install -e ".[playwright]" && playwright install chromium
copy .env.example .env
# set GROQ_API_KEY in .env
```

Ingest (if `data/chroma` is empty):

```bash
python -m scripts.ingest
```

API (http://127.0.0.1:8000):

```bash
python -m uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
```

UI (http://127.0.0.1:5173 — proxies `/v1` and `/health` to the API):

```bash
cd web
npm install
npm run dev
```

Production-style (API serves `web/dist`):

```bash
cd web && npm install && npm run build && cd ..
python -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

Docker:

```bash
docker compose up --build
# http://localhost:8000
```

## Deploy on Render (Free)

See **[DOCS/DEPLOY.md](DOCS/DEPLOY.md)**. Short version:

1. Blueprint or Docker web service, instance type **Free** (512 MB — the largest no-cost plan).
2. Set `GROQ_API_KEY`, `HF_TOKEN` (Hugging Face, for remote `bge-m3`), and `INGEST_TOKEN`.
3. No disk. The index is rebuilt after sleep/redeploy. First answers wait for background ingest.

## Phase map

| Phase | Location |
|---|---|
| 1 Corpus | `src/ingestion/`, `src/config/`, `scripts/ingest.py` |
| 2 Control plane | `src/pipeline/pii_guard.py`, `intent_classifier.py`, `scheme_resolver.py`, `src/retrieval/` |
| 3 Grounded answers | `src/pipeline/answer_generator.py`, `citation_validator.py` |
| 4 Comparisons & guardrails | `field_extractor.py`, `comparison_templater.py`, `refusal_templates.py`, `orchestrator.py` |
| 5 Streamlit UI (MVP, removed) | Replaced by Phase 7 |
| 6 Eval / freshness | `eval/`, `scripts/run_eval.py`, `scripts/daily_refresh.py`, `.github/workflows/` |
| 7 React + FastAPI | `web/`, `src/api/` |

## Common commands

```bash
python -m scripts.ingest
python -m scripts.daily_refresh
python -m scripts.health_check
python -m scripts.smoke_retrieval
python -m scripts.pipeline_route "What is an exit load?"
python -m uvicorn src.api.app:app --reload --port 8000
python -m scripts.run_eval
pytest tests/ -v
```

## Data layout (generated, gitignored)

- `data/raw/` · `data/chroma/` · `data/audit/` · `data/metrics/` · `data/eval/`
