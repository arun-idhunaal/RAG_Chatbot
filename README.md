# INDmoney MF FAQ Chatbot (RAG)

Facts-only mutual fund FAQ chatbot scoped to ICICI Prudential (5 schemes).

**GitHub:** https://github.com/arun-idhunaal/RAG_Chatbot  
**Stack:** `bge-m3` · Chroma · Streamlit · hybrid classifier · extract→template comparisons

## Streamlit Community Cloud

1. Connect this repo at [share.streamlit.io](https://share.streamlit.io)
2. Branch `master`, main file `app/streamlit_app.py`
3. Secrets (App settings → Secrets):

```toml
GROQ_API_KEY = "gsk_..."
LLM_MODEL = "llama-3.3-70b-versatile"
USE_LLM_CLASSIFIER = "true"
ALLOW_PLAYWRIGHT = "false"
```

4. After deploy, if the knowledge base is empty, use sidebar **Build / refresh index** once.

Details: `DOCS/DEPLOY.md`

## Local setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
# Optional (local scrape fallback only):
# pip install -e ".[playwright]" && playwright install chromium
copy .env.example .env
# set GROQ_API_KEY in .env
```

## Phase map (all 6 complete)

| Phase | Location |
|---|---|
| 1 Corpus | `src/ingestion/`, `src/config/`, `scripts/ingest.py` |
| 2 Control plane | `src/pipeline/pii_guard.py`, `intent_classifier.py`, `scheme_resolver.py`, `src/retrieval/` |
| 3 Grounded answers | `src/pipeline/answer_generator.py`, `citation_validator.py` |
| 4 Comparisons & guardrails | `field_extractor.py`, `comparison_templater.py`, `refusal_templates.py`, `orchestrator.py` |
| 5 Streamlit UI | `app/streamlit_app.py` |
| 6 Eval / freshness / deploy | `eval/`, `scripts/run_eval.py`, `scripts/daily_refresh.py`, `.github/workflows/` |

## Common commands

```bash
python -m scripts.ingest
python -m scripts.daily_refresh
python -m scripts.health_check
python -m scripts.smoke_retrieval
python -m scripts.pipeline_route "What is an exit load?"
streamlit run app/streamlit_app.py
python -m scripts.run_eval
pytest tests/ -v   # needs: pip install -e ".[dev]"
```

## Data layout (generated, gitignored)

- `data/raw/` · `data/chroma/` · `data/audit/` · `data/metrics/` · `data/eval/`
