# INDmoney MF FAQ Chatbot (RAG)

Facts-only mutual fund FAQ chatbot scoped to ICICI Prudential (5 schemes).

**GitHub:** https://github.com/arun-idhunaal/RAG_Chatbot

## Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
playwright install chromium
copy .env.example .env
# set GROQ_API_KEY in .env
```

## Ingest & freshness

```bash
python -m scripts.ingest
python -m scripts.ingest --report-only
python -m scripts.daily_refresh    # scrape → upsert → health (10:00 AM IST job)
python -m scripts.health_check     # EC-X-04 cold-start gate
python -m scripts.smoke_retrieval
```

GitHub Action: `.github/workflows/daily_ingest.yml` runs at **10:00 AM IST** (`cron: 30 4 * * *` UTC).

## Chat UI

```bash
streamlit run app/streamlit_app.py
```

## Eval (Phase 6)

```bash
python -m scripts.run_eval
pytest tests/ -v
```

- EDGECASES.md §12 mapped report → `data/eval/latest_report.md`
- **S0** failure blocks release; **S1** failure blocks PRD acceptance
- Acceptance walkthrough: `DOCS/ACCEPTANCE_CHECKLIST.md`
- Deploy: `DOCS/DEPLOY.md`

## Data layout

- `data/raw/` — cached HTML (optional)
- `data/chroma/` — Chroma persistence
- `data/audit/` — scrape audit logs (no PII)
- `data/metrics/` — anonymized intent / scrape metrics (no PII)
- `data/eval/` — eval reports
