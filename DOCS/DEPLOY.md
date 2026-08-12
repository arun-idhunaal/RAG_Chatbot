# Deploy guide — Phase 6 (public shareable URL)

**Repo:** https://github.com/arun-idhunaal/RAG_Chatbot

## Option A — Streamlit Community Cloud (fastest shareable link)

1. Push this repo to `main` on GitHub (secrets stay in Streamlit, not the repo).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select `arun-idhunaal/RAG_Chatbot`, branch `main`, main file `app/streamlit_app.py`.
4. Under **Secrets**, add:

```toml
GROQ_API_KEY = "gsk_..."
LLM_MODEL = "llama-3.3-70b-versatile"
USE_LLM_CLASSIFIER = "true"
```

5. Deploy. First answers need a populated Chroma index:
   - Either run `python -m scripts.daily_refresh` locally and commit is **not** recommended for large chroma; prefer Option B, **or**
   - Use a one-time Cloud bootstrap: open the app after wiring a host that runs `scripts/docker_entrypoint.sh`.

Community Cloud disk is ephemeral — for daily 10:00 AM IST freshness, prefer Railway/Render with a volume, or keep the GitHub Action artifact + re-hydrate strategy.

## Option B — Railway / Render (Docker + volume) — recommended for freshness

1. Connect https://github.com/arun-idhunaal/RAG_Chatbot.git
2. Use the root `Dockerfile`.
3. Mount a persistent volume at `/app/data`.
4. Set env: `GROQ_API_KEY`, `PORT=8501`.
5. Entrypoint runs health check → ingest on cold start → Streamlit.
6. Schedule `python -m scripts.daily_refresh` via host cron **or** rely on `.github/workflows/daily_ingest.yml` plus volume sync.

Public URL will look like `https://<service>.up.railway.app` or Render’s HTTPS URL.

## Option C — Local + tunnel (dev only)

```bash
streamlit run app/streamlit_app.py
```

Not acceptable for PRD §7 shareable-link acceptance.

## Daily freshness (10:00 AM IST)

- Workflow: `.github/workflows/daily_ingest.yml` (`cron: 30 4 * * *` UTC = 10:00 IST)
- Local/cron: `python -m scripts.daily_refresh`
- Health: `python -m scripts.health_check`

## After deploy — acceptance

Walk `DOCS/ACCEPTANCE_CHECKLIST.md` on the live URL, including EC-X-01…03 spot checks.
