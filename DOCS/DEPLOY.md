# Deploy on Render — Free plan only

This project is configured for Render’s **Free web service** (Hobby workspace): **512 MB RAM, 0.1 CPU, no disk**. That is the largest no-cost web instance Render offers.

## What Free includes / does not

| Free includes | Free does not |
|---|---|
| HTTPS URL, Docker, `/health` | Persistent disk (filesystem is wiped on spin-down/redeploy) |
| 512 MB RAM / 0.1 CPU | Enough RAM to load local `bge-m3` + PyTorch |
| 750 instance hours / month | Always-on (sleeps after **15 minutes** idle; ~1 minute to wake) |
| Env vars + TLS | SSH, one-off jobs, extra instances |

Because of 512 MB, the image **does not** install torch, sentence-transformers, or Playwright. Embeddings still use **`BAAI/bge-m3`** via the **Hugging Face Inference API**. Scrape uses **httpx** (some JS-heavy pages may yield thinner chunks than local Playwright).

## Secrets (required)

Create a [Hugging Face token](https://huggingface.co/settings/tokens) with inference access.

| Key | Where |
|---|---|
| `GROQ_API_KEY` | Groq |
| `HF_TOKEN` | Hugging Face |
| `INGEST_TOKEN` | Any long random string (optional but recommended) |

## Deploy

1. Push this repo to GitHub.
2. Render → **New** → **Blueprint** (uses `render.yaml`), or **Web Service** → Docker → instance type **Free**.
3. Fill in `GROQ_API_KEY`, `HF_TOKEN`, `INGEST_TOKEN`.
4. Health check path: `/health`.
5. First boot: service becomes Live quickly; ingest runs **in the background**. The UI stays fail-closed until `/health` shows `"ok": true` (can take several minutes).
6. After idle, Render sleeps the service. The next visit waits ~1 minute, then ingest may run again (ephemeral disk).

Manual refresh (wakes the service too):

```bash
curl -X POST "https://YOUR-SERVICE.onrender.com/v1/admin/ingest" \
  -H "Authorization: Bearer $INGEST_TOKEN"
```

## GitHub daily job (10:00 AM IST)

Repo **Settings → Secrets**:

- `RENDER_INGEST_URL` = `https://YOUR-SERVICE.onrender.com/v1/admin/ingest`
- `INGEST_TOKEN` = same as Render

This pings the live app (and wakes it). It cannot store Chroma on GitHub for Render — Free has no disk to keep.

## Honest limits

- **Cold starts** are slow; first answers after sleep wait for wake + possible re-ingest.
- **Index quality** on Free is weaker than a local Playwright ingest if INDmoney/AMFI pages are JS-only.
- If the process is **killed for RAM**, check Render logs; keep `EMBEDDING_BACKEND=huggingface` and do not install torch on this service.
