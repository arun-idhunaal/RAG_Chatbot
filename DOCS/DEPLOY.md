# Deploy guide — Phase 6 (public shareable URL)

**Repo:** https://github.com/arun-idhunaal/RAG_Chatbot

## Option A — Streamlit Community Cloud (fastest shareable link)

**One-click deploy form (prefilled):**  
https://share.streamlit.io/deploy?repository=arun-idhunaal/RAG_Chatbot&branch=master&mainModule=app/streamlit_app.py

1. Open the link above (sign in with GitHub if prompted).
2. Confirm:
   - Repository: `arun-idhunaal/RAG_Chatbot`
   - Branch: `master`
   - Main file: `app/streamlit_app.py`
3. Open **Advanced settings → Secrets** and paste:

```toml
GROQ_API_KEY = "gsk_..."
LLM_MODEL = "llama-3.3-70b-versatile"
USE_LLM_CLASSIFIER = "true"
ALLOW_PLAYWRIGHT = "false"
```

4. Click **Deploy**.
5. After the app boots, if you see “knowledge base unavailable”, use the sidebar **Build / refresh index** button once (first scrape + `bge-m3` embed can take several minutes).

App URL shape: `https://<app-name>.streamlit.app`

> Note: Community Cloud disk is ephemeral. Reboot may wipe Chroma — re-run **Build / refresh index**. For durable daily 10:00 AM IST freshness, use Option B.

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
