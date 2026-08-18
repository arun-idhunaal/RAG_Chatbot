"""bge-m3 embeddings only (EC-ING-08).

Backends:
- local: sentence-transformers (needs RAM; use on your machine)
- huggingface: Hugging Face Inference API (fits Render Free 512 MB)
"""

from __future__ import annotations

from functools import lru_cache
from typing import Sequence

import httpx

from src.config.settings import Settings, get_settings

ALLOWED_EMBEDDING_MODEL = "BAAI/bge-m3"
_HF_URLS = (
    "https://router.huggingface.co/hf-inference/models/BAAI/bge-m3/pipeline/feature-extraction",
    "https://api-inference.huggingface.co/models/BAAI/bge-m3",
)


class EmbeddingError(RuntimeError):
    """Raised when embedding fails; callers must abort upsert (EC-ING-03)."""


@lru_cache
def _load_model(model_name: str):
    if model_name != ALLOWED_EMBEDDING_MODEL:
        raise EmbeddingError(
            f"Forbidden embedding model '{model_name}'. Only {ALLOWED_EMBEDDING_MODEL} is allowed (EC-ING-08)."
        )
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def get_embedder(settings: Settings | None = None):
    settings = settings or get_settings()
    return _load_model(settings.embedding_model)


def embed_texts(
    texts: Sequence[str],
    *,
    settings: Settings | None = None,
) -> list[list[float]]:
    """Embed texts with BAAI/bge-m3. Raises EmbeddingError on failure."""
    settings = settings or get_settings()
    if settings.embedding_model != ALLOWED_EMBEDDING_MODEL:
        raise EmbeddingError(
            f"Forbidden embedding model '{settings.embedding_model}' (EC-ING-08)."
        )
    if not texts:
        return []
    backend = (settings.embedding_backend or "local").strip().lower()
    try:
        if backend in {"huggingface", "hf", "remote"}:
            return _embed_huggingface(list(texts), settings)
        return _embed_local(list(texts), settings)
    except EmbeddingError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise EmbeddingError(f"Embedding failed: {exc}") from exc


def _embed_local(texts: list[str], settings: Settings) -> list[list[float]]:
    model = get_embedder(settings)
    vectors = model.encode(
        texts,
        batch_size=settings.embedding_batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def _embed_huggingface(texts: list[str], settings: Settings) -> list[list[float]]:
    token = (settings.hf_token or "").strip()
    if not token:
        raise EmbeddingError(
            "EMBEDDING_BACKEND=huggingface requires HF_TOKEN "
            "(Hugging Face access token with inference permission)."
        )
    batch = max(1, int(settings.embedding_batch_size or 1))
    out: list[list[float]] = []
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        raw = _hf_feature_extraction(chunk, token, settings)
        if len(chunk) == 1:
            out.append(_l2_normalize(_as_sentence_vector(raw)))
        else:
            if not isinstance(raw, list) or len(raw) != len(chunk):
                # Some endpoints embed one input only — fall back per-text.
                for t in chunk:
                    one = _hf_feature_extraction([t], token, settings)
                    out.append(_l2_normalize(_as_sentence_vector(one)))
            else:
                for item in raw:
                    out.append(_l2_normalize(_as_sentence_vector(item)))
    return out


def _hf_feature_extraction(
    texts: list[str],
    token: str,
    settings: Settings,
) -> object:
    payload_inputs: str | list[str] = texts[0] if len(texts) == 1 else texts
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "inputs": payload_inputs,
        "options": {"wait_for_model": True},
    }
    last_error = "huggingface_unreached"
    timeout = max(30.0, float(settings.http_timeout_seconds or 30.0))
    for url in _HF_URLS:
        try:
            resp = httpx.post(url, headers=headers, json=body, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            continue
        if resp.status_code == 503:
            last_error = "huggingface_model_loading"
            continue
        if not resp.is_success:
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            continue
        return resp.json()
    raise EmbeddingError(f"Hugging Face bge-m3 inference failed: {last_error}")


def _as_sentence_vector(raw: object) -> list[float]:
    if not isinstance(raw, list) or not raw:
        raise EmbeddingError("Unexpected Hugging Face embedding payload.")
    first = raw[0]
    if isinstance(first, (int, float)):
        return [float(x) for x in raw]
    if isinstance(first, list) and first and isinstance(first[0], (int, float)):
        return _mean_pool(raw)
    if isinstance(first, list) and first and isinstance(first[0], list):
        return _mean_pool(first)
    raise EmbeddingError("Unexpected Hugging Face embedding shape.")


def _mean_pool(token_vectors: list[list[float]]) -> list[float]:
    dim = len(token_vectors[0])
    acc = [0.0] * dim
    for tok in token_vectors:
        for i, v in enumerate(tok):
            acc[i] += float(v)
    n = float(len(token_vectors) or 1)
    return [x / n for x in acc]


def _l2_normalize(vec: list[float]) -> list[float]:
    n = sum(x * x for x in vec) ** 0.5
    if n <= 0:
        return vec
    return [x / n for x in vec]
